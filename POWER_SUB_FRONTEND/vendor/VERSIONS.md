# Vendored Libraries

This directory contains third-party dependencies vendored locally to eliminate runtime CDN dependencies, enable strict offline operation, and satisfy a zero-external-script Content Security Policy (CSP).

| Library | Exact Version | License | Source / Origin URL | Integrity / Checksum |
| :--- | :--- | :--- | :--- | :--- |
| **Chart.js (UMD)** | `4.4.2` | MIT | `https://cdn.jsdelivr.net/npm/chart.js@4.4.2/dist/chart.umd.min.js` | Local vendored bundle |

## Notes on Vendoring & Upgrades
- Chart.js is loaded synchronously in `index.html` via `<script src="vendor/chart.umd.min.js"></script>` so that the Chart constructor is globally accessible across ES module charts components.
- No other external CDNs (fonts, styles, scripts) are referenced at runtime.
- Icons are implemented as clean, self-contained SVG vectors created directly in `assets/` and `js/utils/dom.js`.
