// POWER-SUB Application State Store
import { CONFIG } from './config.js';
import { validateApiUrl } from './utils/validate.js';

class Store {
  constructor() {
    this._listeners = new Set();
    this._inMemoryApiKey = null; // Stays in memory only; never persisted

    // Load persisted non-sensitive preferences defensively
    const prefs = this._loadPreferences();

    this._state = {
      apiBaseUrl: prefs.apiBaseUrl || CONFIG.DEFAULT_API_BASE,
      currentDatasetId: null,
      datasets: [],
      connectionStatus: 'connecting', // 'online' | 'offline' | 'connecting'
      lastHealthCheck: null,
      preferences: {
        pageSize: prefs.pageSize || 25,
        defaultSensitivity: prefs.defaultSensitivity || 'medium',
        defaultBaselineMethod: prefs.defaultBaselineMethod || 'historical_mean'
      }
    };
  }

  get state() {
    return this._state;
  }

  get apiBaseUrl() {
    return this._state.apiBaseUrl;
  }

  get apiKey() {
    return this._inMemoryApiKey;
  }

  get currentDatasetId() {
    return this._state.currentDatasetId;
  }

  get datasets() {
    return this._state.datasets;
  }

  get connectionStatus() {
    return this._state.connectionStatus;
  }

  // Setters with subscriber notification
  setApiKey(key) {
    this._inMemoryApiKey = key ? String(key).trim() : null;
    this._notify('apiKey');
  }

  setApiBaseUrl(url) {
    const res = validateApiUrl(url);
    if (!res.valid) {
      throw new Error(res.error || 'Invalid API Base URL');
    }
    this._state.apiBaseUrl = res.normalizedUrl;
    this._savePreferences();
    this._notify('apiBaseUrl');
  }

  setCurrentDatasetId(id) {
    const cleanId = id ? String(id).trim() : null;
    if (this._state.currentDatasetId !== cleanId) {
      this._state.currentDatasetId = cleanId;
      this._notify('currentDatasetId');
    }
  }

  setDatasets(list) {
    this._state.datasets = Array.isArray(list) ? list : [];
    // If current selected dataset was deleted or doesn't exist in the list, clear it
    if (this._state.currentDatasetId) {
      const exists = this._state.datasets.some((d) => d.dataset_id === this._state.currentDatasetId);
      if (!exists && this._state.datasets.length > 0) {
        // Keep current or clear if empty
      }
    }
    this._notify('datasets');
  }

  setConnectionStatus(status) {
    if (['online', 'offline', 'connecting'].includes(status)) {
      this._state.connectionStatus = status;
      this._state.lastHealthCheck = Date.now();
      this._notify('connectionStatus');
    }
  }

  updatePreferences(newPrefs) {
    this._state.preferences = { ...this._state.preferences, ...newPrefs };
    this._savePreferences();
    this._notify('preferences');
  }

  resetPreferences() {
    try {
      localStorage.removeItem(CONFIG.STORAGE_KEY);
    } catch {
      // Ignore storage access errors
    }
    this._state.apiBaseUrl = CONFIG.DEFAULT_API_BASE;
    this._state.preferences = {
      pageSize: 25,
      defaultSensitivity: 'medium',
      defaultBaselineMethod: 'historical_mean'
    };
    this._inMemoryApiKey = null;
    this._notify('reset');
  }

  // Subscribe to store updates
  subscribe(callback) {
    if (typeof callback === 'function') {
      this._listeners.add(callback);
      return () => this._listeners.delete(callback);
    }
    return () => {};
  }

  _notify(changedKey) {
    for (const listener of this._listeners) {
      try {
        listener(this._state, changedKey);
      } catch (err) {
        if (CONFIG.DEBUG) console.error('State listener error:', err);
      }
    }
  }

  _loadPreferences() {
    try {
      const raw = localStorage.getItem(CONFIG.STORAGE_KEY);
      if (!raw) return {};
      const parsed = JSON.parse(raw);
      if (typeof parsed !== 'object' || parsed === null) return {};

      // Defensive whitelisting only
      const clean = {};
      if (typeof parsed.apiBaseUrl === 'string') {
        const val = validateApiUrl(parsed.apiBaseUrl);
        if (val.valid) clean.apiBaseUrl = val.normalizedUrl;
      }
      if ([10, 25, 50, 100].includes(parsed.pageSize)) {
        clean.pageSize = parsed.pageSize;
      }
      if (['low', 'medium', 'high'].includes(parsed.defaultSensitivity)) {
        clean.defaultSensitivity = parsed.defaultSensitivity;
      }
      if (['historical_mean', 'historical_median', 'rolling_average', 'same_period_average', 'user_target'].includes(parsed.defaultBaselineMethod)) {
        clean.defaultBaselineMethod = parsed.defaultBaselineMethod;
      }
      return clean;
    } catch {
      return {};
    }
  }

  _savePreferences() {
    try {
      const dataToSave = {
        apiBaseUrl: this._state.apiBaseUrl,
        pageSize: this._state.preferences.pageSize,
        defaultSensitivity: this._state.preferences.defaultSensitivity,
        defaultBaselineMethod: this._state.preferences.defaultBaselineMethod
      };
      localStorage.setItem(CONFIG.STORAGE_KEY, JSON.stringify(dataToSave));
    } catch {
      // Storage unavailable or disabled
    }
  }
}

export const store = new Store();
