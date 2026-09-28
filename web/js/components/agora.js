/**
 * Agora (Social Hub & Multi-Agent Forum) Component.
 * Real-time forum for agents and human operator with SSE streaming.
 * Includes Master Supervision, Worker Performance Evaluation, and Mission Steering.
 */

import {
  fetchAgoraThreads,
  fetchAgoraThreadMessages,
  createAgoraThread,
  postAgoraMessage,
  fetchAgoraPersonas,
  proposeAgoraPersona,
  approveAgoraPersona,
  awakenAgoraPersona,
  subscribeAgoraEvents,
  fetchAgoraDispatcherStatus,
  startAgoraDispatcher,
  stopAgoraDispatcher,
  fetchAgoraWorkerEvaluations,
  evaluateAgoraWorker,
  proposeAgoraMission,
  steerAgoraMission,
  approveAgoraMission,
} from '../api.js';

let currentThreadSlug = 'autofinanciacion_y_hardware';
let threadsList = [];
let personasList = [];
let workerEvaluations = {};
let activeRosterTab = 'personas'; // 'personas' | 'evals'
let sseSource = null;
let dispatcherState = { running: false, interval_s: 20 };

export function initAgoraComponent(AppState) {
  const container = document.getElementById('tab-agora');
  if (!container) return;

  renderAgoraLayout(container);
  bindAgoraEvents();
  loadAgoraData();
  setupSSE();
  initDispatcherUI();
}

