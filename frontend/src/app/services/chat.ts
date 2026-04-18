import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { SearchResult } from './search';

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface ChatRequest {
  messages: ChatMessage[];
  model_id?: number;
  file_id?: number | null;
  limit?: number;
}

export interface ChatResponse {
  answer: string;
  sources: SearchResult[];
}

@Injectable({ providedIn: 'root' })
export class ChatService {
  private readonly api = 'http://localhost:8000';

  constructor(private http: HttpClient) {}

  chat(request: ChatRequest): Observable<ChatResponse> {
    return this.http.post<ChatResponse>(`${this.api}/chat`, request);
  }
}
