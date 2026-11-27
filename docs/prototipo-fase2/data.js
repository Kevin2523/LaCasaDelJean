// Datos simulados (mock) exclusivos para el prototipo visual — Etapa A (Fase 2)
// Sin conexión a base de datos ni llamadas a FastAPI.
// Todas las fotografías son reales con licencia verificable (Wikimedia Commons).
// Nota de moneda: "B/." se muestra como referencia visual; su definición frente al contrato COP del backend queda pendiente para Etapa B.

window.LCDJ_DATA = {
  store: {
    name: "La Casa del Jean",
    tagline: "Calidad, comodidad y el fit perfecto para tu día a día.",
    whatsappDisplay: "+507 6522-6428",
    location: "San Carlos, Panamá",
    hours: "Lun – Sáb · 9:00 a.m. – 7:00 p.m.",
    currency: "B/."
  },

  heroImage: {
    url: "https://thumb.wikimedia.org/wikipedia/commons/thumb/0/01/Jeans_Jeans_Jeans.jpg/960px-Jeans_Jeans_Jeans.jpg?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=thumbnail",
    alt: "Campaña editorial de modelos vistiendo jeans y camisas denim azul índigo",
    author: "Jcjeansandclothes",
    license: "CC BY-SA 3.0",
    source: "https://commons.wikimedia.org/wiki/File:Jeans_Jeans_Jeans.jpg"
  },

  denimStackImage: {
    url: "https://thumb.wikimedia.org/wikipedia/commons/thumb/9/99/Jeans_mexicanos.jpg/960px-Jeans_mexicanos.jpg?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=thumbnail",
    alt: "Pantalones jeans denim azul en exhibición",
    author: "El Nuevo Doge",
    license: "CC0",
    source: "https://commons.wikimedia.org/wiki/File:Jeans_mexicanos.jpg"
  },

  categories: [
    {
      id: "todos",
      label: "Todos",
      image: "https://thumb.wikimedia.org/wikipedia/commons/thumb/0/01/Jeans_Jeans_Jeans.jpg/960px-Jeans_Jeans_Jeans.jpg?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=thumbnail"
    },
    {
      id: "jeans",
      label: "Jeans",
      image: "https://images.pexels.com/photos/6764017/pexels-photo-6764017.jpeg?auto=compress&cs=tinysrgb&w=900"
    },
    {
      id: "damas",
      label: "Damas",
      image: "https://images.pexels.com/photos/9713293/pexels-photo-9713293.jpeg?auto=compress&cs=tinysrgb&w=900"
    },
    {
      id: "caballeros",
      label: "Caballeros",
      image: "https://images.pexels.com/photos/6764017/pexels-photo-6764017.jpeg?auto=compress&cs=tinysrgb&w=900"
    },
    {
      id: "ninos",
      label: "Niños y Familia",
      image: "https://thumb.wikimedia.org/wikipedia/commons/thumb/2/27/Man_in_marini%C3%A8re_with_child.jpg/960px-Man_in_marini%C3%A8re_with_child.jpg?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=thumbnail"
    },
    {
      id: "basicos",
      label: "Básicos",
      image: "https://thumb.wikimedia.org/wikipedia/commons/thumb/d/d1/Various_colors_of_polo_shirt_at_JCPenney.jpg/960px-Various_colors_of_polo_shirt_at_JCPenney.jpg?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=thumbnail"
    }
  ],

  colors: [
    { id: "indigo", label: "Índigo", hex: "#1B365D" },
    { id: "azul-medio", label: "Azul Medio", hex: "#4D739B" },
    { id: "oscuro", label: "Azul Oscuro", hex: "#1F2937" },
    { id: "arena", label: "Arena", hex: "#C8B398" },
    { id: "terracota", label: "Terracota / Surtido", hex: "#B85A34" }
  ],

  products: [
    {
      id: "lcdj-001",
      sku: "DJ-CAB-101",
      name: "Jean Clásico Índigo",
      category: "jeans",
      categoryLabel: "Jeans",
      price: 38.50,
      badge: "Más buscado",
      featured: true,
      description: "Jean de corte recto, cómodo y resistente en mezclilla de 12 oz. Ideal para el uso diario con un estilo versátil que combina con todo.",
      material: "98% Algodón, 2% Elastano",
      fit: "Straight Fit · Tiro medio",
      color: "Índigo",
      colorId: "indigo",
      swatches: ["#1B365D", "#4D739B", "#1F2937"],
      image: "https://images.pexels.com/photos/6764017/pexels-photo-6764017.jpeg?auto=compress&cs=tinysrgb&w=900",
      attribution: {
        author: "Pexels (foto #6764017)",
        license: "Pexels License",
        source: "https://www.pexels.com/photo/man-in-jean-jacket-and-pants-on-white-backg-6764017/"
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
      name: "Jean Tiro Alto Slim",
      category: "damas",
      categoryLabel: "Damas",
      price: 42.00,
      badge: "Nueva llegada",
      featured: true,
      description: "Denim suave con elasticidad controlada que estiliza la silueta sin perder comodidad. Acabado limpio en azul medio.",
      material: "92% Algodón, 6% Poliéster, 2% Elastano",
      fit: "High-Rise Slim · Tiro alto",
      color: "Azul Medio",
      colorId: "azul-medio",
      swatches: ["#4D739B", "#1B365D"],
      image: "https://images.pexels.com/photos/37076315/pexels-photo-37076315.jpeg?auto=compress&cs=tinysrgb&w=900",
      attribution: {
        author: "Pexels (foto #37076315)",
        license: "Pexels License",
        source: "https://www.pexels.com/photo/stylish-model-posing-in-casual-denim-and-white-tee-37076315/"
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
      categoryLabel: "Básicos",
      price: 49.00,
      badge: "Esencial",
      featured: true,
      description: "Chaqueta de mezclilla estructurada con bolsillos frontales y botones metálicos. Una prenda versátil para combinar en cualquier ocasión.",
      material: "100% Algodón Denim",
      fit: "Regular Fit",
      color: "Azul Medio",
      colorId: "azul-medio",
      swatches: ["#4D739B", "#1B365D"],
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
      description: "Camisa ligera de algodón chambray pensada para el clima cálido de Panamá. Funciona abierta sobre camiseta o abotonada.",
      material: "100% Algodón Ligero",
      fit: "Tailored Casual",
      color: "Azul Medio",
      colorId: "azul-medio",
      swatches: ["#4D739B", "#C8B398"],
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
      description: "Alternativa fresca al denim tradicional en sarga de algodón peinado. Bolsillos traseros de ojal y acabado suave.",
      material: "97% Algodón, 3% Elastano",
      fit: "Slim Straight",
      color: "Arena",
      colorId: "arena",
      swatches: ["#C8B398", "#1F2937"],
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
      status: "Borrador"
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
      color: "Índigo",
      colorId: "indigo",
      swatches: ["#1B365D", "#F5F2EB"],
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
      colorId: "oscuro",
      swatches: ["#1F2937", "#1B365D"],
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
      categoryLabel: "Básicos",
      price: 22.00,
      badge: "",
      featured: false,
      description: "Camiseta polo en tejido piqué transpirable para combinar con jeans o chinos. Cuello estructurado que mantiene su forma.",
      material: "100% Algodón Piqué",
      fit: "Classic Fit",
      color: "Terracota / Surtido",
      colorId: "terracota",
      swatches: ["#B85A34", "#1B365D", "#C8B398"],
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

  recentMovements: [
    { type: "in", title: "Entrada de stock", detail: "Jean Clásico Índigo · +10 u.", time: "Hace 25 min" },
    { type: "out", title: "Salida de stock", detail: "Camisa Denim · −2 u.", time: "Hace 1 h" },
    { type: "in", title: "Entrada de stock", detail: "Chaqueta Denim Tradicional · +5 u.", time: "Hace 2 h" }
  ],

  initialCart: [
    { productId: "lcdj-001", size: "32", qty: 1 },
    { productId: "lcdj-002", size: "8", qty: 1 }
  ]
};