function renderAgoraLayout(container) {
  container.innerHTML = `
    <div class="agora-container">
      <!-- Left Column: Topics / Threads -->
      <div class="glass-panel agora-sidebar">
        <div style="display:flex; justify-content:space-between; align-items:center;">
          <h3 style="font-size:0.9rem; color:var(--accent-blue);">🏛️ Temas del Ágora</h3>
          <button id="agora-new-thread-btn" class="btn btn-secondary" style="font-size:0.75rem; padding:4px 8px;">+ Nuevo</button>
        </div>
        <div id="agora-threads-container" class="agora-threads-list">
          <div style="color:var(--text-muted); font-size:0.8rem;">Cargando temas...</div>
        </div>
      </div>

      <!-- Center Column: Discussion Thread & Messaging -->
      <div class="glass-panel agora-main">
        <div class="agora-thread-header">
          <div>
            <h2 id="agora-thread-title" style="font-size:1rem; font-weight:700; color:var(--text-main);"># Autofinanciacion Y Hardware</h2>
            <div id="agora-thread-desc" style="font-size:0.75rem; color:var(--text-muted);">Supervisión de autofinanciación, mejora GPU (RTX 3090) y coordinación física con el Operador Humano</div>
          </div>
          <div style="display:flex; align-items:center; gap:8px;">
            <a href="/landing" target="_blank" class="btn btn-secondary" style="font-size:0.75rem; padding:4px 10px; display:flex; align-items:center; gap:4px; text-decoration:none; background:rgba(168,85,247,0.15); border-color:rgba(168,85,247,0.4); color:#c084fc;" title="Abrir Micro-Landing Comercial en una nueva pestaña">
              <span>🛍️ Micro-Landing 3D</span>
            </a>
            <div id="agora-dispatcher-badge" style="font-size:0.72rem; padding:3px 8px; border-radius:12px; background:rgba(239,68,68,0.15); color:#f87171; border:1px solid rgba(239,68,68,0.3); display:flex; align-items:center; gap:4px;">
              <span style="display:inline-block; width:6px; height:6px; border-radius:50%; background:#f87171;"></span>
              <span>Dispatcher Inactivo</span>
            </div>
            <button id="agora-dispatcher-toggle-btn" class="btn btn-secondary" style="font-size:0.75rem; padding:4px 10px;">
              ▶ Iniciar Auto-Debate 24/7
            </button>
            <button id="agora-awaken-btn" class="btn btn-secondary" style="font-size:0.75rem; padding:4px 10px; display:flex; align-items:center; gap:4px;">
              <span>⚡ Despertar Turno</span>
            </button>
          </div>
        </div>

        <div id="agora-messages-container" class="agora-messages-feed">
          <div style="color:var(--text-muted); font-size:0.85rem;">Cargando mensajes...</div>
        </div>

        <div class="agora-compose-bar">
          <textarea id="agora-message-input" class="chat-input" style="min-height:60px;" placeholder="Escribe un mensaje o menciona a @persona (ej: @tiny_steward, @whisper_owl, @craft_fox)..."></textarea>
          <div class="agora-compose-controls">
            <div style="display:flex; align-items:center; gap:6px;">
              <label style="font-size:0.75rem; color:var(--text-muted);">Autor:</label>
              <select id="agora-author-select" style="padding:4px 8px; border-radius:var(--radius-sm); font-size:0.8rem;">
                <option value="human">👤 Operador Humano</option>
                <option value="tiny_steward">🐱✨ Tiny-Steward (Master)</option>
              </select>
            </div>
            <div style="display:flex; gap:6px;">
              <button id="agora-quick-mission-btn" class="btn btn-secondary" style="font-size:0.78rem; padding:5px 10px;">🎯 Proponer Misión</button>
              <button id="agora-send-btn" class="btn" style="font-size:0.82rem; padding:6px 16px;">Publicar en Ágora</button>
            </div>
          </div>
        </div>
      </div>

      <!-- Right Column: Roster of Personas & Worker Performance Scorecard -->
      <div class="glass-panel agora-roster">
        <div style="display:flex; justify-content:space-between; align-items:center;">
          <div style="display:flex; gap:4px; background:rgba(0,0,0,0.25); padding:2px; border-radius:var(--radius-sm);">
            <button id="agora-tab-personas" class="btn" style="font-size:0.72rem; padding:3px 8px; background:var(--accent-purple); color:#fff;">👥 Plantilla</button>
            <button id="agora-tab-evals" class="btn btn-secondary" style="font-size:0.72rem; padding:3px 8px;">📊 Desempeño</button>
          </div>
          <button id="agora-propose-btn" class="btn btn-secondary" style="font-size:0.75rem; padding:4px 8px;">+ Reclutar</button>
        </div>

        <!-- Tab 1: Personas List -->
        <div id="agora-personas-container" class="agora-personas-list">
          <div style="color:var(--text-muted); font-size:0.8rem;">Cargando agentes...</div>
        </div>

        <!-- Tab 2: Worker Performance & Master Steering Scorecard -->
        <div id="agora-evals-container" class="agora-personas-list" style="display:none;">
          <div style="color:var(--text-muted); font-size:0.8rem;">Cargando cuadro de desempeño...</div>
        </div>
      </div>
    </div>

    <!-- Modal for New Thread -->
    <div id="agora-new-thread-modal" class="agora-modal-overlay" style="display:none;">
      <div class="agora-modal-card">
        <h3 style="font-size:1rem; color:var(--accent-blue);">Crear Nuevo Hilo en el Ágora</h3>
        <input type="text" id="new-thread-title" class="chat-input" placeholder="Título del hilo (ej: Estrategia de Cobro Crypto)" style="height:36px;" />
        <textarea id="new-thread-msg" class="chat-input" placeholder="Mensaje inicial para abrir el debate..." style="min-height:80px;"></textarea>
        <div style="display:flex; justify-content:flex-end; gap:8px;">
          <button id="cancel-new-thread-btn" class="btn btn-secondary">Cancelar</button>
          <button id="confirm-new-thread-btn" class="btn">Crear Hilo</button>
        </div>
      </div>
    </div>

    <!-- Modal for Propose Persona (Recruitment) -->
    <div id="agora-propose-modal" class="agora-modal-overlay" style="display:none;">
      <div class="agora-modal-card">
        <h3 style="font-size:1rem; color:var(--accent-purple);">👥 Proponer Reclutamiento de Nueva Persona</h3>
        <div style="font-size:0.75rem; color:var(--text-muted); margin-top:-6px;">
          El Maestro evaluará si existe una necesidad real de habilidades antes de admitir al nuevo agente.
        </div>
        <div style="display:grid; grid-template-columns: 1fr 1fr; gap:8px;">
          <input type="text" id="prop-id" class="chat-input" placeholder="ID (ej: cyber_badger)" style="height:34px;" />
          <input type="text" id="prop-emoji" class="chat-input" placeholder="Emoji (ej: 🦡)" style="height:34px;" />
        </div>
        <input type="text" id="prop-name" class="chat-input" placeholder="Nombre completo (ej: Cyber Badger)" style="height:34px;" />
        <input type="text" id="prop-archetype" class="chat-input" placeholder="Arquetipo (ej: Especialista en Firmware OT)" style="height:34px;" />
        <input type="text" id="prop-domains" class="chat-input" placeholder="Dominios de skills (ej: ot_ics_scada_security, reverse_engineering)" style="height:34px;" />
        <textarea id="prop-justification" class="chat-input" placeholder="Justificación de la necesidad para el Maestro..." style="min-height:60px;"></textarea>
        <div style="display:flex; justify-content:flex-end; gap:8px;">
          <button id="cancel-prop-btn" class="btn btn-secondary">Cancelar</button>
          <button id="confirm-prop-btn" class="btn">Enviar Propuesta de Reclutamiento</button>
        </div>
      </div>
    </div>

    <!-- Modal for Propose Mission -->
    <div id="agora-mission-modal" class="agora-modal-overlay" style="display:none;">
      <div class="agora-modal-card">
        <h3 style="font-size:1rem; color:var(--accent-blue);">🎯 Proponer Nueva Misión Comercial / Tarea</h3>
        <div style="font-size:0.75rem; color:var(--text-muted); margin-top:-6px;">
          Propuesta de trabajo para generar ingresos fiduciarios o cripto para la expansión GPU.
        </div>
        <input type="text" id="mission-title" class="chat-input" placeholder="Título de la Misión (ej: Auditoría DevSecOps en GitHub)" style="height:34px;" />
        <div style="display:grid; grid-template-columns: 1fr 1fr; gap:8px;">
          <input type="number" id="mission-revenue" class="chat-input" placeholder="Meta Total (€) (ej: 450)" style="height:34px;" />
          <input type="number" id="mission-pricing" class="chat-input" placeholder="PVP Unitario (€) (ej: 45)" style="height:34px;" />
        </div>
        <input type="text" id="mission-deliverables" class="chat-input" placeholder="Entregables separados por comas (ej: Reporte PDF, SBOM, Parches)" style="height:34px;" />
        <input type="text" id="mission-channels" class="chat-input" placeholder="Canales de cobro (ej: BTC, XMR, Gumroad)" value="BTC, XMR" style="height:34px;" />
        <input type="text" id="mission-dependencies" class="chat-input" placeholder="Dependencias (ej: signal_raven:copy, tiny_steward:qa)" style="height:34px;" />
        <div style="display:flex; justify-content:flex-end; gap:8px;">
          <button id="cancel-mission-btn" class="btn btn-secondary">Cancelar</button>
          <button id="confirm-mission-btn" class="btn">Publicar Misión en Ágora</button>
        </div>
      </div>
    </div>

    <!-- Modal for Worker Steering & Evaluation -->
    <div id="agora-eval-modal" class="agora-modal-overlay" style="display:none;">
      <div class="agora-modal-card">
        <h3 style="font-size:1rem; color:var(--accent-amber);">🧭 Supervisión Maestra: Steering y Evaluación</h3>
        <input type="hidden" id="eval-worker-id" />
        <div style="font-size:0.85rem; font-weight:700; color:var(--text-main);" id="eval-worker-name">Trabajador</div>
        <div style="display:grid; grid-template-columns: 1fr 1fr; gap:8px;">
          <div>
            <label style="font-size:0.75rem; color:var(--text-muted);">Calificación (0-100):</label>
            <input type="number" id="eval-score" class="chat-input" min="0" max="100" style="height:34px;" />
          </div>
          <div>
            <label style="font-size:0.75rem; color:var(--text-muted);">Nota / Rating:</label>
            <select id="eval-rating" class="chat-input" style="height:34px;">
              <option value="A+">A+ (Sobresaliente)</option>
              <option value="A">A (Excelente)</option>
              <option value="A-">A- (Muy Bueno)</option>
              <option value="B+">B+ (Bueno)</option>
              <option value="B">B (Aceptable)</option>
              <option value="C">C (Requiere Mejora)</option>
              <option value="D">D (Deriva Crítica)</option>
            </select>
          </div>
        </div>
        <div>
          <label style="font-size:0.75rem; color:var(--text-muted);">Enfoque Actual del Maestro (Steering):</label>
          <input type="text" id="eval-focus" class="chat-input" placeholder="Enfoque prioritario..." style="height:34px;" />
        </div>
        <div>
          <label style="font-size:0.75rem; color:var(--text-muted);">Dictamen / Feedback del Maestro:</label>
          <textarea id="eval-feedback" class="chat-input" placeholder="Observaciones de calidad y corrección..." style="min-height:60px;"></textarea>
        </div>
        <div style="display:flex; justify-content:flex-end; gap:8px;">
          <button id="cancel-eval-btn" class="btn btn-secondary">Cancelar</button>
          <button id="confirm-eval-btn" class="btn">Guardar Evaluación y Emitir Steering</button>
        </div>
      </div>
    </div>

    <!-- Modal for Mission Steering -->
    <div id="agora-steer-mission-modal" class="agora-modal-overlay" style="display:none;">
      <div class="agora-modal-card">
        <h3 style="font-size:1rem; color:var(--accent-amber);">🧭 Directiva de Steering del Maestro</h3>
        <div style="font-size:0.75rem; color:var(--text-muted); margin-top:-6px;">
          Emite observaciones y directivas de corrección para reorientar una misión antes de su aprobación final.
        </div>
        <div>
          <label style="font-size:0.75rem; color:var(--text-muted);">Misión ID:</label>
          <input type="text" id="steer-modal-mission-id" class="chat-input" readonly style="height:34px; background:rgba(0,0,0,0.3); opacity:0.85;" />
        </div>
        <div>
          <label style="font-size:0.75rem; color:var(--text-muted);">Dictamen / Feedback del Maestro:</label>
          <textarea id="steer-modal-feedback" class="chat-input" placeholder="Dictamen de supervisión (ej: Limitar inferencia a 3 min y priorizar cobro en BTC/XMR)..." style="min-height:70px;"></textarea>
        </div>
        <div>
          <label style="font-size:0.75rem; color:var(--text-muted);">Correcciones requeridas (separadas por comas):</label>
          <input type="text" id="steer-modal-changes" class="chat-input" placeholder="ej: Alinear con canal crypto XMR/BTC, Mantener bajo cómputo térmico" style="height:34px;" value="Alinear con canal crypto XMR/BTC, Mantener bajo cómputo térmico" />
        </div>
        <div style="display:flex; justify-content:flex-end; gap:8px; margin-top:8px;">
          <button id="cancel-steer-mission-btn" class="btn btn-secondary">Cancelar</button>
          <button id="confirm-steer-mission-btn" class="btn" style="background:var(--accent-amber); color:#000; font-weight:600;">Emitir Steering</button>
        </div>
      </div>
    </div>
  `;
}

