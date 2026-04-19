import { Injectable } from '@angular/core';
import { HttpClient, HttpRequest, HttpEvent } from '@angular/common/http';
import { Observable } from 'rxjs';

export interface Document {
  id: number;
  original_name: string;
  hashed_name: string;
  path: string;
  size: number;
  status: string;
  chunk_count: number;
  created_at: string;
  start_at: string | null;
  ingested_at: string | null;
}

export interface Chunk {
  id: number;
  chunk_index: number;
  content: string;
}

export interface UploadResponse {
  message: string;
  file_id: number;
  original_name: string;
  hashed_name: string;
  path: string;
}

@Injectable({ providedIn: 'root' })
export class UploadService {
  private readonly apiUrl = 'http://localhost:8000';

  constructor(private http: HttpClient) {}

  uploadFile(file: File): Observable<HttpEvent<UploadResponse>> {
    const formData = new FormData();
    formData.append('file', file);
    const req = new HttpRequest('POST', `${this.apiUrl}/upload`, formData, {
      reportProgress: true,
    });
    return this.http.request<UploadResponse>(req);
  }

  getDocuments(): Observable<Document[]> {
    return this.http.get<Document[]>(`${this.apiUrl}/documents`);
  }

  deleteDocument(id: number): Observable<{ message: string }> {
    return this.http.delete<{ message: string }>(`${this.apiUrl}/documents/${id}`);
  }

  getDocumentChunks(id: number): Observable<Chunk[]> {
    return this.http.get<Chunk[]>(`${this.apiUrl}/documents/${id}/chunks`);
  }

  reindexDocument(id: number): Observable<{ message: string; file_id: number }> {
    return this.http.post<{ message: string; file_id: number }>(`${this.apiUrl}/documents/${id}/reindex`, {});
  }
}
