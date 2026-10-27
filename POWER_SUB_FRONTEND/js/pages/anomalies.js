// AI Anomaly Detection Page Module
import { api, ApiError } from '../api.js';
import { store } from '../state.js';
import { el, clearElement, svgIcon } from '../utils/dom.js';
import { formatNumber, formatKwh, formatPercent, safeText, formatDate } from '../utils/format.js';
import { showToast } from '../components/toast.js';
import { createSpinner } from '../components/spinner.js';
import { createEmptyState } from '../components/emptyState.js';
import { createAnomalyDisclaimerNotice, createNotice } from '../components/notice.js';
import { createMethodBadge, createAnomalyBadge } from '../components/statusBadge.js';
import { createDataTable } from '../components/dataTable.js';

export async function render(container, ctx) {
  clearElement(container);

  const datasetId = ctx.param || ctx.datasetId || store.currentDatasetId;

  if (!datasetId) {
    container.appendChild(createEmptyState({
      title: 'No Dataset Selected',
      description: 'Select an energy dataset to inspect or run AI anomaly detection.',
      icon: 'alert',
      action: { text: 'Upload Energy Data', href: '#/upload' }
    }));
    return;
  }

  // Header Card
  const headerCard = el('div', { className: 'card' },
    el('div', { className: 'card-header' },
      el('div', {},
        el('h2', { className: 'card-title', text: 'AI Anomaly Detection & Waste Screening' }),
        el('p', { className: 'card-subtitle', text: `Dataset ID: ${datasetId}` })
      ),
      el('div', { style: 'display: flex; gap: 0.5rem;' },
        el('a', { className: 'btn btn-secondary btn-sm', href: `#/recommendations/${encodeURIComponent(datasetId)}`, text: 'View Recommendations →' }),
        el('a', { className: 'btn btn-outline btn-sm', href: `#/reports/${encodeURIComponent(datasetId)}`, text: 'Export PDF' })
      )
    )
  );
  container.appendChild(headerCard);

  // Mandatory Ethical & Scientific Interpretation Notice
  container.appendChild(createAnomalyDisclaimerNotice());

  // Detection Run Controls Toolbar
  const controlsBar = el('div', { className: 'controls-bar' });

  // Sensitivity Select
  const sensitivitySelect = el('select', { className: 'form-select', id: 'anomaly-sensitivity' },
    el('option', { value: 'low' }, 'Low Sensitivity'),
    el('option', { value: 'medium', selected: true }, 'Medium Sensitivity (Default)'),
    el('option', { value: 'high' }, 'High Sensitivity')
  );
  controlsBar.appendChild(el('div', { className: 'form-group', style: 'margin-bottom: 0;' },
    el('label', { className: 'form-label', htmlFor: 'anomaly-sensitivity', text: 'Detection Sensitivity' }),
    sensitivitySelect
  ));

  // Contamination Input
  const contaminationInput = el('input', {
    type: 'number',
    className: 'form-input',
    id: 'anomaly-contamination',
    min: '0.01',
    max: '0.20',
    step: '0.01',
    value: '0.05',
    title: 'Expected proportion of anomalies (default 0.05 = 5%)',
    style: 'max-width: 130px;'
  });
  controlsBar.appendChild(el('div', { className: 'form-group', style: 'margin-bottom: 0;' },
    el('label', { className: 'form-label', htmlFor: 'anomaly-contamination', text: 'Contamination' }),
    contaminationInput
  ));

  // Run Button
  const runBtn = el('button', {
    type: 'button',
    className: 'btn btn-primary',
    text: 'Run AI Anomaly Detection',
    on: {
      click: async () => {
        const contVal = parseFloat(contaminationInput.value);
        if (Number.isNaN(contVal) || contVal < 0.01 || contVal > 0.20) {
          showToast('Invalid Contamination', 'Contamination rate must be between 0.01 and 0.20.', 'error');
          return;
        }

        runBtn.disabled = true;
        runBtn.textContent = 'Running Detection...';
        try {
          const resp = await api.runAnomalies(datasetId, {
            contamination: contVal,
            sensitivity: sensitivitySelect.value,
            signal: ctx.signal
          });
          showToast('Detection Complete', `Identified ${resp.anomalies_detected ?? 0} flagged records.`, 'success');
          renderAnomalyResults(resultsContainer, resp);
        } catch (err) {
          showToast('Detection Failed', err.message || 'Detection failed.', 'error', err.requestId);
        } finally {
          runBtn.disabled = false;
          runBtn.textContent = 'Run AI Anomaly Detection';
        }
      }
    }
  });
  controlsBar.appendChild(runBtn);
  container.appendChild(controlsBar);

  // Results Container
  const resultsContainer = el('div', { id: 'anomaly-results-container' });
  container.appendChild(resultsContainer);

  // Auto-fetch existing previous results
  await loadExistingAnomalies(resultsContainer, datasetId, ctx);
}

