/**
 * Memory & Knowledge Graph Component.
 */

export function initGraphComponent(AppState) {
  const container = document.getElementById('graph-canvas-container');
  if (!container) return;

  // Render Force Graph if library is present
  if (window.ForceGraph) {
    try {
      fetch('/assembled-graph.json')
        .then(res => res.json())
        .then(graphData => {
          window.ForceGraph()(container)
            .graphData(graphData)
            .nodeLabel('id')
            .nodeAutoColorBy('group')
            .backgroundColor('#0b0f19');
        })
        .catch(() => {
          container.innerHTML = '<div style="padding:20px; color:var(--text-muted)">Graph data loading or empty.</div>';
        });
    } catch (e) {
      container.innerHTML = `<div style="padding:20px; color:var(--text-muted)">${e.message}</div>`;
    }
  }
}
