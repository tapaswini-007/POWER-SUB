// Energy Consumption Analysis Page Module
import { api, ApiError } from '../api.js';
import { store } from '../state.js';
import { el, clearElement, svgIcon } from '../utils/dom.js';
import { formatNumber, formatKwh, formatPercent, formatCurrency, safeText } from '../utils/format.js';
import { isPositiveNumber } from '../utils/validate.js';
import { showToast } from '../components/toast.js';
import { createSpinner } from '../components/spinner.js';
import { createEmptyState } from '../components/emptyState.js';
import { createChart, destroyChart, downsampleData } from '../components/charts.js';
import { createDataTable } from '../components/dataTable.js';

let activeCanvases = [];

export async function render(container, ctx) {
  clearElement(container);
  activeCanvases = [];

  const datasetId = ctx.param || ctx.datasetId || store.currentDatasetId;

  if (!datasetId) {
    container.appendChild(createEmptyState({
      title: 'No Dataset Selected',
      description: 'Select an existing dataset from the header or upload new consumption readings to view detailed energy analytics.',
      icon: 'chart',
      action: { text: 'Upload Energy Data', href: '#/upload' }
    }));
    return;
  }

  // Header & Controls Card
  const headerCard = el('div', { className: 'card' },
    el('div', { className: 'card-header' },
      el('div', {},
        el('h2', { className: 'card-title', text: 'Energy Consumption & Baseline Analysis' }),
        el('p', { className: 'card-subtitle', text: `Analyzing dataset: ${datasetId}` })
      ),
      el('div', { style: 'display: flex; gap: 0.5rem;' },
        el('a', { className: 'btn btn-secondary btn-sm', href: `#/anomalies/${encodeURIComponent(datasetId)}`, text: 'AI Anomaly Detection →' }),
        el('a', { className: 'btn btn-outline btn-sm', href: `#/reports/${encodeURIComponent(datasetId)}`, text: 'Export Report' })
      )
    )
  );
  container.appendChild(headerCard);

  // Controls Toolbar (Baseline method & Target)
  const controlsBar = el('div', { className: 'controls-bar' });

  const baselineSelect = el('select', { className: 'form-select', style: 'max-width: 220px;' },
    el('option', { value: 'historical_mean', selected: true }, 'Historical Mean (Default)'),
    el('option', { value: 'historical_median' }, 'Historical Median'),
    el('option', { value: 'rolling_average' }, 'Rolling Average'),
    el('option', { value: 'same_period_average' }, 'Same Period Average'),
    el('option', { value: 'user_target' }, 'Custom User Target')
  );

  const targetInputGroup = el('div', { className: 'form-group', style: 'margin-bottom: 0; display: none;' },
    el('label', { className: 'form-label', text: 'Target (kWh)' }),
    el('input', {
      type: 'number',
      step: '0.1',
      min: '0.01',
      className: 'form-input',
      placeholder: 'e.g. 500',
      style: 'max-width: 140px;'
    })
  );

  baselineSelect.addEventListener('change', () => {
    if (baselineSelect.value === 'user_target') {
      targetInputGroup.style.display = 'block';
    } else {
      targetInputGroup.style.display = 'none';
    }
  });

  const applyBtn = el('button', {
    type: 'button',
    className: 'btn btn-primary',
    text: 'Recalculate Baseline',
    on: {
      click: () => {
        const method = baselineSelect.value;
        const targetInput = targetInputGroup.querySelector('input');
        let userTarget = null;
        if (method === 'user_target') {
          const val = targetInput.value.trim();
          if (!isPositiveNumber(val, 0)) {
            showToast('Validation Error', 'Custom target must be a positive number greater than 0.', 'error');
            return;
          }
          userTarget = Number(val);
        }
        loadAnalysisData(analysisContentContainer, datasetId, method, userTarget, ctx);
      }
    }
  });

  controlsBar.appendChild(el('div', { className: 'form-group', style: 'margin-bottom: 0;' },
    el('label', { className: 'form-label', text: 'Baseline Comparison Method' }),
    baselineSelect
  ));
  controlsBar.appendChild(targetInputGroup);
  controlsBar.appendChild(applyBtn);
  container.appendChild(controlsBar);

  const analysisContentContainer = el('div', { id: 'analysis-content-container' });
  container.appendChild(analysisContentContainer);

  await loadAnalysisData(analysisContentContainer, datasetId, 'historical_mean', null, ctx);
}

