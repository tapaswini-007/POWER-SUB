// Dashboard Page Module
import { api, ApiError } from '../api.js';
import { store } from '../state.js';
import { el, clearElement, svgIcon } from '../utils/dom.js';
import { formatNumber, formatKwh, safeText } from '../utils/format.js';
import { createSpinner } from '../components/spinner.js';
import { createEmptyState } from '../components/emptyState.js';
import { createChart, destroyChart } from '../components/charts.js';

let activeChartCanvas = null;

export async function render(container, ctx) {
  clearElement(container);

  // If no datasets available in store, check if we need to fetch them
  let datasetId = ctx.datasetId || store.currentDatasetId;

  if (!datasetId && store.datasets.length === 0) {
    try {
      const resp = await api.listDatasets(1, 10, ctx.signal);
      if (resp && resp.items && resp.items.length > 0) {
        store.setDatasets(resp.items);
        datasetId = resp.items[0].dataset_id;
        store.setCurrentDatasetId(datasetId);
      }
    } catch {
      // Backend offline or empty
    }
  }

  // If still no dataset, render empty state
  if (!datasetId) {
    const empty = createEmptyState({
      title: 'No Energy Datasets Available',
      description: 'Upload your sub-metered electricity consumption reports (CSV, Excel) to begin consumption analysis and AI anomaly detection.',
      icon: 'upload',
      action: {
        text: 'Upload Energy Data',
        href: '#/upload'
      }
    });
    container.appendChild(empty);
    return;
  }

  // Render Loading placeholder
  const loading = el('div', { style: 'text-align: center; padding: 3rem;' },
    createSpinner('Loading dashboard metrics...')
  );
  container.appendChild(loading);

  try {
    // Parallel fetch analysis and anomaly results
    const [analysisRes, anomalyRes] = await Promise.allSettled([
      api.getAnalysis(datasetId, { signal: ctx.signal }),
      api.getAnomalies(datasetId, ctx.signal)
    ]);

    clearElement(container);

    if (analysisRes.status === 'rejected') {
      const err = analysisRes.reason;
      container.appendChild(createEmptyState({
        title: 'Unable to Load Dataset Analysis',
        description: err.message || 'Dataset records could not be retrieved.',
        icon: 'alert',
        action: { text: 'Upload New Dataset', href: '#/upload' }
      }));
      return;
    }

    const analysis = analysisRes.value;
    const summary = analysis.summary || {};
    const quality = analysis.data_quality || {};

    let anomalyDisplay = 'Not run yet';
    let anomalyCount = 0;
    let anomalyPercentage = 0;
    let anomalyData = null;

    if (anomalyRes.status === 'fulfilled') {
      anomalyData = anomalyRes.value;
      anomalyCount = anomalyData.anomalies_detected ?? 0;
      anomalyPercentage = anomalyData.anomaly_percentage ?? 0;
      anomalyDisplay = `${formatNumber(anomalyCount, 0)} (${formatNumber(anomalyPercentage, 1)}%)`;
    }

    // 1. KPI Metrics Grid
    const metricsGrid = el('div', { className: 'metrics-grid' });

    // Total Energy Card
    metricsGrid.appendChild(createMetricCard({
      title: 'Total Consumption',
      value: formatKwh(summary.total_consumption_kwh),
      subtitle: `${formatNumber(analysis.record_count, 0)} records analyzed`,
      icon: 'lightning'
    }));

    // Average Consumption
    metricsGrid.appendChild(createMetricCard({
      title: 'Mean Consumption',
      value: formatKwh(summary.mean_consumption_kwh),
      subtitle: `Median: ${formatKwh(summary.median_consumption_kwh)}`,
      icon: 'chart'
    }));

    // Maximum Peak
    metricsGrid.appendChild(createMetricCard({
      title: 'Peak Reading',
      value: formatKwh(summary.max_consumption_kwh),
      subtitle: `Min: ${formatKwh(summary.min_consumption_kwh)}`,
      icon: 'dashboard'
    }));

    // Flagged Anomalies
    metricsGrid.appendChild(createMetricCard({
      title: 'Flagged Anomalies',
      value: anomalyDisplay,
      subtitle: anomalyData ? 'Possible waste, needs investigation' : 'Click to run detection',
      icon: 'alert'
    }));

    // Data Quality Status
    const isQualityClean = quality.rejected_rows_count === 0 && (quality.warnings || []).length === 0;
    metricsGrid.appendChild(createMetricCard({
      title: 'Data Integrity',
      value: isQualityClean ? 'Clean' : 'Warnings',
      subtitle: `${formatNumber(quality.accepted_rows_count, 0)} accepted, ${formatNumber(quality.rejected_rows_count, 0)} rejected`,
      icon: 'shield'
    }));

    container.appendChild(metricsGrid);

    // 2. Trend & Overview Charts Section
    const chartCard = el('div', { className: 'chart-card card' });
    const chartHeader = el('div', { className: 'chart-card-header' },
      el('div', {},
        el('h2', { className: 'card-title', text: 'Recent Energy Trend' }),
        el('p', { className: 'card-subtitle', text: 'Daily consumption patterns across recorded intervals' })
      ),
      el('a', {
        className: 'btn btn-secondary btn-sm',
        href: `#/analysis/${encodeURIComponent(datasetId)}`,
        text: 'Full Analysis & Breakdowns →'
      })
    );
    chartCard.appendChild(chartHeader);

    const canvasContainer = el('div', { className: 'chart-container' });
    const canvas = el('canvas', { id: 'dashboard-trend-canvas' });
    canvasContainer.appendChild(canvas);
    chartCard.appendChild(canvasContainer);
    container.appendChild(chartCard);

    activeChartCanvas = canvas;

    // Populate chart from daily summary or trend
    const daily = analysis.daily_summary || [];
    if (daily.length > 0) {
      const labels = daily.map((d) => d.period || d.date || '—');
      const values = daily.map((d) => Number(d.consumption_kwh ?? d.total_kwh ?? 0));

      createChart(canvas, {
        type: 'line',
        data: {
          labels,
          datasets: [{
            label: 'Daily Consumption (kWh)',
            data: values,
            borderColor: '#0f766e',
            backgroundColor: 'rgba(15, 118, 110, 0.1)',
            fill: true,
            tension: 0.3,
            pointRadius: labels.length > 50 ? 0 : 3
          }]
        },
        options: {
          scales: {
            y: {
              title: { display: true, text: 'Energy (kWh)' },
              beginAtZero: true
            },
            x: {
              title: { display: true, text: 'Date' }
            }
          }
        }
      }, 'Daily consumption trend chart', {
        headers: ['Date', 'Energy (kWh)'],
        rows: daily.map((d) => [d.period || d.date || '—', formatNumber(d.consumption_kwh ?? d.total_kwh ?? 0)])
      });
    } else {
      canvasContainer.innerHTML = '';
      canvasContainer.appendChild(el('div', {
        style: 'height: 100%; display: flex; align-items: center; justify-content: center; color: var(--text-muted); font-size: 0.9rem;',
        text: 'Insufficient daily interval records to render trend line chart.'
      }));
    }

    // 3. Quick Actions Section
    const actionsCard = el('div', { className: 'card' },
      el('h2', { className: 'card-title', style: 'margin-bottom: 0.75rem;', text: 'Next Investigation Steps' }),
      el('div', { style: 'display: flex; gap: 0.75rem; flex-wrap: wrap;' },
        el('a', { className: 'btn btn-primary', href: `#/anomalies/${encodeURIComponent(datasetId)}`, text: 'Run AI Anomaly Detection' }),
        el('a', { className: 'btn btn-secondary', href: `#/recommendations/${encodeURIComponent(datasetId)}`, text: 'View Recommendations' }),
        el('a', { className: 'btn btn-outline', href: `#/reports/${encodeURIComponent(datasetId)}`, text: 'Export PDF Report' })
      )
    );
    container.appendChild(actionsCard);

  } catch (err) {
    if (ctx.signal.aborted) return;
    clearElement(container);
    container.appendChild(createEmptyState({
      title: 'Failed to Load Dashboard',
      description: err.message || 'An error occurred while connecting to backend.',
      icon: 'alert'
    }));
  }
}

function createMetricCard({ title, value, subtitle, icon }) {
  const card = el('div', { className: 'metric-card' });
  const header = el('div', { className: 'metric-header' },
    el('span', { className: 'metric-title', text: title }),
    el('div', { className: 'metric-icon-wrap' }, svgIcon(icon, '', 18))
  );
  const valEl = el('div', { className: 'metric-value', text: value });
  const subEl = el('div', { className: 'metric-subtitle', text: subtitle });

  card.appendChild(header);
  card.appendChild(valEl);
  card.appendChild(subEl);
  return card;
}

export function destroy() {
  if (activeChartCanvas) {
    destroyChart(activeChartCanvas);
    activeChartCanvas = null;
  }
}
