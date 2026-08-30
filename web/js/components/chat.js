/**
 * Agent Chat Component - Real-time Streaming & Collapsible <think> Blocks.
 */

import { streamChat } from '../api.js';

export function initChatComponent(AppState) {
  const feed = document.getElementById('messages-feed');
  const input = document.getElementById('chat-input');
  const sendBtn = document.getElementById('send-btn');

  if (!feed || !input || !sendBtn) return;

  async function handleSend() {
    const prompt = input.value.trim();
    if (!prompt || AppState.isStreaming) return;

    // Append User Message
    appendMessage('user', prompt);
    input.value = '';
    AppState.isStreaming = true;
    sendBtn.disabled = true;

    // Prepare Assistant Message Bubble
    const assistantBubble = createAssistantBubble();
    feed.appendChild(assistantBubble.element);
    scrollToBottom();

    let thinkContent = '';
    let textContent = '';

    await streamChat(
      prompt,
      AppState.session,
      (chunk) => {
        if (chunk.type === 'think') {
          thinkContent += chunk.content;
          assistantBubble.updateThink(thinkContent);
        } else if (chunk.type === 'token' || chunk.type === 'text') {
          textContent += chunk.content;
          assistantBubble.updateText(textContent);
        } else if (chunk.type === 'tool_start') {
          assistantBubble.addBadge(`🛠️ Running ${chunk.name}...`);
        } else if (chunk.type === 'tool_end') {
          assistantBubble.addBadge(`✅ Finished ${chunk.name}`);
        }
        scrollToBottom();
      },
      (err) => {
        assistantBubble.updateText(`\n\n❌ Error: ${err.message}`);
        AppState.isStreaming = false;
        sendBtn.disabled = false;
      },
      () => {
        AppState.isStreaming = false;
        sendBtn.disabled = false;
      }
    );
  }

  sendBtn.addEventListener('click', handleSend);
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  });

  function scrollToBottom() {
    feed.scrollTop = feed.scrollHeight;
  }
}

function appendMessage(role, text) {
  const feed = document.getElementById('messages-feed');
  const bubble = document.createElement('div');
  bubble.className = `message-bubble ${role}`;
  bubble.textContent = text;
  feed.appendChild(bubble);
  feed.scrollTop = feed.scrollHeight;
}

function createAssistantBubble() {
  const container = document.createElement('div');
  container.className = 'message-bubble assistant';

  const thinkDetails = document.createElement('details');
  thinkDetails.className = 'think-block';
  thinkDetails.open = true; // Open by default during reasoning

  const thinkSummary = document.createElement('summary');
  thinkSummary.innerHTML = '🧠 Reasoning Chain';
  thinkDetails.appendChild(thinkSummary);

  const thinkDiv = document.createElement('div');
  thinkDiv.className = 'think-content';
  thinkDetails.appendChild(thinkDiv);

  const textDiv = document.createElement('div');
  textDiv.className = 'text-content';

  const badgesDiv = document.createElement('div');
  badgesDiv.className = 'badges-content';
  badgesDiv.style.marginTop = '8px';

  container.appendChild(thinkDetails);
  container.appendChild(textDiv);
  container.appendChild(badgesDiv);

  // Hide think block until content arrives
  thinkDetails.style.display = 'none';

  return {
    element: container,
    updateThink(content) {
      thinkDetails.style.display = 'block';
      thinkDiv.textContent = content;
    },
    updateText(content) {
      textDiv.textContent = content;
    },
    addBadge(label) {
      const badge = document.createElement('span');
      badge.className = 'status-badge';
      badge.style.marginRight = '6px';
      badge.textContent = label;
      badgesDiv.appendChild(badge);
    }
  };
}
