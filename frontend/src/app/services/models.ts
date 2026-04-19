import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

export interface Model {
  id: number;
  name: string;
  type: string;
  api_key: string | null;
  base_url: string | null;
  is_default: boolean;
  created_at: string;
  updated_at: string;
}

export interface ModelBody {
  name: string;
  type: string;
  api_key?: string | null;
  base_url?: string | null;
  is_default: boolean;
}

@Injectable({ providedIn: 'root' })
export class ModelsService {
  private readonly api = 'http://localhost:8000';

  constructor(private http: HttpClient) {}

  getAll(): Observable<Model[]> {
    return this.http.get<Model[]>(`${this.api}/models`);
  }

  create(body: ModelBody): Observable<Model> {
    return this.http.post<Model>(`${this.api}/models`, body);
  }

  update(id: number, body: ModelBody): Observable<Model> {
    return this.http.put<Model>(`${this.api}/models/${id}`, body);
  }

  setDefault(id: number): Observable<Model> {
    return this.http.patch<Model>(`${this.api}/models/${id}/default`, {});
  }

  delete(id: number): Observable<{ message: string }> {
    return this.http.delete<{ message: string }>(`${this.api}/models/${id}`);
  }

  getOllamaTags(baseUrl?: string): Observable<string[]> {
    const params = baseUrl ? `?base_url=${encodeURIComponent(baseUrl)}` : '';
    return this.http.get<string[]>(`${this.api}/models/ollama-tags${params}`);
  }
}
