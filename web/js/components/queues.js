/**
 * Sessions, Mailbox Queues & Background Tasks Dashboard Component.
 */

import { fetchSessionTree, fetchMailboxQueue, fetchBackgroundTasks, killBackgroundTask, fetchTaskLogTail } from '../api.js';

export function initQueuesComponent(AppState) {
  const container = document.getElementById('tab-queues');
  if (!container) return;

  renderQueuesLayout(container);
  loadQueuesData();

  // Auto-refresh every 4 seconds when queues tab is active
  setInterval(() => {
    if (AppState.activeTab === 'queues') {
      loadQueuesData();
    }
  }, 4000);
}

function renderQueuesLayout(container) {
  container.innerHTML = `
    <div class="queues-dashboard-grid" style="display:grid; grid-template-columns: 1fr 1fr; grid-template-rows: auto auto; gap:16px; padding:16px; height:100%; overflow-y:auto;">
      
      <!-- 1. Sessions Hierarchy & Ephemeral Sandboxes -->
      <div class="glass-panel" style="padding:16px; display:flex; flex-direction:column; gap:12px;">
        <div style="display:flex; justify-content:space-between; align-items:center;">
          <h3 style="font-size:0.95rem; color:var(--accent-blue); margin:0;">🗂️ Sessions & Ephemeral Sandboxes</h3>
          <span id="sessions-count-badge" class="badge" style="background:rgba(59,130,246,0.15); color:var(--accent-blue); padding:3px 8px; border-radius:12px; font-size:0.75rem;">0 active</span>
        </div>
        <div id="sessions-tree-list" style="display:flex; flex-direction:column; gap:8px; max-height:280px; overflow-y:auto;">
          <div style="color:var(--text-muted); font-size:0.85rem;">Loading sessions...</div>
        </div>
      </div>

      <!-- 2. Mailbox & Priorities Queue -->
      <div class="glass-panel" style="padding:16px; display:flex; flex-direction:column; gap:12px;">
        <div style="display:flex; justify-content:space-between; align-items:center;">
          <h3 style="font-size:0.95rem; color:var(--accent-amber); margin:0;">📬 Mailbox & Message Priorities</h3>
          <div id="priority-badges-summary" style="display:flex; gap:6px;"></div>
        </div>
        <div id="mailbox-messages-list" style="display:flex; flex-direction:column; gap:8px; max-height:280px; overflow-y:auto;">
          <div style="color:var(--text-muted); font-size:0.85rem;">Loading mailboxes...</div>
        </div>
      </div>

      <!-- 3. Background Tasks Runner Monitor (Full Width) -->
      <div class="glass-panel" style="grid-column: 1 / -1; padding:16px; display:flex; flex-direction:column; gap:12px;">
        <div style="display:flex; justify-content:space-between; align-items:center;">
          <h3 style="font-size:0.95rem; color:var(--accent-green); margin:0;">⚡ Background Tasks Runner (TaskRunner)</h3>
          <span id="tasks-running-badge" class="badge" style="background:rgba(16,185,129,0.15); color:var(--accent-green); padding:3px 8px; border-radius:12px; font-size:0.75rem;">0 running</span>
        </div>
        <div id="tasks-table-container" style="overflow-x:auto;">
          <table style="width:100%; border-collapse:collapse; font-size:0.82rem; text-align:left;">
            <thead>
              <tr style="border-bottom:1px solid rgba(255,255,255,0.1); color:var(--text-muted);">
                <th style="padding:8px;">Task ID</th>
                <th style="padding:8px;">Shell</th>
                <th style="padding:8px;">Command</th>
                <th style="padding:8px;">PID</th>
                <th style="padding:8px;">Runtime</th>
                <th style="padding:8px;">Status</th>
                <th style="padding:8px; text-align:right;">Actions</th>
              </tr>
            </thead>
            <tbody id="tasks-tbody">
              <tr><td colspan="7" style="padding:12px; text-align:center; color:var(--text-muted);">No background tasks running</td></tr>
            </tbody>
          </table>
        </div>
      </div>

    </div>

    <!-- Task Log Modal -->
    <div id="task-log-modal" style="display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.7); z-index:999; justify-content:center; align-items:center;">
      <div class="glass-panel" style="width:750px; max-width:90%; height:500px; display:flex; flex-direction:column; padding:20px; background:#111827; border:1px solid rgba(255,255,255,0.2);">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
          <h3 id="modal-task-title" style="margin:0; font-size:0.95rem; color:var(--accent-blue);">Task Log Output</h3>
          <button id="close-log-modal-btn" class="btn btn-secondary" style="padding:4px 10px;">Close</button>
        </div>
        <pre id="modal-task-log" style="flex:1; background:#030712; padding:12px; border-radius:6px; overflow-y:auto; font-family:monospace; font-size:0.8rem; color:#e5e7eb; white-space:pre-wrap; margin:0;"></pre>
      </div>
    </div>
  `;

  // Close modal handler
  const closeBtn = document.getElementById('close-log-modal-btn');
  const modal = document.getElementById('task-log-modal');
  if (closeBtn && modal) {
    closeBtn.addEventListener('click', () => { modal.style.display = 'none'; });
    modal.addEventListener('click', (e) => { if (e.target === modal) modal.style.display = 'none'; });
  }
}

