// Chart.js Wrapper with Lifecycle Management, Theme & Downsampling
import { el, clearElement } from '../utils/dom.js';
import { formatNumber, formatKwh } from '../utils/format.js';

// Chart instance registry: Map<HTMLCanvasElement, ChartInstance>
const chartRegistry = new Map();

/**
 * Checks if user prefers reduced motion.
 */
function prefersReducedMotion() {
  return window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

/**
 * Downsamples time series data points to at most maxPoints (default 500) using bucket averaging.
 * @param {Array<string>} labels
 * @param {Array<number>} values
 * @param {number} [maxPoints=500]
 * @returns {{ labels: Array<string>, values: Array<number>, isDownsampled: boolean }}
 */
export function downsampleData(labels, values, maxPoints = 500) {
  if (!Array.isArray(labels) || !Array.isArray(values) || labels.length <= maxPoints) {
    return { labels: labels || [], values: values || [], isDownsampled: false };
  }

  const length = labels.length;
  const bucketSize = length / maxPoints;
  const downsampledLabels = [];
  const downsampledValues = [];

  for (let i = 0; i < maxPoints; i++) {
    const startIdx = Math.floor(i * bucketSize);
    const endIdx = Math.floor((i + 1) * bucketSize);
    const bucketValues = values.slice(startIdx, endIdx);

    const sum = bucketValues.reduce((acc, v) => acc + (Number(v) || 0), 0);
    const avg = bucketValues.length > 0 ? sum / bucketValues.length : 0;

    downsampledLabels.push(labels[startIdx]);
    downsampledValues.push(parseFloat(avg.toFixed(2)));
  }

  return {
    labels: downsampledLabels,
    values: downsampledValues,
    isDownsampled: true
  };
}

/**
 * Destroys any existing chart on a canvas.
 * @param {HTMLCanvasElement} canvas
 */
export function destroyChart(canvas) {
  if (canvas && chartRegistry.has(canvas)) {
    try {
      const instance = chartRegistry.get(canvas);
      instance.destroy();
    } catch {
      // Ignore
    }
    chartRegistry.delete(canvas);
  }
}

/**
 * Destroys all currently registered charts.
 */
export function destroyAllCharts() {
  for (const [canvas, instance] of chartRegistry.entries()) {
    try {
      instance.destroy();
    } catch {
      // Ignore
    }
  }
  chartRegistry.clear();
}

/**
 * Creates and registers a new Chart.js instance with accessibility table fallback.
 * @param {HTMLCanvasElement} canvas
 * @param {Object} config - Chart.js configuration
 * @param {string} ariaLabel - Descriptive accessibility label for the chart
 * @param {Object} [tableData=null] - { headers: string[], rows: (string|number)[][] }
 * @returns {Chart|null}
 */
export function createChart(canvas, config, ariaLabel, tableData = null) {
  if (!canvas) return null;

  // Window.Chart must be loaded from vendor/chart.umd.min.js
  if (typeof window.Chart === 'undefined') {
    console.error('Chart.js library is not loaded.');
    return null;
  }

  // Destroy previous chart on this canvas
  destroyChart(canvas);

  canvas.setAttribute('role', 'img');
  canvas.setAttribute('aria-label', ariaLabel);

  // Set default responsive options
  config.options = config.options || {};
  config.options.responsive = true;
  config.options.maintainAspectRatio = false;

  // Reduced motion support
  if (prefersReducedMotion() || (config.data && config.data.labels && config.data.labels.length > 300)) {
    config.options.animation = false;
  }

  // Format tooltips if not customized
  if (!config.options.plugins) config.options.plugins = {};
  if (!config.options.plugins.tooltip) {
    config.options.plugins.tooltip = {
      callbacks: {
        label: (context) => {
          const val = context.parsed.y !== undefined ? context.parsed.y : context.parsed;
          return `${context.dataset.label || 'Value'}: ${formatKwh(val)}`;
        }
      }
    };
  }

  const chart = new window.Chart(canvas, config);
  chartRegistry.set(canvas, chart);

  // Append accessible table alternative if container provided
  if (tableData && canvas.parentElement) {
    renderAccessibleTableAlternative(canvas.parentElement, ariaLabel, tableData);
  }

  return chart;
}

/**
 * Appends a collapsible accessible data table alternative for screen readers and export.
 */
function renderAccessibleTableAlternative(container, title, tableData) {
  const existing = container.querySelector('.chart-table-toggle');
  if (existing) existing.remove();

  const details = el('details', { className: 'chart-table-toggle' },
    el('summary', {
      style: 'font-size: 0.8rem; color: var(--color-primary); cursor: pointer; font-weight: 600;',
      text: `View data table for: ${title}`
    })
  );

  const table = el('table', { className: 'chart-fallback-table' });
  const thead = el('thead');
  const theadRow = el('tr');

  (tableData.headers || []).forEach((h) => {
    theadRow.appendChild(el('th', { text: h }));
  });
  thead.appendChild(theadRow);
  table.appendChild(thead);

  const tbody = el('tbody');
  // Limit fallback table to first 50 rows to prevent DOM bloat
  const rowsToDisplay = (tableData.rows || []).slice(0, 50);

  rowsToDisplay.forEach((row) => {
    const tr = el('tr');
    row.forEach((cell) => {
      tr.appendChild(el('td', { text: String(cell) }));
    });
    tbody.appendChild(tr);
  });
  table.appendChild(tbody);

  if ((tableData.rows || []).length > 50) {
    table.appendChild(el('tfoot', {},
      el('tr', {},
        el('td', {
          colSpan: (tableData.headers || []).length,
          style: 'font-style: italic; color: var(--text-muted); font-size: 0.75rem;',
          text: `Showing first 50 of ${tableData.rows.length} rows.`
        })
      )
    ));
  }

  details.appendChild(table);
  container.appendChild(details);
}
