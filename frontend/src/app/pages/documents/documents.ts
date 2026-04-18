import { Component, OnInit, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { DomSanitizer, SafeResourceUrl } from '@angular/platform-browser';
import { UploadService, Document } from '../../services/upload';

@Component({
  selector: 'app-documents',
  imports: [CommonModule, RouterLink],
  templateUrl: './documents.html',
  styleUrl: './documents.scss',
})
export class DocumentsPage implements OnInit {
  documents    = signal<Document[]>([]);
  loadingDocs  = signal(false);
  viewerUrl    = signal<SafeResourceUrl | null>(null);
  viewerName   = signal('');
  pendingDelete = signal<Document | null>(null);

  done = computed(() => this.documents().filter(d => d.status === 'done'));

  constructor(
    private uploadService: UploadService,
    private sanitizer: DomSanitizer,
  ) {}

  ngOnInit(): void { this.loadDocuments(); }

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

  getFileIcon(name: string): string {
    return name.toLowerCase().endsWith('.pdf') ? '📄' : '📝';
  }

  isPdf(name: string): boolean {
    return name.toLowerCase().endsWith('.pdf');
  }
}
