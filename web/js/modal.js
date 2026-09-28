/**
 * Global In-DOM Glassmorphic Prompt & Confirm Helper.
 * Replaces window.prompt() and window.confirm() which can be blocked by browsers.
 */

export function showPromptModal(title, placeholder = '', defaultValue = '') {
  return new Promise((resolve) => {
    let modal = document.getElementById('global-input-modal');
    if (!modal) {
      modal = document.createElement('div');
      modal.id = 'global-input-modal';
      modal.style.cssText = 'position:fixed; top:0; left:0; width:100vw; height:100vh; background:rgba(0,0,0,0.65); backdrop-filter:blur(6px); z-index:99999; display:flex; align-items:center; justify-content:center;';
      document.body.appendChild(modal);
    }

    modal.innerHTML = `
      <div class="glass-panel" style="width:440px; max-width:92%; padding:20px; display:flex; flex-direction:column; gap:14px; background:rgba(15,23,42,0.95); border:1px solid var(--border-color); box-shadow:0 12px 40px rgba(0,0,0,0.5);">
        <h3 style="font-size:0.95rem; color:var(--accent-blue); margin:0;">${title}</h3>
        <input type="text" id="global-modal-input" class="chat-input" style="height:38px; width:100%;" placeholder="${placeholder}" value="${defaultValue}" />
        <div style="display:flex; justify-content:flex-end; gap:8px;">
          <button id="global-modal-cancel" class="btn btn-secondary" style="font-size:0.8rem; padding:5px 12px;">Cancelar</button>
          <button id="global-modal-confirm" class="btn" style="font-size:0.8rem; padding:5px 14px;">Aceptar</button>
        </div>
      </div>
    `;

    modal.style.display = 'flex';
    const input = document.getElementById('global-modal-input');
    const confirmBtn = document.getElementById('global-modal-confirm');
    const cancelBtn = document.getElementById('global-modal-cancel');

    input.focus();
    input.select();

    function cleanup(val) {
      modal.style.display = 'none';
      resolve(val);
    }

    confirmBtn.onclick = () => cleanup(input.value.trim());
    cancelBtn.onclick = () => cleanup(null);
    input.onkeydown = (e) => {
      if (e.key === 'Enter') cleanup(input.value.trim());
      if (e.key === 'Escape') cleanup(null);
    };
  });
}

export function showConfirmModal(title, message) {
  return new Promise((resolve) => {
    let modal = document.getElementById('global-confirm-modal');
    if (!modal) {
      modal = document.createElement('div');
      modal.id = 'global-confirm-modal';
      modal.style.cssText = 'position:fixed; top:0; left:0; width:100vw; height:100vh; background:rgba(0,0,0,0.65); backdrop-filter:blur(6px); z-index:99999; display:flex; align-items:center; justify-content:center;';
      document.body.appendChild(modal);
    }

    modal.innerHTML = `
      <div class="glass-panel" style="width:400px; max-width:92%; padding:20px; display:flex; flex-direction:column; gap:14px; background:rgba(15,23,42,0.95); border:1px solid var(--border-color); box-shadow:0 12px 40px rgba(0,0,0,0.5);">
        <h3 style="font-size:0.95rem; color:var(--accent-rose); margin:0;">${title}</h3>
        <p style="font-size:0.85rem; color:var(--text-muted); margin:0;">${message}</p>
        <div style="display:flex; justify-content:flex-end; gap:8px;">
          <button id="global-confirm-cancel" class="btn btn-secondary" style="font-size:0.8rem; padding:5px 12px;">Cancelar</button>
          <button id="global-confirm-ok" class="btn" style="font-size:0.8rem; padding:5px 14px; background:var(--accent-rose);">Confirmar</button>
        </div>
      </div>
    `;

    modal.style.display = 'flex';
    const confirmBtn = document.getElementById('global-confirm-ok');
    const cancelBtn = document.getElementById('global-confirm-cancel');

    function cleanup(val) {
      modal.style.display = 'none';
      resolve(val);
    }

    confirmBtn.onclick = () => cleanup(true);
    cancelBtn.onclick = () => cleanup(false);
  });
}