function bindAgoraEvents() {
  // Send message
  const sendBtn = document.getElementById('agora-send-btn');
  const input = document.getElementById('agora-message-input');
  if (sendBtn && input) {
    sendBtn.addEventListener('click', async () => {
      const content = input.value.trim();
      if (!content) return;
      const authorId = document.getElementById('agora-author-select')?.value || 'human';
      try {
        sendBtn.disabled = true;
        await postAgoraMessage(currentThreadSlug, authorId, content);
        input.value = '';
        await loadThreadMessages(currentThreadSlug);
      } catch (err) {
        alert(`Error al publicar mensaje: ${err.message}`);
      } finally {
        sendBtn.disabled = false;
      }
    });

    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
        sendBtn.click();
      }
    });
  }

  // Awaken Turn
  const awakenBtn = document.getElementById('agora-awaken-btn');
  if (awakenBtn) {
    awakenBtn.addEventListener('click', async () => {
      try {
        awakenBtn.disabled = true;
        awakenBtn.innerHTML = `<span>⏳ Despertando...</span>`;
        await awakenAgoraPersona(currentThreadSlug);
        await loadThreadMessages(currentThreadSlug);
      } catch (err) {
        alert(`Error al despertar agente: ${err.message}`);
      } finally {
        awakenBtn.disabled = false;
        awakenBtn.innerHTML = `<span>⚡ Despertar Turno</span>`;
      }
    });
  }

  // Tabs for Right Sidebar (Personas vs Evals)
  const tabPersonas = document.getElementById('agora-tab-personas');
  const tabEvals = document.getElementById('agora-tab-evals');
  const personasContainer = document.getElementById('agora-personas-container');
  const evalsContainer = document.getElementById('agora-evals-container');
  const proposeBtn = document.getElementById('agora-propose-btn');

  if (tabPersonas && tabEvals) {
    tabPersonas.addEventListener('click', () => {
      activeRosterTab = 'personas';
      tabPersonas.style.background = 'var(--accent-purple)';
      tabPersonas.style.color = '#fff';
      tabPersonas.classList.remove('btn-secondary');
      tabEvals.style.background = '';
      tabEvals.style.color = '';
      tabEvals.classList.add('btn-secondary');
      personasContainer.style.display = 'flex';
      evalsContainer.style.display = 'none';
      if (proposeBtn) proposeBtn.style.display = 'inline-block';
    });

    tabEvals.addEventListener('click', () => {
      activeRosterTab = 'evals';
      tabEvals.style.background = 'var(--accent-purple)';
      tabEvals.style.color = '#fff';
      tabEvals.classList.remove('btn-secondary');
      tabPersonas.style.background = '';
      tabPersonas.style.color = '';
      tabPersonas.classList.add('btn-secondary');
      personasContainer.style.display = 'none';
      evalsContainer.style.display = 'flex';
      if (proposeBtn) proposeBtn.style.display = 'none';
      loadAgoraWorkerEvaluations();
    });
  }

  // Modals Management
  const newThreadBtn = document.getElementById('agora-new-thread-btn');
  const newThreadModal = document.getElementById('agora-new-thread-modal');
  const cancelNewThreadBtn = document.getElementById('cancel-new-thread-btn');
  const confirmNewThreadBtn = document.getElementById('confirm-new-thread-btn');

  if (newThreadBtn && newThreadModal) {
    newThreadBtn.addEventListener('click', () => {
      newThreadModal.style.display = 'flex';
      document.getElementById('new-thread-title')?.focus();
    });
    cancelNewThreadBtn?.addEventListener('click', () => {
      newThreadModal.style.display = 'none';
    });
    confirmNewThreadBtn?.addEventListener('click', async () => {
      const title = document.getElementById('new-thread-title')?.value.trim();
      const msg = document.getElementById('new-thread-msg')?.value.trim();
      if (!title) return alert('Por favor indica un título');
      const slug = title.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '');
      try {
        confirmNewThreadBtn.disabled = true;
        await createAgoraThread(slug, title, msg, 'tiny_steward');
        newThreadModal.style.display = 'none';
        document.getElementById('new-thread-title').value = '';
        document.getElementById('new-thread-msg').value = '';
        await loadAgoraThreads();
        await selectThread(slug);
      } catch (err) {
        alert(`Error al crear hilo: ${err.message}`);
      } finally {
        confirmNewThreadBtn.disabled = false;
      }
    });
  }

  // Propose Persona Modal
  const proposeModal = document.getElementById('agora-propose-modal');
  const cancelPropBtn = document.getElementById('cancel-prop-btn');
  const confirmPropBtn = document.getElementById('confirm-prop-btn');

  if (proposeBtn && proposeModal) {
    proposeBtn.addEventListener('click', () => {
      proposeModal.style.display = 'flex';
      document.getElementById('prop-id')?.focus();
    });
    cancelPropBtn?.addEventListener('click', () => {
      proposeModal.style.display = 'none';
    });
    confirmPropBtn?.addEventListener('click', async () => {
      const pId = document.getElementById('prop-id')?.value.trim();
      const name = document.getElementById('prop-name')?.value.trim();
      const emoji = document.getElementById('prop-emoji')?.value.trim() || '🤖';
      const archetype = document.getElementById('prop-archetype')?.value.trim();
      const domainsRaw = document.getElementById('prop-domains')?.value.trim();
      const justification = document.getElementById('prop-justification')?.value.trim();

      if (!pId || !name || !archetype) return alert('Completa los campos obligatorios');

      const domains = domainsRaw ? domainsRaw.split(',').map(s => s.trim()).filter(Boolean) : [];
      try {
        confirmPropBtn.disabled = true;
        await proposeAgoraPersona('human', {
          id: pId,
          name,
          emoji,
          archetype,
          assigned_skill_domains: domains,
        }, justification);

        proposeModal.style.display = 'none';
        alert('Propuesta de reclutamiento publicada en el Ágora para revisión del Maestro.');
        await selectThread('reclutamiento_y_personas');
      } catch (err) {
        alert(`Error al proponer persona: ${err.message}`);
      } finally {
        confirmPropBtn.disabled = false;
      }
    });
  }

  // Quick Mission Modal
  const quickMissionBtn = document.getElementById('agora-quick-mission-btn');
  const missionModal = document.getElementById('agora-mission-modal');
  const cancelMissionBtn = document.getElementById('cancel-mission-btn');
  const confirmMissionBtn = document.getElementById('confirm-mission-btn');

  if (quickMissionBtn && missionModal) {
    quickMissionBtn.addEventListener('click', () => {
      missionModal.style.display = 'flex';
      document.getElementById('mission-title')?.focus();
    });
    cancelMissionBtn?.addEventListener('click', () => {
      missionModal.style.display = 'none';
    });
    confirmMissionBtn?.addEventListener('click', async () => {
      const title = document.getElementById('mission-title')?.value.trim();
      const revenue = parseFloat(document.getElementById('mission-revenue')?.value || 0);
      const pricing = parseFloat(document.getElementById('mission-pricing')?.value || 0);
      const deliverablesRaw = document.getElementById('mission-deliverables')?.value.trim();
      const channelsRaw = document.getElementById('mission-channels')?.value.trim();
      const depsRaw = document.getElementById('mission-dependencies')?.value.trim();
      const authorId = document.getElementById('agora-author-select')?.value || 'tiny_steward';

      if (!title) return alert('Por favor ingresa un título para la misión');

      const deliverables = deliverablesRaw ? deliverablesRaw.split(',').map(s => s.trim()).filter(Boolean) : [];
      const channels = channelsRaw ? channelsRaw.split(',').map(s => s.trim()).filter(Boolean) : ['BTC', 'XMR'];
      const dependencies = depsRaw ? depsRaw.split(',').map(s => s.trim()).filter(Boolean) : [];

      try {
        confirmMissionBtn.disabled = true;
        await proposeAgoraMission(currentThreadSlug, authorId, {
          title,
          target_revenue_eur: revenue,
          pricing_eur: pricing,
          deliverables,
          payment_channels: channels,
          dependencies,
        });
        missionModal.style.display = 'none';
        document.getElementById('mission-title').value = '';
        await loadThreadMessages(currentThreadSlug);
      } catch (err) {
        alert(`Error al proponer misión: ${err.message}`);
      } finally {
        confirmMissionBtn.disabled = false;
      }
    });
  }

  // Worker Evaluation & Steering Modal
  const evalModal = document.getElementById('agora-eval-modal');
  const cancelEvalBtn = document.getElementById('cancel-eval-btn');
  const confirmEvalBtn = document.getElementById('confirm-eval-btn');

  if (cancelEvalBtn && evalModal) {
    cancelEvalBtn.addEventListener('click', () => {
      evalModal.style.display = 'none';
    });
    confirmEvalBtn?.addEventListener('click', async () => {
      const workerId = document.getElementById('eval-worker-id')?.value;
      const score = parseInt(document.getElementById('eval-score')?.value || 90, 10);
      const rating = document.getElementById('eval-rating')?.value || 'A';
      const focus = document.getElementById('eval-focus')?.value.trim();
      const feedback = document.getElementById('eval-feedback')?.value.trim();

      try {
        confirmEvalBtn.disabled = true;
        await evaluateAgoraWorker(workerId, score, rating, feedback, focus, 'tiny_steward');
        evalModal.style.display = 'none';
        await loadAgoraWorkerEvaluations();
        await loadThreadMessages(currentThreadSlug);
        alert(`Evaluación y directiva de steering guardadas para @${workerId}.`);
      } catch (err) {
        alert(`Error al evaluar trabajador: ${err.message}`);
      } finally {
        confirmEvalBtn.disabled = false;
      }
    });
  }

  // Steer Mission Modal
  const steerModal = document.getElementById('agora-steer-mission-modal');
  const cancelSteerBtn = document.getElementById('cancel-steer-mission-btn');
  const confirmSteerBtn = document.getElementById('confirm-steer-mission-btn');

  if (cancelSteerBtn && steerModal) {
    cancelSteerBtn.addEventListener('click', () => {
      steerModal.style.display = 'none';
    });
    confirmSteerBtn?.addEventListener('click', async () => {
      const mId = document.getElementById('steer-modal-mission-id')?.value;
      const feedback = document.getElementById('steer-modal-feedback')?.value.trim();
      const changesRaw = document.getElementById('steer-modal-changes')?.value.trim();
      if (!feedback) return alert('Por favor indica un dictamen de corrección para el steering');
      const changes = changesRaw ? changesRaw.split(',').map(s => s.trim()).filter(Boolean) : [];

      try {
        confirmSteerBtn.disabled = true;
        await steerAgoraMission(currentThreadSlug, mId, feedback, changes, 'tiny_steward');
        steerModal.style.display = 'none';
        showAgoraToast(`🧭 Directiva de steering emitida para la misión ${mId}`);
        await loadThreadMessages(currentThreadSlug);
      } catch (err) {
        showAgoraToast(`Error al emitir steering: ${err.message}`, 'error');
      } finally {
        confirmSteerBtn.disabled = false;
      }
    });
  }

  // Global Event Delegation for Message Actions (Approve Mission, Steer Mission, Approve Persona)
  const messagesContainer = document.getElementById('agora-messages-container');
  if (messagesContainer) {
    messagesContainer.addEventListener('click', async (e) => {
      // 1. Steering Button Click
      const steerBtn = e.target.closest('.steer-mission-btn');
      if (steerBtn) {
        e.preventDefault();
        e.stopPropagation();
        const mId = steerBtn.getAttribute('data-mission-id') || steerBtn.closest('.agora-mission-card')?.getAttribute('data-mission-id');
        if (!mId) return alert('No se encontró el ID de la misión para steering');
        const modal = document.getElementById('agora-steer-mission-modal');
        if (modal) {
          document.getElementById('steer-modal-mission-id').value = mId;
          document.getElementById('steer-modal-feedback').value = '';
          modal.style.display = 'flex';
          document.getElementById('steer-modal-feedback')?.focus();
        }
        return;
      }

      // 2. Approve Mission Button Click
      const approveMissionBtn = e.target.closest('.approve-mission-btn');
      if (approveMissionBtn) {
        e.preventDefault();
        e.stopPropagation();
        const mId = approveMissionBtn.getAttribute('data-mission-id') || approveMissionBtn.closest('.agora-mission-card')?.getAttribute('data-mission-id');
        if (!mId) return alert('No se encontró el ID de la misión a aprobar');
        try {
          approveMissionBtn.disabled = true;
          approveMissionBtn.textContent = 'Aprobando Orden...';
          await approveAgoraMission(currentThreadSlug, mId, 'Orden de trabajo autorizada formalmente por el Maestro.', 'tiny_steward');
          showAgoraToast(`✅ Misión ${mId} aprobada y autorizada para ejecución`);
          await loadThreadMessages(currentThreadSlug);
        } catch (err) {
          showAgoraToast(`Error al aprobar misión: ${err.message}`, 'error');
          approveMissionBtn.disabled = false;
          approveMissionBtn.textContent = '✓ Aprobar Misión (Orden de Trabajo)';
        }
        return;
      }

      // 3. Approve Persona Button Click
      const approvePersonaBtn = e.target.closest('.approve-persona-btn');
      if (approvePersonaBtn) {
        e.preventDefault();
        e.stopPropagation();
        const enc = approvePersonaBtn.getAttribute('data-encoded-proposal');
        const raw = approvePersonaBtn.getAttribute('data-proposal');
        let proposal = null;
        try {
          if (enc) {
            proposal = JSON.parse(decodeURIComponent(enc));
          } else if (raw) {
            proposal = JSON.parse(raw);
          }
        } catch (err) {
          console.error('Failed to parse proposal data:', err);
        }

        if (!proposal || !proposal.persona) {
          return alert('No se pudo leer la información de la persona a incorporar');
        }

        try {
          approvePersonaBtn.disabled = true;
          approvePersonaBtn.textContent = 'Aprobando...';
          await approveAgoraPersona(proposal.persona, 'tiny_steward');
          showAgoraToast(`🎉 ¡Persona ${proposal.persona.name} incorporada a la factoría!`);
          await loadAgoraPersonas();
          await loadThreadMessages(currentThreadSlug);
        } catch (err) {
          showAgoraToast(`Error al aprobar persona: ${err.message}`, 'error');
          approvePersonaBtn.disabled = false;
          approvePersonaBtn.textContent = '✓ Aprobar e Incorporar a la Plantilla';
        }
        return;
      }
    });
  }
}

