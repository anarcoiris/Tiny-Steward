/**
 * Memory & Knowledge Graph Component - Interactive Force-Directed Graph & Node Inspector.
 */

import { inspectGraphNode, rebuildGraph } from '../api.js';

export function initGraphComponent(AppState) {
  const container = document.getElementById('graph-canvas-container');
  if (!container) return;

  container.innerHTML = `
    <div style="position:absolute; top:12px; left:12px; z-index:10; display:flex; gap:8px;">
      <button id="btn-rebuild-graph" class="btn btn-secondary" style="font-size:0.75rem; padding:4px 10px;">🔄 Reconstruir Grafo</button>
    </div>
    <div id="graph-viewport" style="width:100%; height:100%;"></div>
    <div id="graph-drawer" class="glass-panel" style="position:absolute; right:12px; top:12px; bottom:12px; width:340px; z-index:20; padding:16px; display:none; overflow-y:auto; flex-direction:column;">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
        <strong id="drawer-node-title" style="color:var(--accent-cyan); font-size:0.95rem;"></strong>
        <button id="btn-close-drawer" class="btn btn-secondary" style="padding:2px 6px; font-size:0.75rem;">✕</button>
      </div>
      <div id="drawer-node-meta" style="font-size:0.78rem; color:var(--text-muted); margin-bottom:12px;"></div>
      <div id="drawer-node-links" style="font-size:0.78rem; margin-bottom:12px;"></div>
      <div id="drawer-node-body" style="font-size:0.82rem; color:var(--text-main); white-space:pre-wrap; background:rgba(0,0,0,0.3); padding:10px; border-radius:var(--radius-sm); border:1px solid var(--border-color); flex:1; overflow-y:auto;"></div>
    </div>
  `;

  const viewport = document.getElementById('graph-viewport');
  const drawer = document.getElementById('graph-drawer');
  const drawerTitle = document.getElementById('drawer-node-title');
  const drawerMeta = document.getElementById('drawer-node-meta');
  const drawerLinks = document.getElementById('drawer-node-links');
  const drawerBody = document.getElementById('drawer-node-body');
  const closeBtn = document.getElementById('btn-close-drawer');
  const rebuildBtn = document.getElementById('btn-rebuild-graph');

  closeBtn?.addEventListener('click', () => {
    drawer.style.display = 'none';
  });

  rebuildBtn?.addEventListener('click', async () => {
    rebuildBtn.disabled = true;
    rebuildBtn.textContent = '⏳ Reconstruyendo...';
    try {
      await rebuildGraph();
      loadGraph();
      rebuildBtn.textContent = '✅ Actualizado';
      setTimeout(() => { rebuildBtn.textContent = '🔄 Reconstruir Grafo'; rebuildBtn.disabled = false; }, 1500);
    } catch (e) {
      alert('Error: ' + e.message);
      rebuildBtn.disabled = false;
    }
  });

  async function onNodeClick(node) {
    if (!node || !node.id) return;
    drawer.style.display = 'flex';
    drawerTitle.textContent = node.name || node.id;
    drawerMeta.textContent = 'Cargando detalles del nodo...';
    drawerLinks.innerHTML = '';
    drawerBody.textContent = '';

    try {
      const info = await inspectGraphNode(node.id);
      drawerMeta.innerHTML = `
        <div>Tipo: <strong>${info.type}</strong></div>
        ${info.metadata.size_bytes ? `<div>Tamaño: ${info.metadata.size_bytes} bytes</div>` : ''}
      `;

      if (info.outgoing_links && info.outgoing_links.length > 0) {
        drawerLinks.innerHTML = `<strong>Enlaces Wikilinks:</strong> ` + info.outgoing_links.map(l => `<span class="status-badge" style="font-size:0.7rem; margin-right:4px;">[[${l}]]</span>`).join(' ');
      }

      drawerBody.textContent = info.content || 'Sin contenido Markdown para mostrar.';
    } catch (err) {
      drawerBody.textContent = 'Error al inspeccionar nodo: ' + err.message;
    }
  }

  function loadGraph() {
    if (window.ForceGraph) {
      fetch('/assembled-graph.json')
        .then(res => res.json())
        .then(graphData => {
          viewport.innerHTML = '';
          window.ForceGraph()(viewport)
            .graphData(graphData)
            .nodeLabel('name')
            .nodeAutoColorBy('group')
            .onNodeClick(onNodeClick)
            .backgroundColor('rgba(11, 15, 25, 0.95)');
        })
        .catch(() => {
          viewport.innerHTML = '<div style="padding:20px; color:var(--text-muted)">Grafo vacío. Haz clic en "Reconstruir Grafo" para indexar artefactos.</div>';
        });
    }
  }

  loadGraph();
}