export async function loadQueuesData() {
  await Promise.allSettled([
    loadSessionsTree(),
    loadMailboxQueue(),
    loadBackgroundTasks(),
  ]);
}

async function loadSessionsTree() {
  const container = document.getElementById('sessions-tree-list');
  const badge = document.getElementById('sessions-count-badge');
  if (!container) return;

  try {
    const data = await fetchSessionTree();
    if (badge) badge.textContent = `${data.total_sessions || 0} sessions`;

    let html = '';
    const current = data.current || 'default';

    // Persistent Sessions
    if (data.persistent_sessions && data.persistent_sessions.length > 0) {
      html += `<div style="font-size:0.75rem; color:var(--text-muted); font-weight:600; text-transform:uppercase; margin-top:4px;">Persistent Sessions</div>`;
      data.persistent_sessions.forEach(s => {
        const isCurrent = s.name === current;
        html += `
          <div style="display:flex; justify-content:space-between; align-items:center; padding:8px 12px; background:rgba(255,255,255,0.03); border:1px solid ${isCurrent ? 'var(--accent-blue)' : 'rgba(255,255,255,0.08)'}; border-radius:6px;">
            <div>
              <span style="font-weight:600; font-size:0.85rem; color:${isCurrent ? 'var(--accent-blue)' : '#f3f4f6'};">
                ${isCurrent ? '📍 ' : ''}${s.name}
              </span>
              <span style="font-size:0.72rem; color:var(--text-muted); margin-left:8px;">${s.turn_count || 0} turns</span>
            </div>
            <span style="font-size:0.72rem; color:var(--text-muted);">${s.workspace ? s.workspace.split(/[\\/]/).pop() : 'default ws'}</span>
          </div>
        `;
      });
    }

    // Ephemeral Sandboxes
    if (data.ephemeral_sessions && data.ephemeral_sessions.length > 0) {
      html += `<div style="font-size:0.75rem; color:var(--accent-amber); font-weight:600; text-transform:uppercase; margin-top:8px;">Ephemeral Sandboxes (Zero Context Carryover)</div>`;
      data.ephemeral_sessions.forEach(e => {
        html += `
          <div style="display:flex; justify-content:space-between; align-items:center; padding:8px 12px; background:rgba(245,158,11,0.06); border:1px solid rgba(245,158,11,0.2); border-radius:6px;">
            <div>
              <span style="font-weight:600; font-size:0.85rem; color:var(--accent-amber);">✨ ${e.name}</span>
              <span style="font-size:0.72rem; color:var(--text-muted); margin-left:8px;">Parent: ${e.parent || 'none'}</span>
            </div>
            <span class="badge" style="background:rgba(245,158,11,0.15); color:var(--accent-amber); font-size:0.7rem; padding:2px 6px; border-radius:8px;">Sandbox</span>
          </div>
        `;
      });
    }

    if (!html) {
      html = `<div style="color:var(--text-muted); font-size:0.85rem;">No active sessions found.</div>`;
    }

    container.innerHTML = html;
  } catch (err) {
    container.innerHTML = `<div style="color:var(--accent-red); font-size:0.8rem;">Error loading sessions: ${err.message}</div>`;
  }
}

async function loadMailboxQueue() {
  const container = document.getElementById('mailbox-messages-list');
  const summary = document.getElementById('priority-badges-summary');
  if (!container) return;

  try {
    const data = await fetchMailboxQueue();
    
    // Priority Badges Summary
    if (summary && data.priority_breakdown) {
      const p = data.priority_breakdown;
      summary.innerHTML = `
        <span style="background:rgba(239,68,68,0.2); color:#ef4444; padding:2px 6px; border-radius:10px; font-size:0.7rem; font-weight:600;">🚨 ${p.urgent || 0}</span>
        <span style="background:rgba(245,158,11,0.2); color:#f59e0b; padding:2px 6px; border-radius:10px; font-size:0.7rem; font-weight:600;">⚡ ${p.high || 0}</span>
        <span style="background:rgba(59,130,246,0.2); color:#3b82f6; padding:2px 6px; border-radius:10px; font-size:0.7rem; font-weight:600;">📫 ${p.normal || 0}</span>
      `;
    }

    const boxes = data.mailboxes || {};
    const boxKeys = Object.keys(boxes);

    if (boxKeys.length === 0) {
      container.innerHTML = `<div style="color:var(--text-muted); font-size:0.85rem; padding:12px; text-align:center;">Inbox is empty (no pending messages)</div>`;
      return;
    }

    let html = '';
    boxKeys.forEach(boxName => {
      const msgs = boxes[boxName];
      html += `
        <div style="border:1px solid rgba(255,255,255,0.08); border-radius:6px; padding:8px 10px; background:rgba(255,255,255,0.02);">
          <div style="font-weight:600; font-size:0.8rem; color:#e5e7eb; margin-bottom:6px; display:flex; justify-content:space-between;">
            <span>📬 ${boxName}</span>
            <span style="color:var(--text-muted); font-size:0.72rem;">${msgs.length} message(s)</span>
          </div>
          <div style="display:flex; flex-direction:column; gap:4px;">
      `;

      msgs.forEach(m => {
        let badgeColor = 'rgba(59,130,246,0.2); color:#3b82f6;';
        if (m.priority === 'urgent') badgeColor = 'rgba(239,68,68,0.2); color:#ef4444;';
        if (m.priority === 'high') badgeColor = 'rgba(245,158,11,0.2); color:#f59e0b;';

        html += `
          <div style="display:flex; justify-content:space-between; align-items:center; font-size:0.78rem; padding:4px 8px; background:rgba(0,0,0,0.2); border-radius:4px;">
            <div style="overflow:hidden; text-overflow:ellipsis; white-space:nowrap; max-width:70%;">
              <span style="font-weight:600; color:#9ca3af;">[${m.from}]:</span>
              <span style="color:#d1d5db;">${m.content_preview}</span>
            </div>
            <span style="background:${badgeColor} font-size:0.68rem; padding:2px 6px; border-radius:6px; font-weight:600; text-transform:uppercase;">${m.priority}</span>
          </div>
        `;
      });

      html += `</div></div>`;
    });

    container.innerHTML = html;
  } catch (err) {
    container.innerHTML = `<div style="color:var(--accent-red); font-size:0.8rem;">Error loading mailboxes: ${err.message}</div>`;
  }
}

