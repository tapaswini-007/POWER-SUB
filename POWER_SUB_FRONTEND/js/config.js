// POWER-SUB Global Configuration & Constants

export const CONFIG = Object.freeze({
  DEFAULT_API_BASE: 'http://127.0.0.1:8000',
  STORAGE_KEY: 'powersub.prefs.v1',
  MAX_FILE_SIZE_BYTES: 10 * 1024 * 1024, // 10 MB
  ALLOWED_EXTENSIONS: ['.csv', '.xlsx', '.xls', '.pdf'],
  TIMEOUTS: {
    DEFAULT_MS: 30000,
    UPLOAD_MS: 120000,
    REPORT_MS: 120000,
    HEALTH_POLL_MS: 30000
  },
  ENDPOINTS: {
    HEALTH: '/api/v1/health',
    UPLOAD: '/api/v1/upload',
    DATASETS: '/api/v1/datasets',
    DATASET_DETAIL: (id) => `/api/v1/datasets/${encodeURIComponent(id)}`,
    DATASET_DELETE: (id) => `/api/v1/datasets/${encodeURIComponent(id)}`,
    ANALYSIS: (id) => `/api/v1/analysis/${encodeURIComponent(id)}`,
    ANOMALIES_RUN: (id) => `/api/v1/anomalies/${encodeURIComponent(id)}`,
    ANOMALIES_GET: (id) => `/api/v1/anomalies/${encodeURIComponent(id)}`,
    RECOMMENDATIONS: (id) => `/api/v1/recommendations/${encodeURIComponent(id)}`,
    REPORT_PDF: (id) => `/api/v1/reports/${encodeURIComponent(id)}/pdf`,
    REPORT_CSV: (id) => `/api/v1/reports/${encodeURIComponent(id)}/csv`
  },
  DISCLAIMER_TEXT: 'Anomaly detection identifies unusual consumption patterns. A flagged record does not necessarily indicate energy waste. Review operational schedules, occupancy, weather, and equipment conditions before taking action.',
  SAVINGS_UNAVAILABLE_TEXT: 'Savings estimate unavailable — additional data required.',
  DEBUG: false
});
