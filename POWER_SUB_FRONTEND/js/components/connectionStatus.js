// Backend Connection Status Indicator & Health Monitor
import { api, NetworkError } from '../api.js';
import { store } from '../state.js';
import { el, svgIcon } from '../utils/dom.js';
import { openConfirmModal } from './modal.js';
import { showToast } from './toast.js';

let pollTimer = null;
let currentInterval = 30000;
let isChecking = false;

/**
 * Initializes the connection monitor and renders the header indicator.
 * @param {HTMLElement} container
 */
export function initConnectionMonitor(container) {
  const dot = el('span', { className: 'connection-dot', 'aria-hidden': 'true' });
  const textLabel = el('span', { className: 'connection-label', text: 'Connecting...' });

  const badge = el('button', {
    type: 'button',
    className: 'connection-indicator connecting',
    'aria-label': 'Backend status: Connecting',
    title: 'Click for backend status and instructions',
    on: {
      click: () => showStatusModal()
    }
  }, dot, textLabel);

  container.appendChild(badge);

  // Subscribe to store updates
  store.subscribe((state, key) => {
    if (key === 'connectionStatus') {
      updateBadgeUI(badge, dot, textLabel, state.connectionStatus);
    }
  });

  // Initial check
  checkHealth();

  // Visibility state handling
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') {
      // Immediate check when user switches back to tab
      checkHealth();
      startPolling();
    } else {
      stopPolling();
    }
  });

  startPolling();
}

function updateBadgeUI(badge, dot, textLabel, status) {
  badge.className = `connection-indicator ${status}`;
  if (status === 'online') {
    textLabel.textContent = 'Connected';
    badge.setAttribute('aria-label', 'Backend status: Connected to 127.0.0.1:8000');
  } else if (status === 'offline') {
    textLabel.textContent = 'Backend Offline';
    badge.setAttribute('aria-label', 'Backend status: Offline. Click for troubleshooting.');
  } else {
    textLabel.textContent = 'Connecting...';
    badge.setAttribute('aria-label', 'Backend status: Checking connection...');
  }
}

/**
 * Executes health check with exponential backoff on offline.
 */
export async function checkHealth() {
  if (isChecking) return;
  isChecking = true;

  try {
    const health = await api.getHealth();
    if (health && (health.status === 'healthy' || health.status === 'ok')) {
      store.setConnectionStatus('online');
      currentInterval = 30000; // Reset interval
    } else {
      store.setConnectionStatus('offline');
      increaseBackoff();
    }
  } catch (err) {
    store.setConnectionStatus('offline');
    increaseBackoff();
  } finally {
    isChecking = false;
  }
}

function increaseBackoff() {
  // Cap exponential backoff at 2 minutes (120,000ms)
  currentInterval = Math.min(currentInterval * 1.5, 120000);
}

function startPolling() {
  stopPolling();
  pollTimer = setInterval(() => {
    if (document.visibilityState === 'visible') {
      checkHealth();
    }
  }, currentInterval);
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
}

/**
 * Shows troubleshooting modal when user clicks connection badge.
 */
function showStatusModal() {
  const isOnline = store.connectionStatus === 'online';

  const content = el('div', { style: 'line-height: 1.6;' });

  if (isOnline) {
    content.appendChild(el('p', {
      style: 'color: var(--color-success); font-weight: 600; margin-bottom: 0.75rem;',
      text: '✓ POWER-SUB FastAPI backend is connected and healthy.'
    }));
    content.appendChild(el('p', {
      style: 'font-size: 0.85rem; color: var(--text-muted);',
      text: `Base URL: ${store.apiBaseUrl}`
    }));
  } else {
    content.appendChild(el('p', {
      style: 'color: var(--color-danger); font-weight: 700; margin-bottom: 0.75rem;',
      text: 'Backend Connection Failed'
    }));

    content.appendChild(el('p', {
      style: 'margin-bottom: 0.75rem;',
      text: 'The frontend could not connect to the POWER-SUB backend service at: ' + store.apiBaseUrl
    }));

    content.appendChild(el('p', {
      style: 'font-weight: 600; font-size: 0.88rem; margin-bottom: 0.35rem;',
      text: 'To start the backend on Windows:'
    }));

    const codeBox = el('pre', {
      style: 'background: #0f172a; color: #38bdf8; padding: 0.85rem; border-radius: 6px; font-family: monospace; font-size: 0.85rem; margin-bottom: 1rem; overflow-x: auto;'
    }, el('code', { text: '.\\venv\\Scripts\\activate\nuvicorn app.main:app --reload --host 127.0.0.1 --port 8000' }));
    content.appendChild(codeBox);

    content.appendChild(el('p', {
      style: 'font-size: 0.84rem; color: var(--text-secondary); margin-bottom: 0.5rem;',
      text: 'If the backend is running, verify that the frontend origin (e.g. http://127.0.0.1:5173) is listed in ALLOWED_ORIGINS in the backend .env configuration file.'
    }));
  }

  openConfirmModal({
    title: isOnline ? 'Backend Status: Connected' : 'Backend Status: Offline',
    content,
    confirmText: 'Retry Connection Now',
    cancelText: 'Close',
    onConfirm: async () => {
      await checkHealth();
      if (store.connectionStatus === 'online') {
        showToast('Connected', 'Successfully reconnected to POWER-SUB backend.', 'success');
      } else {
        showToast('Still Offline', 'Could not reach backend at ' + store.apiBaseUrl, 'error');
      }
    }
  });
}
