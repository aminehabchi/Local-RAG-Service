import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';

@Component({
  selector: 'app-home',
  imports: [RouterLink],
  templateUrl: './home.html',
  styleUrl: './home.scss',
})
export class HomePage {
  readonly features = [
    {
      icon: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>`,
      title: 'Chat',
      desc: 'Conversational AI backed by your documents. Ask anything — the model answers using retrieved context.',
      link: '/chat',
      label: 'Open Chat',
    },
    {
      icon: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>`,
      title: 'Search',
      desc: 'Three search modes: Semantic vector search, Keyword full-text, and Hybrid combining both via RRF.',
      link: '/search',
      label: 'Open Search',
    },
    {
      icon: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>`,
      title: 'Documents',
      desc: 'Browse your indexed files, inspect chunks, and manage your knowledge base.',
      link: '/documents',
      label: 'View Documents',
    },
    {
      icon: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75"><path d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5"/></svg>`,
      title: 'Upload',
      desc: 'Drag and drop PDF or text files. They are chunked, embedded, and indexed automatically.',
      link: '/upload',
      label: 'Upload Files',
    },
    {
      icon: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75"><rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8M12 17v4"/></svg>`,
      title: 'Models',
      desc: 'Connect Ollama, OpenAI, Anthropic, or any OpenAI-compatible endpoint. Switch models per session.',
      link: '/models',
      label: 'Manage Models',
    },
  ];

  readonly stack = [
    { label: 'FastAPI',     color: '#009688' },
    { label: 'PostgreSQL',  color: '#4169E1' },
    { label: 'pgvector',    color: '#6366f1' },
    { label: 'fastembed',   color: '#f59e0b' },
    { label: 'Angular 21',  color: '#DD0031' },
    { label: 'TypeScript',  color: '#3178C6' },
    { label: 'Ollama',      color: '#8c8c8c' },
  ];

  readonly steps = [
    { n: '01', title: 'Install pgvector', body: 'Make sure PostgreSQL has the vector extension: CREATE EXTENSION IF NOT EXISTS vector;' },
    { n: '02', title: 'Start the backend', body: 'cd backend && pip install -r requirements.txt && uvicorn main:app --reload --port 8000' },
    { n: '03', title: 'Start the frontend', body: 'cd frontend && npm install && ng serve' },
    { n: '04', title: 'Add a model', body: 'Go to Models, add your Ollama or API model, set it as default.' },
    { n: '05', title: 'Upload a document', body: 'Go to Upload, drop a PDF or text file and wait for ingestion to complete.' },
    { n: '06', title: 'Start chatting', body: 'Open Chat and ask anything about your documents.' },
  ];
}
