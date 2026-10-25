async function fetchEstado() {
  const resp = await fetch(`/estado?t=${Date.now()}`, {
    cache: "no-store"
  });

  if (!resp.ok) {
    throw new Error(`HTTP ${resp.status}`);
  }

  return await resp.json();
}

function fmtNumber(value, digits = 1) {
  if (
    value === null ||
    value === undefined ||
    value === "" ||
    !Number.isFinite(Number(value))
  ) {
    return "Sin dato";
  }

  return Number(value)
    .toFixed(digits)
    .replace(/(\.\d*?[1-9])0+$|\.0+$/, "$1");
}

function medida(value, unidad, digits = 1) {
  const texto = fmtNumber(value, digits);
  return texto === "Sin dato" ? texto : `${texto} ${unidad}`;
}

function setText(id, text) {
  const el = document.getElementById(id);
  if (el) el.textContent = text;
}

function normalizarSemaforo(value) {
  const estado = String(value || "").toUpperCase();

  if (["VERDE", "AMARILLO", "ROJO"].includes(estado)) {
    return estado;
  }

  return "INFORMACIÓN INSUFICIENTE";
}

function getSemaforoClass(semaforo) {
  const estado = normalizarSemaforo(semaforo);

  if (estado === "ROJO") return "rojo";
  if (estado === "AMARILLO") return "amarillo";
  if (estado === "VERDE") return "verde";

  return "insuficiente";
}

function getTendenciaTexto(tendencia) {
  const valor = String(tendencia || "").toLowerCase();

  if (valor === "crece") return "↑ Crece";
  if (valor === "baja") return "↓ Baja";
  if (valor === "invariable") return "→ Invariable";

  return "";
}

function renderChecklist(items) {
  const ul = document.getElementById("checklist");
  if (!ul) return;

  ul.replaceChildren();

  const lista = Array.isArray(items) ? items : [];

  lista.forEach((item) => {
    const li = document.createElement("li");
    li.textContent = String(item);
    ul.appendChild(li);
  });
}

function renderForecast(pronostico) {
  const grid = document.getElementById("forecast-grid");
  if (!grid) return;

  grid.replaceChildren();

  const items = Array.isArray(pronostico) ? pronostico : [];

  if (!items.length) {
    const aviso = document.createElement("div");
    aviso.className = "forecast-empty";
    aviso.textContent = "Sin pronóstico disponible.";
    grid.appendChild(aviso);
    return;
  }

  items.forEach((dia) => {
    const card = document.createElement("div");
    card.className = "forecast-card";

    const fecha = document.createElement("div");
    fecha.className = "forecast-date";
    fecha.textContent = dia.fecha || "Sin fecha";

    const condicion = document.createElement("div");
    condicion.className = "forecast-condition";
    condicion.textContent = dia.condicion || "Sin dato";

    card.append(fecha, condicion);

    const filas = [
      ["Lluvia", medida(dia.lluvia_mm, "mm")],
      ["Probabilidad", medida(dia.prob_lluvia_pct, "%", 0)],
      ["Máx", medida(dia.temp_max_c, "°C")],
      ["Mín", medida(dia.temp_min_c, "°C")]
    ];

    filas.forEach(([nombre, valor]) => {
      const fila = document.createElement("div");
      fila.className = "forecast-row";

      const etiqueta = document.createElement("span");
      etiqueta.textContent = nombre;

      const dato = document.createElement("strong");
      dato.textContent = valor;

      fila.append(etiqueta, dato);
      card.appendChild(fila);
    });

    grid.appendChild(card);
  });
}

function renderFuentes(meta) {
  const fuentes = Array.isArray(meta?.fuentes)
    ? meta.fuentes.filter(Boolean).join(", ")
    : "";

  setText("fuentes", `Fuentes: ${fuentes || "Sin dato"}`);
}

function fechaConsulta(value) {
  if (!value) return "Sin dato";

  const fecha = new Date(value);
  if (Number.isNaN(fecha.getTime())) return "Sin dato";

  return fecha.toLocaleString("es-AR", {
    timeZone: "America/Argentina/Buenos_Aires"
  }) + " (Argentina)";
}

