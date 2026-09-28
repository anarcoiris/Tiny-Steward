/**
 * Centralized API Client for Tiny Steward Web IDE & Control Center.
 */

const BASE_URL = '';

export async function fetchStatus() {
  const res = await fetch(`${BASE_URL}/api/status`);
  if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
  return await res.json();
}

export async function fetchTelemetry() {
  const res = await fetch(`${BASE_URL}/api/telemetry`);
  if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
  return await res.json();
}

export async function fetchSessions() {
  const res = await fetch(`${BASE_URL}/api/sessions`);
  if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
  return await res.json();
}

export async function switchSession(name) {
  const res = await fetch(`${BASE_URL}/api/sessions/switch`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name })
  });
  if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
  return await res.json();
}

export async function createSession(name) {
  const res = await fetch(`${BASE_URL}/api/sessions/create`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name })
  });
  if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
  return await res.json();
}

export async function fetchFileTree() {
  const res = await fetch(`${BASE_URL}/api/files/tree`);
  if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
  return await res.json();
}

export async function fetchFileContent(path) {
  const res = await fetch(`${BASE_URL}/api/files/content?path=${encodeURIComponent(path)}`);
  if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
  return await res.json();
}

export async function saveFileContent(path, content) {
  const res = await fetch(`${BASE_URL}/api/files/save`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path, content })
  });
  if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
  return await res.json();
}

export async function fetchTasks(session = 'default') {
  const res = await fetch(`${BASE_URL}/api/tasks?session=${encodeURIComponent(session)}`);
  if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
  return await res.json();
}

export async function updateTaskStatus(taskId, newStatus, session = 'default') {
  const res = await fetch(`${BASE_URL}/api/tasks/update`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ task_id: taskId, status: newStatus, session })
  });
  if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
  return await res.json();
}

export async function createTask(title, status = 'todo', session = 'default') {
  const res = await fetch(`${BASE_URL}/api/tasks/create`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title, status, session })
  });
  if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
  return await res.json();
}

export async function createFile(path, isDir = false, initialContent = '') {
  const res = await fetch(`${BASE_URL}/api/files/create`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path, is_dir: isDir, initial_content: initialContent })
  });
  if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
  return await res.json();
}

export async function deleteFile(path) {
  const res = await fetch(`${BASE_URL}/api/files/delete`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path })
  });
  if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
  return await res.json();
}

export async function fetchChatHistory(session = 'default') {
  const res = await fetch(`${BASE_URL}/api/chat/history?session=${encodeURIComponent(session)}`);
  if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
  return await res.json();
}

export async function inspectGraphNode(nodeId) {
  const res = await fetch(`${BASE_URL}/api/graph/inspect?id=${encodeURIComponent(nodeId)}`);
  if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
  return await res.json();
}

export async function rebuildGraph() {
  const res = await fetch(`${BASE_URL}/api/graph/rebuild`, { method: 'POST' });
  if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
  return await res.json();
}

export async function fetchFactoryOrders() {
  const res = await fetch(`${BASE_URL}/api/factory/orders/list`);
  if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
  return await res.json();
}

export async function updateFactoryOrderStatus(orderId, status, carrier = '', trackingCode = '', operatorNotes = '') {
  const res = await fetch(`${BASE_URL}/api/factory/orders/${encodeURIComponent(orderId)}/status`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      status,
      carrier,
      tracking_code: trackingCode,
      operator_notes: operatorNotes
    })
  });
  if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
  return await res.json();
}

export async function sendMailboxMessage(fromSession, toSession, content, priority = 'normal', type = 'message', blocking = false) {
  const res = await fetch(`${BASE_URL}/api/v1/mailbox/send`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      from_session: fromSession,
      to_session: toSession,
      content,
      priority,
      type,
      blocking
    })
  });
  if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
  return await res.json();
}

export async function triggerDream() {
  const res = await fetch(`${BASE_URL}/api/dream`, { method: 'POST' });
  if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
  return await res.json();
}

/**
 * Stream prompt interaction using Server-Sent Events (SSE).
 */
