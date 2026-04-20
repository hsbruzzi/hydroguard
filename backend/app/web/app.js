async function fetchEstado() {
  const resp = await fetch("/estado", { cache: "no-store" });
  if (!resp.ok) {
    throw new Error(`HTTP ${resp.status}`);
  }
  return await resp.json();
}

function fmtNumber(value, digits = 1) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "Sin dato";
  }
  return Number(value).toFixed(digits).replace(".0", "");
}

function setText(id, text) {
  const el = document.getElementById(id);
  if (el) el.textContent = text;
}

function getSemaforoClass(semaforo) {
  const s = String(semaforo || "").toUpperCase();
  if (s === "ROJO") return "rojo";
  if (s === "AMARILLO") return "amarillo";
  return "verde";
}

function renderChecklist(items) {
  const ul = document.getElementById("checklist");
  if (!ul) return;
  ul.innerHTML = "";
  (items || []).forEach((item) => {
    const li = document.createElement("li");
    li.textContent = item;
    ul.appendChild(li);
  });
}

function ensureForecastContainer() {
  let section = document.getElementById("forecast-section");
  if (section) return section;

  const appShell = document.querySelector(".app-shell");
  if (!appShell) return null;

  const footer = appShell.querySelector(".footer");

  section = document.createElement("section");
  section.id = "forecast-section";
  section.className = "panel forecast-panel";
  section.innerHTML = `
    <div class="panel-header">
      <h2>Pronóstico próximos 5 días</h2>
      <p class="forecast-subtitle">
        Referencia útil para anticipar cuándo podría aflojar la lluvia o mejorar el tiempo.
      </p>
    </div>
    <div id="forecast-grid" class="forecast-grid"></div>
  `;

  if (footer) {
    appShell.insertBefore(section, footer);
  } else {
    appShell.appendChild(section);
  }

  return section;
}

function renderForecast(pronostico) {
  const section = ensureForecastContainer();
  if (!section) return;

  const grid = document.getElementById("forecast-grid");
  if (!grid) return;

  grid.innerHTML = "";

  const items = pronostico || [];
  if (!items.length) {
    grid.innerHTML = `<div class="forecast-empty">Sin pronóstico disponible.</div>`;
    return;
  }

  items.forEach((dia) => {
    const card = document.createElement("div");
    card.className = "forecast-card";

    const lluvia = dia.lluvia_mm ?? null;
    const prob = dia.prob_lluvia_pct ?? null;
    const tmax = dia.temp_max_c ?? null;
    const tmin = dia.temp_min_c ?? null;

    card.innerHTML = `
      <div class="forecast-date">${dia.fecha || "Sin fecha"}</div>
      <div class="forecast-condition">${dia.condicion || "Sin dato"}</div>
      <div class="forecast-row"><span>Lluvia</span><strong>${fmtNumber(lluvia, 1)} mm</strong></div>
      <div class="forecast-row"><span>Probabilidad</span><strong>${fmtNumber(prob, 0)}%</strong></div>
      <div class="forecast-row"><span>Máx</span><strong>${fmtNumber(tmax, 1)} °C</strong></div>
      <div class="forecast-row"><span>Mín</span><strong>${fmtNumber(tmin, 1)} °C</strong></div>
    `;
    grid.appendChild(card);
  });
}

function renderFuentes(meta) {
  const fuentes = (meta && meta.fuentes) ? meta.fuentes.join(", ") : "Sin dato";
  setText("fuentes", `Fuentes: ${fuentes}`);
}

function renderEstado(payload) {
  const semaforo = payload.semaforo || "VERDE";
  const datos = payload.datos || {};
  const meta = payload.meta || {};

  setText("semaforo-label", semaforo);
  setText(
    "updated-at",
    `Actualizado: ${new Date(meta.updated_at || Date.now()).toLocaleString("es-AR")}`
  );
  setText("interpretacion", payload.interpretacion || "-");
  setText("conclusion", payload.conclusion || "-");

  const statusCard = document.querySelector(".status-card");
  if (statusCard) {
    statusCard.classList.remove("verde", "amarillo", "rojo");
    statusCard.classList.add(getSemaforoClass(semaforo));
  }

  const estadoLabel = document.getElementById("semaforo-label");
  if (estadoLabel) {
    estadoLabel.classList.remove("texto-verde", "texto-amarillo", "texto-rojo");
    estadoLabel.classList.add(`texto-${getSemaforoClass(semaforo)}`);
  }

  setText("v-lluvia-actual", `${fmtNumber(datos.lluvia_actual_mm, 1)} mm`);
  setText("v-lluvia-24h", `${fmtNumber(datos.lluvia_24h_mm, 1)} mm`);
  setText("v-intensidad", `${fmtNumber(datos.intensidad_mm_h, 1)} mm/h`);
  setText("v-lluvia-3dias", `${fmtNumber(datos.lluvia_3dias_mm, 1)} mm`);
  setText("v-nivel-rio", datos.nivel_rio_m == null ? "Sin dato" : `${fmtNumber(datos.nivel_rio_m, 2)} m`);
  setText("v-nivel-alerta", `${fmtNumber(datos.alerta_rio_m, 1)} m`);
  setText("v-nivel-evac", `${fmtNumber(datos.evacuacion_rio_m, 1)} m`);
  setText("v-viento", `${datos.direccion_viento || "--"} ${fmtNumber(datos.viento_kmh, 1)} km/h`);

  renderChecklist(payload.checklist || []);
  renderFuentes(meta);
  renderForecast(datos.pronostico_5dias || []);
}

async function loadEstado() {
  try {
    const data = await fetchEstado();
    renderEstado(data);
  } catch (err) {
    console.error(err);
    setText("interpretacion", "No se pudo cargar el estado actual.");
    setText("conclusion", "Error al consultar el backend.");
  }
}

document.addEventListener("DOMContentLoaded", () => {
  const btn = document.getElementById("btn-refresh");
  if (btn) {
    btn.addEventListener("click", loadEstado);
  }
  loadEstado();
});