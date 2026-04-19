import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ModelsService, Model, ModelBody } from '../../services/models';
import { ConfirmDialogComponent } from '../../components/confirm-dialog/confirm-dialog';

type ModalMode = 'create' | 'edit';

const EMPTY_FORM = (): ModelBody => ({
  name: '', type: 'local', api_key: '', base_url: '', is_default: false,
});

@Component({
  selector: 'app-models',
  imports: [CommonModule, FormsModule, ConfirmDialogComponent],
  templateUrl: './models.html',
  styleUrl: './models.scss',
})
export class ModelsPage implements OnInit {
  models        = signal<Model[]>([]);
  loading       = signal(false);
  modalOpen     = signal(false);
  modalMode     = signal<ModalMode>('create');
  editingId     = signal<number | null>(null);
  saving        = signal(false);
  pendingDelete = signal<Model | null>(null);
  showKey       = signal<number | null>(null);
  ollamaModels  = signal<string[]>([]);
  ollamaLoading = signal(false);
  form          = EMPTY_FORM();

  readonly types = [
    { value: 'local',     label: 'Local' },
    { value: 'ollama',    label: 'Ollama' },
    { value: 'openai',    label: 'OpenAI' },
    { value: 'anthropic', label: 'Anthropic' },
    { value: 'gemini',    label: 'Gemini' },
    { value: 'custom',    label: 'Custom' },
  ];

  constructor(private modelsService: ModelsService) {}

  ngOnInit(): void { this.load(); }

  load(): void {
    this.loading.set(true);
    this.modelsService.getAll().subscribe({
      next: (m) => { this.models.set(m); this.loading.set(false); },
      error: ()  => this.loading.set(false),
    });
  }

  openCreate(): void {
    this.form = EMPTY_FORM();
    this.editingId.set(null);
    this.modalMode.set('create');
    this.modalOpen.set(true);
    this.fetchOllamaModels();
  }

  openEdit(m: Model): void {
    this.form = { name: m.name, type: m.type, api_key: m.api_key ?? '', base_url: m.base_url ?? '', is_default: m.is_default };
    this.editingId.set(m.id);
    this.modalMode.set('edit');
    this.modalOpen.set(true);
    if (this.isOllama(m.type)) this.fetchOllamaModels(m.base_url ?? undefined);
  }

  onTypeChange(): void {
    if (this.isOllama(this.form.type)) this.fetchOllamaModels(this.form.base_url || undefined);
  }

  fetchOllamaModels(baseUrl?: string): void {
    this.ollamaLoading.set(true);
    this.modelsService.getOllamaTags(baseUrl).subscribe({
      next: (tags) => { this.ollamaModels.set(tags); this.ollamaLoading.set(false); },
      error: ()    => { this.ollamaModels.set([]); this.ollamaLoading.set(false); },
    });
  }

  isOllama(type: string): boolean {
    return type === 'ollama' || type === 'local';
  }

  closeModal(): void { this.modalOpen.set(false); }

  save(): void {
    if (!this.form.name.trim()) return;
    this.saving.set(true);
    const body: ModelBody = {
      ...this.form,
      api_key:  this.form.api_key  || null,
      base_url: this.form.base_url || null,
    };
    const req = this.modalMode() === 'create'
      ? this.modelsService.create(body)
      : this.modelsService.update(this.editingId()!, body);

    req.subscribe({
      next: () => { this.saving.set(false); this.closeModal(); this.load(); },
      error: () => this.saving.set(false),
    });
  }

  setDefault(m: Model): void {
    if (m.is_default) return;
    this.modelsService.setDefault(m.id).subscribe({ next: () => this.load() });
  }

  confirmDelete(m: Model): void { this.pendingDelete.set(m); }
  cancelDelete(): void          { this.pendingDelete.set(null); }

  executeDelete(): void {
    const m = this.pendingDelete();
    if (!m) return;
    this.pendingDelete.set(null);
    this.modelsService.delete(m.id).subscribe({ next: () => this.load() });
  }

  toggleKey(id: number): void {
    this.showKey.set(this.showKey() === id ? null : id);
  }

  typeLabel(type: string): string {
    return this.types.find(t => t.value === type)?.label ?? type;
  }

  needsKey(type: string): boolean {
    return ['openai', 'anthropic', 'gemini', 'custom'].includes(type);
  }
}
