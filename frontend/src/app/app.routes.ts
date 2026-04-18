import { Routes } from '@angular/router';
import { HomePage } from './pages/home/home';
import { ChatPage } from './pages/chat/chat';
import { UploadPage } from './pages/upload/upload';
import { DocumentsPage } from './pages/documents/documents';
import { SearchPage } from './pages/search/search';
import { ModelsPage } from './pages/models/models';

export const routes: Routes = [
  { path: '',          component: HomePage },
  { path: 'chat',      component: ChatPage },
  { path: 'search',    component: SearchPage },
  { path: 'documents', component: DocumentsPage },
  { path: 'upload',    component: UploadPage },
  { path: 'models',    component: ModelsPage },
  { path: '**',        redirectTo: '' },
];
