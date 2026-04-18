import { Routes } from '@angular/router';
import { UploadPage } from './pages/upload/upload';
import { DocumentsPage } from './pages/documents/documents';
import { SearchPage } from './pages/search/search';
import { ModelsPage } from './pages/models/models';

export const routes: Routes = [
  { path: '',          component: SearchPage },
  { path: 'search',    component: SearchPage },
  { path: 'documents', component: DocumentsPage },
  { path: 'upload',    component: UploadPage },
  { path: 'models',    component: ModelsPage },
  { path: '**',        redirectTo: '' },
];
