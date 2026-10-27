// SPA Hash Router with Lifecycle Management & Dynamic Page Loading
import { store } from './state.js';
import { clearElement, el } from './utils/dom.js';
import { isValidUuid } from './utils/validate.js';
import { destroyAllCharts } from './components/charts.js';

const ROUTES = {
  'dashboard': { file: 'dashboard.js', title: 'Dashboard Overview' },
  'upload': { file: 'upload.js', title: 'Upload Energy Data' },
  'analysis': { file: 'analysis.js', title: 'Energy Consumption Analysis' },
  'anomalies': { file: 'anomalies.js', title: 'AI Anomaly Detection' },
  'recommendations': { file: 'recommendations.js', title: 'Smart Energy Recommendations' },
  'reports': { file: 'reports.js', title: 'Download Reports & Exports' },
  'history': { file: 'history.js', title: 'Dataset History & Management' },
  'settings': { file: 'settings.js', title: 'System Settings & Connectivity' }
};

let currentViewContainer = null;
let currentPageModule = null;
let currentAbortController = null;

/**
 * Initializes the hash router.
 * @param {HTMLElement} viewContainer
 */
export function initRouter(viewContainer) {
  currentViewContainer = viewContainer;

  window.addEventListener('hashchange', handleRoute);

  // Initial routing
  if (!window.location.hash || window.location.hash === '#/') {
    window.location.hash = '#/dashboard';
  } else {
    handleRoute();
  }
}

/**
 * Main route dispatcher.
 */
async function handleRoute() {
  const hash = window.location.hash.replace(/^#\/?/, '').trim();
  const segments = hash.split('/').filter(Boolean);
  const routeKey = segments[0] || 'dashboard';
  const param = segments[1] || null;

  // Cleanup active page lifecycle
  if (currentPageModule && typeof currentPageModule.destroy === 'function') {
    try {
      currentPageModule.destroy();
    } catch (err) {
      console.error('Error destroying page:', err);
    }
  }

  // Cancel any pending network requests from previous page
  if (currentAbortController) {
    currentAbortController.abort('navigation');
  }
  currentAbortController = new AbortController();

  // Destroy all active charts to prevent memory leaks
  destroyAllCharts();

  // If a valid UUID parameter was passed in the URL, sync to store
  if (param && isValidUuid(param)) {
    store.setCurrentDatasetId(param);
  }

  // Update nav link active state in sidebar
  updateNavSelection(routeKey);

  const routeConfig = ROUTES[routeKey];
  if (!routeConfig) {
    renderNotFound();
    return;
  }

  // Update header title
  const titleEl = document.getElementById('page-title-heading');
  if (titleEl) {
    titleEl.textContent = routeConfig.title;
  }
  document.title = `POWER-SUB — ${routeConfig.title}`;

  // Close mobile sidebar if open
  const sidebar = document.getElementById('app-sidebar');
  const backdrop = document.getElementById('sidebar-backdrop');
  if (sidebar && sidebar.classList.contains('open')) {
    sidebar.classList.remove('open');
    if (backdrop) backdrop.classList.remove('active');
  }

  clearElement(currentViewContainer);

  try {
    // Dynamic import of hardcoded local page modules
    let pageMod;
    switch (routeKey) {
      case 'dashboard':
        pageMod = await import('./pages/dashboard.js');
        break;
      case 'upload':
        pageMod = await import('./pages/upload.js');
        break;
      case 'analysis':
        pageMod = await import('./pages/analysis.js');
        break;
      case 'anomalies':
        pageMod = await import('./pages/anomalies.js');
        break;
      case 'recommendations':
        pageMod = await import('./pages/recommendations.js');
        break;
      case 'reports':
        pageMod = await import('./pages/reports.js');
        break;
      case 'history':
        pageMod = await import('./pages/history.js');
        break;
      case 'settings':
        pageMod = await import('./pages/settings.js');
        break;
      default:
        renderNotFound();
        return;
    }

    currentPageModule = pageMod;

    const ctx = {
      param,
      signal: currentAbortController.signal,
      datasetId: store.currentDatasetId
    };

    if (typeof pageMod.render === 'function') {
      await pageMod.render(currentViewContainer, ctx);
    }
  } catch (err) {
    if (err.name === 'AbortError' || currentAbortController.signal.aborted) {
      return; // Navigation aborted
    }
    console.error('Page rendering error:', err);
    renderError(err);
  }
}

function updateNavSelection(activeKey) {
  const links = document.querySelectorAll('.sidebar-nav .nav-link');
  links.forEach((link) => {
    const route = link.dataset.route;
    if (route === activeKey) {
      link.setAttribute('aria-current', 'page');
    } else {
      link.removeAttribute('aria-current');
    }
  });
}

function renderNotFound() {
  clearElement(currentViewContainer);
  const card = el('div', { className: 'card empty-state' },
    el('h2', { className: 'empty-state-title', text: '404 — Page Not Found' }),
    el('p', { className: 'empty-state-desc', text: 'The requested route does not exist.' }),
    el('a', { className: 'btn btn-primary', href: '#/dashboard', text: 'Back to Dashboard' })
  );
  currentViewContainer.appendChild(card);
}

function renderError(err) {
  clearElement(currentViewContainer);
  const card = el('div', { className: 'card empty-state' },
    el('h2', { className: 'empty-state-title', style: 'color: var(--color-danger);', text: 'Error Loading View' }),
    el('p', { className: 'empty-state-desc', text: err.message || 'An unexpected error occurred while rendering this page.' }),
    el('button', {
      type: 'button',
      className: 'btn btn-secondary',
      text: 'Retry',
      on: { click: () => handleRoute() }
    })
  );
  currentViewContainer.appendChild(card);
}
