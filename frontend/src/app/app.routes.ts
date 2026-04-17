import { Routes } from '@angular/router';
import { UploadPage } from './pages/upload/upload';
import { SearchPage } from './pages/search/search';

export const routes: Routes = [
  { path: '',       component: UploadPage },
  { path: 'search', component: SearchPage },
  { path: '**',     redirectTo: '' },
];
