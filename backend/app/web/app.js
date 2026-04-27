async function fetchEstado() {
  const resp = await fetch(`/estado?t=${Date.now()}`, { cache: "no-store" });
  if (!resp.ok) {
    throw new Error(`HTTP ${resp.status}`);
  }
  return await resp.json();
}

function fmtNumber(value, digits = 1) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "Sin dato";
  }

  const n = Number(value);
  const fixed = n.toFixed(digits);

  // Quita ceros finales sin romper decimales como 1.02
  return fixed.replace(/\.?0+$/, "");
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

function getTendenciaTexto(tendencia) {
  const t = String(tendencia || "").toLowerCase();

  if (t === "crece") return "↑ Crece";
  if (t === "baja") return "↓ Baja";
  if (t === "invariable") return "→ Invariable";

  return "";
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

function renderForecast(pronostico) {
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

    card.innerHTML = `
      <div class="forecast-date">${dia.fecha || "Sin fecha"}</div>
      <div class="forecast-condition">${dia.condicion || "Sin dato"}</div>
      <div class="forecast-row"><span>Lluvia</span><strong>${fmtNumber(dia.lluvia_mm, 1)} mm</strong></div>
      <div class="forecast-row"><span>Probabilidad</span><strong>${fmtNumber(dia.prob_lluvia_pct, 0)}%</strong></div>
      <div class="forecast-row"><span>Máx</span><strong>${fmtNumber(dia.temp_max_c, 1)} °C</strong></div>
      <div class="forecast-row"><span>Mín</span><strong>${fmtNumber(dia.temp_min_c, 1)} °C</strong></div>
    `;
    grid.appendChild(card);
  });
}

function renderFuentes(meta) {
  const fuentes = meta?.fuentes ? meta.fuentes.join(", ") : "Sin dato";
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

  const tendenciaTexto = getTendenciaTexto(datos.river_tendencia);

  const nivelRioTexto =
    datos.nivel_rio_m == null
      ? "Sin dato"
      : `${fmtNumber(datos.nivel_rio_m, 2)} m${tendenciaTexto ? " " + tendenciaTexto : ""}`;

  setText("v-lluvia-actual", `${fmtNumber(datos.lluvia_actual_mm, 1)} mm`);
  setText("v-lluvia-24h", `${fmtNumber(datos.lluvia_24h_mm, 1)} mm`);
  setText("v-intensidad", `${fmtNumber(datos.intensidad_mm_h, 1)} mm/h`);
  setText("v-lluvia-3dias", `${fmtNumber(datos.lluvia_3dias_mm, 1)} mm`);
  setText("v-nivel-rio", nivelRioTexto);
  setText("v-nivel-alerta", `${fmtNumber(datos.alerta_rio_m, 1)} m`);
  setText("v-nivel-evac", `${fmtNumber(datos.evacuacion_rio_m, 1)} m`);
  setText("v-viento", `${datos.direccion_viento || "--"} ${fmtNumber(datos.viento_kmh, 1)} km/h`);

  renderChecklist(payload.checklist || []);
  renderFuentes(meta);
  renderForecast(datos.pronostico_5dias || []);
}

async function loadEstado() {
  try {
    const btn = document.getElementById("btn-refresh");
    if (btn) btn.textContent = "Actualizando...";

    const data = await fetchEstado();
    renderEstado(data);

    if (btn) btn.textContent = "Actualizar";
  } catch (err) {
    console.error(err);
    setText("interpretacion", "No se pudo cargar el estado actual.");
    setText("conclusion", "Error al consultar el backend.");

    const btn = document.getElementById("btn-refresh");
    if (btn) btn.textContent = "Actualizar";
  }
}

document.addEventListener("DOMContentLoaded", () => {
  const btn = document.getElementById("btn-refresh");
  if (btn) {
    btn.addEventListener("click", loadEstado);
  }
  loadEstado();
});
