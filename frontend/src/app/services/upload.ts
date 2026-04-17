import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

export interface Document {
  id: number;
  original_name: string;
  hashed_name: string;
  path: string;
  created_at: string;
}

export interface UploadResponse {
  message: string;
  original_name: string;
  hashed_name: string;
  path: string;
}

@Injectable({ providedIn: 'root' })
export class UploadService {
  private readonly apiUrl = 'http://localhost:8000';

  constructor(private http: HttpClient) {}

  uploadFile(file: File): Observable<UploadResponse> {
    const formData = new FormData();
    formData.append('file', file);
    return this.http.post<UploadResponse>(`${this.apiUrl}/upload`, formData);
  }

  getDocuments(): Observable<Document[]> {
    return this.http.get<Document[]>(`${this.apiUrl}/documents`);
  }

  deleteDocument(id: number): Observable<{ message: string }> {
    return this.http.delete<{ message: string }>(`${this.apiUrl}/documents/${id}`);
  }
}
