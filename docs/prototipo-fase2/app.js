(() => {
  const DATA = window.LCDJ_DATA;
  const state = {
    view: "inicio",
    products: JSON.parse(JSON.stringify(DATA.products)),
    cart: JSON.parse(JSON.stringify(DATA.initialCart)),
    selectedProductId: DATA.products[0].id,
    selectedSize: null,
    selectedQty: 1,
    filters: {
      search: "",
      category: "todos",
      size: "",
      sort: "featured"
    },
    admin: {
      loggedIn: false,
      email: "",
      role: "Administrador",
      search: "",
      stockFilter: "all",
      editingProductId: null
    }
  };

  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => Array.from(document.querySelectorAll(sel));

  const formatPrice = (n) => `${DATA.store.currency} ${Number(n).toFixed(2)}`;
  const totalStock = (p) => p.sizes.reduce((sum, s) => sum + s.stock, 0);

  let toastTimer = null;
  function showToast(msg) {
    const el = $("#toast");
    el.textContent = msg;
    el.classList.add("is-visible");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => el.classList.remove("is-visible"), 2800);
  }

  function updateCartBadge() {
    const count = state.cart.reduce((sum, i) => sum + i.qty, 0);
    $("#header-cart-count").textContent = String(count);
  }

  function closeMobileNav() {
    $("#mobile-nav").classList.remove("is-open");
    $("#mobile-menu-btn").setAttribute("aria-expanded", "false");
  }

  function navigate(viewName, options = {}) {
    if (viewName === "admin-panel" && !state.admin.loggedIn) {
      viewName = "admin-login";
    }
    if (viewName === "admin-login" && state.admin.loggedIn) {
      viewName = "admin-panel";
    }

    state.view = viewName;
    closeMobileNav();

    $$(".view-section").forEach((sec) => {
      sec.classList.toggle("is-active", sec.id === `view-${viewName}`);
    });

    const activeNavKey = viewName === "admin-panel" ? "admin-login" : viewName === "detalle" ? "catalogo" : viewName;
    $$("[data-nav]").forEach((el) => {
      if (el.classList.contains("nav-link")) {
        if (el.dataset.nav === activeNavKey) {
          el.setAttribute("aria-current", "page");
        } else {
          el.removeAttribute("aria-current");
        }
      }
    });

    if (viewName === "inicio") renderHome();
    if (viewName === "catalogo") renderCatalog();
    if (viewName === "detalle") renderDetail(options.productId || state.selectedProductId);
    if (viewName === "carrito") renderCart();
    if (viewName === "admin-panel") renderAdminPanel();

    if (!options.skipHash) {
      const hash = viewName === "detalle" ? `#detalle/${state.selectedProductId}` : `#${viewName}`;
      if (window.location.hash !== hash) {
        history.replaceState(null, "", hash);
      }
    }

    window.scrollTo({ top: 0, behavior: "instant" });
  }

  function createProductCard(product) {
    const availSizes = product.sizes.filter((s) => s.stock > 0).map((s) => s.size);
    const article = document.createElement("article");
    article.className = "product-card";
    article.innerHTML = `
      <div class="product-thumb">
        <img src="${product.image}" alt="${product.name} — fotografía ilustrativa" loading="lazy" />
        ${product.badge ? `<span class="product-badge">${product.badge}</span>` : ""}
      </div>
      <div class="product-body">
        <div class="product-meta">${product.categoryLabel} · ${product.sku}</div>
        <h3 class="product-title">${product.name}</h3>
        <p class="product-price">${formatPrice(product.price)}</p>
        <p class="product-sizes-preview">Tallas: ${availSizes.length ? availSizes.join(", ") : "Agotado"}</p>
        <div class="product-card-actions">
          <button type="button" class="btn btn-primary btn-sm btn-full" data-open-product="${product.id}">
            Ver tallas y detalle
          </button>
        </div>
      </div>
    `;
    return article;
  }

  function renderHome() {
    const heroImg = $("#hero-img");
    heroImg.src = DATA.heroImage.url;
    heroImg.alt = DATA.heroImage.alt;
    $("#hero-caption").textContent = `Foto ilustrativa: ${DATA.heroImage.author} (${DATA.heroImage.license}) · Wikimedia Commons`;

    const chipsWrap = $("#home-category-chips");
    chipsWrap.innerHTML = "";
    DATA.categories.forEach((cat) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "chip" + (cat.id === "todos" ? " is-active" : "");
      btn.textContent = cat.label;
      btn.addEventListener("click", () => {
        state.filters.category = cat.id;
        $("#category-select").value = cat.id;
        navigate("catalogo");
      });
      chipsWrap.appendChild(btn);
    });

    const featuredGrid = $("#home-featured-grid");
    featuredGrid.innerHTML = "";
    state.products.filter((p) => p.featured).forEach((p) => {
      featuredGrid.appendChild(createProductCard(p));
    });
  }

  function populateFilterOptions() {
    const catSel = $("#category-select");
    catSel.innerHTML = "";
    DATA.categories.forEach((c) => {
      const opt = document.createElement("option");
      opt.value = c.id;
      opt.textContent = c.label;
      catSel.appendChild(opt);
    });

    const allSizes = Array.from(
      new Set(state.products.flatMap((p) => p.sizes.map((s) => s.size)))
    );
    const sizeSel = $("#size-select");
    sizeSel.innerHTML = `<option value="">Todas</option>`;
    allSizes.forEach((sz) => {
      const opt = document.createElement("option");
      opt.value = sz;
      opt.textContent = sz;
      sizeSel.appendChild(opt);
    });
  }

  function renderCatalog() {
    const q = state.filters.search.trim().toLowerCase();
    let list = state.products.filter((p) => {
      const matchCat = state.filters.category === "todos" || p.category === state.filters.category;
      const matchSearch =
        !q ||
        p.name.toLowerCase().includes(q) ||
        p.sku.toLowerCase().includes(q) ||
        p.color.toLowerCase().includes(q) ||
        p.categoryLabel.toLowerCase().includes(q);
      const matchSize =
        !state.filters.size ||
        p.sizes.some((s) => s.size === state.filters.size && s.stock > 0);
      return matchCat && matchSearch && matchSize;
    });

    if (state.filters.sort === "price-asc") list.sort((a, b) => a.price - b.price);
    if (state.filters.sort === "price-desc") list.sort((a, b) => b.price - a.price);
    if (state.filters.sort === "name-asc") list.sort((a, b) => a.name.localeCompare(b.name, "es"));

    $("#catalog-count").textContent = `Mostrando ${list.length} de ${state.products.length} prendas`;

    const grid = $("#catalog-grid");
    const empty = $("#catalog-empty");
    grid.innerHTML = "";

    if (list.length === 0) {
      empty.hidden = false;
    } else {
      empty.hidden = true;
      list.forEach((p) => grid.appendChild(createProductCard(p)));
    }
  }

  function renderDetail(productId) {
    const product = state.products.find((p) => p.id === productId) || state.products[0];
    state.selectedProductId = product.id;

    const firstAvail = product.sizes.find((s) => s.stock > 0);
    if (!state.selectedSize || !product.sizes.some((s) => s.size === state.selectedSize && s.stock > 0)) {
      state.selectedSize = firstAvail ? firstAvail.size : null;
    }
    state.selectedQty = 1;

    $("#detail-breadcrumb-cat").textContent = product.categoryLabel;

    const activeSizeObj = product.sizes.find((s) => s.size === state.selectedSize);
    const stockNote = activeSizeObj
      ? activeSizeObj.stock <= 3
        ? `Pocas unidades disponibles (${activeSizeObj.stock} en tienda)`
        : `Disponible (${activeSizeObj.stock} en tienda)`
      : "Sin existencias en este momento";

    const container = $("#detail-container");
    container.innerHTML = `
      <div>
        <div class="detail-image-wrap">
          <img src="${product.image}" alt="${product.name} — fotografía ilustrativa" />
        </div>
        <p class="photo-caption">
          Foto ilustrativa: ${product.attribution.author} (${product.attribution.license}) · Wikimedia Commons
        </p>
      </div>
      <div>
        <p class="eyebrow">${product.categoryLabel} · SKU ${product.sku}</p>
        <h1 id="detail-title" style="margin:0 0 8px;font-size:1.75rem;">${product.name}</h1>
        <p class="product-price" style="font-size:1.375rem;margin-bottom:14px;">${formatPrice(product.price)}</p>
        <p style="color:var(--ink-secondary);margin:0 0 18px;">${product.description}</p>

        <div>
          <strong style="font-size:0.875rem;">Selecciona tu talla</strong>
          <div class="size-grid" id="detail-size-grid">
            ${product.sizes
              .map(
                (s) => `
              <button type="button"
                class="size-btn ${s.size === state.selectedSize ? "is-selected" : ""}"
                data-select-size="${s.size}"
                ${s.stock === 0 ? "disabled" : ""}
                aria-pressed="${s.size === state.selectedSize}">
                ${s.size}
              </button>`
              )
              .join("")}
          </div>
          <p id="detail-stock-note" style="font-size:0.875rem;color:var(--ink-secondary);margin:0 0 18px;">${stockNote}</p>
        </div>

        <div style="display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin-bottom:16px;">
          <div class="qty-control" aria-label="Cantidad">
            <button type="button" id="detail-qty-dec" aria-label="Disminuir cantidad">−</button>
            <span id="detail-qty-val">${state.selectedQty}</span>
            <button type="button" id="detail-qty-inc" aria-label="Aumentar cantidad">+</button>
          </div>
          <button type="button" class="btn btn-primary" id="detail-add-cart" ${!state.selectedSize ? "disabled" : ""}>
            Agregar a consulta
          </button>
        </div>

        <dl class="specs-list">
          <div class="specs-row"><dt>Composición</dt><dd>${product.material}</dd></div>
          <div class="specs-row"><dt>Corte</dt><dd>${product.fit}</dd></div>
          <div class="specs-row"><dt>Color</dt><dd>${product.color}</dd></div>
          <div class="specs-row"><dt>Atención en tienda</dt><dd>WhatsApp ${DATA.store.whatsappDisplay}</dd></div>
        </dl>
      </div>
    `;

    $$("#detail-size-grid [data-select-size]").forEach((btn) => {
      btn.addEventListener("click", () => {
        state.selectedSize = btn.dataset.selectSize;
        renderDetail(product.id);
      });
    });

    $("#detail-qty-dec").addEventListener("click", () => {
      if (state.selectedQty > 1) {
        state.selectedQty -= 1;
        $("#detail-qty-val").textContent = String(state.selectedQty);
      }
    });

    $("#detail-qty-inc").addEventListener("click", () => {
      const max = activeSizeObj ? activeSizeObj.stock : 1;
      if (state.selectedQty < max) {
        state.selectedQty += 1;
        $("#detail-qty-val").textContent = String(state.selectedQty);
      }
    });

    $("#detail-add-cart").addEventListener("click", () => {
      if (!state.selectedSize) return;
      const existing = state.cart.find(
        (i) => i.productId === product.id && i.size === state.selectedSize
      );
      if (existing) {
        existing.qty += state.selectedQty;
      } else {
        state.cart.push({
          productId: product.id,
          size: state.selectedSize,
          qty: state.selectedQty
        });
      }
      updateCartBadge();
      showToast(`Agregado: ${product.name} (Talla ${state.selectedSize})`);
    });
  }

  function renderCart() {
    const container = $("#cart-items-container");
    let subtotal = 0;
    let totalUnits = 0;

    if (state.cart.length === 0) {
      container.innerHTML = `
        <div class="empty-state" style="border:none;padding:24px 8px;">
          <h3>Tu lista de consulta está vacía</h3>
          <p>Agrega prendas desde el catálogo para armar tu consulta sin compromiso.</p>
          <button type="button" class="btn btn-primary" data-nav="catalogo">Ir al catálogo</button>
        </div>
      `;
    } else {
      container.innerHTML = "";
      state.cart.forEach((item, idx) => {
        const product = state.products.find((p) => p.id === item.productId);
        if (!product) return;
        subtotal += product.price * item.qty;
        totalUnits += item.qty;

        const row = document.createElement("div");
        row.className = "cart-item";
        row.innerHTML = `
          <img src="${product.image}" alt="${product.name}" />
          <div>
            <div style="display:flex;justify-content:space-between;gap:8px;align-items:start;">
              <div>
                <strong style="display:block;">${product.name}</strong>
                <span style="font-size:0.8125rem;color:var(--ink-secondary);">SKU ${product.sku} · Talla ${item.size}</span>
              </div>
              <strong>${formatPrice(product.price * item.qty)}</strong>
            </div>
            <div style="display:flex;justify-content:space-between;align-items:center;margin-top:12px;">
              <div class="qty-control">
                <button type="button" data-cart-dec="${idx}" aria-label="Disminuir cantidad">−</button>
                <span>${item.qty}</span>
                <button type="button" data-cart-inc="${idx}" aria-label="Aumentar cantidad">+</button>
              </div>
              <button type="button" class="btn btn-ghost btn-sm" data-cart-remove="${idx}">Quitar</button>
            </div>
          </div>
        `;
        container.appendChild(row);
      });
    }

    $("#cart-total-units").textContent = String(totalUnits);
    $("#cart-subtotal").textContent = formatPrice(subtotal);

    const lines = [
      `Hola La Casa del Jean, quisiera consultar disponibilidad de:`
    ];
    state.cart.forEach((item) => {
      const p = state.products.find((pr) => pr.id === item.productId);
      if (p) {
        lines.push(`• ${item.qty}x ${p.name} (Talla ${item.size}) — ${formatPrice(p.price * item.qty)}`);
      }
    });
    if (state.cart.length === 0) {
      lines.push("(Sin prendas seleccionadas todavía)");
    } else {
      lines.push(`Total referencial: ${formatPrice(subtotal)}`);
    }
    $("#wa-preview").textContent = lines.join("\n");
    $("#wa-demo-btn").disabled = state.cart.length === 0;

    $$("[data-cart-dec]").forEach((btn) =>
      btn.addEventListener("click", () => {
        const i = Number(btn.dataset.cartDec);
        if (state.cart[i].qty > 1) state.cart[i].qty -= 1;
        else state.cart.splice(i, 1);
        updateCartBadge();
        renderCart();
      })
    );
    $$("[data-cart-inc]").forEach((btn) =>
      btn.addEventListener("click", () => {
        const i = Number(btn.dataset.cartInc);
        state.cart[i].qty += 1;
        updateCartBadge();
        renderCart();
      })
    );
    $$("[data-cart-remove]").forEach((btn) =>
      btn.addEventListener("click", () => {
        state.cart.splice(Number(btn.dataset.cartRemove), 1);
        updateCartBadge();
        renderCart();
      })
    );
  }

  function renderAdminPanel() {
    $("#admin-session-info").textContent = `Sesión simulada: ${state.admin.email} · Rol: ${state.admin.role}`;

    const totalProducts = state.products.length;
    const totalUnits = state.products.reduce((s, p) => s + totalStock(p), 0);
    const lowStockCount = state.products.filter((p) => totalStock(p) <= 10).length;

    $("#admin-kpis").innerHTML = `
      <div class="kpi-card"><div class="kpi-label">Prendas activas</div><div class="kpi-value">${totalProducts}</div></div>
      <div class="kpi-card"><div class="kpi-label">Unidades en inventario</div><div class="kpi-value">${totalUnits}</div></div>
      <div class="kpi-card"><div class="kpi-label">Alertas stock bajo</div><div class="kpi-value">${lowStockCount}</div></div>
      <div class="kpi-card"><div class="kpi-label">Permiso activo</div><div class="kpi-value" style="font-size:1.05rem;">${state.admin.role}</div></div>
    `;

    const q = state.admin.search.trim().toLowerCase();
    const filtered = state.products.filter((p) => {
      const stk = totalStock(p);
      const matchQ = !q || p.name.toLowerCase().includes(q) || p.sku.toLowerCase().includes(q);
      const matchStk =
        state.admin.stockFilter === "all" ||
        (state.admin.stockFilter === "low" && stk <= 10) ||
        (state.admin.stockFilter === "ok" && stk > 10);
      return matchQ && matchStk;
    });

    const tbody = $("#admin-table-body");
    tbody.innerHTML = "";
    filtered.forEach((p) => {
      const stk = totalStock(p);
      const statusClass = stk === 0 ? "status-out" : stk <= 10 ? "status-low" : "status-ok";
      const statusLabel = stk === 0 ? "Agotado" : stk <= 10 ? "Stock bajo" : "Disponible";
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td><code>${p.sku}</code></td>
        <td><strong>${p.name}</strong></td>
        <td>${p.categoryLabel}</td>
        <td>${formatPrice(p.price)}</td>
        <td>${stk} u.</td>
        <td><span class="status-pill ${statusClass}">${statusLabel}</span></td>
        <td>
          <button type="button" class="btn btn-secondary btn-sm" data-adjust-stock="${p.id}">Ajustar stock</button>
        </td>
      `;
      tbody.appendChild(tr);
    });

    $$("[data-adjust-stock]").forEach((btn) => {
      btn.addEventListener("click", () => openStockModal(btn.dataset.adjustStock));
    });
  }

  function openStockModal(productId) {
    const product = state.products.find((p) => p.id === productId);
    if (!product) return;
    state.admin.editingProductId = productId;
    $("#stock-modal-title").textContent = `Ajustar stock · ${product.sku}`;
    $("#stock-modal-subtitle").textContent = product.name;

    const sel = $("#modal-size-select");
    sel.innerHTML = "";
    product.sizes.forEach((s) => {
      const opt = document.createElement("option");
      opt.value = s.size;
      opt.textContent = `Talla ${s.size} (actual: ${s.stock})`;
      sel.appendChild(opt);
    });
    $("#modal-qty-input").value = String(product.sizes[0].stock);
    sel.onchange = () => {
      const found = product.sizes.find((s) => s.size === sel.value);
      if (found) $("#modal-qty-input").value = String(found.stock);
    };

    $("#stock-modal").classList.add("is-open");
    $("#modal-qty-input").focus();
  }

  // Global event wiring
  document.addEventListener("click", (e) => {
    const navEl = e.target.closest("[data-nav]");
    if (navEl) {
      e.preventDefault();
      navigate(navEl.dataset.nav);
      return;
    }
    const prodEl = e.target.closest("[data-open-product]");
    if (prodEl) {
      e.preventDefault();
      navigate("detalle", { productId: prodEl.dataset.openProduct });
    }
  });

  $("#mobile-menu-btn").addEventListener("click", () => {
    const nav = $("#mobile-nav");
    const open = nav.classList.toggle("is-open");
    $("#mobile-menu-btn").setAttribute("aria-expanded", String(open));
  });

  $("#search-input").addEventListener("input", (e) => {
    state.filters.search = e.target.value;
    renderCatalog();
  });
  $("#category-select").addEventListener("change", (e) => {
    state.filters.category = e.target.value;
    renderCatalog();
  });
  $("#size-select").addEventListener("change", (e) => {
    state.filters.size = e.target.value;
    renderCatalog();
  });
  $("#sort-select").addEventListener("change", (e) => {
    state.filters.sort = e.target.value;
    renderCatalog();
  });

  function resetFilters() {
    state.filters = { search: "", category: "todos", size: "", sort: "featured" };
    $("#search-input").value = "";
    $("#category-select").value = "todos";
    $("#size-select").value = "";
    $("#sort-select").value = "featured";
    renderCatalog();
  }
  $("#clear-filters-btn").addEventListener("click", resetFilters);
  $("#empty-reset-btn").addEventListener("click", resetFilters);

  $("#wa-demo-btn").addEventListener("click", () => {
    showToast("Prototipo Etapa A: el enlace real wa.me a +507 6522-6428 se integra en Etapa B.");
  });

  $("#admin-login-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const email = $("#admin-email").value.trim();
    const pass = $("#admin-password").value.trim();
    const err = $("#login-error");
    if (!email || !pass) {
      err.textContent = "Completa correo y contraseña para la simulación.";
      err.hidden = false;
      return;
    }
    err.hidden = true;
    state.admin.loggedIn = true;
    state.admin.email = email;
    state.admin.role = $("#admin-role").value;
    showToast(`Acceso demo concedido (${state.admin.role})`);
    navigate("admin-panel");
  });

  $("#admin-logout-btn").addEventListener("click", () => {
    state.admin.loggedIn = false;
    showToast("Sesión demo cerrada");
    navigate("admin-login");
  });

  $("#admin-search").addEventListener("input", (e) => {
    state.admin.search = e.target.value;
    renderAdminPanel();
  });
  $("#admin-stock-filter").addEventListener("change", (e) => {
    state.admin.stockFilter = e.target.value;
    renderAdminPanel();
  });

  $("#close-stock-modal").addEventListener("click", () => {
    $("#stock-modal").classList.remove("is-open");
  });

  $("#stock-modal-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const product = state.products.find((p) => p.id === state.admin.editingProductId);
    if (!product) return;
    const size = $("#modal-size-select").value;
    const qty = Math.max(0, parseInt($("#modal-qty-input").value, 10) || 0);
    const szObj = product.sizes.find((s) => s.size === size);
    if (szObj) szObj.stock = qty;
    $("#stock-modal").classList.remove("is-open");
    renderAdminPanel();
    showToast(`Stock actualizado: ${product.sku} talla ${size} → ${qty} u.`);
  });

  $("#open-new-product-btn").addEventListener("click", () => {
    $("#new-product-modal").classList.add("is-open");
    $("#np-sku").focus();
  });
  $("#close-new-product-modal").addEventListener("click", () => {
    $("#new-product-modal").classList.remove("is-open");
  });
  $("#new-product-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const sku = $("#np-sku").value.trim().toUpperCase();
    const name = $("#np-name").value.trim();
    const price = parseFloat($("#np-price").value) || 35;
    if (!sku || !name) return;
    state.products.unshift({
      id: "lcdj-demo-" + Date.now(),
      sku,
      name,
      category: "damas",
      categoryLabel: "Damas",
      price,
      badge: "Nuevo (Demo)",
      featured: false,
      description: "Prenda agregada en modo simulación desde el panel administrativo.",
      material: "98% Algodón, 2% Elastano",
      fit: "Regular Fit",
      color: "Índigo",
      image: DATA.products[0].image,
      attribution: DATA.products[0].attribution,
      sizes: [
        { size: "S", stock: 5 },
        { size: "M", stock: 8 },
        { size: "L", stock: 4 }
      ],
      status: "Publicado"
    });
    $("#new-product-modal").classList.remove("is-open");
    $("#new-product-form").reset();
    renderAdminPanel();
    showToast(`Prenda ${sku} agregada (simulación local)`);
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      $("#stock-modal").classList.remove("is-open");
      $("#new-product-modal").classList.remove("is-open");
      closeMobileNav();
    }
  });

  function syncFromHash() {
    const raw = window.location.hash.replace(/^#/, "");
    if (!raw) return navigate("inicio", { skipHash: true });
    if (raw.startsWith("detalle/")) {
      const id = raw.split("/")[1];
      return navigate("detalle", { productId: id, skipHash: true });
    }
    const valid = ["inicio", "catalogo", "carrito", "admin-login", "admin-panel"];
    navigate(valid.includes(raw) ? raw : "inicio", { skipHash: true });
  }

  populateFilterOptions();
  updateCartBadge();
  syncFromHash();
  window.addEventListener("hashchange", syncFromHash);
})();
