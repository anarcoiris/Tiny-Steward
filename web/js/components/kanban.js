/**
 * Task & Plan Kanban Board Component - HTML5 Drag & Drop and Bidirectional Sync.
 */

import { fetchTasks, updateTaskStatus, createTask } from '../api.js';

let activeAppState = null;

export function initKanbanComponent(AppState) {
  activeAppState = AppState;
  const container = document.querySelector('.kanban-container');
  if (!container) return;

  setupKanbanHeaders();
  loadKanbanTasks(AppState);
}

function setupKanbanHeaders() {
  const columns = ['backlog', 'todo', 'in_progress', 'review', 'done'];
  
  columns.forEach(colKey => {
    const colId = `kanban-${colKey.replace('_', '-')}`;
    const colEl = document.getElementById(colId);
    if (!colEl) return;

    const parentCol = colEl.closest('.kanban-column');
    if (parentCol && !parentCol.querySelector('.col-action-btn')) {
      const header = parentCol.querySelector('.kanban-header');
      if (header) {
        header.style.display = 'flex';
        header.style.justifyContent = 'space-between';
        header.style.alignItems = 'center';

        const addBtn = document.createElement('button');
        addBtn.className = 'btn btn-secondary col-action-btn';
        addBtn.style.padding = '2px 8px';
        addBtn.style.fontSize = '0.75rem';
        addBtn.textContent = '+ Tarea';
        addBtn.addEventListener('click', () => promptNewTask(colKey));
        header.appendChild(addBtn);
      }
    }

    // Drag & Drop event listeners on drop zone
    colEl.addEventListener('dragover', (e) => {
      e.preventDefault();
      colEl.style.background = 'rgba(255, 255, 255, 0.04)';
      colEl.style.borderRadius = 'var(--radius-sm)';
    });

    colEl.addEventListener('dragleave', () => {
      colEl.style.background = '';
    });

    colEl.addEventListener('drop', async (e) => {
      e.preventDefault();
      colEl.style.background = '';
      const taskId = e.dataTransfer.getData('text/plain');
      if (!taskId) return;

      try {
        await updateTaskStatus(taskId, colKey, activeAppState ? activeAppState.session : 'default');
        loadKanbanTasks(activeAppState);
      } catch (err) {
        console.error('Error updating task status on drop:', err);
      }
    });
  });
}

export async function loadKanbanTasks(AppState) {
  const session = AppState ? AppState.session : 'default';
  const columns = {
    backlog: document.getElementById('kanban-backlog'),
    todo: document.getElementById('kanban-todo'),
    in_progress: document.getElementById('kanban-in-progress'),
    review: document.getElementById('kanban-review'),
    done: document.getElementById('kanban-done')
  };

  try {
    const data = await fetchTasks(session);
    const colsData = data.columns || data;

    Object.keys(columns).forEach(colKey => {
      const colEl = columns[colKey];
      if (!colEl) return;
      colEl.innerHTML = '';

      const tasks = colsData[colKey] || [];
      tasks.forEach(task => {
        const card = document.createElement('div');
        card.className = 'task-card';
        card.setAttribute('draggable', 'true');
        card.dataset.taskId = task.id || task.title;

        card.addEventListener('dragstart', (e) => {
          e.dataTransfer.setData('text/plain', task.id || task.title);
          card.style.opacity = '0.5';
        });

        card.addEventListener('dragend', () => {
          card.style.opacity = '1';
        });

        card.innerHTML = `
          <div class="task-card-title">${escapeHtml(task.title)}</div>
          <div style="font-size:0.72rem; color:var(--text-dim); display:flex; justify-content:space-between; margin-top:6px;">
            <span>📄 ${task.source || 'task.md'}</span>
            <span class="status-badge" style="font-size:0.68rem; padding:1px 6px;">${colKey}</span>
          </div>
        `;
        colEl.appendChild(card);
      });
    });
  } catch (err) {
    console.error('Failed to load Kanban tasks:', err);
  }
}

import { showPromptModal } from '../modal.js';

async function promptNewTask(colKey) {
  const title = await showPromptModal(`Nueva tarea para la columna [${colKey.toUpperCase()}]:`, 'Título de la tarea...');
  if (!title || !title.trim()) return;

  try {
    await createTask(title.trim(), colKey, activeAppState ? activeAppState.session : 'default');
    loadKanbanTasks(activeAppState);
  } catch (err) {
    alert(`Error al crear tarea: ${err.message}`);
  }
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str || '';
  return div.innerHTML;
}
