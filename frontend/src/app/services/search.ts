import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

export type SearchType = 'semantic' | 'keyword' | 'hybrid';

export interface SearchResult {
  id: number;
  file_id: number;
  chunk_index: number;
  content: string;
  score: number;
  original_name: string;
}

@Injectable({ providedIn: 'root' })
export class SearchService {
  private readonly apiUrl = 'http://localhost:8000';

  constructor(private http: HttpClient) {}

  search(
    query: string,
    limit = 5,
    fileId: number | null = null,
    searchType: SearchType = 'semantic',
  ): Observable<SearchResult[]> {
    return this.http.post<SearchResult[]>(`${this.apiUrl}/search`, {
      query,
      limit,
      file_id:     fileId,
      search_type: searchType,
    });
  }
}
