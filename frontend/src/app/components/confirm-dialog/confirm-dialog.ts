import { Component, input, output } from '@angular/core';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-confirm-dialog',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './confirm-dialog.html',
  styleUrl: './confirm-dialog.scss',
})
export class ConfirmDialogComponent {
  title        = input<string>('Confirm');
  message      = input<string>('Are you sure?');
  highlight    = input<string>('');
  confirmLabel = input<string>('Confirm');
  cancelLabel  = input<string>('Cancel');
  danger       = input<boolean>(true);

  confirmed = output<void>();
  cancelled = output<void>();
}
