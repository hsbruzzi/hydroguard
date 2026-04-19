const endpoint = '/estado';

function fmtUpdatedAt(isoString) {
  if (!isoString) return 'Sin hora de actualización';
  const d = new Date(isoString);
  return `Actualizado: ${d.toLocaleString('es-AR')}`;
}

function renderMetric(label, value) {
  return `
    <div class="metric">
      <div class="label">${label}</div>
      <div class="value">${value}</div>
    </div>
  `;
}

function mapEstadoClass(semaforo) {
  const s = (semaforo || '').toLowerCase();
  if (s.includes('verde')) return 'verde';
  if (s.includes('amarillo')) return 'amarillo';
  if (s.includes('rojo')) return 'rojo';
  return 'neutral';
}

function formatMeters(value) {
  if (value === null || value === undefined) return 'Sin dato';
  return `${value} m`;
}

async function loadEstado() {
  const btn = document.getElementById('refreshBtn');
  btn.disabled = true;
  btn.textContent = 'Actualizando…';

  try {
    const res = await fetch(endpoint, { cache: 'no-store' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    const statusCard = document.getElementById('statusCard');
    statusCard.className = `status-card ${mapEstadoClass(data.semaforo)}`;

    document.getElementById('statusText').textContent = data.semaforo || '--';
    document.getElementById('updatedAt').textContent = fmtUpdatedAt(data?.meta?.updated_at);
    document.getElementById('interpretacion').textContent = data.interpretacion || '--';
    document.getElementById('conclusion').textContent = data.conclusion || '--';

    const checklist = document.getElementById('checklist');
    checklist.innerHTML = '';
    (data.checklist || []).forEach(item => {
      const li = document.createElement('li');
      li.textContent = item;
      checklist.appendChild(li);
    });

    const d = data.datos || {};
    document.getElementById('metrics').innerHTML = [
      renderMetric('Lluvia actual', `${d.lluvia_actual_mm ?? '--'} mm`),
      renderMetric('Lluvia 24 h', `${d.lluvia_24h_mm ?? '--'} mm`),
      renderMetric('Intensidad', `${d.intensidad_mm_h ?? '--'} mm/h`),
      renderMetric('Lluvia 3 días', `${d.lluvia_3dias_mm ?? '--'} mm`),
      renderMetric('Nivel del río', formatMeters(d.nivel_rio_m)),
      renderMetric('Nivel de alerta', formatMeters(d.alerta_rio_m)),
      renderMetric('Nivel de evacuación', formatMeters(d.evacuacion_rio_m)),
      renderMetric('Viento', `${d.direccion_viento ?? '--'} ${d.viento_kmh ?? '--'} km/h`)
    ].join('');

    document.getElementById('zona').textContent = `Zona: ${data?.meta?.zona || '--'}`;
    document.getElementById('fuentes').textContent = `Fuentes: ${(data?.meta?.fuentes || []).join(', ') || '--'}`;
  } catch (err) {
    document.getElementById('statusText').textContent = 'ERROR';
    document.getElementById('interpretacion').textContent = 'No pude leer el backend. Verificá que FastAPI siga corriendo.';
    document.getElementById('conclusion').textContent = String(err);
    document.getElementById('checklist').innerHTML = '<li>Backend inaccesible</li><li>Revisar servicio</li>';
    document.getElementById('metrics').innerHTML = '';
  } finally {
    btn.disabled = false;
    btn.textContent = 'Actualizar';
  }
}

document.getElementById('refreshBtn').addEventListener('click', loadEstado);
loadEstado();