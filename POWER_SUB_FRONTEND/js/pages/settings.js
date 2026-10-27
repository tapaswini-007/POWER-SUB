// System Settings & Connectivity Page Module
import { store } from '../state.js';
import { api } from '../api.js';
import { el, clearElement, svgIcon } from '../utils/dom.js';
import { validateApiUrl } from '../utils/validate.js';
import { showToast } from '../components/toast.js';
import { openConfirmModal } from '../components/modal.js';
import { createNotice } from '../components/notice.js';

export async function render(container, ctx) {
  clearElement(container);

  const headerCard = el('div', { className: 'card' },
    el('h2', { className: 'card-title', text: 'System & Connectivity Settings' }),
    el('p', {
      className: 'card-subtitle',
      text: 'Configure the backend FastAPI endpoint, test connectivity, manage session authentication, and customize local frontend defaults.'
    })
  );
  container.appendChild(headerCard);

  // 1. Backend Connectivity Card
  const connCard = el('div', { className: 'card' },
    el('h3', { className: 'card-title', style: 'margin-bottom: 0.5rem;', text: 'Backend API Connection' })
  );

  const urlInput = el('input', {
    type: 'url',
    className: 'form-input',
    id: 'settings-api-url',
    value: store.apiBaseUrl,
    placeholder: 'http://127.0.0.1:8000'
  });

  const unencryptedWarning = el('div', {
    className: 'notice-banner notice-warning',
    style: 'display: none; margin-top: 0.75rem;',
    text: 'Warning: This URL uses unencrypted HTTP to a remote host. Energy consumption data and API keys would be transmitted over plaintext networks.'
  });

  function checkUrlEncryption() {
    const res = validateApiUrl(urlInput.value);
    if (res.valid && res.isUnencryptedRemote) {
      unencryptedWarning.style.display = 'flex';
    } else {
      unencryptedWarning.style.display = 'none';
    }
  }

  urlInput.addEventListener('input', checkUrlEncryption);
  checkUrlEncryption();

  const testBtn = el('button', {
    type: 'button',
    className: 'btn btn-secondary',
    text: 'Test Connection',
    on: {
      click: async () => {
        testBtn.disabled = true;
        testBtn.textContent = 'Testing...';
        try {
          const res = validateApiUrl(urlInput.value);
          if (!res.valid) {
            showToast('Invalid URL', res.error, 'error');
            return;
          }
          store.setApiBaseUrl(res.normalizedUrl);

          const health = await api.getHealth();
          if (health && (health.status === 'healthy' || health.status === 'ok')) {
            showToast('Connection Successful', `Connected to POWER-SUB backend (v${health.version || '1.0.0'}).`, 'success');
            store.setConnectionStatus('online');
          } else {
            showToast('Unexpected Response', 'Backend reached but returned non-healthy status.', 'warning');
          }
        } catch (err) {
          showToast('Connection Failed', err.message || 'Could not connect to backend.', 'error');
          store.setConnectionStatus('offline');
        } finally {
          testBtn.disabled = false;
          testBtn.textContent = 'Test Connection';
        }
      }
    }
  });

  const saveUrlBtn = el('button', {
    type: 'button',
    className: 'btn btn-primary',
    text: 'Save Base URL',
    on: {
      click: () => {
        const res = validateApiUrl(urlInput.value);
        if (!res.valid) {
          showToast('Invalid URL', res.error, 'error');
          return;
        }
        store.setApiBaseUrl(res.normalizedUrl);
        showToast('Settings Saved', 'Backend API Base URL updated.', 'success');
      }
    }
  });

  connCard.appendChild(el('div', { className: 'form-group' },
    el('label', { className: 'form-label', htmlFor: 'settings-api-url', text: 'Backend API Base URL' }),
    urlInput,
    unencryptedWarning,
    el('span', { className: 'form-help', text: 'Default: http://127.0.0.1:8000. Note: Changing origins requires updating Content-Security-Policy connect-src.' })
  ));

  connCard.appendChild(el('div', { style: 'display: flex; gap: 0.75rem;' }, testBtn, saveUrlBtn));
  container.appendChild(connCard);

  // 2. Authentication (In-Memory Key Only)
  const authCard = el('div', { className: 'card' },
    el('h3', { className: 'card-title', style: 'margin-bottom: 0.5rem;', text: 'API Key Authentication (Session Only)' }),
    el('p', {
      style: 'font-size: 0.85rem; color: var(--text-secondary); margin-bottom: 1rem;',
      text: 'For security, your API key is retained strictly in volatile browser memory and will NEVER be stored in localStorage, sessionStorage, or browser cookies. It must be re-entered upon page reload.'
    })
  );

  const apiKeyInput = el('input', {
    type: 'password',
    className: 'form-input',
    id: 'settings-api-key',
    value: store.apiKey || '',
    placeholder: 'Enter backend X-API-Key (optional)',
    autocomplete: 'off'
  });

  const setKeyBtn = el('button', {
    type: 'button',
    className: 'btn btn-primary',
    text: 'Set Session Key',
    on: {
      click: () => {
        const val = apiKeyInput.value.trim();
        store.setApiKey(val || null);
        if (val) {
          showToast('API Key Active', 'API key configured for this active session.', 'info');
        } else {
          showToast('API Key Cleared', 'Session API key removed.', 'info');
        }
      }
    }
  });

  authCard.appendChild(el('div', { className: 'form-group' },
    el('label', { className: 'form-label', htmlFor: 'settings-api-key', text: 'X-API-Key Header' }),
    apiKeyInput
  ));
  authCard.appendChild(setKeyBtn);
  container.appendChild(authCard);

  // 3. Frontend Request Defaults & Preferences
  const prefsCard = el('div', { className: 'card' },
    el('h3', { className: 'card-title', style: 'margin-bottom: 0.5rem;', text: 'Frontend UI Preferences' }),
    el('p', {
      className: 'card-subtitle',
      style: 'margin-bottom: 1rem;',
      text: 'These options act as client-side defaults for your requests and tables. They do not alter backend server configuration.'
    })
  );

  const prefs = store.state.preferences;

  // Table Page Size
  const pageSizeSelect = el('select', { className: 'form-select', id: 'pref-page-size' },
    el('option', { value: 10, selected: prefs.pageSize === 10 }, '10 rows per page'),
    el('option', { value: 25, selected: prefs.pageSize === 25 }, '25 rows per page (Default)'),
    el('option', { value: 50, selected: prefs.pageSize === 50 }, '50 rows per page'),
    el('option', { value: 100, selected: prefs.pageSize === 100 }, '100 rows per page')
  );

  // Default Baseline Method
  const baselineMethodSelect = el('select', { className: 'form-select', id: 'pref-baseline-method' },
    el('option', { value: 'historical_mean', selected: prefs.defaultBaselineMethod === 'historical_mean' }, 'Historical Mean (Default)'),
    el('option', { value: 'historical_median', selected: prefs.defaultBaselineMethod === 'historical_median' }, 'Historical Median'),
    el('option', { value: 'rolling_average', selected: prefs.defaultBaselineMethod === 'rolling_average' }, 'Rolling Average'),
    el('option', { value: 'same_period_average', selected: prefs.defaultBaselineMethod === 'same_period_average' }, 'Same Period Average')
  );

  // Default Anomaly Sensitivity
  const sensitivitySelect = el('select', { className: 'form-select', id: 'pref-sensitivity' },
    el('option', { value: 'low', selected: prefs.defaultSensitivity === 'low' }, 'Low Sensitivity'),
    el('option', { value: 'medium', selected: prefs.defaultSensitivity === 'medium' }, 'Medium Sensitivity (Default)'),
    el('option', { value: 'high', selected: prefs.defaultSensitivity === 'high' }, 'High Sensitivity')
  );

  const formGrid = el('div', {
    style: 'display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 1rem; margin-bottom: 1.25rem;'
  },
    el('div', { className: 'form-group' },
      el('label', { className: 'form-label', htmlFor: 'pref-page-size', text: 'Default Table Page Size' }),
      pageSizeSelect
    ),
    el('div', { className: 'form-group' },
      el('label', { className: 'form-label', htmlFor: 'pref-baseline-method', text: 'Default Baseline Method' }),
      baselineMethodSelect
    ),
    el('div', { className: 'form-group' },
      el('label', { className: 'form-label', htmlFor: 'pref-sensitivity', text: 'Default Anomaly Sensitivity' }),
      sensitivitySelect
    )
  );
  prefsCard.appendChild(formGrid);

  const savePrefsBtn = el('button', {
    type: 'button',
    className: 'btn btn-primary',
    text: 'Save Preferences',
    on: {
      click: () => {
        store.updatePreferences({
          pageSize: Number(pageSizeSelect.value),
          defaultBaselineMethod: baselineMethodSelect.value,
          defaultSensitivity: sensitivitySelect.value
        });
        showToast('Preferences Saved', 'Client display defaults stored successfully.', 'success');
      }
    }
  });

  const resetPrefsBtn = el('button', {
    type: 'button',
    className: 'btn btn-outline',
    text: 'Reset to Factory Defaults',
    on: {
      click: () => {
        openConfirmModal({
          title: 'Reset Preferences',
          content: 'Reset all stored local browser preferences (API Base URL and table settings) to original defaults?',
          confirmText: 'Reset Defaults',
          confirmVariant: 'danger',
          onConfirm: () => {
            store.resetPreferences();
            urlInput.value = store.apiBaseUrl;
            pageSizeSelect.value = '25';
            baselineMethodSelect.value = 'historical_mean';
            sensitivitySelect.value = 'medium';
            showToast('Reset Complete', 'Local preferences have been cleared.', 'info');
          }
        });
      }
    }
  });

  prefsCard.appendChild(el('div', { style: 'display: flex; gap: 0.75rem;' }, savePrefsBtn, resetPrefsBtn));
  container.appendChild(prefsCard);
}

export function destroy() {
  // Cleanup
}
