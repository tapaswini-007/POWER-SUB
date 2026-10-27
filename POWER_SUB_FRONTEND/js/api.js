// Centralized API Client Module for POWER-SUB Backend
import { CONFIG } from './config.js';
import { store } from './state.js';

/**
 * Custom Typed API Error.
 */
export class ApiError extends Error {
  constructor(message, status = 0, code = 'API_ERROR', requestId = null, details = null) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.requestId = requestId;
    this.details = details;
  }
}

export class NetworkError extends Error {
  constructor(message = 'Network connection failed. Is the POWER-SUB backend running?') {
    super(message);
    this.name = 'NetworkError';
  }
}

export class TimeoutError extends Error {
  constructor(message = 'Request timed out waiting for backend response.') {
    super(message);
    this.name = 'TimeoutError';
  }
}

// In-Memory Cache with TTL
const cache = new Map();
const inFlightRequests = new Map();

/**
 * Invalidates cache entries matching a datasetId or completely.
 * @param {string} [datasetId]
 */
export function invalidateCache(datasetId = null) {
  if (!datasetId) {
    cache.clear();
    return;
  }
  for (const key of cache.keys()) {
    if (key.includes(datasetId)) {
      cache.delete(key);
    }
  }
}

/**
 * Primary HTTP request dispatcher.
 */
async function request(method, path, options = {}) {
  const {
    query = null,
    body = null,
    signal = null,
    timeoutMs = CONFIG.TIMEOUTS.DEFAULT_MS,
    responseType = 'json',
    skipCache = false,
    onUploadProgress = null
  } = options;

  const baseUrl = store.apiBaseUrl;

  // Build query string safely
  let url = `${baseUrl}${path}`;
  if (query && typeof query === 'object') {
    const params = new URLSearchParams();
    for (const [k, v] of Object.entries(query)) {
      if (v !== null && v !== undefined && String(v).trim() !== '') {
        params.append(k, String(v).trim());
      }
    }
    const qs = params.toString();
    if (qs) {
      url += (url.includes('?') ? '&' : '?') + qs;
    }
  }

  // Check GET cache
  const cacheKey = `${method}:${url}`;
  if (method === 'GET' && !skipCache && responseType === 'json') {
    const cached = cache.get(cacheKey);
    if (cached && Date.now() < cached.expiresAt) {
      return cached.data;
    }
  }

  // Deduplicate concurrent GETs
  if (method === 'GET' && inFlightRequests.has(cacheKey)) {
    return inFlightRequests.get(cacheKey);
  }

  const reqPromise = (async () => {
    // Setup AbortController for timeouts
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort('timeout'), timeoutMs);

    // Merge external abort signal if provided
    if (signal) {
      signal.addEventListener('abort', () => controller.abort(signal.reason));
    }

    // Prepare headers
    const headers = {};
    if (store.apiKey) {
      headers['X-API-Key'] = store.apiKey;
    }

    let requestBody = body;
    if (body && !(body instanceof FormData) && typeof body === 'object') {
      headers['Content-Type'] = 'application/json';
      requestBody = JSON.stringify(body);
    }

    try {
      // Use XMLHttpRequest if upload progress is requested and body is FormData
      if (onUploadProgress && body instanceof FormData) {
        return await new Promise((resolve, reject) => {
          const xhr = new XMLHttpRequest();
          xhr.open(method, url, true);
          xhr.timeout = timeoutMs;

          for (const [hKey, hVal] of Object.entries(headers)) {
            xhr.setRequestHeader(hKey, hVal);
          }

          if (signal) {
            signal.addEventListener('abort', () => xhr.abort());
          }

          xhr.upload.onprogress = (evt) => {
            if (evt.lengthComputable) {
              const percent = Math.round((evt.loaded / evt.total) * 100);
              onUploadProgress(percent, evt.loaded, evt.total);
            }
          };

          xhr.onload = () => {
            clearTimeout(timeoutId);
            const reqId = xhr.getResponseHeader('X-Request-ID');
            let respData = null;
            try {
              respData = JSON.parse(xhr.responseText);
            } catch {
              respData = { message: xhr.responseText };
            }

            if (xhr.status >= 200 && xhr.status < 300) {
              resolve(respData);
            } else {
              const err = parseErrorEnvelope(respData, xhr.status, reqId);
              reject(err);
            }
          };

          xhr.onerror = () => {
            clearTimeout(timeoutId);
            reject(new NetworkError('Network connection failed during upload. Check backend status and CORS.'));
          };

          xhr.ontimeout = () => {
            clearTimeout(timeoutId);
            reject(new TimeoutError('Upload timed out. File processing took longer than expected.'));
          };

          xhr.onabort = () => {
            clearTimeout(timeoutId);
            reject(new DOMException('Upload aborted by user', 'AbortError'));
          };

          xhr.send(body);
        });
      }

      // Standard Fetch
      const response = await fetch(url, {
        method,
        headers,
        body: requestBody,
        signal: controller.signal,
        redirect: 'error'
      });

      clearTimeout(timeoutId);
      const reqId = response.headers.get('X-Request-ID');

      if (!response.ok) {
        let errData = null;
        try {
          errData = await response.json();
        } catch {
          errData = { message: response.statusText || 'Unknown error' };
        }
        throw parseErrorEnvelope(errData, response.status, reqId);
      }

      if (responseType === 'blob') {
        return await response.blob();
      }

      const json = await response.json();

      // Store in memory cache for GETs (60s TTL)
      if (method === 'GET' && !skipCache) {
        cache.set(cacheKey, {
          data: json,
          expiresAt: Date.now() + 60000
        });
      }

      return json;
    } catch (err) {
      clearTimeout(timeoutId);
      if (err instanceof ApiError) throw err;
      if (err.name === 'AbortError' || controller.signal.aborted) {
        if (controller.signal.reason === 'timeout') {
          throw new TimeoutError();
        }
        throw err;
      }
      if (err instanceof TypeError && err.message.includes('fetch')) {
        throw new NetworkError('Backend connection failed. Make sure backend is running and ALLOWED_ORIGINS includes this origin.');
      }
      throw err;
    } finally {
      inFlightRequests.delete(cacheKey);
    }
  })();

  if (method === 'GET') {
    inFlightRequests.set(cacheKey, reqPromise);
  }

  return reqPromise;
}

