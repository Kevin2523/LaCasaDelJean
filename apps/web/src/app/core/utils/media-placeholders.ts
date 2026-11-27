export interface LicensedPhoto {
  id: string;
  url: string;
  alt: string;
  author: string;
  license: string;
  sourceUrl: string;
}

/**
 * Curated real placeholder photos with verified open licenses (Pexels License & Wikimedia Commons),
 * matching the approved references in docs/prototipo-fase2/README.md.
 */
export const HERO_PHOTO: LicensedPhoto = {
  id: 'hero-denim',
  url: 'https://images.pexels.com/photos/37076315/pexels-photo-37076315.jpeg?auto=compress&cs=tinysrgb&w=1280',
  alt: 'Colección de jeans y prendas denim en tonos índigo',
  author: 'Pexels (#37076315)',
  license: 'Pexels License',
  sourceUrl: 'https://www.pexels.com/photo/stylish-model-posing-in-casual-denim-and-white-tee-37076315/',
};

export const PLACEHOLDER_PHOTOS: LicensedPhoto[] = [
  {
    id: 'jeans-indigo',
    url: 'https://images.pexels.com/photos/6764017/pexels-photo-6764017.jpeg?auto=compress&cs=tinysrgb&w=900',
    alt: 'Jean clásico índigo con chaqueta denim',
    author: 'Pexels (#6764017)',
    license: 'Pexels License',
    sourceUrl: 'https://www.pexels.com/photo/man-in-jean-jacket-and-pants-on-white-backg-6764017/',
  },
  {
    id: 'damas-denim',
    url: 'https://images.pexels.com/photos/37076315/pexels-photo-37076315.jpeg?auto=compress&cs=tinysrgb&w=900',
    alt: 'Jean tiro alto slim con camiseta blanca',
    author: 'Pexels (#37076315)',
    license: 'Pexels License',
    sourceUrl: 'https://www.pexels.com/photo/stylish-model-posing-in-casual-denim-and-white-tee-37076315/',
  },
  {
    id: 'chaqueta-denim',
    url: 'https://upload.wikimedia.org/wikipedia/commons/thumb/3/3c/Jean_jacket.jpg/960px-Jean_jacket.jpg',
    alt: 'Chaqueta denim tradicional azul índigo',
    author: 'NikosLikomitros',
    license: 'CC0',
    sourceUrl: 'https://commons.wikimedia.org/wiki/File:Jean_jacket.jpg',
  },
  {
    id: 'caballeros-camisa',
    url: 'https://upload.wikimedia.org/wikipedia/commons/thumb/8/88/Man_wearing_blue_denim_shirt_with_rolled_sleeves%2C_tan_chinos_1.jpg/960px-Man_wearing_blue_denim_shirt_with_rolled_sleeves%2C_tan_chinos_1.jpg',
    alt: 'Camisa denim azul con pantalón chino arena',
    author: 'May Lee',
    license: 'CC BY-SA 2.0',
    sourceUrl: 'https://commons.wikimedia.org/wiki/File:Man_wearing_blue_denim_shirt_with_rolled_sleeves,_tan_chinos_1.jpg',
  },
  {
    id: 'damas-editorial',
    url: 'https://images.pexels.com/photos/9713293/pexels-photo-9713293.jpeg?auto=compress&cs=tinysrgb&w=900',
    alt: 'Prenda denim femenina de corte moderno',
    author: 'Pexels (#9713293)',
    license: 'Pexels License',
    sourceUrl: 'https://www.pexels.com/photo/a-woman-wearing-crop-top-and-denim-jeans-9713293/',
  },
  {
    id: 'basicos-polo',
    url: 'https://upload.wikimedia.org/wikipedia/commons/thumb/0/0a/Various_colors_of_polo_shirt_at_JCPenney.jpg/960px-Various_colors_of_polo_shirt_at_JCPenney.jpg',
    alt: 'Prendas básicas en algodón piqué',
    author: 'Ser Amantio di Nicolao',
    license: 'CC BY-SA 4.0',
    sourceUrl: 'https://commons.wikimedia.org/wiki/File:Various_colors_of_polo_shirt_at_JCPenney.jpg',
  },
  {
    id: 'familia-ninos',
    url: 'https://upload.wikimedia.org/wikipedia/commons/thumb/c/c8/Man_in_marini%C3%A8re_with_child.jpg/960px-Man_in_marini%C3%A8re_with_child.jpg',
    alt: 'Vestuario casual para niños y familia',
    author: 'DimiTalen',
    license: 'CC0',
    sourceUrl: 'https://commons.wikimedia.org/wiki/File:Man_in_marini%C3%A8re_with_child.jpg',
  },
];

function hashKey(key: string): number {
  let hash = 0;
  for (let i = 0; i < key.length; i += 1) {
    hash = (hash * 31 + key.charCodeAt(i)) >>> 0;
  }
  return hash;
}

export function getPlaceholderPhoto(key: string): LicensedPhoto {
  const normalized = key.toLowerCase();
  if (normalized.includes('dama') || normalized.includes('mujer')) {
    return PLACEHOLDER_PHOTOS[4];
  }
  if (normalized.includes('caballero') || normalized.includes('hombre') || normalized.includes('camisa')) {
    return PLACEHOLDER_PHOTOS[3];
  }
  if (normalized.includes('chaqueta') || normalized.includes('jacket')) {
    return PLACEHOLDER_PHOTOS[2];
  }
  if (normalized.includes('nino') || normalized.includes('niño') || normalized.includes('familia')) {
    return PLACEHOLDER_PHOTOS[6];
  }
  if (normalized.includes('basico') || normalized.includes('básico') || normalized.includes('polo')) {
    return PLACEHOLDER_PHOTOS[5];
  }
  if (normalized.includes('slim') || normalized.includes('jean')) {
    return PLACEHOLDER_PHOTOS[0];
  }
  return PLACEHOLDER_PHOTOS[hashKey(normalized) % PLACEHOLDER_PHOTOS.length];
}

function isSafeRelativeStoragePath(rawPath: string): boolean {
  if (!rawPath || rawPath.startsWith('/') || rawPath.startsWith('\\')) {
    return false;
  }
  if (rawPath.includes('\\') || rawPath.includes(':')) {
    return false;
  }
  const segments = rawPath.split('/');
  return segments.every(
    (segment) =>
      segment.length > 0 &&
      segment !== '.' &&
      segment !== '..' &&
      !/[\u0000-\u001F\u007F]/.test(segment)
  );
}

export function resolveCatalogImageUrl(
  storagePath: string | null | undefined,
  fallbackKey: string
): string {
  const trimmed = storagePath?.trim();
  if (!trimmed) {
    return getPlaceholderPhoto(fallbackKey).url;
  }
  if (/^https?:\/\//i.test(trimmed)) {
    return trimmed;
  }
  if (isSafeRelativeStoragePath(trimmed)) {
    const encodedPath = trimmed
      .split('/')
      .map((segment) => encodeURIComponent(segment))
      .join('/');
    return `/media/${encodedPath}`;
  }
  return getPlaceholderPhoto(fallbackKey).url;
}