async function loadAnalysisData(container, datasetId, baselineMethod, userTarget, ctx) {
  clearElement(container);
  cleanupCharts();

  container.appendChild(createSpinner('Calculating energy metrics and breakdowns...'));

  try {
    const [analysisRes, anomalyRes] = await Promise.allSettled([
      api.getAnalysis(datasetId, { baselineMethod, userTarget, signal: ctx.signal }),
      api.getAnomalies(datasetId, ctx.signal)
    ]);

    clearElement(container);

    if (analysisRes.status === 'rejected') {
      const err = analysisRes.reason;
      container.appendChild(createEmptyState({
        title: 'Analysis Failed',
        description: err.message || 'Could not calculate consumption metrics.',
        icon: 'alert'
      }));
      return;
    }

    const data = analysisRes.value;
    const summary = data.summary || {};
    const baseline = data.baseline || {};
    const anomalyData = anomalyRes.status === 'fulfilled' ? anomalyRes.value : null;

    // 1. Executive Metrics Grid
    const metricsGrid = el('div', { className: 'metrics-grid' });

    metricsGrid.appendChild(createStatCard('Total Consumption', formatKwh(summary.total_consumption_kwh), `${formatNumber(data.record_count, 0)} total records`, 'lightning'));
    metricsGrid.appendChild(createStatCard('Mean Consumption', formatKwh(summary.mean_consumption_kwh), `Std Dev: ${formatNumber(summary.std_dev_consumption_kwh, 2)}`, 'chart'));
    metricsGrid.appendChild(createStatCard('Median Reading', formatKwh(summary.median_consumption_kwh), `Min: ${formatKwh(summary.min_consumption_kwh)}`, 'dashboard'));
    metricsGrid.appendChild(createStatCard('Peak (Max) Reading', formatKwh(summary.max_consumption_kwh), 'Highest single interval', 'alert'));

    // Baseline & Deviation Metric
    let baselineValDisplay = 'N/A — baseline unavailable';
    let deviationDisplay = 'N/A';
    if (baseline.baseline_value_kwh !== null && baseline.baseline_value_kwh !== undefined) {
      baselineValDisplay = formatKwh(baseline.baseline_value_kwh);
      deviationDisplay = formatPercent(baseline.percent_deviation, true, 1);
    }

    metricsGrid.appendChild(createStatCard(
      `Baseline (${safeText(baseline.method_used, 'mean')})`,
      baselineValDisplay,
      `Deviation: ${deviationDisplay}`,
      'shield'
    ));

    container.appendChild(metricsGrid);

    // 2. Charts Grid
    const chartGrid = el('div', { className: 'chart-grid' });

    // Chart 1: Line Chart Actual vs Baseline (Daily)
    const daily = data.daily_summary || [];
    const chart1Card = el('div', { className: 'chart-card' },
      el('h3', { className: 'card-title', style: 'margin-bottom: 0.75rem;', text: 'Daily Consumption vs Baseline' })
    );
    const canvas1Container = el('div', { className: 'chart-container' });
    const canvas1 = el('canvas', { id: 'chart-actual-vs-baseline' });
    canvas1Container.appendChild(canvas1);
    chart1Card.appendChild(canvas1Container);
    chartGrid.appendChild(chart1Card);
    activeCanvases.push(canvas1);

    if (daily.length > 0) {
      const rawLabels = daily.map((d) => d.period || d.date || '—');
      const rawValues = daily.map((d) => Number(d.consumption_kwh ?? d.total_kwh ?? 0));

      const { labels, values, isDownsampled } = downsampleData(rawLabels, rawValues, 500);

      const baselineVal = baseline.baseline_value_kwh;
      const baselineData = baselineVal !== null && baselineVal !== undefined
        ? labels.map(() => baselineVal)
        : [];

      const datasets = [{
        label: 'Daily Energy (kWh)',
        data: values,
        borderColor: '#0f766e',
        backgroundColor: 'rgba(15, 118, 110, 0.1)',
        fill: true,
        tension: 0.2
      }];

      if (baselineData.length > 0) {
        datasets.push({
          label: `Baseline (${safeText(baseline.method_used, 'mean')})`,
          data: baselineData,
          borderColor: '#b91c1c',
          borderDash: [5, 5],
          pointRadius: 0,
          fill: false
        });
      }

      createChart(canvas1, {
        type: 'line',
        data: { labels, datasets },
        options: {
          scales: {
            y: { title: { display: true, text: 'Energy (kWh)' }, beginAtZero: true },
            x: { title: { display: true, text: 'Date' } }
          }
        }
      }, 'Daily consumption vs baseline line chart', {
        headers: ['Date', 'Energy (kWh)'],
        rows: labels.map((l, idx) => [l, formatNumber(values[idx])])
      });

      if (isDownsampled) {
        canvas1Container.appendChild(el('div', {
          className: 'chart-downsample-note',
          text: `* Time series downsampled to 500 points via bucket averaging for rendering performance.`
        }));
      }
    } else {
      canvas1Container.appendChild(renderEmptyChartNotice('No daily interval summary available for this dataset.'));
    }

    // Chart 2: Bar Chart by Building / Department / Equipment
    const bldSummary = data.building_summary || data.department_summary || data.equipment_summary || [];
    const bldKey = data.building_summary ? 'Building' : data.department_summary ? 'Department' : 'Equipment';

    const chart2Card = el('div', { className: 'chart-card' },
      el('h3', { className: 'card-title', style: 'margin-bottom: 0.75rem;', text: `Breakdown by ${bldKey}` })
    );
    const canvas2Container = el('div', { className: 'chart-container' });
    const canvas2 = el('canvas', { id: 'chart-breakdown' });
    canvas2Container.appendChild(canvas2);
    chart2Card.appendChild(canvas2Container);
    chartGrid.appendChild(chart2Card);
    activeCanvases.push(canvas2);

    if (bldSummary.length > 0) {
      const bldLabels = bldSummary.map((b) => b.building || b.department || b.equipment || 'Unknown');
      const bldValues = bldSummary.map((b) => Number(b.total_kwh ?? b.consumption_kwh ?? 0));

      createChart(canvas2, {
        type: 'bar',
        data: {
          labels: bldLabels,
          datasets: [{
            label: `Total Consumption (kWh)`,
            data: bldValues,
            backgroundColor: '#0284c7'
          }]
        },
        options: {
          scales: {
            y: { title: { display: true, text: 'Energy (kWh)' }, beginAtZero: true },
            x: { title: { display: true, text: bldKey } }
          }
        }
      }, `Consumption breakdown by ${bldKey}`, {
        headers: [bldKey, 'Total Energy (kWh)'],
        rows: bldLabels.map((l, i) => [l, formatNumber(bldValues[i])])
      });
    } else {
      canvas2Container.appendChild(renderEmptyChartNotice(`No categorical ${bldKey.toLowerCase()} breakdown available in this dataset.`));
    }

    // Chart 3: Monthly Consumption Bar Chart
    const monthly = data.monthly_summary || [];
    const chart3Card = el('div', { className: 'chart-card' },
      el('h3', { className: 'card-title', style: 'margin-bottom: 0.75rem;', text: 'Monthly Consumption' })
    );
    const canvas3Container = el('div', { className: 'chart-container' });
    const canvas3 = el('canvas', { id: 'chart-monthly' });
    canvas3Container.appendChild(canvas3);
    chart3Card.appendChild(canvas3Container);
    chartGrid.appendChild(chart3Card);
    activeCanvases.push(canvas3);

    if (monthly.length > 0) {
      const mLabels = monthly.map((m) => m.period || m.month || '—');
      const mValues = monthly.map((m) => Number(m.consumption_kwh ?? m.total_kwh ?? 0));

      createChart(canvas3, {
        type: 'bar',
        data: {
          labels: mLabels,
          datasets: [{
            label: 'Monthly Energy (kWh)',
            data: mValues,
            backgroundColor: '#0d9488'
          }]
        },
        options: {
          scales: {
            y: { title: { display: true, text: 'Energy (kWh)' }, beginAtZero: true },
            x: { title: { display: true, text: 'Month' } }
          }
        }
      }, 'Monthly consumption bar chart', {
        headers: ['Month', 'Energy (kWh)'],
        rows: mLabels.map((l, i) => [l, formatNumber(mValues[i])])
      });
    } else {
      canvas3Container.appendChild(renderEmptyChartNotice('Dataset timespan does not span multiple months or has no monthly aggregate.'));
    }

    // Chart 4: Doughnut Normal vs Flagged Records
    const chart4Card = el('div', { className: 'chart-card' },
      el('h3', { className: 'card-title', style: 'margin-bottom: 0.75rem;', text: 'Normal vs Flagged Records' })
    );
    const canvas4Container = el('div', { className: 'chart-container' });
    const canvas4 = el('canvas', { id: 'chart-doughnut-anomalies' });
    canvas4Container.appendChild(canvas4);
    chart4Card.appendChild(canvas4Container);
    chartGrid.appendChild(chart4Card);
    activeCanvases.push(canvas4);

    if (anomalyData && anomalyData.anomalies_detected !== undefined) {
      const flagged = anomalyData.anomalies_detected;
      const total = anomalyData.records_analyzed || data.record_count;
      const normal = Math.max(0, total - flagged);

      createChart(canvas4, {
        type: 'doughnut',
        data: {
          labels: ['Normal Records', 'Flagged Anomalies (Possible Waste)'],
          datasets: [{
            data: [normal, flagged],
            backgroundColor: ['#10b981', '#ef4444']
          }]
        },
        options: {
          plugins: {
            tooltip: {
              callbacks: {
                label: (ctx) => `${ctx.label}: ${formatNumber(ctx.raw, 0)} records`
              }
            }
          }
        }
      }, 'Normal vs flagged records doughnut chart', {
        headers: ['Classification', 'Record Count'],
        rows: [
          ['Normal Records', normal],
          ['Flagged Anomalies (Possible Waste)', flagged]
        ]
      });
    } else {
      canvas4Container.appendChild(renderEmptyChartNotice('Run AI Anomaly Detection first to populate normal vs flagged breakdown.', {
        text: 'Go to AI Anomaly Detection',
        href: `#/anomalies/${encodeURIComponent(datasetId)}`
      }));
    }

    container.appendChild(chartGrid);

    // 3. High Consumption Records Table
    const highRecords = data.high_consumption_records || [];
    if (highRecords.length > 0) {
      const highTableCard = el('div', { className: 'card' },
        el('h3', { className: 'card-title', style: 'margin-bottom: 0.5rem;', text: 'Records with Unusually High Consumption' }),
        el('p', {
          className: 'card-subtitle',
          style: 'margin-bottom: 1rem;',
          text: 'Readings identified as statistical outliers (> 99th percentile or > 3 standard deviations from mean).'
        })
      );

      const tableComponent = createDataTable({
        columns: [
          { key: 'timestamp', label: 'Timestamp', type: 'date' },
          {
            key: 'consumption_kwh',
            label: 'Consumption',
            type: 'number',
            render: (v) => el('strong', { style: 'color: var(--color-danger);', text: formatKwh(v) })
          },
          { key: 'building', label: 'Building' },
          { key: 'department', label: 'Department' },
          { key: 'equipment', label: 'Equipment' }
        ],
        data: highRecords,
        searchPlaceholder: 'Search high readings...',
        emptyMessage: 'No high consumption records found.'
      });

      highTableCard.appendChild(tableComponent);
      container.appendChild(highTableCard);
    }

  } catch (err) {
    if (ctx.signal.aborted) return;
    clearElement(container);
    container.appendChild(createEmptyState({
      title: 'Failed to Load Analysis',
      description: err.message || 'Error communicating with backend.',
      icon: 'alert'
    }));
  }
}

function createStatCard(title, val, subtitle, icon) {
  const card = el('div', { className: 'metric-card' });
  card.appendChild(el('div', { className: 'metric-header' },
    el('span', { className: 'metric-title', text: title }),
    el('div', { className: 'metric-icon-wrap' }, svgIcon(icon, '', 18))
  ));
  card.appendChild(el('div', { className: 'metric-value', text: val }));
  card.appendChild(el('div', { className: 'metric-subtitle', text: subtitle }));
  return card;
}

function renderEmptyChartNotice(msg, action = null) {
  const box = el('div', {
    style: 'height: 100%; display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; color: var(--text-muted); font-size: 0.88rem; padding: 1.5rem;'
  }, el('p', { text: msg }));

  if (action) {
    box.appendChild(el('a', {
      className: 'btn btn-secondary btn-sm',
      style: 'margin-top: 0.75rem;',
      href: action.href,
      text: action.text
    }));
  }
  return box;
}

function cleanupCharts() {
  activeCanvases.forEach((c) => destroyChart(c));
  activeCanvases = [];
}

export function destroy() {
  cleanupCharts();
}