/**
 * Normalizes backend error envelopes.
 */
function parseErrorEnvelope(data, status, requestId) {
  let message = 'An error occurred while processing the request.';
  let code = 'ERROR';
  let details = null;
  let reqId = requestId;

  if (data && typeof data === 'object') {
    if (data.error && typeof data.error === 'object') {
      message = data.error.message || message;
      code = data.error.code || code;
      details = data.error.details || null;
      reqId = data.error.request_id || reqId;
    } else if (data.detail) {
      if (typeof data.detail === 'string') {
        message = data.detail;
      } else if (Array.isArray(data.detail)) {
        // FastAPI validation errors array
        message = data.detail.map((d) => d.msg || `${d.loc ? d.loc.join('.') + ': ' : ''}${d.type}`).join('; ');
        details = data.detail;
      }
    } else if (data.message) {
      message = data.message;
    }
  }

  return new ApiError(message, status, code, reqId, details);
}

// Public Endpoint Methods
export const api = {
  /**
   * GET /api/v1/health
   */
  async getHealth(signal = null) {
    return request('GET', CONFIG.ENDPOINTS.HEALTH, {
      signal,
      timeoutMs: 5000,
      skipCache: true
    });
  },

  /**
   * POST /api/v1/energy/upload
   */
  async uploadFile(file, options = {}) {
    const { energyUnit = null, sheetName = null, onProgress = null, signal = null } = options;
    const formData = new FormData();
    formData.append('file', file);

    const query = {};
    if (energyUnit) query.energy_unit = energyUnit;
    if (sheetName) query.sheet_name = sheetName;

    const res = await request('POST', CONFIG.ENDPOINTS.UPLOAD, {
      query,
      body: formData,
      signal,
      timeoutMs: CONFIG.TIMEOUTS.UPLOAD_MS,
      onUploadProgress: onProgress
    });

    invalidateCache();
    return res;
  },

  /**
   * GET /api/v1/datasets
   */
  async listDatasets(page = 1, pageSize = 20, signal = null) {
    const limit = pageSize;
    const offset = Math.max(0, (page - 1) * pageSize);
    const res = await request('GET', CONFIG.ENDPOINTS.DATASETS, {
      query: { limit, offset },
      signal
    });
    if (res && Array.isArray(res.items)) {
      res.items.forEach((item) => {
        item.dataset_id = item.id || item.dataset_id;
        item.filename = item.display_filename || item.filename || item.name;
      });
    }
    return res;
  },

  /**
   * GET /api/v1/datasets/{id}
   */
  async getDataset(datasetId, signal = null) {
    return request('GET', CONFIG.ENDPOINTS.DATASET_DETAIL(datasetId), { signal });
  },

  /**
   * DELETE /api/v1/datasets/{id}
   */
  async deleteDataset(datasetId, signal = null) {
    const res = await request('DELETE', CONFIG.ENDPOINTS.DATASET_DELETE(datasetId), { signal });
    invalidateCache(datasetId);
    return res;
  },

  /**
   * GET /api/v1/analysis/{id}
   */
  async getAnalysis(datasetId, options = {}) {
    const { baselineMethod = null, userTarget = null, signal = null } = options;
    const query = {};
    if (baselineMethod) query.baseline_method = baselineMethod;
    if (userTarget !== null && userTarget !== undefined && userTarget !== '') {
      query.user_target = userTarget;
    }

    return request('GET', CONFIG.ENDPOINTS.ANALYSIS(datasetId), {
      query,
      signal
    });
  },

  /**
   * POST /api/v1/anomalies/{id}
   */
  async runAnomalies(datasetId, options = {}) {
    const { contamination = 0.05, sensitivity = 'medium', signal = null } = options;
    const query = {
      contamination,
      sensitivity
    };

    const res = await request('POST', CONFIG.ENDPOINTS.ANOMALIES_RUN(datasetId), {
      query,
      signal
    });

    invalidateCache(datasetId);
    return res;
  },

  /**
   * GET /api/v1/anomalies/{id}
   */
  async getAnomalies(datasetId, signal = null) {
    return request('GET', CONFIG.ENDPOINTS.ANOMALIES_GET(datasetId), { signal });
  },

  /**
   * GET /api/v1/recommendations/{id}
   */
  async getRecommendations(datasetId, options = {}) {
    const { tariffPerKwh = null, signal = null } = options;
    const query = {};
    if (tariffPerKwh !== null && tariffPerKwh !== undefined && tariffPerKwh !== '') {
      query.tariff_per_kwh = tariffPerKwh;
    }

    return request('GET', CONFIG.ENDPOINTS.RECOMMENDATIONS(datasetId), {
      query,
      signal
    });
  },

  /**
   * GET /api/v1/reports/{id}/pdf
   */
  async downloadReportPdf(datasetId, signal = null) {
    return request('GET', CONFIG.ENDPOINTS.REPORT_PDF(datasetId), {
      signal,
      responseType: 'blob',
      timeoutMs: CONFIG.TIMEOUTS.REPORT_MS
    });
  },

  /**
   * GET /api/v1/reports/{id}/csv
   */
  async downloadReportCsv(datasetId, signal = null) {
    return request('GET', CONFIG.ENDPOINTS.REPORT_CSV(datasetId), {
      signal,
      responseType: 'blob',
      timeoutMs: CONFIG.TIMEOUTS.REPORT_MS
    });
  }
};