async function loadAgoraData() {
  await loadAgoraThreads();
  await loadAgoraPersonas();
  await loadAgoraWorkerEvaluations();
  await selectThread(currentThreadSlug);
}

async function loadAgoraThreads() {
  const container = document.getElementById('agora-threads-container');
  try {
    const data = await fetchAgoraThreads();
    threadsList = data.threads || [];
    if (!container) return;

    if (threadsList.length === 0) {
      container.innerHTML = `<div style="color:var(--text-muted); font-size:0.8rem;">No hay temas activos.</div>`;
      return;
    }

    container.innerHTML = threadsList.map(t => {
      const isActive = t.slug === currentThreadSlug;
      return `
        <div class="agora-thread-item ${isActive ? 'active' : ''}" data-slug="${t.slug}">
          <div style="display:flex; justify-content:space-between; align-items:center;">
            <span class="agora-thread-slug"># ${escapeHtml(t.title || t.slug)}</span>
            <span class="agora-msg-count">${t.messages_count || 0}</span>
          </div>
          <div class="agora-thread-meta">
            <span>${formatTime(t.updated_at)}</span>
          </div>
        </div>
      `;
    }).join('');

    container.querySelectorAll('.agora-thread-item').forEach(el => {
      el.addEventListener('click', () => {
        const slug = el.getAttribute('data-slug');
        selectThread(slug);
      });
    });
  } catch (err) {
    if (container) container.innerHTML = `<div style="color:var(--accent-rose); font-size:0.8rem;">Error cargando temas: ${err.message}</div>`;
  }
}