export async function streamChat(prompt, sessionName, onChunk, onError, onComplete) {
  try {
    const response = await fetch(`${BASE_URL}/api/chat/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt, session: sessionName })
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      const lines = buffer.split('\n');
      buffer = lines.pop(); // Keep incomplete line in buffer

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const dataStr = line.slice(6).trim();
          if (dataStr === '[DONE]') {
            if (onComplete) onComplete();
            return;
          }
          try {
            const parsed = JSON.parse(dataStr);
            if (onChunk) onChunk(parsed);
          } catch (e) {
            // raw text token
            if (onChunk) onChunk({ type: 'token', content: dataStr });
          }
        }
      }
    }
    if (onComplete) onComplete();
  } catch (err) {
    if (onError) onError(err);
  }
}

export async function fetchSessionTree() {
  const res = await fetch(`${BASE_URL}/api/v1/sessions/tree`);
  if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
  return await res.json();
}

export async function fetchMailboxQueue() {
  const res = await fetch(`${BASE_URL}/api/v1/mailbox/queue`);
  if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
  return await res.json();
}

export async function fetchBackgroundTasks() {
  const res = await fetch(`${BASE_URL}/api/v1/tasks/background`);
  if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
  return await res.json();
}

export async function killBackgroundTask(taskId) {
  const res = await fetch(`${BASE_URL}/api/v1/tasks/kill`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ task_id: taskId })
  });
  if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
  return await res.json();
}

export async function fetchTaskLogTail(taskId, lines = 50) {
  const res = await fetch(`${BASE_URL}/api/v1/tasks/tail?task_id=${encodeURIComponent(taskId)}&lines=${lines}`);
  if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
  return await res.json();
}

// ─── 🏛️ Ágora (Social Hub & Multi-Agent Forum) API ───────────

export async function fetchAgoraThreads() {
  const res = await fetch(`${BASE_URL}/api/agora/threads`);
  if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
  return await res.json();
}

export async function fetchAgoraThreadMessages(slug) {
  const res = await fetch(`${BASE_URL}/api/agora/threads/${encodeURIComponent(slug)}`);
  if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
  return await res.json();
}

export async function createAgoraThread(slug, title = '', initialMessage = '', authorId = 'tiny_steward') {
  const res = await fetch(`${BASE_URL}/api/agora/threads`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ slug, title, initial_message: initialMessage, author_id: authorId })
  });
  if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
  return await res.json();
}

export async function postAgoraMessage(slug, authorId, content, inReplyTo = null, proposal = null) {
  const res = await fetch(`${BASE_URL}/api/agora/threads/${encodeURIComponent(slug)}/messages`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ author_id: authorId, content, in_reply_to: inReplyTo, proposal })
  });
  if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
  return await res.json();
}

export async function fetchAgoraPersonas() {
  const res = await fetch(`${BASE_URL}/api/agora/personas`);
  if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
  return await res.json();
}

export async function proposeAgoraPersona(proposerId, persona, justification = '') {
  const res = await fetch(`${BASE_URL}/api/agora/personas/propose`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ proposer_id: proposerId, persona, justification })
  });
  if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
  return await res.json();
}

export async function approveAgoraPersona(persona, approverId = 'tiny_steward') {
  const res = await fetch(`${BASE_URL}/api/agora/personas/approve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ persona, approver_id: approverId })
  });
  if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
  return await res.json();
}

export async function awakenAgoraPersona(slug, personaId = null, customInstructions = '') {
  const res = await fetch(`${BASE_URL}/api/agora/threads/${encodeURIComponent(slug)}/awaken`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ persona_id: personaId, custom_instructions: customInstructions })
  });
  if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
  return await res.json();
}

export function subscribeAgoraEvents(onEvent, onError) {
  const eventSource = new EventSource(`${BASE_URL}/api/agora/events`);
  eventSource.onmessage = (e) => {
    try {
      const data = JSON.parse(e.data);
      if (onEvent) onEvent(data);
    } catch (err) {
      console.warn('Agora event parse error:', err);
    }
  };
  eventSource.onerror = (err) => {
    if (onError) onError(err);
  };
  return eventSource;
}

export async function fetchAgoraDispatcherStatus() {
  const res = await fetch(`${BASE_URL}/api/agora/dispatcher/status`);
  if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
  return await res.json();
}

export async function startAgoraDispatcher(intervalS = 20.0, threads = null) {
  const res = await fetch(`${BASE_URL}/api/agora/dispatcher/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ interval_s: intervalS, threads })
  });
  if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
  return await res.json();
}

export async function stopAgoraDispatcher() {
  const res = await fetch(`${BASE_URL}/api/agora/dispatcher/stop`, {
    method: 'POST',
  });
  if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
  return await res.json();
}

export async function fetchAgoraWorkerEvaluations() {
  const res = await fetch(`${BASE_URL}/api/agora/workers/evaluations`);
  if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
  return await res.json();
}

export async function evaluateAgoraWorker(workerId, score, rating, feedback, currentFocus, evaluatorId = 'tiny_steward') {
  const res = await fetch(`${BASE_URL}/api/agora/workers/evaluate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      worker_id: workerId,
      evaluator_id: evaluatorId,
      score,
      rating,
      feedback,
      current_focus: currentFocus,
    }),
  });
  if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
  return await res.json();
}

export async function proposeAgoraMission(threadSlug, proposerId, mission) {
  const res = await fetch(`${BASE_URL}/api/agora/missions/propose`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ thread_slug: threadSlug, proposer_id: proposerId, mission }),
  });
  if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
  return await res.json();
}

export async function steerAgoraMission(threadSlug, missionId, feedback, requiredChanges = [], steererId = 'tiny_steward') {
  const res = await fetch(`${BASE_URL}/api/agora/missions/steer`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      thread_slug: threadSlug,
      mission_id: missionId,
      steerer_id: steererId,
      feedback,
      required_changes: requiredChanges,
    }),
  });
  if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
  return await res.json();
}

export async function approveAgoraMission(threadSlug, missionId, comments = '', approverId = 'tiny_steward') {
  const res = await fetch(`${BASE_URL}/api/agora/missions/approve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      thread_slug: threadSlug,
      mission_id: missionId,
      approver_id: approverId,
      comments,
    }),
  });
  if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
  return await res.json();
}


