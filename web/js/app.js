/**
 * Main Application Router & State Manager - Tiny Steward Web IDE.
 */

import { fetchSessions, switchSession } from './api.js';
import { initChatComponent } from './components/chat.js';
import { initEditorComponent } from './components/editor.js';
import { initKanbanComponent } from './components/kanban.js';
import { initGraphComponent } from './components/graph.js';
import { initTelemetryComponent } from './components/telemetry.js';

export const AppState = {
  activeTab: 'chat',
  session: 'default',
  isStreaming: false,
  sessions: []
};

document.addEventListener('DOMContentLoaded', () => {
  initTabs();
  initSessionSelector();

  // Initialize components
  initChatComponent(AppState);
  initEditorComponent(AppState);
  initKanbanComponent(AppState);
  initGraphComponent(AppState);
  initTelemetryComponent(AppState);
});

function initTabs() {
  const tabBtns = document.querySelectorAll('.tab-btn');
  const tabContents = document.querySelectorAll('.tab-content');

  tabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      const targetTab = btn.getAttribute('data-tab');
      if (!targetTab) return;

      tabBtns.forEach(b => b.classList.remove('active'));
      tabContents.forEach(c => c.classList.remove('active'));

      btn.classList.add('active');
      const targetEl = document.getElementById(`tab-${targetTab}`);
      if (targetEl) targetEl.classList.add('active');

      AppState.activeTab = targetTab;
    });
  });
}

async function initSessionSelector() {
  const select = document.getElementById('session-select');
  if (!select) return;

  try {
    const data = await fetchSessions();
    AppState.sessions = data.sessions || [];
    AppState.session = data.current || 'default';

    select.innerHTML = '';
    AppState.sessions.forEach(sName => {
      const opt = document.createElement('option');
      opt.value = sName;
      opt.textContent = sName;
      if (sName === AppState.session) opt.selected = true;
      select.appendChild(opt);
    });

    select.addEventListener('change', async (e) => {
      const newSession = e.target.value;
      try {
        await switchSession(newSession);
        AppState.session = newSession;
        console.log(`Switched to session: ${newSession}`);
      } catch (err) {
        alert(`Failed to switch session: ${err.message}`);
      }
    });
  } catch (err) {
    console.error('Session init error:', err);
  }
}
