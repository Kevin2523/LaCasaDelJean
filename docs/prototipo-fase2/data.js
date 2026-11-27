// Datos simulados (mock) exclusivos para el prototipo visual — Etapa A (Fase 2)
// Sin conexión a base de datos ni llamadas a FastAPI.
// Todas las fotografías son ilustrativas con licencia verificable (Wikimedia Commons).

window.LCDJ_DATA = {
  store: {
    name: "La Casa del Jean",
    tagline: "Moda denim y básicos esenciales para toda la familia en Panamá.",
    whatsappDisplay: "+507 6522-6428",
    location: "Ciudad de Panamá, Panamá",
    hours: "Lun – Sáb · 9:00 a.m. – 7:00 p.m.",
    currency: "B/."
  },

  heroImage: {
    url: "https://thumb.wikimedia.org/wikipedia/commons/thumb/0/01/Jeans_Jeans_Jeans.jpg/960px-Jeans_Jeans_Jeans.jpg?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=thumbnail",
    alt: "Pila de jeans denim doblados en distintos tonos de azul",
    author: "Jcjeansandclothes",
    license: "CC BY-SA 3.0",
    source: "https://commons.wikimedia.org/wiki/File:Jeans_Jeans_Jeans.jpg"
  },

  categories: [
    { id: "todos", label: "Todos" },
    { id: "damas", label: "Damas" },
    { id: "caballeros", label: "Caballeros" },
    { id: "ninos", label: "Niños y Familia" },
    { id: "basicos", label: "Básicos y Chaquetas" }
  ],

  products: [
    {
      id: "lcdj-001",
      sku: "DJ-CAB-101",
      name: "Jean Recto Clásico Índigo",
      category: "caballeros",
      categoryLabel: "Caballeros",
      price: 38.50,
      badge: "Más buscado",
      featured: true,
      description: "Corte recto atemporal en mezclilla resistente de 12 oz. Ideal para uso diario en el clima de Panamá con costura reforzada y caída cómoda.",
      material: "98% Algodón, 2% Elastano",
      fit: "Straight Fit · Tiro medio",
      color: "Índigo Clásico",
      image: "https://thumb.wikimedia.org/wikipedia/commons/thumb/0/00/Broken_twill_denim_Wrangler_13MWZ_jeans_%282026-01-21%29.jpg/960px-Broken_twill_denim_Wrangler_13MWZ_jeans_%282026-01-21%29.jpg?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=thumbnail",
      attribution: {
        author: "Olgierd Rudak",
        license: "CC BY-SA 4.0",
        source: "https://commons.wikimedia.org/wiki/File:Broken_twill_denim_Wrangler_13MWZ_jeans_(2026-01-21).jpg"
      },
      sizes: [
        { size: "28", stock: 6 },
        { size: "30", stock: 12 },
        { size: "32", stock: 9 },
        { size: "34", stock: 3 },
        { size: "36", stock: 0 }
      ],
      status: "Publicado"
    },
    {
      id: "lcdj-002",
      sku: "DJ-DAM-204",
      name: "Jean Tiro Alto Silueta Estilizada",
      category: "damas",
      categoryLabel: "Damas",
      price: 42.00,
      badge: "Nueva llegada",
      featured: true,
      description: "Denim suave con elasticidad controlada que acompaña el movimiento sin perder su forma. Acabado limpio en azul medio.",
      material: "92% Algodón, 6% Poliéster, 2% Elastano",
      fit: "High-Rise Slim · Tiro alto",
      color: "Azul Medio",
      image: "https://thumb.wikimedia.org/wikipedia/commons/thumb/f/fe/Sedcard_outfit_consisting_of_white_top_%28bodysuit%29%2C_%28blue%29_denim_and_heels.jpg/960px-Sedcard_outfit_consisting_of_white_top_%28bodysuit%29%2C_%28blue%29_denim_and_heels.jpg?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=thumbnail",
      attribution: {
        author: "Tobias ToMar Maier",
        license: "CC BY-SA 4.0",
        source: "https://commons.wikimedia.org/wiki/File:Sedcard_outfit_consisting_of_white_top_(bodysuit),_(blue)_denim_and_heels.jpg"
      },
      sizes: [
        { size: "6", stock: 5 },
        { size: "8", stock: 10 },
        { size: "10", stock: 8 },
        { size: "12", stock: 2 },
        { size: "14", stock: 4 }
      ],
      status: "Publicado"
    },
    {
      id: "lcdj-003",
      sku: "CH-BAS-301",
      name: "Chaqueta Denim Tradicional",
      category: "basicos",
      categoryLabel: "Básicos y Chaquetas",
      price: 49.00,
      badge: "Esencial",
      featured: true,
      description: "Chaqueta de mezclilla estructurada con bolsillos frontales y botones metálicos. Una prenda versátil para combinar en cualquier temporada.",
      material: "100% Algodón Denim",
      fit: "Regular Fit",
      color: "Azul Lavado",
      image: "https://thumb.wikimedia.org/wikipedia/commons/thumb/0/06/Jean_jacket.jpg/960px-Jean_jacket.jpg?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=thumbnail",
      attribution: {
        author: "NikosLikomitros",
        license: "CC0",
        source: "https://commons.wikimedia.org/wiki/File:Jean_jacket.jpg"
      },
      sizes: [
        { size: "S", stock: 4 },
        { size: "M", stock: 7 },
        { size: "L", stock: 5 },
        { size: "XL", stock: 2 }
      ],
      status: "Publicado"
    },
    {
      id: "lcdj-004",
      sku: "CM-CAB-118",
      name: "Camisa Denim Manga Enrollable",
      category: "caballeros",
      categoryLabel: "Caballeros",
      price: 34.00,
      badge: "",
      featured: true,
      description: "Camisa ligera de algodón chambray pensada para climas cálidos. Funciona abierta sobre camiseta o abotonada para un look casual limpio.",
      material: "100% Algodón Ligero",
      fit: "Tailored Casual",
      color: "Celeste Denim",
      image: "https://upload.wikimedia.org/wikipedia/commons/e/ec/Man_wearing_blue_denim_shirt_with_rolled_sleeves%2C_tan_chinos_1.jpg?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=thumbnail_unscaled",
      attribution: {
        author: "May Lee",
        license: "CC BY-SA 2.0",
        source: "https://commons.wikimedia.org/wiki/File:Man_wearing_blue_denim_shirt_with_rolled_sleeves,_tan_chinos_1.jpg"
      },
      sizes: [
        { size: "S", stock: 3 },
        { size: "M", stock: 9 },
        { size: "L", stock: 6 },
        { size: "XL", stock: 0 }
      ],
      status: "Publicado"
    },
    {
      id: "lcdj-005",
      sku: "PN-CAB-125",
      name: "Pantalón Chino Algodón Arena",
      category: "caballeros",
      categoryLabel: "Caballeros",
      price: 36.00,
      badge: "",
      featured: false,
      description: "Alternativa fresca al denim tradicional en sarga de algodón peinado. Bolsillos traseros de ojal y acabado suave al tacto.",
      material: "97% Algodón, 3% Elastano",
      fit: "Slim Straight",
      color: "Arena / Khaki",
      image: "https://thumb.wikimedia.org/wikipedia/commons/thumb/3/3e/Chino_pants.jpg/960px-Chino_pants.jpg?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=thumbnail",
      attribution: {
        author: "Kuha455405",
        license: "CC BY-SA 3.0",
        source: "https://commons.wikimedia.org/wiki/File:Chino_pants.jpg"
      },
      sizes: [
        { size: "30", stock: 8 },
        { size: "32", stock: 11 },
        { size: "34", stock: 5 },
        { size: "36", stock: 2 }
      ],
      status: "Publicado"
    },
    {
      id: "lcdj-006",
      sku: "FM-NIN-402",
      name: "Conjunto Familiar Rayas y Denim",
      category: "ninos",
      categoryLabel: "Niños y Familia",
      price: 26.50,
      badge: "Familiar",
      featured: false,
      description: "Prendas frescas de algodón transpirable pensadas para fines de semana en familia. Tejido suave y lavado fácil.",
      material: "100% Algodón Peinado",
      fit: "Comfort Fit",
      color: "Blanco / Marino",
      image: "https://thumb.wikimedia.org/wikipedia/commons/thumb/2/27/Man_in_marini%C3%A8re_with_child.jpg/960px-Man_in_marini%C3%A8re_with_child.jpg?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=thumbnail",
      attribution: {
        author: "DimiTalen",
        license: "CC0",
        source: "https://commons.wikimedia.org/wiki/File:Man_in_marini%C3%A8re_with_child.jpg"
      },
      sizes: [
        { size: "4", stock: 7 },
        { size: "6", stock: 6 },
        { size: "8", stock: 4 },
        { size: "10", stock: 1 }
      ],
      status: "Publicado"
    },
    {
      id: "lcdj-007",
      sku: "CH-DAM-219",
      name: "Sobrecamisa Denim Costura Contraste",
      category: "damas",
      categoryLabel: "Damas",
      price: 44.50,
      badge: "Pocas unidades",
      featured: false,
      description: "Acabado detallado con pespuntes en hilo ocre y bolsillos de parche. Ideal para superponer sobre básicos blancos.",
      material: "100% Algodón Denim",
      fit: "Relaxed Fit",
      color: "Azul Oscuro",
      image: "https://thumb.wikimedia.org/wikipedia/commons/thumb/2/27/Denim_jacket_details.jpg/960px-Denim_jacket_details.jpg?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=thumbnail",
      attribution: {
        author: "Shixart1985",
        license: "CC BY 2.0",
        source: "https://commons.wikimedia.org/wiki/File:Denim_jacket_details.jpg"
      },
      sizes: [
        { size: "XS", stock: 1 },
        { size: "S", stock: 2 },
        { size: "M", stock: 3 },
        { size: "L", stock: 0 }
      ],
      status: "Publicado"
    },
    {
      id: "lcdj-008",
      sku: "PL-BAS-315",
      name: "Polo Piqué Clásico Colección Color",
      category: "basicos",
      categoryLabel: "Básicos y Chaquetas",
      price: 22.00,
      badge: "",
      featured: false,
      description: "Camiseta polo en tejido piqué transpirable para combinar con jeans o chinos. Cuello estructurado que mantiene su forma.",
      material: "100% Algodón Piqué",
      fit: "Classic Fit",
      color: "Surtido Neutro",
      image: "https://thumb.wikimedia.org/wikipedia/commons/thumb/d/d1/Various_colors_of_polo_shirt_at_JCPenney.jpg/960px-Various_colors_of_polo_shirt_at_JCPenney.jpg?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=thumbnail",
      attribution: {
        author: "Ser Amantio di Nicolao",
        license: "CC BY-SA 4.0",
        source: "https://commons.wikimedia.org/wiki/File:Various_colors_of_polo_shirt_at_JCPenney.jpg"
      },
      sizes: [
        { size: "S", stock: 10 },
        { size: "M", stock: 14 },
        { size: "L", stock: 9 },
        { size: "XL", stock: 5 }
      ],
      status: "Publicado"
    }
  ],

  initialCart: [
    {
      productId: "lcdj-001",
      size: "32",
      qty: 1
    },
    {
      productId: "lcdj-002",
      size: "8",
      qty: 1
    }
  ]
};
