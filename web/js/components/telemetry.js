/**
 * System Telemetry & GPU Metrics Component.
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
    const gpus = data.gpus || [];

    if (gpus.length === 0) {
      container.innerHTML = '<div style="color:var(--text-muted)">No GPU telemetry reported.</div>';
      return;
    }

    gpus.forEach(gpu => {
      const card = document.createElement('div');
      card.className = 'glass-panel gpu-card';
      card.style.padding = '16px';

      const isWarn = gpu.memoryPct > 85;
      card.innerHTML = `
        <div style="font-weight:700; color:var(--accent-blue);">GPU ${gpu.index}: ${gpu.name}</div>
        <div style="font-size:0.8rem; color:var(--text-muted); display:flex; justify-content:space-between;">
          <span>VRAM Used</span>
          <span>${gpu.memoryUsedMb} / ${gpu.memoryTotalMb} MiB (${gpu.memoryPct}%)</span>
        </div>
        <div class="metric-bar-bg">
          <div class="metric-bar-fill ${isWarn ? 'warn' : ''}" style="width: ${gpu.memoryPct}%"></div>
        </div>
        <div style="font-size:0.78rem; color:var(--text-dim); display:flex; gap:12px; margin-top:4px;">
          <span>Temp: ${gpu.tempC}°C</span>
          <span>GPU Util: ${gpu.gpuUtilPct}%</span>
          <span>Power: ${gpu.powerW}W</span>
        </div>
      `;
      container.appendChild(card);
    });
  }

  updateMetrics();
  setInterval(updateMetrics, 3000);
}
