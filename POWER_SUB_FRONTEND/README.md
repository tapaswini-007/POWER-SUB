# POWER-SUB: Frontend Web Application

A modern, responsive, accessible Single-Page Application (SPA) dashboard for:
**POWER-SUB: An AI-Based Software System for Energy Waste Detection, Consumption Analysis, and Intelligent Recommendations**

Designed for Windows 10/11 development and current desktop/mobile browsers (Chrome, Edge, Firefox). Built with standard vanilla HTML5, CSS3, and ES2020+ JavaScript Modules with **zero runtime build tools** and **zero external CDN dependencies**.

---

## 1. Core Principle & Ethical Scientific Interpretation

> [!IMPORTANT]
> **Fundamental Principle:** An AI-flagged anomaly is only a *possible sign* of energy waste, never confirmed waste.
>
> In accordance with energy auditing standards, the term **"Flagged anomaly"** or **"Possible waste, needs investigation"** is used strictly across all interfaces, charts, and reports. Certainty phrasing such as *"confirmed waste"* or *"waste detected"* is strictly prohibited. Statistical deviations must always be corroborated with physical operational schedules, building occupancy, weather conditions, and metering hardware integrity.

---

## 2. Architecture & Technology Stack

```text
               +-------------------------------------------------------+
               |                  Browser Client                       |
               |                                                       |
               |   index.html (App Shell, Strict CSP, Semantic Landmarks)|
               |                          |                            |
               |     +--------------------+--------------------+       |
               |     |                    |                    |       |
               |  router.js            state.js             api.js     |
               | (Hash Router)     (In-Memory Store)   (Fetch + Cache) |
               |     |                                         |       |
               |  pages/*.js                                   |       |
               | (Dynamic Imports)                             |       |
               +-----------------------------------------------|-------+
                                                               | HTTP / JSON & Blobs
                                                               v
               +-------------------------------------------------------+
               |            POWER-SUB FastAPI Backend                  |
               |             (http://127.0.0.1:8000)                   |
               +-------------------------------------------------------+
```

- **Runtime Architecture:** Vanilla ES2020+ ES Modules (`import`/`export`), custom CSS design tokens, and lightweight hash routing (`#/dashboard`, `#/upload`, `#/analysis`, `#/anomalies`, `#/recommendations`, `#/reports`, `#/history`, `#/settings`).
- **Data Visualization:** Locally vendored [Chart.js v4.4.2](vendor/chart.umd.min.js) with custom lifecycle tracking (guaranteed chart destruction before re-instantiation, downsampling to $\le 500$ points for time-series performance, and WCAG AA contrast).
- **Icons:** Self-contained inline vector SVG paths rendered via `js/utils/dom.js`.
- **Security & XSS Immunity:** 100% strict element construction via `el(tag, attrs, ...children)` and `textContent`. Dynamic data is **never interpolated into `innerHTML`**.

---

## 3. Directory Layout

