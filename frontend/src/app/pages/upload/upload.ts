import { Component, OnInit, OnDestroy, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
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
}

let _seq = 0;
function nextId(): string { return `f${Date.now()}-${_seq++}`; }

@Component({
  selector: 'app-upload',
  imports: [CommonModule],
  templateUrl: './upload.html',
  styleUrl: './upload.scss',
})
export class UploadPage implements OnInit, OnDestroy {
  dragOver      = signal(false);
  uploadQueue   = signal<FileUploadState[]>([]);
  documents     = signal<Document[]>([]);
  loadingDocs   = signal(false);
  viewerUrl     = signal<SafeResourceUrl | null>(null);
  viewerName    = signal('');
  pendingDelete = signal<Document | null>(null);

  hasQueue = computed(() => this.uploadQueue().length > 0);
  allDone  = computed(() =>
    this.hasQueue() &&
    this.uploadQueue().every(f => f.phase === 'done' || f.phase === 'error')
  );

  private ingestTimers = new Map<string, ReturnType<typeof setInterval>>();

  constructor(
    private uploadService: UploadService,
    private sanitizer: DomSanitizer,
  ) {}

  ngOnInit(): void { this.loadDocuments(); }

  ngOnDestroy(): void {
    this.ingestTimers.forEach(id => clearInterval(id));
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
      id: nextId(),
      name: f.name,
      size: f.size,
      uploadProgress: 0,
      ingestProgress: 0,
      phase: 'pending',
    }));

    // Append to existing queue (don't replace)
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
            this.stopIngestTimer(item.id);
            this.patch(item.id, { ingestProgress: 100, phase: 'done' });
            this.loadDocuments();
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

  dismissItem(id: string): void {
    this.stopIngestTimer(id);
    this.uploadQueue.update(q => q.filter(f => f.id !== id));
  }

  clearDone(): void {
    this.uploadQueue().filter(f => f.phase === 'done' || f.phase === 'error')
      .forEach(f => this.stopIngestTimer(f.id));
    this.uploadQueue.update(q => q.filter(f => f.phase !== 'done' && f.phase !== 'error'));
  }

  private startIngestTimer(id: string, name: string, size: number): void {
    this.patch(id, { phase: 'ingesting', ingestProgress: 0 });
    const totalMs = this.estimateIngestionMs(name, size);
    const tickMs  = 120;
    const step    = (tickMs / totalMs) * 95;

    const timer = setInterval(() => {
      const item = this.uploadQueue().find(f => f.id === id);
      if (!item || item.ingestProgress >= 95) { clearInterval(timer); return; }
      this.patch(id, { ingestProgress: Math.min(95, item.ingestProgress + step) });
    }, tickMs);

    this.ingestTimers.set(id, timer);
  }

  private stopIngestTimer(id: string): void {
    const timer = this.ingestTimers.get(id);
    if (timer !== undefined) { clearInterval(timer); this.ingestTimers.delete(id); }
  }

  private patch(id: string, patch: Partial<FileUploadState>): void {
    this.uploadQueue.update(q =>
      q.map(f => f.id === id ? { ...f, ...patch } : f)
    );
  }

  loadDocuments(): void {
    this.loadingDocs.set(true);
    this.uploadService.getDocuments().subscribe({
      next: (docs) => { this.documents.set(docs); this.loadingDocs.set(false); },
      error: ()     => this.loadingDocs.set(false),
    });
  }

  viewDocument(doc: Document): void {
    const url = `http://localhost:8000/documents/${doc.id}/view`;
    this.viewerUrl.set(this.sanitizer.bypassSecurityTrustResourceUrl(url));
    this.viewerName.set(doc.original_name);
  }

  closeViewer(): void { this.viewerUrl.set(null); this.viewerName.set(''); }

  confirmDelete(doc: Document): void { this.pendingDelete.set(doc); }
  cancelDelete(): void               { this.pendingDelete.set(null); }

  deleteDocument(): void {
    const doc = this.pendingDelete();
    if (!doc) return;
    this.pendingDelete.set(null);
    this.uploadService.deleteDocument(doc.id).subscribe({
      next: () => {
        this.documents.update(docs => docs.filter(d => d.id !== doc.id));
        if (this.viewerName() === doc.original_name) this.closeViewer();
      },
    });
  }

  formatSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  private estimateIngestionMs(name: string, size: number): number {
    const isPdf       = name.toLowerCase().endsWith('.pdf');
    const charsPerByte = isPdf ? 0.4 : 0.9;
    const numChunks    = Math.ceil((size * charsPerByte) / 450);
    const extractionMs = isPdf ? size / 800 : size / 8000;
    return Math.max(1000, extractionMs + numChunks * 85);
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
