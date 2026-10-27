// Application Bootstrapper & Lifecycle Controller
import { store } from './state.js';
import { api } from './api.js';
import { initRouter } from './router.js';
import { initConnectionMonitor } from './components/connectionStatus.js';
import { showToast } from './components/toast.js';
import { shortenId, safeText } from './utils/format.js';
import { el, clearElement } from './utils/dom.js';

document.addEventListener('DOMContentLoaded', async () => {
  // 1. Setup Global Error Boundaries
  window.addEventListener('error', (event) => {
    console.error('Unhandled runtime error:', event.error);
    showToast('Application Notice', 'An unexpected interface error occurred. Please refresh if behavior persists.', 'error');
  });

  window.addEventListener('unhandledrejection', (event) => {
    console.error('Unhandled promise rejection:', event.reason);
    const msg = event.reason && event.reason.message
      ? event.reason.message
      : 'A background data operation could not complete.';
    showToast('Operation Failed', msg, 'error');
  });

  // 2. Initialize Backend Connection Monitor
  const connContainer = document.getElementById('connection-status-container');
  if (connContainer) {
    initConnectionMonitor(connContainer);
  }

  // 3. Initialize Mobile Menu Toggle
  const menuBtn = document.getElementById('menu-toggle-btn');
  const sidebar = document.getElementById('app-sidebar');
  const backdrop = document.getElementById('sidebar-backdrop');

  if (menuBtn && sidebar && backdrop) {
    menuBtn.addEventListener('click', () => {
      sidebar.classList.toggle('open');
      backdrop.classList.toggle('active');
    });

    backdrop.addEventListener('click', () => {
      sidebar.classList.remove('open');
      backdrop.classList.remove('active');
    });
  }

  // 4. Initialize Header Dataset Selector
  const datasetSelect = document.getElementById('header-dataset-select');
  if (datasetSelect) {
    setupHeaderDatasetSelector(datasetSelect);
  }

  // 5. Initialize SPA Hash Router
  const viewContainer = document.getElementById('view');
  if (viewContainer) {
    initRouter(viewContainer);
  }

  // 6. Initial Fetch of Available Datasets
  await refreshDatasetsList();
});

async function refreshDatasetsList() {
  try {
    const res = await api.listDatasets(1, 50);
    if (res && res.items) {
      store.setDatasets(res.items);
      // Auto-select first dataset if none selected currently
      if (!store.currentDatasetId && res.items.length > 0) {
        store.setCurrentDatasetId(res.items[0].dataset_id);
      }
    }
  } catch (err) {
    // Backend may be offline initially; connectionStatus handles UI
  }
}

function setupHeaderDatasetSelector(selectEl) {
  selectEl.addEventListener('change', (e) => {
    const val = e.target.value.trim() || null;
    store.setCurrentDatasetId(val);

    // If current hash route has a dataset ID param, update route
    const hash = window.location.hash.replace(/^#\/?/, '').trim();
    const parts = hash.split('/');
    if (parts.length >= 2 && ['analysis', 'anomalies', 'recommendations', 'reports'].includes(parts[0])) {
      if (val) {
        window.location.hash = `#/${parts[0]}/${encodeURIComponent(val)}`;
      } else {
        window.location.hash = `#/${parts[0]}`;
      }
    }
  });

  // Sync with store updates
  store.subscribe((state, key) => {
    if (key === 'datasets' || key === 'currentDatasetId') {
      updateSelectOptions(selectEl, state.datasets, state.currentDatasetId);
    }
  });
}

function updateSelectOptions(selectEl, datasets, currentId) {
  clearElement(selectEl);

  if (!datasets || datasets.length === 0) {
    selectEl.appendChild(el('option', { value: '' }, 'No dataset selected'));
    return;
  }

  datasets.forEach((item) => {
    const id = item.dataset_id;
    const name = item.filename || item.name || id;
    const label = `${safeText(name)} (${shortenId(id, 6)})`;
    const opt = el('option', {
      value: id,
      selected: id === currentId
    }, label);
    selectEl.appendChild(opt);
  });
}