```text
POWER_SUB_FRONTEND/
├── index.html                  # Semantic app shell with strict Content Security Policy
├── css/
│   ├── style.css               # Design tokens (CSS vars), typography, layout, cards, buttons, modals, toasts
│   ├── dashboard.css           # Metrics grid, dropzone, tables, charts, recommendation cards
│   └── responsive.css          # Mobile offcanvas drawer, tablet breakpoints, @media print
├── js/
│   ├── main.js                 # App startup, global error boundaries, dataset selector sync
│   ├── router.js               # Hash router with lazy dynamic page imports & lifecycle hooks
│   ├── state.js                # State store: current datasetId, preferences, in-memory API key
│   ├── api.js                  # Centralized HTTP client, AbortController timeouts, short TTL cache
│   ├── config.js               # Global limits, default URLs, endpoint mapping, disclaimer text
│   ├── utils/
│   │   ├── dom.js              # Safe element builder el(), clearElement(), SVG icon generator
│   │   ├── format.js           # Safe text formatting (zero NaN/null leakage), kwh, currency, dates
│   │   ├── validate.js         # File extension/size checks, URL safety, positive number checks
│   │   └── download.js         # Blob download helper with immediate URL.revokeObjectURL
│   ├── components/
│   │   ├── toast.js            # Accessible live announcements (role="status" / role="alert")
│   │   ├── modal.js            # Confirm dialog with focus trap & ESC handling
│   │   ├── spinner.js          # Accessible loading spinners & skeleton loaders
│   │   ├── emptyState.js       # Reusable illustration & message blocks
│   │   ├── statusBadge.js      # Status, priority, and algorithm badges
│   │   ├── connectionStatus.js # Header connection indicator & offline diagnostic modal
│   │   ├── notice.js           # Standard operational limitation notice banners
│   │   ├── dataTable.js        # Sortable, filterable, paginated table (DocumentFragment, 1000 row cap)
│   │   └── charts.js           # Chart.js registry, downsampling, and accessible table fallback
│   └── pages/
│       ├── dashboard.js        # Executive KPIs, energy summaries, trend sparkline
│       ├── upload.js           # Accessible drag-and-drop, unit selection, preview table
│       ├── analysis.js         # Baseline selector, custom targets, breakdown charts
│       ├── anomalies.js        # Isolation Forest controls, contamination slider, flagged records
│       ├── recommendations.js  # Prioritized recommendations, tariff input, defensible savings
│       ├── reports.js          # Formal PDF executive reports and raw CSV callsets
│       ├── history.js          # Ingested datasets list, schema inspect modal, deletion flow
│       └── settings.js         # Backend URL configuration, connection test, session key
├── vendor/
│   ├── chart.umd.min.js        # Vendored Chart.js 4.4.2 bundle
│   └── VERSIONS.md             # Pinned third-party version and license registry
├── assets/
│   └── logo.svg                # POWER-SUB vector logo
├── docs/
│   └── api-contract.md         # Full verified backend OpenAPI contract
├── tests/
│   ├── test.html               # Interactive browser-based unit test runner
│   └── test_frontend_integrity.py # Automated Python security & XSS integrity test suite
├── .gitignore
└── README.md
```

---

## 4. Windows Execution Instructions

### Step 1: Start the POWER-SUB FastAPI Backend
Open a PowerShell terminal in the project root:
```powershell
cd "c:\POWER SUB"
.\venv\Scripts\activate
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```
Verify the backend is live at `http://127.0.0.1:8000/docs`.

### Step 2: Start the Frontend Static Server
Open a second PowerShell terminal:
```powershell
cd "c:\POWER SUB\POWER_SUB_FRONTEND"
python -m http.server 5173 --bind 127.0.0.1
```

### Step 3: Open in Browser
Open `http://127.0.0.1:5173` in Google Chrome, Microsoft Edge, or Mozilla Firefox.

> [!NOTE]
> Modern JavaScript ES Modules require HTTP/HTTPS serving. Do not open `index.html` via `file://` protocol as browser security models prevent module imports from local filesystem paths.

---

## 5. Security & Privacy Architecture

1. **XSS Immunity via Safe DOM Construction:**
   - Text interpolation into `innerHTML`, `outerHTML`, or `insertAdjacentHTML` is **strictly forbidden**.
   - All server and user strings (file names, headers, building/equipment labels, error messages) are set exclusively using `textContent` or text nodes via `el()`.
   - Dynamic `javascript:` URLs are filtered out in `dom.js`.
2. **Strict Content Security Policy (CSP):**
   ```html
   <meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data: blob:; font-src 'self'; connect-src 'self' http://127.0.0.1:8000 http://localhost:8000; object-src 'none'; base-uri 'self'; form-action 'none'; frame-ancestors 'none'">
   ```
   No `'unsafe-inline'` or `'unsafe-eval'` is permitted in script execution.
3. **Storage Security & Ephemeral Secrets:**
   - `localStorage` stores only non-sensitive display preferences under the namespaced key `powersub.prefs.v1`.
   - If configured, the backend `X-API-Key` is held **strictly in volatile browser memory** and is never persisted to storage, cookies, or logs.
4. **Local Vendoring:**
   - Third-party scripts (Chart.js) are committed locally in `vendor/` so the application runs completely offline in local research labs.

---

## 6. API Endpoints Map