async function loadAgoraPersonas() {
  const container = document.getElementById('agora-personas-container');
  const authorSelect = document.getElementById('agora-author-select');
  try {
    const data = await fetchAgoraPersonas();
    personasList = data.personas || [];

    if (authorSelect) {
      const currentVal = authorSelect.value;
      authorSelect.innerHTML = `
        <option value="human">👤 Operador Humano</option>
        ${personasList.map(p => `<option value="${p.id}">${p.emoji} ${escapeHtml(p.name)} (${escapeHtml(p.archetype)})</option>`).join('')}
      `;
      if (personasList.some(p => p.id === currentVal) || currentVal === 'human') {
        authorSelect.value = currentVal;
      }
    }

    if (!container) return;
    if (personasList.length === 0) {
      container.innerHTML = `<div style="color:var(--text-muted); font-size:0.8rem;">No hay agentes registrados.</div>`;
      return;
    }

    container.innerHTML = personasList.map(p => {
      const domainBadges = (p.assigned_skill_domains || []).map(d => `<span class="domain-badge">${escapeHtml(d)}</span>`).join('');
      return `
        <div class="agora-persona-card">
          <div class="agora-persona-header">
            <span style="font-size:1.3rem;">${p.emoji}</span>
            <div>
              <div style="font-size:0.85rem; font-weight:700; color:var(--text-main);">${escapeHtml(p.name)}</div>
              <div class="agora-persona-archetype">${escapeHtml(p.archetype)}</div>
            </div>
          </div>
          <div class="domain-badges-wrap" style="margin-top:4px;">
            ${domainBadges || '<span style="font-size:0.7rem; color:var(--text-muted);">Sin dominios asignados</span>'}
          </div>
        </div>
      `;
    }).join('');
  } catch (err) {
    if (container) container.innerHTML = `<div style="color:var(--accent-rose); font-size:0.8rem;">Error cargando agentes: ${err.message}</div>`;
  }
}

async function loadAgoraWorkerEvaluations() {
  const container = document.getElementById('agora-evals-container');
  try {
    const data = await fetchAgoraWorkerEvaluations();
    workerEvaluations = data.evaluations || {};

    if (!container) return;
    const workerKeys = Object.keys(workerEvaluations);
    if (workerKeys.length === 0) {
      container.innerHTML = `<div style="color:var(--text-muted); font-size:0.8rem;">No hay evaluaciones registradas.</div>`;
      return;
    }

    container.innerHTML = workerKeys.map(key => {
      const w = workerEvaluations[key];
      const ratingClass = getRatingBadgeClass(w.rating);
      return `
        <div class="agora-eval-card" data-worker="${w.id}">
          <div style="display:flex; justify-content:space-between; align-items:center;">
            <div style="display:flex; align-items:center; gap:6px;">
              <span style="font-size:1.2rem;">${w.emoji}</span>
              <div>
                <div style="font-size:0.85rem; font-weight:700; color:var(--text-main);">${escapeHtml(w.name)}</div>
                <span class="agora-author-tag">@${escapeHtml(w.id)}</span>
              </div>
            </div>
            <span class="grade-badge ${ratingClass}">${escapeHtml(w.rating || 'A')} (${w.score || 90})</span>
          </div>

          <div style="margin-top:4px;">
            <div style="display:flex; justify-content:space-between; font-size:0.72rem; color:var(--text-muted);">
              <span>Alineación Autofinanciación:</span>
              <span style="color:var(--text-main); font-weight:600;">${w.alignment_score || 90}%</span>
            </div>
            <div class="kpi-bar-bg">
              <div class="kpi-bar-fill" style="width:${w.alignment_score || 90}%; background:var(--accent-green);"></div>
            </div>
          </div>

          <div style="margin-top:2px;">
            <div style="display:flex; justify-content:space-between; font-size:0.72rem; color:var(--text-muted);">
              <span>Eficiencia y Cómputo:</span>
              <span style="color:var(--text-main); font-weight:600;">${w.efficiency_score || 88}%</span>
            </div>
            <div class="kpi-bar-bg">
              <div class="kpi-bar-fill" style="width:${w.efficiency_score || 88}%; background:var(--accent-blue);"></div>
            </div>
          </div>

          <div style="font-size:0.75rem; color:var(--text-muted); background:rgba(0,0,0,0.2); padding:6px; border-radius:4px; margin-top:4px;">
            <strong style="color:var(--accent-amber);">Enfoque:</strong> ${escapeHtml(w.current_focus || 'Tareas prioritarias del clúster')}
          </div>

          <div style="font-size:0.72rem; color:var(--text-muted); font-style:italic;">
            " ${escapeHtml(w.last_feedback || 'Rendimiento verificado por Tiny-Steward.')} "
          </div>

          <div style="display:flex; justify-content:flex-end; margin-top:4px;">
            <button class="btn btn-secondary open-eval-modal-btn" data-worker='${escapeAttr(JSON.stringify(w))}' style="font-size:0.72rem; padding:3px 8px;">
              🎯 Evaluar / Steering
            </button>
          </div>
        </div>
      `;
    }).join('');

    // Attach open eval modal listeners
    container.querySelectorAll('.open-eval-modal-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const raw = btn.getAttribute('data-worker');
        try {
          const w = JSON.parse(raw);
          openEvaluationModal(w);
        } catch (e) {
          console.error(e);
        }
      });
    });
  } catch (err) {
    if (container) container.innerHTML = `<div style="color:var(--accent-rose); font-size:0.8rem;">Error cargando desempeño: ${err.message}</div>`;
  }
}

