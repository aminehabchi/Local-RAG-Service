import { Component, OnInit, OnDestroy, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { HttpEventType, HttpResponse } from '@angular/common/http';
import { DomSanitizer, SafeResourceUrl } from '@angular/platform-browser';
import { UploadService, Document } from '../../services/upload';

type FilePhase = 'pending' | 'uploading' | 'ingesting' | 'done' | 'error';

interface FileUploadState {
  id: string;
  name: string;
  size: number;
  uploadProgress: number;
  ingestProgress: number;
  phase: FilePhase;
  error?: string;
  chunkCount?: number;  // real count once known
  createdAt?: string;   // set for injected (previous-session) items
}

let _seq = 0;
function nextId(): string { return `f${Date.now()}-${_seq++}`; }

@Component({
  selector: 'app-upload',
  imports: [CommonModule, RouterLink],
  templateUrl: './upload.html',
  styleUrl: './upload.scss',
})
export class UploadPage implements OnInit, OnDestroy {
  dragOver     = signal(false);
  uploadQueue  = signal<FileUploadState[]>([]);
  loadingDocs  = signal(false);
  viewerUrl    = signal<SafeResourceUrl | null>(null);
  viewerName   = signal('');
  now          = signal(Date.now());

  hasQueue = computed(() => this.uploadQueue().length > 0);
  allDone  = computed(() =>
    this.hasQueue() &&
    this.uploadQueue().every(f => f.phase === 'done' || f.phase === 'error')
  );

  private ingestTimers  = new Map<string, ReturnType<typeof setInterval>>();
  private ingestTotalMs = new Map<string, number>();
  private fileIdMap     = new Map<string, number>();  // itemId -> backend file_id
  private pollTimer:  ReturnType<typeof setInterval> | null = null;
  private clockTimer: ReturnType<typeof setInterval> | null = null;

  constructor(
    private uploadService: UploadService,
    private sanitizer: DomSanitizer,
  ) {}

  ngOnInit(): void {
    this.clockTimer = setInterval(() => this.now.set(Date.now()), 1000);
    this.loadDocuments();
  }

  ngOnDestroy(): void {
    this.ingestTimers.forEach(t => clearInterval(t));
    if (this.pollTimer)  clearInterval(this.pollTimer);
    if (this.clockTimer) clearInterval(this.clockTimer);
  }

  onDragOver(event: DragEvent): void { event.preventDefault(); this.dragOver.set(true); }
  onDragLeave(): void { this.dragOver.set(false); }

  onDrop(event: DragEvent): void {
    event.preventDefault();
    this.dragOver.set(false);
    const files = Array.from(event.dataTransfer?.files ?? []);
    if (files.length) this.enqueueFiles(files);
  }

  onFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    const files = Array.from(input.files ?? []);
    if (files.length) this.enqueueFiles(files);
    input.value = '';
  }

  enqueueFiles(files: File[]): void {
    const newItems: FileUploadState[] = files.map(f => ({
      id: nextId(), name: f.name, size: f.size,
      uploadProgress: 0, ingestProgress: 0, phase: 'pending',
    }));

    this.uploadQueue.update(q => [...q, ...newItems]);

    newItems.forEach((item, i) => {
      const file = files[i];
      this.uploadService.uploadFile(file).subscribe({
        next: (event) => {
          if (event.type === HttpEventType.UploadProgress && event.total) {
            const p = Math.round(100 * event.loaded / event.total);
            this.patch(item.id, { uploadProgress: p, phase: 'uploading' });
            if (p === 100) this.startIngestTimer(item.id, file.name, file.size);
          } else if (event instanceof HttpResponse) {
            const body = event.body as { file_id: number };
            this.fileIdMap.set(item.id, body.file_id);
            this.startStatusPolling();
          }
        },
        error: (err) => {
          this.stopIngestTimer(item.id);
          this.patch(item.id, {
            phase: 'error',
            error: err.error?.detail ?? 'Upload failed. Please try again.',
          });
        },
      });
    });
  }

  private loadDocuments(): void {
    this.loadingDocs.set(true);
    this.uploadService.getDocuments().subscribe({
      next: (docs) => {
        this.loadingDocs.set(false);
        this.injectProcessingDocs(docs);
        if (docs.some(d => d.status === 'processing')) this.startStatusPolling();
      },
      error: () => this.loadingDocs.set(false),
    });
  }

  private injectProcessingDocs(docs: Document[]): void {
    const trackedDocIds = new Set(this.fileIdMap.values());
    for (const doc of docs) {
      if (doc.status !== 'processing' && doc.status !== 'failed') continue;
      if (trackedDocIds.has(doc.id)) continue;

      const id = nextId();
      const chunks = doc.chunk_count || this.estimateChunks(doc.original_name, doc.size);
      const progress = doc.status === 'processing'
        ? this.computeTimeProgress(doc.chunk_count, doc.created_at)
        : 0;

      this.uploadQueue.update(q => [...q, {
        id,
        name: doc.original_name,
        size: doc.size,
        uploadProgress: 100,
        ingestProgress: progress,
        phase: doc.status === 'failed' ? 'error' : 'ingesting',
        error: doc.status === 'failed' ? 'Ingestion failed.' : undefined,
        chunkCount: doc.chunk_count,
        createdAt: doc.created_at,
      }]);

      this.fileIdMap.set(id, doc.id);
      if (doc.status === 'processing') {
        this.ingestTotalMs.set(id, Math.max(1000, chunks * 1000));
      }
    }
  }

  dismissItem(id: string): void {
    this.stopIngestTimer(id);
    this.fileIdMap.delete(id);
    this.uploadQueue.update(q => q.filter(f => f.id !== id));
  }

  private startStatusPolling(): void {
    if (this.pollTimer) return;
    this.pollTimer = setInterval(() => {
      this.uploadService.getDocuments().subscribe({
        next: (docs) => {
          let anyPending = false;
          this.fileIdMap.forEach((fileId, itemId) => {
            const doc = docs.find(d => d.id === fileId);
            if (doc?.status === 'done') {
              this.stopIngestTimer(itemId);
              this.patch(itemId, { ingestProgress: 100, phase: 'done', chunkCount: doc.chunk_count });
              this.fileIdMap.delete(itemId);
            } else if (doc?.status === 'failed') {
              this.stopIngestTimer(itemId);
              this.patch(itemId, { phase: 'error', error: 'Ingestion failed.' });
              this.fileIdMap.delete(itemId);
            } else {
              anyPending = true;
              if (doc && doc.chunk_count > 0) {
                const realMs = Math.max(1000, doc.chunk_count * 1000);
                if (this.ingestTotalMs.get(itemId) !== realMs) {
                  this.ingestTotalMs.set(itemId, realMs);
                  this.patch(itemId, { chunkCount: doc.chunk_count, createdAt: doc.created_at });
                  this._runIngestTimer(itemId, realMs);
                }
              }
            }
          });
          if (!anyPending) { clearInterval(this.pollTimer!); this.pollTimer = null; }
        },
      });
    }, 2000);
  }

  clearDone(): void {
    this.uploadQueue().filter(f => f.phase === 'done' || f.phase === 'error')
      .forEach(f => { this.stopIngestTimer(f.id); this.fileIdMap.delete(f.id); });
    this.uploadQueue.update(q => q.filter(f => f.phase !== 'done' && f.phase !== 'error'));
  }

  private startIngestTimer(id: string, name: string, size: number): void {
    this.patch(id, { phase: 'ingesting', ingestProgress: 0 });
    const totalMs = this.estimateIngestionMs(name, size);
    this.ingestTotalMs.set(id, totalMs);
    this._runIngestTimer(id, totalMs);
  }

  private _runIngestTimer(id: string, totalMs: number): void {
    const existing = this.ingestTimers.get(id);
    if (existing) clearInterval(existing);

    const tickMs = 120;
    const timer = setInterval(() => {
      const item = this.uploadQueue().find(f => f.id === id);
      if (!item || item.ingestProgress >= 95) { clearInterval(timer); return; }
      const step = (tickMs / this.ingestTotalMs.get(id)!) * 95;
      this.patch(id, { ingestProgress: Math.min(95, item.ingestProgress + step) });
    }, tickMs);

    this.ingestTimers.set(id, timer);
  }

  private stopIngestTimer(id: string): void {
    const t = this.ingestTimers.get(id);
    if (t !== undefined) { clearInterval(t); this.ingestTimers.delete(id); }
    this.ingestTotalMs.delete(id);
  }

  private patch(id: string, p: Partial<FileUploadState>): void {
    this.uploadQueue.update(q => q.map(f => f.id === id ? { ...f, ...p } : f));
  }

  getItemIngestProgress(item: FileUploadState): number {
    if (item.createdAt && item.chunkCount) {
      return this.computeTimeProgress(item.chunkCount, item.createdAt);
    }
    return Math.round(item.ingestProgress);
  }

  private computeTimeProgress(chunkCount: number, createdAt: string): number {
    if (!chunkCount) return 0;
    const totalMs = chunkCount * 1000;
    const elapsed = this.now() - new Date(createdAt + 'Z').getTime();
    return Math.min(95, Math.round((elapsed / totalMs) * 100));
  }

  viewDocument(name: string, id: number): void {
    const url = `http://localhost:8000/documents/${id}/view`;
    this.viewerUrl.set(this.sanitizer.bypassSecurityTrustResourceUrl(url));
    this.viewerName.set(name);
  }

  closeViewer(): void { this.viewerUrl.set(null); this.viewerName.set(''); }

  formatSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  estimateChunks(name: string, size: number): number {
    const charsPerByte = name.toLowerCase().endsWith('.pdf') ? 0.4 : 0.9;
    return Math.max(1, Math.ceil((size * charsPerByte) / 450));
  }

  private estimateIngestionMs(name: string, size: number): number {
    return Math.max(1000, this.estimateChunks(name, size) * 1000);
  }

  estimateIngestionTime(name: string, size: number): string {
    const s = Math.round(this.estimateIngestionMs(name, size) / 1000);
    return s < 60 ? `~${s}s` : `~${Math.round(s / 60)}m`;
  }

  getFileIcon(name: string): string {
    return name.toLowerCase().endsWith('.pdf') ? '📄' : '📝';
  }

  isPdf(name: string): boolean {
    return name.toLowerCase().endsWith('.pdf');
  }
}
