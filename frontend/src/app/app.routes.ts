import { Routes } from '@angular/router';
import { UploadPage } from './pages/upload/upload';
import { DocumentsPage } from './pages/documents/documents';
import { SearchPage } from './pages/search/search';

export const routes: Routes = [
  { path: '',          component: UploadPage },
  { path: 'documents', component: DocumentsPage },
  { path: 'search',    component: SearchPage },
  { path: '**',        redirectTo: '' },
];
