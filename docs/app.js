(() => {
  "use strict";

  // ---------------------------------------------------------------------------
  // Configuración
  // ---------------------------------------------------------------------------

  const SECTORS = {
    oilgas: { label: "Oil & Gas", color: "#FF7A1A", emoji: "🛢️" },
    mineria: { label: "Minería", color: "#FFC21A", emoji: "⛏️" },
    energia: { label: "Energía", color: "#2EE6A6", emoji: "⚡" },
  };
  // Lectura rápida: rubro + si tiene RIGI (💰✅) o es solo noticia (📰)
  const RIGI_EMOJI = "💰✅";
  const NEWS_EMOJI = "📰";
  const sectorEmojis = (sectors) => Object.keys(SECTORS)
    .filter((s) => (Array.isArray(sectors) ? sectors.includes(s) : sectors[s]))
    .map((s) => SECTORS[s].emoji).join(" ");
  const statusEmoji = (it) => (it.signals.includes("rigi") ? RIGI_EMOJI : NEWS_EMOJI);
  const SIGNALS = { rigi: "RIGI", obra: "Obra o planta nueva", expansion: "Expansión", inversion: "Inversión anunciada" };
  const PERIODS = [
    { days: 7, label: "Semana" },
    { days: 30, label: "Mes" },
    { days: 90, label: "3 meses" },
    { days: 0, label: "Todo" },
  ];
  const COUNTRIES = { AR: "Argentina", CL: "Chile", BO: "Bolivia", PY: "Paraguay", UY: "Uruguay", BR: "Brasil" };
  const COUNTRY_TONE = { AR: "#1E5AA8", CL: "#174C93", BO: "#2566B6", PY: "#1A54A0", UY: "#2A6EC0", BR: "#1B529C" };
  const PROV_TONES = ["#1E5AA8", "#2363B3", "#1A519B", "#2A6CBE"];

  // Niveles de detalle según el zoom
  const PROV_Z = 4.3;
  const CITY_Z = 6.2;
  const LEVELS = [
    { id: "country", label: "Países", zoom: 3.1, hint: "Acercá el mapa para ver provincias." },
    { id: "prov", label: "Provincias", zoom: 5.1, hint: "Acercá más para ver ciudades y polos." },
    { id: "city", label: "Ciudades", zoom: 7.0, hint: "Pasá el mouse por un punto o hacé clic para ver sus noticias." },
  ];
  const DOT_KM = { country: 120, prov: 40, city: 9 };

  // Espesor del bloque y altura de los puntos (en metros) para cada zoom
  const LAND_STOPS = [[2, 300000], [4, 110000], [6, 30000], [8, 7000], [11, 1200]];
  const DOT_STOPS = [[2, 750000], [4, 270000], [6, 75000], [8, 17000], [11, 3000]];
  const LAND = ["interpolate", ["exponential", 1.3], ["zoom"], ...LAND_STOPS.flat()];
  const DOT_HEIGHT = ["interpolate", ["exponential", 1.3], ["zoom"],
    ...LAND_STOPS.flatMap(([z, land], i) => [z, ["+", land, ["*", ["get", "h"], DOT_STOPS[i][1]]]])];

  const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const isMobile = () => matchMedia("(max-width: 860px)").matches;

  // ---------------------------------------------------------------------------
  // Estado y utilidades
  // ---------------------------------------------------------------------------

  const state = {
    items: [],
    places: { countries: {}, provinces: {} },
    updated: null,
    sectors: new Set(Object.keys(SECTORS)),
    period: 90,
    company: null,
    level: "country",
    view: { type: "ranking", tab: "novedades" },   // o { type: "zone", level, key } / { type: "company", name }
    contacts: {},
    groups: { country: [], prov: [], city: [] },
    hasProvinces: false,
  };

  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const fmtDate = (iso) => new Date(iso).toLocaleDateString("es-AR", { day: "2-digit", month: "2-digit", year: "numeric" });
  const fmtNum = (n) => n.toLocaleString("es-AR");
  const plural = (n, one, many) => `${fmtNum(n)} ${n === 1 ? one : many}`;
  const daysAgo = (iso) => (Date.now() - Date.parse(iso)) / 86400000;
  const NEW_DAYS = 2;  // "NUEVO" = últimas 48 horas
  const isNew = (it) => daysAgo(it.date) <= NEW_DAYS;
  const contractorsOf = (it) => it.contractors || [];

  async function getJSON(url) {
    const res = await fetch(url, { cache: "no-cache" });
    if (!res.ok) throw new Error(`${url}: HTTP ${res.status}`);
    return res.json();
  }

  function passes(it) {
    if (!it.sectors.some((s) => state.sectors.has(s))) return false;
    if (state.period && daysAgo(it.date) > state.period) return false;
    if (state.company && !it.companies.includes(state.company) && !contractorsOf(it).includes(state.company)) return false;
    return true;
  }

  // ---------------------------------------------------------------------------
  // Agrupación por nivel
  // ---------------------------------------------------------------------------

  function newGroup(key, level, label, where, lat, lon) {
    return { key, level, label, where, lat, lon, items: [], sectors: {}, companies: {}, contractors: {}, rigi: 0, fresh: 0 };
  }
  function addTo(g, it) {
    g.items.push(it);
    it.sectors.forEach((s) => { g.sectors[s] = (g.sectors[s] || 0) + 1; });
    it.companies.forEach((c) => { g.companies[c] = (g.companies[c] || 0) + 1; });
    contractorsOf(it).forEach((c) => { g.contractors[c] = (g.contractors[c] || 0) + 1; });
    if (it.signals.includes("rigi")) g.rigi += 1;
    if (isNew(it)) g.fresh += 1;
  }

  function buildGroups() {
    const country = new Map(), prov = new Map(), city = new Map();
    const C = state.places.countries, P = state.places.provinces;
    for (const it of state.items) {
      if (!passes(it)) continue;
      const cn = COUNTRIES[it.country] || it.country;
      // país
      if (!country.has(it.country)) {
        const c = C[it.country] || { lat: it.lat, lon: it.lon };
        country.set(it.country, newGroup(it.country, "country", cn, "", c.lat, c.lon));
      }
      addTo(country.get(it.country), it);

      // provincia (las notas que solo nombran el país quedan en el centro del país)
      const pk = it.admin1 ? `${it.country}|${it.admin1}` : `${it.country}|*`;
      if (!prov.has(pk)) {
        const p = it.admin1 ? (P[pk] || [it.lat, it.lon]) : [C[it.country]?.lat ?? it.lat, C[it.country]?.lon ?? it.lon];
        prov.set(pk, newGroup(pk, "prov", it.admin1 || `${cn} (sin provincia precisa)`, it.admin1 ? cn : "", p[0], p[1]));
      }
      addTo(prov.get(pk), it);

      // ciudad (las que no nombran ciudad quedan en el centro de su provincia)
      const ck = it.city ? `${it.country}|${it.admin1}|${it.city}` : pk;
      if (!city.has(ck)) {
        const base = prov.get(pk);
        city.set(ck, it.city
          ? newGroup(ck, "city", it.city, `${it.admin1}, ${cn}`, it.lat, it.lon)
          : newGroup(ck, "city", it.admin1 ? `${it.admin1} (sin ciudad precisa)` : base.label, it.admin1 ? cn : "", base.lat, base.lon));
      }
      addTo(city.get(ck), it);
    }
    const sort = (m) => [...m.values()].sort((a, b) => b.items.length - a.items.length);
    state.groups = { country: sort(country), prov: sort(prov), city: sort(city) };
  }

  function topSector(g) {
    return Object.keys(SECTORS).filter((s) => state.sectors.has(s)).sort((a, b) => (g.sectors[b] || 0) - (g.sectors[a] || 0))[0];
  }
  function topCompanies(g, n = 4) {
    return Object.entries(g.companies).sort((a, b) => b[1] - a[1]).slice(0, n).map((e) => e[0]);
  }

  // ---------------------------------------------------------------------------
  // Pantalla de inicio
  // ---------------------------------------------------------------------------

  const ready = loadData();

  function placeBlips(points) {
    // proyecta lat/lon de Sudamérica dentro del círculo del radar
    const box = $("blips");
    box.innerHTML = "";
    points.slice(0, 60).forEach((p, i) => {
      const x = ((p.lon + 82) / 50) * 100;
      const y = ((14 - p.lat) / 72) * 100;
      if (Math.hypot(x - 50, y - 50) > 46) return;
      const b = document.createElement("span");
      b.className = "blip";
      b.style.left = `${x}%`;
      b.style.top = `${y}%`;
      b.style.setProperty("--c", SECTORS[topSector(p)]?.color || "#3FE0C5");
      // aparece cuando el barrido pasa por su ángulo
      const angle = (Math.atan2(x - 50, -(y - 50)) * 180 / Math.PI + 360) % 360;
      b.style.animationDelay = `${(angle / 360) * 2.2 + Math.floor(i / 20) * 2.2}s`;
      box.appendChild(b);
    });
  }

  function countUp(el, to, ms) {
    if (reducedMotion || to === 0) { el.textContent = fmtNum(to); return Promise.resolve(); }
    return new Promise((done) => {
      const t0 = performance.now();
      const step = (t) => {
        const k = Math.min(1, (t - t0) / ms);
        el.textContent = fmtNum(Math.round(to * (1 - Math.pow(1 - k, 3))));
        k < 1 ? requestAnimationFrame(step) : done();
      };
      requestAnimationFrame(step);
    });
  }
  const wait = (ms) => new Promise((r) => setTimeout(r, reducedMotion ? Math.min(ms, 120) : ms));

  async function logLine(text, value, ms = 650) {
    const li = document.createElement("li");
    li.innerHTML = `<span>${esc(text)}</span><b>0</b>`;
    $("log").appendChild(li);
    await countUp(li.querySelector("b"), value, ms);
    li.classList.add("done");
    await wait(220);
  }

  let started = false;
  async function startRadar() {
    if (started) return;
    started = true;
    $("start").hidden = true;
    $("scope").classList.add("scanning");
    const skip = document.createElement("button");
    skip.type = "button";
    skip.className = "skip";
    skip.textContent = "Saltar animación";
    skip.addEventListener("click", reveal);
    $("log").after(skip);

    await ready;
    const all = state.items;
    await logLine("Noticias de hoy", all.filter((i) => daysAgo(i.date) <= 1).length);
    await logLine("Últimos 7 días", all.filter((i) => daysAgo(i.date) <= 7).length);
    await logLine("Últimos 30 días", all.filter((i) => daysAgo(i.date) <= 30).length);
    await logLine("Total analizado", all.length, 800);
    const provs = new Set(all.filter((i) => i.admin1).map((i) => `${i.country}|${i.admin1}`)).size;
    await logLine("Provincias con obras", provs);
    await logLine("Empresas identificadas", new Set(all.flatMap((i) => i.companies)).size);
    const fin = document.createElement("li");
    fin.className = "final done";
    fin.innerHTML = `<span>${all.length ? "Listo. Armando el mapa…" : "Todavía no hay noticias cargadas."}</span>`;
    $("log").appendChild(fin);
    await wait(900);
    reveal();
  }

  let revealed = false;
  function flyHome() {
    map.resize();
    map.flyTo({ center: [-60, -27], zoom: isMobile() ? 2.6 : 3.1, pitch: 52, bearing: -12, duration: reducedMotion ? 0 : 3200, essential: true });
  }
  function reveal() {
    if (revealed) return;
    revealed = true;
    $("intro").classList.add("gone");
    $("app").setAttribute("aria-hidden", "false");
    if (map && map.loaded()) flyHome();
    if (!state.items.length) {
      showNotice("Todavía no hay noticias", "La recolección automática corre todos los días. Volvé a entrar más tarde.");
    }
  }

  // ---------------------------------------------------------------------------
  // Mapa
  // ---------------------------------------------------------------------------

  let map = null;
  let hovered = null;
  const countryMarkers = [];

  function circle(lon, lat, km, steps = 28) {
    const coords = [];
    const dLat = km / 110.57;
    const dLon = km / (111.32 * Math.cos((lat * Math.PI) / 180));
    for (let i = 0; i <= steps; i++) {
      const a = (i / steps) * 2 * Math.PI;
      coords.push([lon + dLon * Math.cos(a), lat + dLat * Math.sin(a)]);
    }
    return [coords];
  }

  function dotsGeoJSON(level) {
    const groups = state.groups[level];
    const max = Math.max(1, ...groups.map((g) => g.items.length));
    return {
      type: "FeatureCollection",
      features: groups.map((g, id) => {
        const k = Math.sqrt(g.items.length / max);
        return {
          type: "Feature",
          id,
          properties: { h: 0.12 + 0.88 * k, color: SECTORS[topSector(g)].color },
          geometry: { type: "Polygon", coordinates: circle(g.lon, g.lat, DOT_KM[level] * (0.75 + 0.45 * k)) },
        };
      }),
    };
  }

  function initMap(paises, provincias) {
    try {
      map = new maplibregl.Map({
        container: "map",
        style: {
          version: 8,
          sources: {},
          layers: [{ id: "fondo", type: "background", paint: { "background-color": "#E9EFF6" } }],
        },
        center: [-62, -22],
        zoom: 1.9,
        pitch: 20,
        bearing: 0,
        minZoom: 1.6,
        maxZoom: 11,
        maxPitch: 70,
        maxBounds: [[-140, -70], [-10, 40]],
        attributionControl: false,
      });
    } catch (err) {
      showNotice("Tu navegador no puede mostrar el mapa 3D", "Hace falta WebGL. Probá con Chrome, Edge o Firefox actualizados.");
      console.error(err);
      return;
    }
    map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "bottom-right");
    map.addControl(new maplibregl.AttributionControl({ compact: true, customAttribution: "Mapa base: Natural Earth" }), "bottom-right");

    map.on("load", () => {
      map.setLight({ anchor: "viewport", color: "#ffffff", intensity: 0.5, position: [1.4, 200, 35] });

      if (paises) {
        map.addSource("paises", { type: "geojson", data: paises });
        map.addLayer({
          id: "paises-otros", type: "fill-extrusion", source: "paises",
          filter: ["!", ["get", "focus"]],
          paint: { "fill-extrusion-color": "#9DB2CB", "fill-extrusion-height": LAND, "fill-extrusion-base": 0, "fill-extrusion-vertical-gradient": true },
        });
        map.addLayer({
          id: "paises-foco", type: "fill-extrusion", source: "paises",
          filter: ["get", "focus"],
          ...(provincias ? { maxzoom: PROV_Z } : {}),
          paint: {
            "fill-extrusion-color": ["match", ["get", "iso"], ...Object.entries(COUNTRY_TONE).flat(), "#1E5AA8"],
            "fill-extrusion-height": LAND, "fill-extrusion-base": 0, "fill-extrusion-vertical-gradient": true,
          },
        });
      }
      if (provincias) {
        map.addSource("provincias", { type: "geojson", data: provincias });
        map.addLayer({
          id: "provincias", type: "fill-extrusion", source: "provincias", minzoom: PROV_Z,
          paint: {
            "fill-extrusion-color": ["match", ["get", "tone"], 0, PROV_TONES[0], 1, PROV_TONES[1], 2, PROV_TONES[2], PROV_TONES[3]],
            "fill-extrusion-height": LAND, "fill-extrusion-base": 0, "fill-extrusion-vertical-gradient": true,
          },
        });
      }

      const ranges = { country: [0, PROV_Z], prov: [PROV_Z, CITY_Z], city: [CITY_Z, 24] };
      for (const level of ["country", "prov", "city"]) {
        map.addSource(`dots-${level}`, { type: "geojson", data: dotsGeoJSON(level) });
        map.addLayer({
          id: `dots-${level}`, type: "fill-extrusion", source: `dots-${level}`,
          minzoom: ranges[level][0], maxzoom: ranges[level][1],
          paint: {
            "fill-extrusion-color": ["case", ["boolean", ["feature-state", "hover"], false], "#FFFFFF", ["get", "color"]],
            "fill-extrusion-base": LAND,
            "fill-extrusion-height": DOT_HEIGHT,
            "fill-extrusion-vertical-gradient": true,
          },
        });
        map.on("mousemove", `dots-${level}`, (e) => onHover(level, e));
        map.on("mouseleave", `dots-${level}`, clearHover);
        map.on("click", `dots-${level}`, (e) => {
          clearHover();
          const g = state.groups[level][e.features[0].id];
          if (g) openZone(level, g.key, true);
        });
      }

      // nombres de los 6 países en la vista lejana
      Object.entries(COUNTRIES).forEach(([iso, name]) => {
        const c = state.places.countries[iso];
        if (!c) return;
        const el = document.createElement("div");
        el.className = "country-label";
        el.textContent = name;
        countryMarkers.push(new maplibregl.Marker({ element: el, anchor: "top", offset: [0, 14] }).setLngLat([c.lon, c.lat]).addTo(map));
      });

      map.on("zoom", onZoom);
      map.on("movestart", (e) => { if (e.originalEvent === undefined) clearHover(); });
      onZoom();
      refreshNewPins();
      if (revealed) flyHome();
    });
  }

  function refreshDots() {
    if (!map || !map.getSource("dots-country")) return;
    clearHover();
    for (const level of ["country", "prov", "city"]) map.getSource(`dots-${level}`).setData(dotsGeoJSON(level));
    refreshNewPins();
  }

  const newPins = [];
  function refreshNewPins() {
    newPins.splice(0).forEach((m) => m.remove());
    if (!map) return;
    for (const g of state.groups[state.level]) {
      if (!g.fresh) continue;
      const el = document.createElement("button");
      el.type = "button";
      el.className = "new-pin";
      el.textContent = `NUEVO${g.fresh > 1 ? " " + g.fresh : ""}`;
      el.title = `${g.label}: ${plural(g.fresh, "noticia nueva", "noticias nuevas")} en 48 h`;
      el.addEventListener("click", () => openZone(state.level, g.key, true));
      newPins.push(new maplibregl.Marker({ element: el, anchor: "bottom", offset: [0, -10] }).setLngLat([g.lon, g.lat]).addTo(map));
    }
  }

  function onZoom() {
    const z = map.getZoom();
    const level = z < PROV_Z ? "country" : z < CITY_Z ? "prov" : "city";
    countryMarkers.forEach((m) => { m.getElement().style.display = level === "country" ? "" : "none"; });
    if (level !== state.level) {
      state.level = level;
      refreshNewPins();
      renderLevels();
      if (state.view.type === "ranking") renderDrawer();
    }
  }

  // --- Tooltip -----------------------------------------------------------------

  function onHover(level, e) {
    const f = e.features[0];
    if (!f) return;
    map.getCanvas().style.cursor = "pointer";
    const src = `dots-${level}`;
    if (!hovered || hovered.src !== src || hovered.id !== f.id) {
      clearHover(false);
      hovered = { src, id: f.id };
      map.setFeatureState({ source: src, id: f.id }, { hover: true });
      const g = state.groups[level][f.id];
      if (g) $("tip").innerHTML = tipHTML(g);
    }
    if (isMobile()) return;
    const tip = $("tip");
    tip.hidden = false;
    const { x, y } = e.point;
    const w = tip.offsetWidth, h = tip.offsetHeight;
    const W = map.getContainer().clientWidth;
    tip.style.left = `${Math.min(x + 16, W - w - 12)}px`;
    tip.style.top = `${Math.max(12, y - h - 14)}px`;
  }

  function clearHover(hideTip = true) {
    if (hovered && map.getSource(hovered.src)) map.setFeatureState({ source: hovered.src, id: hovered.id }, { hover: false });
    hovered = null;
    if (hideTip !== false) {
      $("tip").hidden = true;
      if (map) map.getCanvas().style.cursor = "";
    }
  }

  function sectorRows(g) {
    return Object.keys(SECTORS).filter((s) => g.sectors[s] && state.sectors.has(s))
      .sort((a, b) => g.sectors[b] - g.sectors[a])
      .map((s) => `<div style="--c:${SECTORS[s].color}"><i></i>${SECTORS[s].emoji} ${SECTORS[s].label}<b>${g.sectors[s]}</b></div>`).join("");
  }

  function tipHTML(g) {
    const cos = topCompanies(g);
    const more = Object.keys(g.companies).length - cos.length;
    return `<h3>${sectorEmojis(g.sectors)} ${esc(g.label)}</h3>
      ${g.where ? `<div class="where">${esc(g.where)}</div>` : ""}
      <div class="sec">${sectorRows(g)}</div>
      <div class="co">${cos.length ? `Dueños: <strong>${esc(cos.join(", "))}</strong>${more > 0 ? ` y ${more} más` : ""}` : "Dueños: no identificados en las notas"}</div>
      ${Object.keys(g.contractors).length ? `<div class="co">🏗️ Segundo anillo: <strong>${esc(Object.keys(g.contractors).slice(0, 3).join(", "))}</strong></div>` : ""}
      ${g.fresh ? `<div class="co fresh">🆕 ${plural(g.fresh, "nueva en 48 h", "nuevas en 48 h")}</div>` : ""}
      <div class="status">${g.rigi ? `<span>${RIGI_EMOJI} ${plural(g.rigi, "con RIGI", "con RIGI")}</span>` : ""}${g.items.length - g.rigi ? `<span>${NEWS_EMOJI} ${plural(g.items.length - g.rigi, "solo noticia", "solo noticias")}</span>` : ""}</div>
      <div class="cta">${plural(g.items.length, "noticia", "noticias")}. Clic para ver proyectos y contactos.</div>`;
  }

  // ---------------------------------------------------------------------------
  // Controles
  // ---------------------------------------------------------------------------

  function renderFilters() {
    $("f-sector").replaceChildren(...Object.entries(SECTORS).map(([k, v]) => {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "chip";
      b.style.setProperty("--c", v.color);
      b.setAttribute("aria-pressed", String(state.sectors.has(k)));
      b.innerHTML = `<i></i>${v.emoji} ${esc(v.label)}`;
      b.addEventListener("click", () => {
        if (state.sectors.has(k) && state.sectors.size === 1) return; // siempre al menos uno
        state.sectors.has(k) ? state.sectors.delete(k) : state.sectors.add(k);
        update();
      });
      return b;
    }));
    $("f-period").replaceChildren(...PERIODS.map((p) => {
      const b = document.createElement("button");
      b.type = "button";
      b.textContent = p.label;
      b.setAttribute("aria-pressed", String(state.period === p.days));
      b.addEventListener("click", () => { state.period = p.days; update(); });
      return b;
    }));
    $("legend").innerHTML = Object.values(SECTORS).map((s) => `<li style="--c:${s.color}"><i></i>${s.emoji} ${s.label}</li>`).join("")
      + `<li class="sep">${RIGI_EMOJI} Con RIGI</li><li class="sep">${NEWS_EMOJI} Solo noticia</li>`;
  }

  function renderLevels() {
    $("levels").replaceChildren(...LEVELS.map((l) => {
      const b = document.createElement("button");
      b.type = "button";
      b.textContent = l.label;
      b.setAttribute("aria-pressed", String(state.level === l.id));
      b.addEventListener("click", () => {
        if (!map) return;
        // al bajar de nivel, centrar en la zona más activa del nivel actual
        const order = LEVELS.map((x) => x.id);
        const deeper = order.indexOf(l.id) > order.indexOf(state.level);
        const top = state.groups[state.level][0];
        const opts = { zoom: l.zoom, pitch: 52, duration: reducedMotion ? 0 : 1400 };
        if (l.id === "country") opts.center = [-60, -27];
        else if (deeper && top) opts.center = [top.lon, top.lat];
        map.easeTo(opts);
      });
      return b;
    }));
    $("level-hint").textContent = LEVELS.find((l) => l.id === state.level).hint;
  }

  function renderStatus() {
    const n = state.items.filter(passes).length;
    $("updated").textContent = `${plural(n, "noticia", "noticias")}${state.updated ? `, actualizado el ${fmtDate(state.updated)}` : ""}`;
  }

  // ---------------------------------------------------------------------------
  // Panel lateral
  // ---------------------------------------------------------------------------

  function splitBar(sectors) {
    const total = Object.values(sectors).reduce((a, b) => a + b, 0) || 1;
    return `<span class="sector-split">${Object.keys(SECTORS).filter((s) => sectors[s])
      .map((s) => `<i style="--c:${SECTORS[s].color};width:${(100 * sectors[s] / total).toFixed(1)}%"></i>`).join("")}</span>`;
  }

  function newsList(items) {
    if (!items.length) return `<p class="note">No hay noticias con estos filtros.</p>`;
    const sorted = [...items].sort((a, b) => (a.date < b.date ? 1 : -1));
    return `<ul class="news">${sorted.map((it) => `<li>
      <div class="meta"><span>${fmtDate(it.date)}</span><span>${esc(it.source)}</span><span>${esc([it.city, it.admin1, COUNTRIES[it.country]].filter(Boolean).join(", "))}</span></div>
      <a href="${esc(it.url)}" target="_blank" rel="noopener"><span class="emo">${sectorEmojis(it.sectors)} ${statusEmoji(it)}</span> ${esc(it.title)}</a>
      <div class="tags">
        ${it.sectors.map((s) => `<span class="tag s" style="--c:${SECTORS[s].color}">${SECTORS[s].emoji} ${SECTORS[s].label}</span>`).join("")}
        ${it.signals.map((s) => `<span class="tag ${s === "rigi" ? "rigi" : ""}">${s === "rigi" ? RIGI_EMOJI + " " : ""}${SIGNALS[s]}</span>`).join("")}
        ${it.companies.map((c) => `<span class="tag">${esc(c)}</span>`).join("")}
      </div></li>`).join("")}</ul>`;
  }

  // --- Proyectos y contactos ---------------------------------------------------

  const placeOf = (it) => it.city || it.admin1 || COUNTRIES[it.country] || it.country;
  const shortUrl = (u) => u.replace(/^https?:\/\//, "").replace(/\/$/, "");

  function buildProjects(items) {
    const byKey = new Map();
    for (const it of items) {
      const owner = it.companies[0] || contractorsOf(it)[0] || "";
      const key = it.project ? `p:${it.project}` : `a:${owner}|${it.sectors[0]}|${it.country}|${it.admin1 || ""}|${it.city || ""}`;
      if (!byKey.has(key)) {
        const sector = SECTORS[it.sectors[0]]?.label || "Obra";
        byKey.set(key, {
          key,
          name: it.project || (owner ? `${owner} en ${placeOf(it)}` : `${sector} en ${placeOf(it)}`),
          items: [], owners: {}, contractors: {}, sectors: {}, places: {}, rigi: 0, last: it.date, fresh: 0,
        });
      }
      const p = byKey.get(key);
      p.items.push(it);
      it.companies.forEach((c) => { p.owners[c] = (p.owners[c] || 0) + 1; });
      contractorsOf(it).forEach((c) => { p.contractors[c] = (p.contractors[c] || 0) + 1; });
      it.sectors.forEach((s) => { p.sectors[s] = (p.sectors[s] || 0) + 1; });
      const pl = [it.city, it.admin1, COUNTRIES[it.country]].filter(Boolean).join(", ");
      p.places[pl] = (p.places[pl] || 0) + 1;
      if (it.signals.includes("rigi")) p.rigi += 1;
      if (isNew(it)) p.fresh += 1;
      if (it.date > p.last) p.last = it.date;
    }
    return [...byKey.values()].sort((a, b) => (b.fresh - a.fresh) || (a.last < b.last ? 1 : -1));
  }

  const contractorRole = (name) =>
    state.items.some((it) => contractorsOf(it).includes(name)) && !state.items.some((it) => it.companies.includes(name));

  function hasContact(name) {
    const c = state.contacts[name];
    return Boolean(c && (c.portal || (c.emails && c.emails.length) || (c.telefonos && c.telefonos.length)));
  }

  function contactCard(name, role, big = false) {
    const c = state.contacts[name];
    const roleTag = role === "contratista"
      ? `<span class="role ring">🏗️ Segundo anillo</span>`
      : `<span class="role">Dueño del proyecto</span>`;
    let body;
    if (!hasContact(name)) {
      body = `<p class="none">Sin contacto todavía.${c && c.web
        ? ` Web: <a href="${esc(c.web)}" target="_blank" rel="noopener">${esc(shortUrl(c.web))}</a>`
        : " El robot lo busca en la próxima actualización."}</p>`;
    } else {
      const rows = [];
      if (c.portal) rows.push(`<li>🧾 <a href="${esc(c.portal)}" target="_blank" rel="noopener">Portal de proveedores</a></li>`);
      (c.emails || []).forEach((e) => rows.push(`<li>✉️ <a href="mailto:${esc(e.email)}">${esc(e.email)}</a>${
        e.tipo === "compras" ? ` <span class="kind buy">Compras</span>` : e.tipo === "general" ? ` <span class="kind">General</span>` : ""}</li>`));
      (c.telefonos || []).forEach((t) => rows.push(`<li>☎️ <a href="tel:${esc(t.replace(/[^\d+]/g, ""))}">${esc(t)}</a></li>`));
      if (c.web) rows.push(`<li>🌐 <a href="${esc(c.web)}" target="_blank" rel="noopener">${esc(shortUrl(c.web))}</a></li>`);
      const src = (c.fuentes || [])[0];
      const badge = c.metodo === "web oficial"
        ? `<span class="badge ok">Datos de su web oficial</span>`
        : `<span class="badge warn">Sin verificar (búsqueda automática)</span>`;
      body = `<ul class="contact">${rows.join("")}</ul>
        <p class="src">${badge}${src ? ` <a href="${esc(src)}" target="_blank" rel="noopener">Ver fuente</a>` : ""}${
          c.revisado ? `. Revisado el ${fmtDate(c.revisado + "T12:00:00Z")}` : ""}</p>`;
    }
    return `<div class="ccard${role === "contratista" ? " ring" : ""}${big ? " big" : ""}"><div class="chead"><strong>${esc(name)}</strong>${roleTag}</div>${body}</div>`;
  }

  function projectCard(p, open) {
    const owners = Object.keys(p.owners);
    const contractors = Object.keys(p.contractors);
    const place = Object.entries(p.places).sort((a, b) => b[1] - a[1])[0]?.[0] || "";
    const companyButtons = (list) => list.map((c) => `<button type="button" class="tag link" data-company="${esc(c)}">${esc(c)}</button>`).join(" ");
    const contacts = [
      ...contractors.map((c) => contactCard(c, "contratista")),
      ...owners.map((c) => contactCard(c, "dueño")),
    ].join("");
    return `<details class="proj"${open ? " open" : ""}>
      <summary>
        <span class="ptitle"><span class="emo">${sectorEmojis(p.sectors)} ${p.rigi ? RIGI_EMOJI : NEWS_EMOJI}</span> ${esc(p.name)}${p.fresh ? ` <span class="new">NUEVO</span>` : ""}</span>
        <span class="pmeta">${esc(place)}. ${plural(p.items.length, "noticia", "noticias")}, la última del ${fmtDate(p.last)}</span>
      </summary>
      <div class="pbody">
        <dl class="roles">
          <div><dt>Dueño del proyecto</dt><dd>${owners.length ? companyButtons(owners) : "No identificado en las notas"}</dd></div>
          <div class="ring"><dt>🏗️ Segundo anillo (quién ejecuta la obra)</dt><dd>${contractors.length ? companyButtons(contractors) : "Todavía no aparece en las noticias"}</dd></div>
        </dl>
        ${contacts ? `<h4>📇 Contactos</h4>${contacts}` : ""}
        <h4>📰 Noticias</h4>${newsList(p.items)}
      </div>
    </details>`;
  }

  function projectList(items) {
    if (!items.length) return `<p class="note">No hay noticias con estos filtros.</p>`;
    const projects = buildProjects(items);
    return `<p class="note small">${plural(projects.length, "proyecto", "proyectos")}. Abrí uno para ver quién lo ejecuta, los contactos y las noticias.</p>`
      + projects.slice(0, 80).map((p, i) => projectCard(p, i === 0)).join("");
  }

  function newsFeed() {
    const base = state.items.filter((it) => it.sectors.some((s) => state.sectors.has(s))
      && (!state.company || it.companies.includes(state.company) || contractorsOf(it).includes(state.company)));
    let items = base.filter(isNew);
    let note = "";
    if (!items.length) {
      items = base.filter((it) => daysAgo(it.date) <= 7);
      note = `<p class="note">No hubo novedades en las últimas 48 horas. Te muestro las de la última semana.</p>`;
    }
    if (!items.length) return `<p class="note">No hay novedades en la última semana.</p>`;
    return note + projectList(items);
  }


  function periodText() {
    return state.period ? `últimos ${state.period} días` : "todo el historial";
  }

  function renderDrawer() {
    const head = $("drawer-head"), body = $("drawer-body");
    const v = state.view;

    if (v.type === "zone") {
      const g = state.groups[v.level].find((x) => x.key === v.key);
      head.innerHTML = `<button type="button" class="back" id="back">Volver al ranking</button>
        <h2>${esc(g ? g.label : "Sin noticias")}</h2>
        <p>${g ? `${esc(g.where ? g.where + ". " : "")}${plural(g.items.length, "noticia", "noticias")}, ${periodText()}` : "No quedan noticias con estos filtros."}</p>
        ${g ? splitBar(g.sectors) : ""}`;
      body.innerHTML = g ? projectList(g.items) : "";
    } else if (v.type === "company") {
      const items = state.items.filter((it) => passes(it));
      const sectors = {};
      items.forEach((it) => it.sectors.forEach((s) => { sectors[s] = (sectors[s] || 0) + 1; }));
      head.innerHTML = `<button type="button" class="back" id="back">Volver al ranking</button>
        <h2>${esc(v.name)}</h2>
        <p>${contractorRole(v.name) ? "🏗️ Contratista (segundo anillo). " : ""}${plural(items.length, "noticia", "noticias")}, ${periodText()}. El mapa muestra solo sus proyectos.</p>
        ${splitBar(sectors)}`;
      body.innerHTML = contactCard(v.name, contractorRole(v.name) ? "contratista" : "dueño", true) + projectList(items);
    } else {
      const lvl = LEVELS.find((l) => l.id === state.level);
      head.innerHTML = `<h2>${v.tab === "novedades" ? "Novedades" : "Dónde hay más obras"}</h2>
        <p>${v.tab === "novedades" ? "Proyectos con noticias de las últimas 48 horas." : esc(periodText().replace(/^./, (c) => c.toUpperCase())) + ". Hacé clic en una zona para ver sus proyectos."}</p>
        <div class="tabs" role="tablist">
          <button type="button" role="tab" data-tab="novedades" aria-selected="${v.tab === "novedades"}">🆕 Novedades</button>
          <button type="button" role="tab" data-tab="zonas" aria-selected="${v.tab === "zonas"}">${esc(lvl.label)}</button>
          <button type="button" role="tab" data-tab="empresas" aria-selected="${v.tab === "empresas"}">Empresas</button>
        </div>`;
      head.querySelectorAll("[data-tab]").forEach((b) => b.addEventListener("click", () => { state.view.tab = b.dataset.tab; renderDrawer(); }));
      body.innerHTML = v.tab === "novedades" ? newsFeed() : v.tab === "zonas" ? zoneRanking() : companyRanking();
      body.querySelectorAll("[data-zone]").forEach((b) => b.addEventListener("click", () => openZone(state.level, b.dataset.zone, true)));
      body.querySelectorAll("[data-company]").forEach((b) => b.addEventListener("click", () => openCompany(b.dataset.company)));
    }
    body.querySelectorAll(".proj [data-company]").forEach((b) => b.addEventListener("click", (e) => { e.preventDefault(); openCompany(b.dataset.company); }));
    const back = $("back");
    if (back) back.addEventListener("click", closeDetail);
    body.scrollTop = 0;
  }

  function zoneRanking() {
    const groups = state.groups[state.level].slice(0, 40);
    if (!groups.length) return `<p class="note">No hay zonas con noticias para estos filtros. Probá con un período más largo.</p>`;
    return `<ol class="rank">${groups.map((g) => {
      const cos = topCompanies(g, 3);
      const sub = [g.where, cos.join(", ")].filter(Boolean).join(". ");
      return `<li><button type="button" data-zone="${esc(g.key)}">
        <span class="name">${esc(g.label)} <span class="emo">${sectorEmojis(g.sectors)}${g.rigi ? " " + RIGI_EMOJI : ""}</span></span><span class="n">${fmtNum(g.items.length)}</span>
        <span class="sub">${esc(sub || " ")}</span>${splitBar(g.sectors)}</button></li>`;
    }).join("")}</ol>`;
  }

  function companyRanking() {
    const agg = new Map();
    for (const it of state.items) {
      if (!it.sectors.some((s) => state.sectors.has(s))) continue;
      if (state.period && daysAgo(it.date) > state.period) continue;
      for (const c of [...it.companies, ...contractorsOf(it)]) {
        if (!agg.has(c)) agg.set(c, { name: c, n: 0, sectors: {}, places: {}, rigi: 0 });
        const g = agg.get(c);
        g.n += 1;
        if (it.signals.includes("rigi")) g.rigi += 1;
        it.sectors.forEach((s) => { g.sectors[s] = (g.sectors[s] || 0) + 1; });
        const p = it.admin1 || COUNTRIES[it.country];
        g.places[p] = (g.places[p] || 0) + 1;
      }
    }
    const rows = [...agg.values()].sort((a, b) => b.n - a.n).slice(0, 50);
    if (!rows.length) return `<p class="note">No se identificaron empresas para estos filtros.</p>`;
    return `<ol class="rank">${rows.map((g) => {
      const places = Object.entries(g.places).sort((a, b) => b[1] - a[1]).slice(0, 3).map((e) => e[0]).join(", ");
      const sub = (g.rigi ? `${RIGI_EMOJI} ${g.rigi} con RIGI. ` : "") + places;
      return `<li><button type="button" data-company="${esc(g.name)}">
        <span class="name">${contractorRole(g.name) ? "🏗️ " : ""}${esc(g.name)} <span class="emo">${sectorEmojis(g.sectors)}${hasContact(g.name) ? " 📇" : ""}</span></span><span class="n">${fmtNum(g.n)}</span>
        <span class="sub">${esc(sub)}</span>${splitBar(g.sectors)}</button></li>`;
    }).join("")}</ol>`;
  }

  function openZone(level, key, fly) {
    state.view = { type: "zone", level, key, fromTab: state.view.tab || state.view.fromTab };
    renderDrawer();
    const g = state.groups[level].find((x) => x.key === key);
    if (fly && g && map) {
      const next = level === "country" ? 4.9 : level === "prov" ? 6.9 : Math.max(map.getZoom(), 7.2);
      map.flyTo({ center: [g.lon, g.lat], zoom: next, pitch: 52, duration: reducedMotion ? 0 : 1600, essential: true });
    }
  }

  function openCompany(name) {
    state.company = name;
    state.view = { type: "company", name, fromTab: state.view.tab || state.view.fromTab };
    update();
  }

  function closeDetail() {
    const wasCompany = state.view.type === "company";
    state.view = { type: "ranking", tab: state.view.fromTab || (wasCompany ? "empresas" : "zonas") };
    if (wasCompany) { state.company = null; update(); } else renderDrawer();
  }

  function showNotice(title, text) {
    const n = $("notice");
    n.innerHTML = `<h2>${esc(title)}</h2><p>${esc(text)}</p>`;
    n.hidden = false;
  }

  // ---------------------------------------------------------------------------
  // Ciclo
  // ---------------------------------------------------------------------------

  function update() {
    buildGroups();
    renderFilters();
    renderLevels();
    renderStatus();
    renderDrawer();
    refreshDots();
  }

  async function loadData() {
    const [news, places, paises, provincias, contacts] = await Promise.allSettled([
      getJSON("data/news.json"),
      getJSON("data/lugares.json"),
      getJSON("data/paises.geojson"),
      getJSON("data/provincias.geojson"),
      getJSON("data/contactos.json"),
    ]);
    if (contacts.status === "fulfilled") state.contacts = contacts.value;
    if (news.status === "fulfilled") {
      state.items = news.value.items || [];
      state.updated = news.value.updated;
    }
    if (places.status === "fulfilled") state.places = places.value;
    state.hasProvinces = provincias.status === "fulfilled";
    buildGroups();
    renderFilters();
    renderLevels();
    renderStatus();
    renderDrawer();
    initMap(paises.status === "fulfilled" ? paises.value : null, state.hasProvinces ? provincias.value : null);
    placeBlips(state.groups.city);
    if (paises.status !== "fulfilled") {
      showNotice("El mapa base todavía se está generando", "Se crea en la próxima actualización automática. Mientras tanto podés ver el ranking y las noticias en el panel.");
    }
    if (news.status !== "fulfilled") console.error(news.reason);
  }

  $("start").addEventListener("click", startRadar);
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && state.view.type !== "ranking") closeDetail();
  });
})();
