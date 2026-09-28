/**
 * System Telemetry, Host Hardware & GPU Metrics Component.
 */

import { fetchTelemetry } from '../api.js';

export function initTelemetryComponent(AppState) {
  const container = document.getElementById('gpu-metrics-grid');
  if (!container) return;

  async function updateMetrics() {
    try {
      const data = await fetchTelemetry();
      renderMetrics(data);
    } catch (err) {
      console.error('Telemetry update error:', err);
    }
  }

  function renderMetrics(data) {
    container.innerHTML = '';

    // 1. Host System & Hardware Overview Panel
    const hostCard = document.createElement('div');
    hostCard.className = 'glass-panel gpu-card';
    hostCard.style.padding = '16px';
    hostCard.style.gridColumn = '1 / -1';

    const ram = data.ram || { usedMb: 0, totalMb: 0, pct: 0 };
    const disk = data.disk || { usedGb: 0, totalGb: 0, pct: 0, freeGb: 0 };
    const services = data.services || {};

    const serviceBadges = Object.keys(services).map(sKey => {
      const s = services[sKey];
      const color = s.alive ? 'var(--accent-green)' : 'var(--text-dim)';
      const icon = s.alive ? '🟢' : '⚪';
      return `<span style="border:1px solid ${color}; padding:2px 8px; border-radius:12px; font-size:0.75rem; margin-right:6px;">
        ${icon} ${sKey} (:${s.port})
      </span>`;
    }).join(' ');

    hostCard.innerHTML = `
      <div style="font-weight:700; color:var(--accent-cyan); font-size:1.05rem; margin-bottom:12px; display:flex; justify-content:space-between;">
        <span>🖥️ Host Telemetry & Daemon Services</span>
        <span style="font-size:0.8rem; color:var(--text-muted); font-weight:normal;">Sesión: <strong>${data.active_session || 'default'}</strong></span>
      </div>
      <div style="display:grid; grid-template-columns: 1fr 1fr; gap:16px; margin-bottom:14px;">
        <div>
          <div style="font-size:0.82rem; color:var(--text-muted); display:flex; justify-content:space-between; margin-bottom:4px;">
            <span>Memoria RAM del Sistema</span>
            <span>${ram.usedMb} / ${ram.totalMb} MiB (${ram.pct}%)</span>
          </div>
          <div class="metric-bar-bg" style="height:8px;">
            <div class="metric-bar-fill ${ram.pct > 85 ? 'warn' : ''}" style="width: ${ram.pct}%"></div>
          </div>
        </div>
        <div>
          <div style="font-size:0.82rem; color:var(--text-muted); display:flex; justify-content:space-between; margin-bottom:4px;">
            <span>Almacenamiento Workspace</span>
            <span>${disk.usedGb} / ${disk.totalGb} GiB (${disk.pct}%) &nbsp;|&nbsp; Libre: ${disk.freeGb} GiB</span>
          </div>
          <div class="metric-bar-bg" style="height:8px;">
            <div class="metric-bar-fill ${disk.pct > 90 ? 'warn' : ''}" style="width: ${disk.pct}%"></div>
          </div>
        </div>
      </div>
      <div style="font-size:0.8rem; color:var(--text-muted);">
        <strong style="color:var(--text-main);">Servicios Detectados:</strong> ${serviceBadges}
      </div>
    `;
    container.appendChild(hostCard);

    // 2. GPU Cards
    const gpus = data.gpus || [];
    if (gpus.length === 0) {
      const emptyGpu = document.createElement('div');
      emptyGpu.className = 'glass-panel';
      emptyGpu.style.padding = '14px';
      emptyGpu.style.gridColumn = '1 / -1';
      emptyGpu.style.color = 'var(--text-muted)';
      emptyGpu.textContent = 'ℹ️ Sin aceleración GPU NVIDIA detectada (Inferencia en CPU / API remota).';
      container.appendChild(emptyGpu);
      return;
    }

    gpus.forEach(gpu => {
      const card = document.createElement('div');
      card.className = 'glass-panel gpu-card';
      card.style.padding = '16px';

      const isWarn = gpu.memoryPct > 85;
      card.innerHTML = `
        <div style="font-weight:700; color:var(--accent-blue); margin-bottom:6px;">🎮 GPU ${gpu.index}: ${gpu.name}</div>
        <div style="font-size:0.8rem; color:var(--text-muted); display:flex; justify-content:space-between;">
          <span>VRAM Usada</span>
          <span>${gpu.memoryUsedMb} / ${gpu.memoryTotalMb} MiB (${gpu.memoryPct}%)</span>
        </div>
        <div class="metric-bar-bg" style="height:8px; margin: 4px 0 8px 0;">
          <div class="metric-bar-fill ${isWarn ? 'warn' : ''}" style="width: ${gpu.memoryPct}%"></div>
        </div>
        <div style="font-size:0.78rem; color:var(--text-dim); display:flex; justify-content:space-between; margin-top:6px;">
          <span>🌡️ Temp: ${gpu.tempC}°C</span>
          <span>⚡ Carga: ${gpu.gpuUtilPct}%</span>
          <span>🔋 Potencia: ${gpu.powerW}W</span>
        </div>
      `;
      container.appendChild(card);
    });
  }

  async function pollMetrics() {
    if (AppState && AppState.activeTab === 'telemetry') {
      await updateMetrics();
    }
  }

  // Initial load
  updateMetrics();
  setInterval(pollMetrics, 3500);
}