async function loadExistingAnomalies(container, datasetId, ctx) {
  clearElement(container);
  container.appendChild(createSpinner('Checking for previous anomaly analysis...'));

  try {
    const data = await api.getAnomalies(datasetId, ctx.signal);
    clearElement(container);
    renderAnomalyResults(container, data);
  } catch (err) {
    clearElement(container);
    if (err.status === 404) {
      // Not run yet
      container.appendChild(createEmptyState({
        title: 'No Anomaly Analysis Run Yet',
        description: 'Click "Run AI Anomaly Detection" above to screen this dataset with the Isolation Forest machine learning algorithm.',
        icon: 'lightning'
      }));
    } else {
      container.appendChild(createNotice(
        err.message || 'Could not load existing anomaly results.',
        'warning',
        'Results Unavailable'
      ));
    }
  }
}

function renderAnomalyResults(container, data) {
  clearElement(container);

  // Check for insufficient_data status from backend
  if (data.status === 'insufficient_data') {
    container.appendChild(createNotice(
      data.limitations || 'Dataset contains fewer than 30 records, which is insufficient for statistical Isolation Forest fitting. Fallback IQR was utilized or results are withheld.',
      'warning',
      'Insufficient Records for Machine Learning'
    ));
    return;
  }

  // 1. Executive Summary Cards
  const summaryGrid = el('div', { className: 'metrics-grid' });

  summaryGrid.appendChild(createMetricCard(
    'Records Screened',
    formatNumber(data.records_analyzed, 0),
    'Full dataset coverage',
    'chart'
  ));

  summaryGrid.appendChild(createMetricCard(
    'Flagged Anomalies',
    formatNumber(data.anomalies_detected, 0),
    'Possible waste, needs investigation',
    'alert'
  ));

  summaryGrid.appendChild(createMetricCard(
    'Anomaly Proportion',
    formatPercent(data.anomaly_percentage, false, 1),
    'Relative to total readings',
    'dashboard'
  ));

  // Model & Method Card
  const modelInfo = data.model_info || {};
  const methodBadge = createMethodBadge(modelInfo.method);
  const methodCard = el('div', { className: 'metric-card' },
    el('div', { className: 'metric-header' },
      el('span', { className: 'metric-title', text: 'Detection Model' }),
      el('div', { className: 'metric-icon-wrap' }, svgIcon('shield', '', 18))
    ),
    el('div', { style: 'margin-bottom: 0.5rem;' }, methodBadge),
    el('div', {
      className: 'metric-subtitle',
      text: `Algorithm: ${safeText(modelInfo.algorithm || modelInfo.method)}`
    })
  );
  summaryGrid.appendChild(methodCard);

  container.appendChild(summaryGrid);

  // Model Details & Heuristics Notice
  const modelDetailsCard = el('div', { className: 'card' },
    el('h3', { className: 'card-title', style: 'font-size: 0.95rem; margin-bottom: 0.35rem;', text: 'Model Configuration & Feature Diagnostics' }),
    el('p', {
      style: 'font-size: 0.82rem; color: var(--text-secondary); margin-bottom: 0.5rem;',
      text: 'Features evaluated: ' + ((modelInfo.features_used || []).join(', ') || 'consumption_kwh, temporal periodicity')
    }),
    el('p', {
      style: 'font-size: 0.78rem; color: var(--text-muted); font-style: italic;',
      text: 'Note: Heuristic contributing features highlighted below denote statistical deviation drivers, not proven causal faults. Always inspect physical meters and operational conditions.'
    })
  );

  if (data.limitations) {
    modelDetailsCard.appendChild(createNotice(data.limitations, 'info', 'Algorithm Limitations:'));
  }
  container.appendChild(modelDetailsCard);

  // 2. Anomaly Records Data Table
  const anomalies = data.anomalies || [];

  const tableCard = el('div', { className: 'card' },
    el('h3', { className: 'card-title', style: 'margin-bottom: 0.35rem;', text: 'Anomaly Screening Results Table' }),
    el('p', { className: 'card-subtitle', style: 'margin-bottom: 1rem;', text: 'Explore and filter individual flagged energy readings.' })
  );

  const filterSelect = el('select', {
    className: 'form-select',
    style: 'max-width: 180px; font-size: 0.85rem;',
    'aria-label': 'Filter table'
  },
    el('option', { value: 'all' }, 'Show All Records'),
    el('option', { value: 'flagged', selected: true }, 'Flagged Only')
  );

  // Render initial table with flagged only or all
  let activeFilter = 'flagged';

  const tableWrapper = el('div', {});
  tableCard.appendChild(tableWrapper);

  function renderTable() {
    clearElement(tableWrapper);

    const filteredRecords = activeFilter === 'flagged'
      ? anomalies.filter((a) => a.is_anomaly === true || a.severity === 'high' || a.severity === 'medium')
      : anomalies;

    const dataTable = createDataTable({
      columns: [
        {
          key: 'timestamp',
          label: 'Timestamp',
          type: 'date',
          render: (v) => formatDate(v)
        },
        {
          key: 'consumption_kwh',
          label: 'Consumption',
          type: 'number',
          render: (v, r) => el('strong', {
            style: r.is_anomaly ? 'color: var(--color-danger);' : '',
            text: formatKwh(v)
          })
        },
        { key: 'building', label: 'Building' },
        { key: 'department', label: 'Department' },
        { key: 'equipment', label: 'Equipment' },
        {
          key: 'anomaly_score',
          label: 'Anomaly Score',
          type: 'number',
          render: (v) => formatNumber(v, 3)
        },
        {
          key: 'severity',
          label: 'Severity',
          render: (v) => {
            const sev = String(v || 'low').toLowerCase();
            const badgeClass = sev === 'high' ? 'badge-danger' : sev === 'medium' ? 'badge-warning' : 'badge-normal';
            return el('span', { className: `badge ${badgeClass}`, text: sev.toUpperCase() });
          }
        },
        {
          key: 'status',
          label: 'Classification',
          render: (v, r) => createAnomalyBadge(r.is_anomaly)
        },
        {
          key: 'contributing_features',
          label: 'Top Contributors',
          render: (v) => {
            if (Array.isArray(v) && v.length > 0) {
              return el('span', { style: 'font-size: 0.78rem; color: var(--text-secondary);', text: v.join(', ') });
            }
            return '—';
          }
        }
      ],
      data: filteredRecords,
      searchPlaceholder: 'Search anomaly records...',
      emptyMessage: activeFilter === 'flagged' ? 'No flagged anomalies found in this dataset.' : 'No records available.',
      actions: [filterSelect]
    });

    tableWrapper.appendChild(dataTable);
  }

  filterSelect.addEventListener('change', (e) => {
    activeFilter = e.target.value;
    renderTable();
  });

  renderTable();
  container.appendChild(tableCard);
}

function createMetricCard(title, val, subtitle, icon) {
  const card = el('div', { className: 'metric-card' });
  card.appendChild(el('div', { className: 'metric-header' },
    el('span', { className: 'metric-title', text: title }),
    el('div', { className: 'metric-icon-wrap' }, svgIcon(icon, '', 18))
  ));
  card.appendChild(el('div', { className: 'metric-value', text: val }));
  card.appendChild(el('div', { className: 'metric-subtitle', text: subtitle }));
  return card;
}

export function destroy() {
  // Cleanup if needed
}
