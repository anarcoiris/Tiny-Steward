/**
 * Task & Plan Kanban Board Component.
 */

import { fetchTasks, updateTaskStatus } from '../api.js';

export function initKanbanComponent(AppState) {
  const columns = {
    backlog: document.getElementById('kanban-backlog'),
    todo: document.getElementById('kanban-todo'),
    in_progress: document.getElementById('kanban-in-progress'),
    review: document.getElementById('kanban-review'),
    done: document.getElementById('kanban-done')
  };

  async function loadTasks() {
    try {
      const data = await fetchTasks();
      renderBoard(data);
    } catch (err) {
      console.error('Failed to load Kanban tasks:', err);
    }
  }

  function renderBoard(data) {
    Object.keys(columns).forEach(colKey => {
      const colEl = columns[colKey];
      if (!colEl) return;
      colEl.innerHTML = '';

      const tasks = data[colKey] || [];
      tasks.forEach(task => {
        const card = document.createElement('div');
        card.className = 'task-card';
        card.innerHTML = `
          <div class="task-card-title">${task.title}</div>
          <div style="font-size:0.75rem; color:var(--text-dim); display:flex; justify-space-between;">
            <span>Source: ${task.source || 'task.md'}</span>
            <span>${task.status}</span>
          </div>
        `;
        colEl.appendChild(card);
      });
    });
  }

  loadTasks();
}