async function loadBackgroundTasks() {
  const tbody = document.getElementById('tasks-tbody');
  const badge = document.getElementById('tasks-running-badge');
  if (!tbody) return;

  try {
    const data = await fetchBackgroundTasks();
    if (badge) badge.textContent = `${data.running || 0} running`;

    const tasks = data.tasks || [];
    if (tasks.length === 0) {
      tbody.innerHTML = `<tr><td colspan="7" style="padding:12px; text-align:center; color:var(--text-muted);">No background tasks running</td></tr>`;
      return;
    }

    let html = '';
    tasks.forEach(t => {
      let statusColor = '#10b981'; // green for finished
      if (t.status === 'running') statusColor = '#3b82f6';
      if (t.status === 'failed' || t.status === 'killed') statusColor = '#ef4444';

      html += `
        <tr style="border-bottom:1px solid rgba(255,255,255,0.05);">
          <td style="padding:8px; font-family:monospace; color:#93c5fd;">${t.task_id}</td>
          <td style="padding:8px; color:var(--text-muted);">${t.shell}</td>
          <td style="padding:8px; max-width:250px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;" title="${t.command}">${t.command}</td>
          <td style="padding:8px; color:var(--text-muted);">${t.pid > 0 ? t.pid : '-'}</td>
          <td style="padding:8px; color:var(--text-muted);">${t.runtime_s || 0}s</td>
          <td style="padding:8px;"><span style="color:${statusColor}; font-weight:600; text-transform:uppercase; font-size:0.75rem;">${t.status}</span></td>
          <td style="padding:8px; text-align:right; display:flex; gap:6px; justify-content:flex-end;">
            <button class="btn btn-secondary view-log-btn" data-id="${t.task_id}" style="padding:3px 8px; font-size:0.72rem;">Log</button>
            ${t.status === 'running' ? `<button class="btn btn-danger kill-task-btn" data-id="${t.task_id}" style="padding:3px 8px; font-size:0.72rem; background:#dc2626; color:#fff; border:none; border-radius:4px; cursor:pointer;">Kill</button>` : ''}
          </td>
        </tr>
      `;
    });

    tbody.innerHTML = html;

    // Attach Log and Kill handlers
    tbody.querySelectorAll('.view-log-btn').forEach(btn => {
      btn.addEventListener('click', async () => {
        const taskId = btn.getAttribute('data-id');
        const modal = document.getElementById('task-log-modal');
        const title = document.getElementById('modal-task-title');
        const pre = document.getElementById('modal-task-log');
        if (modal && title && pre) {
          title.textContent = `Task Log: ${taskId}`;
          pre.textContent = 'Loading log output...';
          modal.style.display = 'flex';
          try {
            const logData = await fetchTaskLogTail(taskId, 100);
            pre.textContent = logData.output || 'Log is empty.';
          } catch (e) {
            pre.textContent = `Failed to load log: ${e.message}`;
          }
        }
      });
    });

    tbody.querySelectorAll('.kill-task-btn').forEach(btn => {
      btn.addEventListener('click', async () => {
        const taskId = btn.getAttribute('data-id');
        if (confirm(`Kill background task ${taskId}?`)) {
          try {
            await killBackgroundTask(taskId);
            loadBackgroundTasks();
          } catch (e) {
            alert(`Error killing task: ${e.message}`);
          }
        }
      });
    });

  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="7" style="padding:12px; text-align:center; color:var(--accent-red);">Error loading tasks: ${err.message}</td></tr>`;
  }
}
