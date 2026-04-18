import {
  Component, OnInit, signal,
  ElementRef, ViewChild, AfterViewChecked,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { ChatService, ChatMessage } from '../../services/chat';
import { ModelsService, Model } from '../../services/models';
import { UploadService, Document } from '../../services/upload';
import { SearchResult } from '../../services/search';

interface DisplayMessage {
  role: 'user' | 'assistant';
  content: string;
  sources?: SearchResult[];
  loading?: boolean;
}

@Component({
  selector: 'app-chat',
  imports: [CommonModule, FormsModule, RouterLink],
  templateUrl: './chat.html',
  styleUrl: './chat.scss',
})
export class ChatPage implements OnInit, AfterViewChecked {
  @ViewChild('messagesEl') messagesEl!: ElementRef<HTMLDivElement>;
  @ViewChild('inputEl')    inputEl!:    ElementRef<HTMLTextAreaElement>;

  messages          = signal<DisplayMessage[]>([]);
  models            = signal<Model[]>([]);
  documents         = signal<Document[]>([]);
  selectedModelId: number | null = null;
  fileId:          number | null = null;
  input  = '';
  loading = signal(false);

  private shouldScroll = false;

  constructor(
    private chatService:   ChatService,
    private modelsService: ModelsService,
    private uploadService: UploadService,
  ) {}

  ngOnInit(): void {
    this.modelsService.getAll().subscribe({
      next: (list) => {
        this.models.set(list);
        const def = list.find(m => m.is_default);
        if (def) this.selectedModelId = def.id;
      },
    });
    this.uploadService.getDocuments().subscribe({
      next: (docs) => this.documents.set(docs.filter(d => d.status === 'ready')),
    });
  }

  ngAfterViewChecked(): void {
    if (this.shouldScroll) {
      const el = this.messagesEl?.nativeElement;
      if (el) el.scrollTop = el.scrollHeight;
      this.shouldScroll = false;
    }
  }

  send(): void {
    const text = this.input.trim();
    if (!text || this.loading()) return;

    const history: ChatMessage[] = this.messages()
      .filter(m => !m.loading)
      .map(m => ({ role: m.role, content: m.content }));

    this.messages.update(m => [
      ...m,
      { role: 'user',      content: text },
      { role: 'assistant', content: '', loading: true },
    ]);

    this.input = '';
    this.loading.set(true);
    this.shouldScroll = true;
    this.autoResize();

    this.chatService.chat({
      messages: [...history, { role: 'user', content: text }],
      model_id: this.selectedModelId ?? undefined,
      file_id:  this.fileId,
    }).subscribe({
      next: (res) => {
        this.messages.update(msgs => {
          const copy = [...msgs];
          const idx = copy.length - 1 - [...copy].reverse().findIndex(m => m.loading);
          copy[idx] = { role: 'assistant', content: res.answer, sources: res.sources };
          return copy;
        });
        this.loading.set(false);
        this.shouldScroll = true;
      },
      error: (err) => {
        const msg = err.error?.detail ?? 'Something went wrong. Please try again.';
        this.messages.update(msgs => {
          const copy = [...msgs];
          const idx = copy.length - 1 - [...copy].reverse().findIndex(m => m.loading);
          copy[idx] = { role: 'assistant', content: `⚠ ${msg}`, sources: [] };
          return copy;
        });
        this.loading.set(false);
        this.shouldScroll = true;
      },
    });
  }

  onKeydown(event: KeyboardEvent): void {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      this.send();
    }
  }

  autoResize(): void {
    const el = this.inputEl?.nativeElement;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 120) + 'px';
  }

  clearChat(): void {
    this.messages.set([]);
  }

  getFileIcon(name: string): string {
    return name?.toLowerCase().endsWith('.pdf') ? '📄' : '📝';
  }
}
