/**
 * 📦 Factory 3D Orders Dispatch & Commercial Management Component.
 */

import { fetchFactoryOrders, updateFactoryOrderStatus } from '../api.js';

export function initOrdersComponent(AppState) {
  const container = document.getElementById('tab-orders');
  if (!container) return;

  container.innerHTML = `
    <div style="padding:16px; display:flex; flex-direction:column; gap:16px; height:100%; overflow-y:auto;">
      <!-- Stats Header Cards -->
      <div id="orders-stats-grid" style="display:grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap:12px;">
        <div class="glass-panel" style="padding:12px;">
          <div style="font-size:0.75rem; color:var(--text-muted);">Total Comandas</div>
          <div id="stat-total-orders" style="font-size:1.4rem; font-weight:700; color:var(--accent-cyan);">0</div>
        </div>
        <div class="glass-panel" style="padding:12px;">
          <div style="font-size:0.75rem; color:var(--text-muted);">Pendientes Impresión</div>
          <div id="stat-pending-orders" style="font-size:1.4rem; font-weight:700; color:var(--accent-amber);">0</div>
        </div>
        <div class="glass-panel" style="padding:12px;">
          <div style="font-size:0.75rem; color:var(--text-muted);">En Impresión 3D</div>
          <div id="stat-in-print-orders" style="font-size:1.4rem; font-weight:700; color:var(--accent-blue);">0</div>
        </div>
        <div class="glass-panel" style="padding:12px;">
          <div style="font-size:0.75rem; color:var(--text-muted);">Enviadas por @human</div>
          <div id="stat-shipped-orders" style="font-size:1.4rem; font-weight:700; color:var(--accent-green);">0</div>
        </div>
        <div class="glass-panel" style="padding:12px;">
          <div style="font-size:0.75rem; color:var(--text-muted);">Ingresos Facturados</div>
          <div id="stat-revenue-orders" style="font-size:1.4rem; font-weight:700; color:var(--accent-purple);">€0.00</div>
        </div>
      </div>

      <!-- Action Toolbar -->
      <div style="display:flex; justify-content:space-between; align-items:center;">
        <h3 style="font-size:1rem; color:var(--text-main); margin:0;">📋 Cola de Pedidos Bajo Demanda (fabrica/orders/)</h3>
        <div style="display:flex; gap:8px;">
          <a href="/landing" target="_blank" class="btn btn-secondary" style="font-size:0.78rem; text-decoration:none; padding:5px 10px;">🌐 Ver Micro-Landing</a>
          <button id="btn-refresh-orders" class="btn btn-secondary" style="font-size:0.78rem; padding:5px 10px;">🔄 Refrescar</button>
        </div>
      </div>

      <!-- Orders List Container -->
      <div id="orders-list-container" style="display:flex; flex-direction:column; gap:10px;">
        <div style="color:var(--text-muted);">Cargando pedidos...</div>
      </div>
    </div>
  `;

  const refreshBtn = document.getElementById('btn-refresh-orders');
  refreshBtn?.addEventListener('click', loadOrders);

  async function loadOrders() {
    const listEl = document.getElementById('orders-list-container');
    if (!listEl) return;

    try {
      const data = await fetchFactoryOrders();
      const stats = data.stats || {};
      const orders = data.orders || [];

      // Update stats
      document.getElementById('stat-total-orders').textContent = stats.total || 0;
      document.getElementById('stat-pending-orders').textContent = stats.pending || 0;
      document.getElementById('stat-in-print-orders').textContent = stats.in_print || 0;
      document.getElementById('stat-shipped-orders').textContent = stats.shipped || 0;
      document.getElementById('stat-revenue-orders').textContent = `€${(stats.total_revenue_eur || 0).toFixed(2)}`;

      listEl.innerHTML = '';

      if (orders.length === 0) {
        listEl.innerHTML = '<div class="glass-panel" style="padding:20px; color:var(--text-muted); text-align:center;">No hay comandas registradas en <code>fabrica/orders/</code> todavía.</div>';
        return;
      }

      orders.forEach(ord => {
        const card = document.createElement('div');
        card.className = 'glass-panel';
        card.style.padding = '14px';
        card.style.display = 'flex';
        card.style.flexDirection = 'column';
        card.style.gap = '8px';

        const p = ord.product || {};
        const c = ord.customer || {};
        const statusColors = {
          pending: 'var(--accent-amber)',
          in_print: 'var(--accent-blue)',
          printed: 'var(--accent-cyan)',
          shipped: 'var(--accent-green)',
          delivered: 'var(--accent-purple)',
          cancelled: 'var(--accent-rose)'
        };

        const statusBadge = `<span style="background:rgba(255,255,255,0.06); border:1px solid ${statusColors[ord.status] || 'var(--border-color)'}; color:${statusColors[ord.status] || 'white'}; padding:2px 8px; border-radius:12px; font-size:0.75rem; font-weight:600;">${(ord.status || 'pending').toUpperCase()}</span>`;

        card.innerHTML = `
          <div style="display:flex; justify-content:space-between; align-items:center;">
            <div>
              <strong style="color:var(--accent-cyan);">${p.title || 'Artículo 3D'}</strong>
              <span style="font-size:0.8rem; color:var(--text-muted); margin-left:8px;">ID: <code>${ord.order_id}</code></span>
            </div>
            <div>${statusBadge}</div>
          </div>
          <div style="display:grid; grid-template-columns: 1fr 1fr 1fr; font-size:0.8rem; color:var(--text-muted); gap:8px;">
            <div>👤 <strong>Cliente:</strong> ${c.name || 'Anónimo'} (${c.city || 'España'})</div>
            <div>💰 <strong>Total:</strong> €${p.total || p.price || 0}</div>
            <div>📅 <strong>Fecha:</strong> ${ord.created_at || 'Reciente'}</div>
          </div>
          ${ord.tracking_code ? `<div style="font-size:0.78rem; color:var(--accent-green);">🚚 <strong>Envío:</strong> ${ord.carrier || 'Transportista'} - Tracking: <code>${ord.tracking_code}</code></div>` : ''}
          ${ord.operator_notes ? `<div style="font-size:0.78rem; color:var(--text-dim); background:rgba(0,0,0,0.2); padding:6px; border-radius:4px;">📝 <strong>Notas:</strong> ${ord.operator_notes}</div>` : ''}
          <div style="display:flex; gap:8px; margin-top:6px; border-top:1px solid var(--border-color); padding-top:8px;">
            <button class="btn btn-secondary btn-order-action" data-id="${ord.order_id}" data-action="in_print" style="font-size:0.75rem; padding:3px 8px;">🖨️ En Impresión</button>
            <button class="btn btn-secondary btn-order-action" data-id="${ord.order_id}" data-action="printed" style="font-size:0.75rem; padding:3px 8px;">✅ STL Impreso</button>
            <button class="btn btn-secondary btn-order-action" data-id="${ord.order_id}" data-action="shipped" style="font-size:0.75rem; padding:3px 8px;">📦 Marcar Enviado</button>
          </div>
        `;

        card.querySelectorAll('.btn-order-action').forEach(btn => {
          btn.addEventListener('click', async () => {
            const nextStatus = btn.dataset.action;
            let carrier = ord.carrier || '';
            let tracking = ord.tracking_code || '';
            let notes = ord.operator_notes || '';

            if (nextStatus === 'shipped') {
              carrier = prompt('Empresa de transporte (ej: Correos Express, GLS, SEUR):', carrier || 'Correos Express') || carrier;
              tracking = prompt('Código de Seguimiento / Tracking Number:', tracking || '') || tracking;
            }
            notes = prompt('Notas adicionales del operador (@human):', notes || '') || notes;

            try {
              await updateFactoryOrderStatus(ord.order_id, nextStatus, carrier, tracking, notes);
              loadOrders();
            } catch (e) {
              alert('Error al actualizar estado: ' + e.message);
            }
          });
        });

        listEl.appendChild(card);
      });
    } catch (err) {
      listEl.innerHTML = `<div style="color:var(--accent-rose);">Error al consultar pedidos: ${err.message}</div>`;
    }
  }

  loadOrders();
}