| Page | Method | Endpoint | Description |
| :--- | :--- | :--- | :--- |
| **Global / App Shell** | `GET` | `/api/v1/health` | Health monitor (version, status) |
| **Global / App Shell** | `GET` | `/api/v1/datasets` | Dataset selector dropdown items |
| **Upload Page** | `POST` | `/api/v1/energy/upload` | Multipart file upload (`.csv,.xlsx,.xls,.pdf`) |
| **Dashboard / Analysis**| `GET` | `/api/v1/analysis/{id}` | Summary metrics, baselines, breakdowns |
| **Anomaly Detection** | `POST` | `/api/v1/anomalies/{id}` | Run Isolation Forest screening |
| **Anomaly Detection** | `GET` | `/api/v1/anomalies/{id}` | Fetch previous anomaly results |
| **Recommendations** | `GET` | `/api/v1/recommendations/{id}` | Retrieve evidence-based action cards |
| **Reports & Exports** | `GET` | `/api/v1/reports/{id}/pdf` | Executive PDF report stream |
| **Reports & Exports** | `GET` | `/api/v1/reports/{id}/csv` | Anomaly screening callset CSV stream |
| **History Page** | `GET` | `/api/v1/datasets` | Paginated dataset history |
| **History Page** | `GET` | `/api/v1/datasets/{id}` | Full dataset schema metadata |
| **History Page** | `DELETE`| `/api/v1/datasets/{id}` | Delete dataset and clear caches |

---

## 7. Verification & Testing

### Running Automated Python Integrity Tests
From the workspace root:
```powershell
python -m unittest POWER_SUB_FRONTEND/tests/test_frontend_integrity.py
```
This tests:
- Local presence of vendored Chart.js and `VERSIONS.md`.
- Strict CSP meta tag structure without `'unsafe-inline'`/`'unsafe-eval'`.
- Absence of forbidden certainty wording (`"confirmed waste"`, `"waste detected"`).
- Static audit verifying zero dynamic interpolation into `innerHTML`.
- Absence of `eval()`, `new Function()`, and `document.write()`.
- Preference key namespacing.

### Running Interactive Browser Tests
Serve the frontend and open:
`http://127.0.0.1:5173/tests/test.html`
Verifies XSS escaping, safe text formatting (zero `NaN`/`null` leakage), client-side file and URL validators, UUID checks, and in-memory secret immunity.

---

## 8. Manual Verification Checklist

| # | Check Item | Status | Verification Detail |
| :--- | :--- | :--- | :--- |
| 1 | App Shell Loads | PASS | Clean rendering, no console errors, no CSP violations |
| 2 | Connection Indicator | PASS | Shows "Connected", toggles to "Offline" if backend stopped, auto-reconnects |
| 3 | File Upload Flow | PASS | Ingests `sample_data/sample_energy.csv`, displays real record count & preview |
| 4 | XSS Injection Test | PASS | Building names like `<img src=x onerror=alert(1)>` render as plain text |
| 5 | Energy Analysis Charts| PASS | Daily actual vs baseline, building breakdown, and monthly charts render accurately |
| 6 | Anomaly Detection | PASS | Distinguishes AI Isolation Forest vs Rule-based IQR fallback; displays notice |
| 7 | Recommendations | PASS | Shows `"Savings estimate unavailable..."` when savings cannot be calculated |
| 8 | Report Downloads | PASS | PDF and CSV blobs download with clean sanitized filenames |
| 9 | Dataset History & Delete| PASS | Lists datasets, inspects metadata, confirms deletion, clears selection |
| 10 | Responsive Layout | PASS | Desktop, tablet, and mobile offcanvas drawer function smoothly |
| 11 | Keyboard Accessibility | PASS | Skip-to-content, tab order, modal focus trap, and enter-to-dropzone work |
| 12 | Zero Dynamic innerHTML | PASS | Grep audit confirmed zero dynamic interpolation into `innerHTML` |
| 13 | Secrets in Storage | PASS | DevTools Inspection confirms no tokens or datasets in `localStorage` |

---

## 9. Troubleshooting & FAQ

- **Backend Offline / Fetch Error:**
  Ensure the backend is running at `http://127.0.0.1:8000`. Check that `ALLOWED_ORIGINS` in `.env` includes `http://127.0.0.1:5173`.
- **CORS Failure on Localhost vs 127.0.0.1:**
  Note that `http://localhost:5173` and `http://127.0.0.1:5173` are distinct browser origins. Use the identical origin configured in the backend `.env`.
- **Blank Page when Opening `index.html` directly:**
  Always use Python's HTTP server (`python -m http.server 5173`). ES module imports are blocked by browser CORS when loaded from `file:///`.
