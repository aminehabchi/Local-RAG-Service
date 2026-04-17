import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { DomSanitizer, SafeResourceUrl } from '@angular/platform-browser';
import { UploadService, Document } from '../../services/upload';

type UploadStatus = 'idle' | 'uploading' | 'success' | 'error';

@Component({
  selector: 'app-upload',
  imports: [CommonModule],
  templateUrl: './upload.html',
  styleUrl: './upload.scss',
})
export class UploadPage implements OnInit {
  dragOver = signal(false);
  status = signal<UploadStatus>('idle');
  statusMessage = signal('');
  documents = signal<Document[]>([]);
  loadingDocs = signal(false);
  viewerUrl = signal<SafeResourceUrl | null>(null);
  viewerName = signal('');

  constructor(
    private uploadService: UploadService,
    private sanitizer: DomSanitizer,
  ) {}

  ngOnInit(): void {
    this.loadDocuments();
  }

  onDragOver(event: DragEvent): void {
    event.preventDefault();
    this.dragOver.set(true);
  }

  onDragLeave(): void {
    this.dragOver.set(false);
  }

  onDrop(event: DragEvent): void {
    event.preventDefault();
    this.dragOver.set(false);
    const file = event.dataTransfer?.files[0];
    if (file) this.upload(file);
  }

  onFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (file) this.upload(file);
    input.value = '';
  }

  upload(file: File): void {
    this.status.set('uploading');
    this.statusMessage.set(`Uploading "${file.name}"...`);

    this.uploadService.uploadFile(file).subscribe({
      next: (res) => {
        this.status.set('success');
        this.statusMessage.set(`"${res.original_name}" uploaded successfully.`);
        this.loadDocuments();
      },
      error: (err) => {
        this.status.set('error');
        this.statusMessage.set(err.error?.detail ?? 'Upload failed. Please try again.');
      },
    });
  }

  loadDocuments(): void {
    this.loadingDocs.set(true);
    this.uploadService.getDocuments().subscribe({
      next: (docs) => {
        this.documents.set(docs);
        this.loadingDocs.set(false);
      },
      error: () => {
        this.loadingDocs.set(false);
      },
    });
  }

  viewDocument(doc: Document): void {
    const url = `http://localhost:8000/documents/${doc.id}/view`;
    this.viewerUrl.set(this.sanitizer.bypassSecurityTrustResourceUrl(url));
    this.viewerName.set(doc.original_name);
  }

  closeViewer(): void {
    this.viewerUrl.set(null);
    this.viewerName.set('');
  }

  deleteDocument(doc: Document): void {
    this.uploadService.deleteDocument(doc.id).subscribe({
      next: () => {
        this.documents.update(docs => docs.filter(d => d.id !== doc.id));
        if (this.viewerName() === doc.original_name) this.closeViewer();
      },
    });
  }

  getFileIcon(name: string): string {
    return name.toLowerCase().endsWith('.pdf') ? '📄' : '📝';
  }

  isPdf(name: string): boolean {
    return name.toLowerCase().endsWith('.pdf');
  }
}