function renderEstado(payload) {
  const semaforo = normalizarSemaforo(payload.semaforo);
  const clase = getSemaforoClass(semaforo);
  const insuficiente = clase === "insuficiente";
  const datos = payload.datos || {};
  const meta = payload.meta || {};

  setText("semaforo-label", semaforo);
  setText(
    "updated-at",
    `Consulta del tablero, no medición: ${fechaConsulta(meta.updated_at)}`
  );
  setText("interpretacion", payload.interpretacion || "Sin información.");
  setText("conclusion", payload.conclusion || "Evaluación no disponible.");

  const statusCard = document.querySelector(".status-card");

  if (statusCard) {
    statusCard.classList.remove(
      "verde", "amarillo", "rojo", "insuficiente"
    );
    statusCard.classList.add(clase);

    // Permite mostrar el estado neutral sin modificar styles.css.
    statusCard.style.backgroundColor = insuficiente ? "#26313d" : "";
    statusCard.style.borderColor = insuficiente ? "#94a3b8" : "";
    statusCard.style.backgroundImage = insuficiente ? "none" : "";
  }

  const estadoLabel = document.getElementById("semaforo-label");

  if (estadoLabel) {
    estadoLabel.classList.remove(
      "texto-verde",
      "texto-amarillo",
      "texto-rojo",
      "texto-insuficiente"
    );
    estadoLabel.classList.add(`texto-${clase}`);
    estadoLabel.style.color = insuficiente ? "#e2e8f0" : "";
  }

  const tendencia = getTendenciaTexto(datos.river_tendencia);
  let nivelRio = medida(datos.nivel_rio_m, "m", 2);

  if (nivelRio !== "Sin dato" && tendencia) {
    nivelRio += ` ${tendencia}`;
  }

  if (
    nivelRio !== "Sin dato" &&
    datos.river_data_status === "dato atrasado"
  ) {
    nivelRio += " — dato atrasado";
  } else if (
    nivelRio !== "Sin dato" &&
    datos.river_data_status === "antigüedad no verificable"
  ) {
    nivelRio += " — antigüedad desconocida";
  }

  setText("v-lluvia-actual", medida(datos.lluvia_actual_mm, "mm"));
  setText("v-lluvia-24h", medida(datos.lluvia_24h_mm, "mm"));
  setText("v-intensidad", medida(datos.intensidad_mm_h, "mm/h"));
  setText("v-lluvia-3dias", medida(datos.lluvia_3dias_mm, "mm"));
  setText("v-nivel-rio", nivelRio);
  setText("v-nivel-alerta", medida(datos.alerta_rio_m, "m"));
  setText("v-nivel-evac", medida(datos.evacuacion_rio_m, "m"));

  const viento = medida(datos.viento_kmh, "km/h");
  setText(
    "v-viento",
    viento === "Sin dato"
      ? viento
      : `${datos.direccion_viento || "Dirección sin dato"} ${viento}`
  );

  renderChecklist(payload.checklist);
  renderFuentes(meta);
  renderForecast(datos.pronostico_5dias);
}

async function loadEstado() {
  const btn = document.getElementById("btn-refresh");
  if (btn) btn.textContent = "Actualizando...";

  try {
    const data = await fetchEstado();
    renderEstado(data);
  } catch (err) {
    console.error(err);

    // Elimina los valores y el color de la consulta anterior.
    renderEstado({
      semaforo: "INFORMACIÓN INSUFICIENTE",
      interpretacion: "No se pudo obtener el estado actual.",
      conclusion: (
        "La falta de datos no permite confirmar condiciones seguras. " +
        "Consultá las fuentes oficiales."
      ),
      datos: {},
      checklist: [
        "Falló la consulta del tablero.",
        "Los valores anteriores no se muestran como datos actuales.",
        "Alertas oficiales: https://www.smn.gob.ar/alertas"
      ],
      meta: {}
    });
  } finally {
    if (btn) btn.textContent = "Actualizar";
  }
}

document.addEventListener("DOMContentLoaded", () => {
  const btn = document.getElementById("btn-refresh");
  if (btn) btn.addEventListener("click", loadEstado);

  loadEstado();
});