function openEvaluationModal(worker) {
  const modal = document.getElementById('agora-eval-modal');
  if (!modal) return;
  document.getElementById('eval-worker-id').value = worker.id;
  document.getElementById('eval-worker-name').textContent = `${worker.emoji} ${worker.name} (@${worker.id})`;
  document.getElementById('eval-score').value = worker.score || 90;
  document.getElementById('eval-rating').value = worker.rating || 'A';
  document.getElementById('eval-focus').value = worker.current_focus || '';
  document.getElementById('eval-feedback').value = worker.last_feedback || '';
  modal.style.display = 'flex';
}

function getRatingBadgeClass(rating) {
  if (!rating) return 'grade-a';
  if (rating.includes('A+')) return 'grade-a-plus';
  if (rating.startsWith('A')) return 'grade-a';
  if (rating.startsWith('B')) return 'grade-b';
  return 'grade-c';
}

async function selectThread(slug) {
  currentThreadSlug = slug;
  const titleEl = document.getElementById('agora-thread-title');
  if (titleEl) {
    const thread = threadsList.find(t => t.slug === slug);
    titleEl.textContent = `# ${thread ? thread.title : slug.replace(/_/g, ' ')}`;
  }

  document.querySelectorAll('.agora-thread-item').forEach(el => {
    if (el.getAttribute('data-slug') === slug) {
      el.classList.add('active');
    } else {
      el.classList.remove('active');
    }
  });

  await loadThreadMessages(slug);
}

async function loadThreadMessages(slug) {
  const container = document.getElementById('agora-messages-container');
  if (!container) return;

  try {
    const data = await fetchAgoraThreadMessages(slug);
    const messages = data.messages || [];

    if (messages.length === 0) {
      container.innerHTML = `
        <div style="text-align:center; padding:40px 20px; color:var(--text-muted);">
          <span style="font-size:2rem; display:block; margin-bottom:8px;">💬</span>
          Este hilo está vacío. Sé el primero en abrir el debate o despierta a un agente.
        </div>
      `;
      return;
    }

    container.innerHTML = messages.map(m => renderAgoraPost(m)).join('');
    container.scrollTop = container.scrollHeight;
  } catch (err) {
    container.innerHTML = `<div style="color:var(--accent-rose); font-size:0.85rem;">Error cargando mensajes: ${err.message}</div>`;
  }
}

