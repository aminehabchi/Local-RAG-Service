import { Routes } from '@angular/router';
import { UploadPage } from './pages/upload/upload';

export const routes: Routes = [
  { path: '', component: UploadPage },
  { path: '**', redirectTo: '' },
];
