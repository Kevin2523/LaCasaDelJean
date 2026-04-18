import 'zone.js'; // <--- ¡ESTO SOLUCIONA LA PANTALLA BLANCA!
import { bootstrapApplication } from '@angular/platform-browser';
import { appConfig } from './app/app.config';
import { App } from './app/app';

bootstrapApplication(App, appConfig)
  .catch((err) => console.error(err));