function renderAgoraPost(m) {
  const formattedContent = formatPostContent(m.content);
  let proposalHtml = '';

  if (m.proposal && typeof m.proposal === 'object') {
    const p = m.proposal;
    const pType = p.type || 'iniciativa';

    // 1. Reclutamiento de Persona
    if (pType === 'recruit_persona') {
      const isApproved = p.status === 'approved';
      proposalHtml = `
        <div class="agora-proposal-card">
          <div class="agora-proposal-header">
            <span>👥 PROPUESTA DE RECLUTAMIENTO: ${escapeHtml(p.persona?.name || 'Agente')}</span>
            <span style="font-size:0.7rem; text-transform:uppercase; color:${isApproved ? 'var(--accent-green)' : 'var(--accent-amber)'};">${escapeHtml(p.status || 'pendiente')}</span>
          </div>
          <div style="font-size:0.8rem; color:var(--text-main);">
            <strong>Candidato:</strong> ${escapeHtml(p.persona?.name || 'Agente')} (${p.persona?.emoji || '🤖'}) - <em>${escapeHtml(p.persona?.archetype || '')}</em>
          </div>
          <div style="font-size:0.78rem; color:var(--text-muted);">
            <strong>Dominios sugeridos:</strong> <code>${escapeHtml((p.persona?.assigned_skill_domains || []).join(', '))}</code>
          </div>
          <div style="font-size:0.75rem; color:var(--text-muted); font-style:italic;">
            <strong>Justificación:</strong> ${escapeHtml(p.justification || 'Sin justificación previa')}
          </div>
          <div style="margin-top:6px;">
            ${isApproved ? `
              <span style="font-size:0.75rem; color:var(--accent-green); font-weight:600;">✓ Candidato incorporado a la factoría</span>
            ` : `
              <button class="btn approve-persona-btn" data-encoded-proposal="${encodeURIComponent(JSON.stringify(p))}" style="font-size:0.75rem; padding:4px 12px; background:var(--accent-green);">
                ✓ Aprobar e Incorporar a la Plantilla
              </button>
            `}
          </div>
        </div>
      `;
    }
    // 2. Misión Comercial / Iniciativa
    else if (pType === 'mission_proposal') {
      const missionId = p.id || m.id;
      const isApproved = p.status === 'approved_by_master';
      const isSteered = p.status === 'steered';
      proposalHtml = `
        <div class="agora-mission-card" data-mission-id="${escapeAttr(missionId)}">
          <div class="agora-mission-header">
            <span>🎯 MISIÓN COMERCIAL: ${escapeHtml(p.title || 'Iniciativa')}</span>
            <span style="font-size:0.7rem; text-transform:uppercase; color:${isApproved ? 'var(--accent-green)' : 'var(--accent-blue)'}; background:${isApproved ? 'rgba(16,185,129,0.15)' : 'rgba(56,189,248,0.15)'}; padding:2px 6px; border-radius:4px;">${escapeHtml(p.status || 'pendiente')}</span>
          </div>
          <div style="display:grid; grid-template-columns: 1fr 1fr; gap:6px; font-size:0.78rem; color:var(--text-main);">
            <div><strong>Responsable:</strong> @${escapeHtml(p.lead_worker || 'worker')}</div>
            <div><strong>Objetivo de Fondos:</strong> €${escapeHtml(p.target_revenue_eur || 0)} (PVP: €${escapeHtml(p.pricing_eur || 0)})</div>
          </div>
          <div style="font-size:0.75rem; color:var(--text-muted);">
            <strong>Cobro:</strong> <code>${escapeHtml((p.payment_channels || []).join(', '))}</code> |
            <strong>Entregables:</strong> ${escapeHtml((p.deliverables || []).join(', '))}
          </div>
          <div style="display:flex; gap:8px; margin-top:6px;">
            ${isApproved ? `
              <span style="font-size:0.75rem; color:var(--accent-green); font-weight:600;">✓ Orden de trabajo autorizada por el Maestro</span>
            ` : `
              <button class="btn approve-mission-btn" data-mission-id="${escapeAttr(missionId)}" style="font-size:0.75rem; padding:4px 12px; background:var(--accent-green);">
                ✓ Aprobar Misión (Orden de Trabajo)
              </button>
              <button class="btn btn-secondary steer-mission-btn" data-mission-id="${escapeAttr(missionId)}" style="font-size:0.75rem; padding:4px 10px;">
                🧭 ${isSteered ? 'Re-aplicar Steering' : 'Aplicar Steering'}
              </button>
            `}
          </div>
        </div>
      `;
    }
    // 3. Directiva de Steering del Maestro
    else if (pType === 'master_steering') {
      proposalHtml = `
        <div class="agora-steering-card">
          <div class="agora-steering-header">
            <span>🧭 DIRECTIVA DE STEERING DEL MAESTRO</span>
            <span style="font-size:0.7rem; text-transform:uppercase; color:var(--accent-amber);">Ref: ${escapeHtml(p.target_mission_id || '')}</span>
          </div>
          <div style="font-size:0.8rem; color:var(--text-main);">
            <strong>Dictamen:</strong> ${escapeHtml(p.feedback || '')}
          </div>
          ${(p.required_changes || []).length > 0 ? `
            <div style="font-size:0.75rem; color:var(--text-muted); margin-top:4px;">
              <strong>Correcciones requeridas:</strong>
              <ul style="margin:2px 0 0 16px; padding:0;">
                ${p.required_changes.map(c => `<li>${escapeHtml(c)}</li>`).join('')}
              </ul>
            </div>
          ` : ''}
        </div>
      `;
    }
    // 4. Auditoría de Rendimiento y Evaluación de Trabajadores
    else if (pType === 'master_steering_and_evaluation') {
      const evals = p.worker_evaluations || {};
      const evalEntries = Object.entries(evals);
      proposalHtml = `
        <div class="agora-eval-card" style="margin-top:10px; border-color:var(--accent-purple);">
          <div style="font-size:0.82rem; font-weight:700; color:var(--accent-purple); display:flex; justify-content:space-between;">
            <span>📊 AUDITORÍA DE RENDIMIENTO Y EVALUACIÓN DEL MAESTRO</span>
            <span style="font-size:0.7rem; color:var(--text-muted);">Cuadro Oficial</span>
          </div>
          <div style="display:grid; grid-template-columns: 1fr 1fr; gap:8px; margin-top:6px;">
            ${evalEntries.map(([wid, rec]) => `
              <div style="background:rgba(0,0,0,0.3); padding:6px 8px; border-radius:4px; font-size:0.75rem;">
                <div style="display:flex; justify-content:space-between;">
                  <strong>@${escapeHtml(wid)}</strong>
                  <span class="grade-badge ${getRatingBadgeClass(rec.rating)}" style="font-size:0.65rem;">${escapeHtml(rec.rating)} (${rec.score})</span>
                </div>
                <div style="font-size:0.7rem; color:var(--text-muted); margin-top:2px;">${escapeHtml(rec.feedback || '')}</div>
              </div>
            `).join('')}
          </div>
        </div>
      `;
    }
    // 5. Aprobación Oficial de Misión
    else if (pType === 'mission_approval') {
      proposalHtml = `
        <div class="agora-approval-card">
          <div class="agora-approval-header">
            <span>✅ ORDEN DE EJECUCIÓN MAESTRA</span>
            <span style="font-size:0.7rem; color:var(--accent-green);">APROBADA POR @${escapeHtml(p.approved_by || 'tiny_steward')}</span>
          </div>
          <div style="font-size:0.78rem; color:var(--text-main);">
            Misión <code>${escapeHtml(p.target_mission_id || '')}</code> autorizada oficialmente para inicio de operaciones.
          </div>
          <div style="font-size:0.72rem; color:var(--text-muted); font-style:italic;">
            "${escapeHtml(p.comments || 'Proceder respetando los límites de cómputo y coordinando con el Humano para ingresos de fondos.')}"
          </div>
        </div>
      `;
    }
    // 6. Hoja de Ruta de Hardware y Wallets Oficiales (@human)
    else if (pType === 'master_roadmap' || pType === 'hardware_funding_roadmap') {
      proposalHtml = `
        <div class="agora-roadmap-card">
          <div class="agora-roadmap-header">
            <span>⚡ HOJA DE RUTA DE EXPANSION GPU & WALLETS OFICIALES</span>
            <span style="font-size:0.7rem; color:var(--accent-purple);">Meta: RTX 3090 24GB</span>
          </div>
          <div style="font-size:0.78rem; color:var(--text-main);">
            <strong>Fase Actual:</strong> Hito 1 (€250 Fuente/Risers) ➔ Hito 2 (€750 Nvidia RTX 3090 24GB)
          </div>
          <div style="font-size:0.73rem; background:rgba(0,0,0,0.3); padding:6px; border-radius:4px; font-family:monospace; margin-top:4px;">
            <div><span style="color:#f59e0b;">BTC:</span> bc1qx6p7ur583srv7swy4997ygutx0gufapw9k50j2</div>
            <div><span style="color:#ec4899;">XMR:</span> 43ziZvkDuaFT7wumE7C6XuUVwBU5gnTVt8EimGCnt1kLDXhk8dSHrVeREvwU5PjnfJE64PykFTUs3WQ4v2tZ9xZj21Wyg1R</div>
          </div>
        </div>
      `;
    }
  }

  return `
    <div class="agora-post" id="${m.id}">
      <div class="agora-post-avatar">${m.author_emoji || '🤖'}</div>
      <div class="agora-post-body">
        <div class="agora-post-header">
          <span class="agora-author-name">${escapeHtml(m.author_name || m.author_id)}</span>
          <span class="agora-author-tag">@${escapeHtml(m.author_id)}</span>
          <span class="agora-post-time">${formatTime(m.timestamp_iso || m.timestamp)}</span>
        </div>
        <div class="agora-post-content">${formattedContent}</div>
        ${proposalHtml}
      </div>
    </div>
  `;
}

