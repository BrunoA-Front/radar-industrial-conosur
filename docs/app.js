(() => {
  "use strict";

  const SECTORS = {
    mineria: { label: "Minería", color: "--mineria" },
    energia: { label: "Energía", color: "--energia" },
    oilgas: { label: "Oil & Gas", color: "--oilgas" },
  };
  const SIGNALS = {
    rigi: "RIGI",
    obra: "Obra o planta nueva",
    expansion: "Expansión",
    inversion: "Inversión anunciada",
  };
  const PERIODS = [
    { days: 7, label: "7 días" },
    { days: 30, label: "30 días" },
    { days: 90, label: "90 días" },
    { days: 365, label: "1 año" },
    { days: 0, label: "Todo" },
  ];
  const LEVELS = [
    { id: "country", label: "Países" },
    { id: "prov", label: "Provincias" },
    { id: "city", label: "Ciudades y polos" },
  ];
  const COUNTRIES = { AR: "Argentina", CL: "Chile", BO: "Bolivia", PY: "Paraguay", UY: "Uruguay", BR: "Brasil" };
  const HEAT_GRADIENT = { 0.15: "#FFE7A0", 0.4: "#F2B705", 0.65: "#E8830C", 1: "#C2341B" };

  const state = {
    items: [],
    updated: null,
    sectors: new Set(Object.keys(SECTORS)),
    signals: new Set(Object.keys(SIGNALS)),
    period: 90,
    zone: null,      // { level, key, label }
    company: null,
    zoneLevel: "prov",
    tab: "zonas",
  };

  const $ = (id) => document.getElementById(id);
  const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const fmtDate = (iso) => new Date(iso).toLocaleDateString("es-AR", { day: "2-digit", month: "2-digit", year: "numeric" });
  const fmtNum = (n) => n.toLocaleString("es-AR");

  // --- Claves de zona -------------------------------------------------------

  function zoneKey(item, level) {
    if (level === "country") return item.country;
    if (level === "prov") return item.admin1 ? `${item.country}|${item.admin1}` : null;
    return item.city ? `${item.country}|${item.admin1}|${item.city}` : null;
  }
  function zoneLabel(item, level) {
    if (level === "country") return COUNTRIES[item.country] || item.country;
    if (level === "prov") return item.admin1;
    return item.city;
  }
  function placeText(item) {
    const parts = [item.city, item.admin1, COUNTRIES[item.country]].filter(Boolean);
    return [...new Set(parts)].join(", ");
  }

  // --- Filtros ----------------------------------------------------------------

  function baseFilter(item, { ignoreZone = false, ignoreCompany = false } = {}) {
    if (!item.sectors.some((s) => state.sectors.has(s))) return false;
    if (!item.signals.some((s) => state.signals.has(s))) return false;
    if (state.period) {
      const cutoff = Date.now() - state.period * 86400000;
      if (Date.parse(item.date) < cutoff) return false;
    }
    if (!ignoreZone && state.zone && zoneKey(item, state.zone.level) !== state.zone.key) return false;
    if (!ignoreCompany && state.company && !item.companies.includes(state.company)) return false;
    return true;
  }

  // --- Mapa -------------------------------------------------------------------

  let map, heat, markers, tiles;

  function isDark() {
    return css("color-scheme") === "dark";
  }

  function initMap() {
    map = L.map("map", { zoomControl: true, minZoom: 3, worldCopyJump: false, attributionControl: true });
    map.fitBounds([[-55.5, -76], [4, -34]]);
    setTiles();
    window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => { setTiles(); renderMap(); });
    heat = L.heatLayer([], { radius: 30, blur: 24, maxZoom: 9, max: 1, minOpacity: 0.35, gradient: HEAT_GRADIENT }).addTo(map);
    markers = L.layerGroup().addTo(map);
  }

  function setTiles() {
    if (tiles) tiles.remove();
    const style = isDark() ? "dark_all" : "light_all";
    tiles = L.tileLayer(`https://{s}.basemaps.cartocdn.com/${style}/{z}/{x}/{y}{r}.png`, {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>',
      subdomains: "abcd",
      maxZoom: 12,
    }).addTo(map);
    tiles.bringToBack();
  }

  function renderMap() {
    const pts = new Map();
    for (const it of state.items) {
      if (it.level === "country" || !baseFilter(it, { ignoreZone: true })) continue;
      const k = `${it.lat},${it.lon}`;
      if (!pts.has(k)) pts.set(k, { lat: it.lat, lon: it.lon, n: 0, item: it });
      pts.get(k).n += 1;
    }
    const list = [...pts.values()];
    const max = Math.max(1, ...list.map((p) => p.n));
    // raíz cuadrada: un polo con 40 notas no debe tapar a todos los de 2-3
    heat.setLatLngs(list.map((p) => [p.lat, p.lon, 0.25 + 0.75 * Math.sqrt(p.n / max)]));

    markers.clearLayers();
    const ink = css("--ink");
    const surface = css("--surface");
    for (const p of list) {
      const level = p.item.level === "city" ? "city" : "prov";
      const key = zoneKey(p.item, level);
      const selected = state.zone && state.zone.key === key;
      const m = L.circleMarker([p.lat, p.lon], {
        radius: 3 + Math.sqrt(p.n) * 2.2,
        color: selected ? css("--signal") : ink,
        weight: selected ? 3 : 1.5,
        fillColor: surface,
        fillOpacity: 0.85,
      });
      m.bindTooltip(`${esc(placeText(p.item))}: ${p.n} ${p.n === 1 ? "noticia" : "noticias"}`, { className: "zone-label", direction: "top", offset: [0, -6] });
      m.on("click", () => selectZone(level, key, zoneLabel(p.item, level)));
      m.on("keypress", (e) => { if (e.originalEvent.key === "Enter") selectZone(level, key, zoneLabel(p.item, level)); });
      markers.addLayer(m);
    }
  }

  function fitToZone() {
    if (!state.zone) return;
    const pts = state.items
      .filter((it) => zoneKey(it, state.zone.level) === state.zone.key && it.level !== "country")
      .map((it) => [it.lat, it.lon]);
    if (!pts.length) return;
    const maxZoom = state.zone.level === "city" ? 8 : state.zone.level === "prov" ? 6 : 5;
    map.flyToBounds(L.latLngBounds(pts).pad(0.4), { maxZoom, duration: matchMedia("(prefers-reduced-motion: reduce)").matches ? 0 : 0.8 });
  }

  // --- Controles ---------------------------------------------------------------

  function chip({ label, pressed, color, onClick }) {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "chip";
    b.setAttribute("aria-pressed", String(pressed));
    if (color) b.style.setProperty("--c", `var(${color})`);
    b.innerHTML = (color ? '<span class="dot"></span>' : "") + esc(label);
    b.addEventListener("click", onClick);
    return b;
  }

  function toggleIn(set, key) {
    // Si estaban todos activos, el primer clic deja solo el elegido
    const all = set.size === (set === state.sectors ? Object.keys(SECTORS).length : Object.keys(SIGNALS).length);
    if (all) { set.clear(); set.add(key); }
    else if (set.has(key)) { set.delete(key); }
    else { set.add(key); }
    if (set.size === 0) Object.keys(set === state.sectors ? SECTORS : SIGNALS).forEach((k) => set.add(k));
  }

  function renderFilters() {
    const fs = $("f-sector");
    fs.replaceChildren(...Object.entries(SECTORS).map(([k, v]) =>
      chip({ label: v.label, color: v.color, pressed: state.sectors.has(k) && state.sectors.size < 3, onClick: () => { toggleIn(state.sectors, k); update(); } })));

    const fsig = $("f-signal");
    fsig.replaceChildren(...Object.entries(SIGNALS).map(([k, v]) =>
      chip({ label: v, pressed: state.signals.has(k) && state.signals.size < 4, onClick: () => { toggleIn(state.signals, k); update(); } })));

    const fp = $("f-period");
    fp.replaceChildren(...PERIODS.map((p) => {
      const b = document.createElement("button");
      b.type = "button";
      b.textContent = p.label;
      b.setAttribute("aria-pressed", String(state.period === p.days));
      b.addEventListener("click", () => { state.period = p.days; update(); });
      return b;
    }));

    const zl = $("zone-level");
    zl.replaceChildren(...LEVELS.map((l) => {
      const b = document.createElement("button");
      b.type = "button";
      b.textContent = l.label;
      b.setAttribute("aria-pressed", String(state.zoneLevel === l.id));
      b.addEventListener("click", () => { state.zoneLevel = l.id; renderZones(); renderFilters(); });
      return b;
    }));

    const act = $("active-filters");
    const chips = [];
    if (state.zone) chips.push(chip({ label: `Zona: ${state.zone.label}`, pressed: false, onClick: () => { state.zone = null; update(); } }));
    if (state.company) chips.push(chip({ label: `Empresa: ${state.company}`, pressed: false, onClick: () => { state.company = null; update(); } }));
    chips.forEach((c) => c.setAttribute("aria-label", `${c.textContent}. Quitar filtro`));
    act.replaceChildren(...chips);
  }

  function selectZone(level, key, label) {
    if (state.zone && state.zone.key === key) {
      state.zone = null;
    } else {
      state.zone = { level, key, label };
      setTab("noticias");
    }
    update();
    fitToZone();
  }

  function selectCompany(name) {
    state.company = state.company === name ? null : name;
    if (state.company) setTab("noticias");
    update();
  }

  // --- Rankings -------------------------------------------------------------

  function sectorBar(counts, total) {
    return Object.keys(SECTORS)
      .filter((s) => counts[s])
      .map((s) => `<i style="width:${(100 * counts[s] / total).toFixed(1)}%;background:var(${SECTORS[s].color})" title="${SECTORS[s].label}: ${counts[s]}"></i>`)
      .join("");
  }

  function emptyNote(el, text) {
    el.innerHTML = `<li class="note">${esc(text)}</li>`;
  }

  function renderZones() {
    const level = state.zoneLevel;
    const groups = new Map();
    for (const it of state.items) {
      if (!baseFilter(it, { ignoreZone: true })) continue;
      const key = zoneKey(it, level);
      if (!key) continue;
      if (!groups.has(key)) groups.set(key, { key, label: zoneLabel(it, level), country: it.country, admin1: it.admin1, n: 0, sectors: {}, companies: {} });
      const g = groups.get(key);
      g.n += 1;
      it.sectors.forEach((s) => { g.sectors[s] = (g.sectors[s] || 0) + 1; });
      it.companies.forEach((c) => { g.companies[c] = (g.companies[c] || 0) + 1; });
    }
    const rows = [...groups.values()].sort((a, b) => b.n - a.n).slice(0, 40);
    const ol = $("rank-zonas");
    if (!rows.length) return emptyNote(ol, "No hay zonas con noticias para estos filtros. Probá con un período más largo.");
    ol.innerHTML = rows.map((g) => {
      const top = Object.entries(g.companies).sort((a, b) => b[1] - a[1]).slice(0, 3).map((e) => e[0]);
      const where = level === "country" ? "" : level === "prov" ? COUNTRIES[g.country] : `${g.admin1}, ${COUNTRIES[g.country]}`;
      const sub = [where, top.length ? top.join(", ") : ""].filter(Boolean).join(". ");
      const totalS = Object.values(g.sectors).reduce((a, b) => a + b, 0);
      const pressed = state.zone && state.zone.key === g.key;
      return `<li><button type="button" data-level="${level}" data-key="${esc(g.key)}" data-label="${esc(g.label)}" aria-pressed="${pressed}">
        <span class="name">${esc(g.label)}</span><span class="n">${fmtNum(g.n)}</span>
        <span class="sub">${esc(sub)}</span>
        <span class="bar">${sectorBar(g.sectors, totalS)}</span></button></li>`;
    }).join("");
    ol.querySelectorAll("button").forEach((b) => b.addEventListener("click", () => selectZone(b.dataset.level, b.dataset.key, b.dataset.label)));
  }

  function renderCompanies() {
    const groups = new Map();
    for (const it of state.items) {
      if (!baseFilter(it, { ignoreCompany: true })) continue;
      for (const c of it.companies) {
        if (!groups.has(c)) groups.set(c, { name: c, n: 0, sectors: {}, places: {}, rigi: 0 });
        const g = groups.get(c);
        g.n += 1;
        if (it.signals.includes("rigi")) g.rigi += 1;
        it.sectors.forEach((s) => { g.sectors[s] = (g.sectors[s] || 0) + 1; });
        const p = it.admin1 || COUNTRIES[it.country];
        g.places[p] = (g.places[p] || 0) + 1;
      }
    }
    const rows = [...groups.values()].sort((a, b) => b.n - a.n).slice(0, 50);
    const ol = $("rank-empresas");
    if (!rows.length) return emptyNote(ol, "No se identificaron empresas para estos filtros.");
    ol.innerHTML = rows.map((g) => {
      const places = Object.entries(g.places).sort((a, b) => b[1] - a[1]).slice(0, 3).map((e) => e[0]).join(", ");
      const sub = (g.rigi ? `${g.rigi} con RIGI. ` : "") + places;
      const totalS = Object.values(g.sectors).reduce((a, b) => a + b, 0);
      return `<li><button type="button" data-name="${esc(g.name)}" aria-pressed="${state.company === g.name}">
        <span class="name">${esc(g.name)}</span><span class="n">${fmtNum(g.n)}</span>
        <span class="sub">${esc(sub)}</span>
        <span class="bar">${sectorBar(g.sectors, totalS)}</span></button></li>`;
    }).join("");
    ol.querySelectorAll("button").forEach((b) => b.addEventListener("click", () => selectCompany(b.dataset.name)));
  }

  function renderNews() {
    const list = state.items.filter((it) => baseFilter(it)).slice(0, 300);
    const total = state.items.filter((it) => baseFilter(it)).length;
    $("news-count").textContent = total ? `(${fmtNum(total)})` : "";
    const ul = $("news-list");
    if (!list.length) return emptyNote(ul, "No hay noticias con estos filtros. Probá con un período más largo o quitá el filtro de zona.");
    ul.innerHTML = list.map((it) => {
      const sectors = it.sectors.map((s) => `<span class="tag sector" style="--c:var(${SECTORS[s].color})">${SECTORS[s].label}</span>`).join("");
      const signals = it.signals.map((s) => `<span class="tag ${s === "rigi" ? "rigi" : ""}">${SIGNALS[s]}</span>`).join("");
      const companies = it.companies.map((c) => `<button type="button" class="tag" data-company="${esc(c)}">${esc(c)}</button>`).join("");
      return `<li>
        <div class="meta"><span>${fmtDate(it.date)}</span><span>${esc(it.source)}</span><span>${esc(placeText(it))}</span></div>
        <a class="title" href="${esc(it.url)}" target="_blank" rel="noopener">${esc(it.title)}</a>
        <div class="tags">${sectors}${signals}${companies}</div>
      </li>`;
    }).join("") + (total > list.length ? `<li class="note">Se muestran las ${list.length} más recientes de ${fmtNum(total)}. Usá los filtros para acotar.</li>` : "");
    ul.querySelectorAll("button[data-company]").forEach((b) => b.addEventListener("click", () => selectCompany(b.dataset.company)));
  }

  function renderStatus() {
    const n = state.items.filter((it) => baseFilter(it)).length;
    const upd = state.updated ? `Actualizado el ${fmtDate(state.updated)}` : "";
    $("status").innerHTML = `<strong>${fmtNum(n)}</strong>${n === 1 ? "noticia" : "noticias"} con los filtros actuales<br>${esc(upd)}`;
  }

  // --- Pestañas ---------------------------------------------------------------

  function setTab(name) {
    state.tab = name;
    for (const t of ["zonas", "empresas", "noticias"]) {
      $(`tab-${t}`).setAttribute("aria-selected", String(t === name));
      $(`pane-${t}`).hidden = t !== name;
    }
  }

  function initTabs() {
    const order = ["zonas", "empresas", "noticias"];
    order.forEach((t) => $(`tab-${t}`).addEventListener("click", () => setTab(t)));
    document.querySelector(".tabs").addEventListener("keydown", (e) => {
      if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
      const i = order.indexOf(state.tab) + (e.key === "ArrowRight" ? 1 : -1);
      const next = order[(i + order.length) % order.length];
      setTab(next);
      $(`tab-${next}`).focus();
    });
  }

  // --- Ciclo -----------------------------------------------------------------

  function update() {
    renderFilters();
    renderMap();
    renderZones();
    renderCompanies();
    renderNews();
    renderStatus();
  }

  function showEmpty(title, text) {
    const el = $("empty");
    el.innerHTML = `<div><h2>${esc(title)}</h2><p>${esc(text)}</p></div>`;
    el.hidden = false;
  }

  async function start() {
    initMap();
    initTabs();
    try {
      const res = await fetch("data/news.json", { cache: "no-cache" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      state.items = data.items || [];
      state.updated = data.updated;
    } catch (err) {
      showEmpty("No se pudieron cargar las noticias", "El archivo data/news.json no respondió. Recargá la página en unos minutos.");
      console.error(err);
    }
    if (!state.items.length && $("empty").hidden) {
      showEmpty("Todavía no hay noticias cargadas", "La recolección automática corre todos los días. Para la primera carga, en el repositorio de GitHub abrí Actions, elegí “Actualizar noticias” y tocá Run workflow.");
    }
    update();
  }

  start();
})();
