import { Component, signal, ElementRef, ViewChild } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { SearchService, SearchResult } from '../../services/search';

type SearchStatus = 'idle' | 'loading' | 'done' | 'error';

@Component({
  selector: 'app-search',
  imports: [CommonModule, FormsModule, RouterLink],
  templateUrl: './search.html',
  styleUrl: './search.scss',
})
export class SearchPage {
  @ViewChild('queryInput') queryInput!: ElementRef<HTMLInputElement>;

  query   = '';
  limit   = 5;
  status  = signal<SearchStatus>('idle');
  results = signal<SearchResult[]>([]);
  error   = signal('');

  constructor(private searchService: SearchService) {}

  submit(): void {
    const q = this.query.trim();
    if (!q) return;
    this.status.set('loading');
    this.results.set([]);
    this.error.set('');

    this.searchService.search(q, this.limit).subscribe({
      next: (res) => {
        this.results.set(res);
        this.status.set('done');
      },
      error: (err) => {
        this.error.set(err.error?.detail ?? 'Search failed. Please try again.');
        this.status.set('error');
      },
    });
  }

  clear(): void {
    this.query = '';
    this.results.set([]);
    this.status.set('idle');
    this.error.set('');
    setTimeout(() => this.queryInput?.nativeElement.focus(), 0);
  }

  scoreLabel(score: number): string {
    if (score >= 0.85) return 'High';
    if (score >= 0.65) return 'Medium';
    return 'Low';
  }

  scoreClass(score: number): string {
    if (score >= 0.85) return 'score--high';
    if (score >= 0.65) return 'score--medium';
    return 'score--low';
  }

  getFileIcon(name: string): string {
    return name?.toLowerCase().endsWith('.pdf') ? '📄' : '📝';
  }
}