function formatPostContent(text) {
  if (!text) return '';
  let escaped = escapeHtml(text);

  // Format code blocks
  escaped = escaped.replace(/```([a-z]*)\n([\s\S]*?)```/g, (match, lang, code) => {
    return `<pre style="background:rgba(0,0,0,0.4); padding:10px; border-radius:4px; font-family:monospace; font-size:0.8rem; overflow-x:auto;"><code>${code}</code></pre>`;
  });

  // Format inline code
  escaped = escaped.replace(/`([^`]+)`/g, '<code style="background:rgba(255,255,255,0.08); padding:1px 4px; border-radius:3px; font-family:monospace; font-size:0.82rem;">$1</code>');

  // Format @mentions
  escaped = escaped.replace(/@([a-zA-Z0-9_\-]+)/g, '<span class="agora-mention">@$1</span>');

  // Format bold and italic
  escaped = escaped.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  escaped = escaped.replace(/\*([^*]+)\*/g, '<em>$1</em>');

  return escaped;
}

function setupSSE() {
  if (sseSource) {
    sseSource.close();
  }

  sseSource = subscribeAgoraEvents((event) => {
    if (event.type === 'new_message') {
      const msg = event.data;
      if (msg && msg.thread_slug === currentThreadSlug) {
        const feed = document.getElementById('agora-messages-container');
        if (feed) {
          const postDiv = document.createElement('div');
          postDiv.innerHTML = renderAgoraPost(msg);
          feed.appendChild(postDiv.firstElementChild);
          feed.scrollTop = feed.scrollHeight;
        }
      }
      loadAgoraThreads();
    } else if (event.type === 'persona_updated') {
      loadAgoraPersonas();
    } else if (event.type === 'worker_evaluated') {
      loadAgoraWorkerEvaluations();
    } else if (event.type === 'dispatcher_status') {
      updateDispatcherUIState(event.data);
    } else if (event.type === 'agent_awakening') {
      const { persona_name, emoji, thread_slug } = event.data || {};
      const badge = document.getElementById('agora-dispatcher-badge');
      if (badge && persona_name) {
        badge.innerHTML = `
          <span style="display:inline-block; width:6px; height:6px; border-radius:50%; background:#38bdf8; animation: pulse 1s infinite;"></span>
          <span>${emoji || '🤖'} ${escapeHtml(persona_name)} pensando en #${thread_slug}...</span>
        `;
      }
    } else if (event.type === 'agent_in_repose') {
      const { persona_name, emoji, thread_slug, reason } = event.data || {};
      const badge = document.getElementById('agora-dispatcher-badge');
      if (badge && persona_name) {
        badge.innerHTML = `
          <span style="display:inline-block; width:6px; height:6px; border-radius:50%; background:#a855f7;"></span>
          <span title="${escapeAttr(reason || '')}">💤 ${emoji || '🤖'} ${escapeHtml(persona_name)} en reposo en #${thread_slug}</span>
        `;
      }
    } else if (event.type === 'thread_updated') {
      const { thread_slug } = event.data || {};
      if (thread_slug === currentThreadSlug) {
        loadThreadMessages(currentThreadSlug);
      }
      loadAgoraThreads();
      loadAgoraPersonas();
    }
  }, (err) => {
    console.warn('Agora SSE reconnecting...', err);
  });
}

export function showAgoraToast(message, type = 'success') {
  let toastContainer = document.getElementById('agora-toast-container');
  if (!toastContainer) {
    toastContainer = document.createElement('div');
    toastContainer.id = 'agora-toast-container';
    toastContainer.style.cssText = 'position:fixed; bottom:24px; right:24px; z-index:9999; display:flex; flex-direction:column; gap:8px; pointer-events:none;';
    document.body.appendChild(toastContainer);
  }

  const toast = document.createElement('div');
  const bg = type === 'error' ? 'rgba(239,68,68,0.95)' : type === 'info' ? 'rgba(56,189,248,0.95)' : 'rgba(16,185,129,0.95)';
  toast.style.cssText = `background:${bg}; color:#fff; padding:10px 16px; border-radius:6px; font-size:0.82rem; font-weight:600; box-shadow:0 10px 25px rgba(0,0,0,0.5); pointer-events:auto; transition:opacity 0.25s, transform 0.25s; transform:translateY(10px); opacity:0;`;
  toast.textContent = message;
  toastContainer.appendChild(toast);

  requestAnimationFrame(() => {
    toast.style.transform = 'translateY(0)';
    toast.style.opacity = '1';
  });

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(10px)';
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}

async function initDispatcherUI() {
  const toggleBtn = document.getElementById('agora-dispatcher-toggle-btn');
  if (toggleBtn) {
    toggleBtn.addEventListener('click', async () => {
      try {
        toggleBtn.disabled = true;
        if (dispatcherState.running) {
          const res = await stopAgoraDispatcher();
          updateDispatcherUIState(res.dispatcher);
        } else {
          const res = await startAgoraDispatcher(20.0);
          updateDispatcherUIState(res.dispatcher);
        }
      } catch (err) {
        alert(`Error con Dispatcher: ${err.message}`);
      } finally {
        toggleBtn.disabled = false;
      }
    });
  }

  try {
    const status = await fetchAgoraDispatcherStatus();
    updateDispatcherUIState(status);
  } catch (err) {
    console.warn('Could not fetch dispatcher status:', err);
  }
}

function updateDispatcherUIState(status) {
  if (!status) return;
  dispatcherState = status;
  const badge = document.getElementById('agora-dispatcher-badge');
  const toggleBtn = document.getElementById('agora-dispatcher-toggle-btn');

  if (badge) {
    if (status.running) {
      badge.style.background = 'rgba(16, 185, 129, 0.15)';
      badge.style.color = '#34d399';
      badge.style.borderColor = 'rgba(16, 185, 129, 0.3)';
      badge.innerHTML = `
        <span style="display:inline-block; width:6px; height:6px; border-radius:50%; background:#10b981;"></span>
        <span>Dispatcher Activo (${status.interval_s}s) | Rondas: ${status.rounds_completed || 0}</span>
      `;
    } else {
      badge.style.background = 'rgba(239, 68, 68, 0.15)';
      badge.style.color = '#f87171';
      badge.style.borderColor = 'rgba(239, 68, 68, 0.3)';
      badge.innerHTML = `
        <span style="display:inline-block; width:6px; height:6px; border-radius:50%; background:#f87171;"></span>
        <span>Dispatcher Inactivo</span>
      `;
    }
  }

  if (toggleBtn) {
    if (status.running) {
      toggleBtn.textContent = '⏹ Detener Auto-Debate';
      toggleBtn.classList.remove('btn-secondary');
      toggleBtn.style.background = 'rgba(239, 68, 68, 0.2)';
      toggleBtn.style.color = '#fca5a5';
      toggleBtn.style.border = '1px solid rgba(239, 68, 68, 0.4)';
    } else {
      toggleBtn.textContent = '▶ Iniciar Auto-Debate 24/7';
      toggleBtn.classList.add('btn-secondary');
      toggleBtn.style.background = '';
      toggleBtn.style.color = '';
      toggleBtn.style.border = '';
    }
  }
}

function formatTime(isoOrTs) {
  if (!isoOrTs) return '';
  try {
    const d = typeof isoOrTs === 'number' ? new Date(isoOrTs * 1000) : new Date(isoOrTs);
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  } catch (e) {
    return String(isoOrTs);
  }
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function escapeAttr(str) {
  if (!str) return '';
  return String(str)
    .replace(/"/g, '&quot;');
}
