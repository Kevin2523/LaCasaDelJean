import { CommonModule } from '@angular/common';
import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';
import { HERO_PHOTO, PLACEHOLDER_PHOTOS } from '../../../core/utils/media-placeholders';

@Component({
  selector: 'app-footer',
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `
    <footer class="denim-twill mt-16 border-t border-white/10 text-[#f4efe8]">
      <div class="mx-auto max-w-[1240px] px-4 py-12 md:px-7">
        <div class="grid gap-10 md:grid-cols-3">
          <div>
            <p class="font-editorial text-2xl font-bold tracking-tight text-white">
              La Casa del Jean
            </p>
            <p class="mt-2 text-sm leading-relaxed text-[#d9d0c5]">
              Catálogo público en línea con precios en Balboas panameños (<strong class="text-white">B/. · PAB</strong>)
              y disponibilidad indicativa sincronizada con inventario.
            </p>
            <p class="mt-3 text-xs text-[#c5b9aa]">
              Identidad tipográfica provisional (no logotipo definitivo). Sin cuentas de cliente ni pagos en línea en esta etapa.
            </p>
          </div>

          <div>
            <h2 class="text-xs font-semibold uppercase tracking-[0.16em] text-[#e7b297]">
              Navegación
            </h2>
            <ul class="mt-3 space-y-2 text-sm text-[#e7ddd1]">
              <li>
                <a routerLink="/" class="hover:text-white hover:underline">Inicio</a>
              </li>
              <li>
                <a routerLink="/catalogo" class="hover:text-white hover:underline">Catálogo completo</a>
              </li>
              <li>
                <a
                  routerLink="/catalogo"
                  [queryParams]="{ in_stock: 'true' }"
                  class="hover:text-white hover:underline"
                >
                  Solo prendas disponibles
                </a>
              </li>
            </ul>
          </div>

          <div>
            <h2 class="text-xs font-semibold uppercase tracking-[0.16em] text-[#e7b297]">
              Atribución de fotografías ilustrativas
            </h2>
            <p class="mt-2 text-xs leading-relaxed text-[#d9d0c5]">
              Cuando una prenda no cuenta aún con fotografía propia en servidor, se muestran imágenes reales con licencia abierta verificable:
            </p>
            <details class="mt-2 text-xs text-[#d9d0c5]">
              <summary class="cursor-pointer font-medium text-white hover:underline">
                Ver fuentes y licencias ({{ attributions.length }})
              </summary>
              <ul class="mt-2 space-y-1.5 border-l border-white/20 pl-3">
                @for (photo of attributions; track photo.id) {
                  <li>
                    <a
                      [href]="photo.sourceUrl"
                      target="_blank"
                      rel="noopener noreferrer"
                      class="underline decoration-white/30 hover:text-white"
                    >
                      {{ photo.author }}
                    </a>
                    <span class="text-[#c5b9aa]"> ({{ photo.license }})</span>
                  </li>
                }
              </ul>
            </details>
          </div>
        </div>

        <div class="mt-10 flex flex-col items-start justify-between gap-2 border-t border-white/10 pt-6 text-xs text-[#c5b9aa] sm:flex-row sm:items-center">
          <p>© {{ year }} La Casa del Jean · Catálogo Público V2</p>
          <p>Precios expresados en Balboas (B/. · PAB) · Disponibilidad indicativa</p>
        </div>
      </div>
    </footer>
  `,
})
export class FooterComponent {
  readonly year = new Date().getFullYear();
  readonly attributions = [HERO_PHOTO, ...PLACEHOLDER_PHOTOS];
}
