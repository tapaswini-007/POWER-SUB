// Reports & Export Downloads Page Module
import { api, ApiError } from '../api.js';
import { store } from '../state.js';
import { el, clearElement, svgIcon } from '../utils/dom.js';
import { triggerBlobDownload } from '../utils/download.js';
import { showToast } from '../components/toast.js';
import { createEmptyState } from '../components/emptyState.js';
import { createNotice } from '../components/notice.js';

let activeDownloadController = null;

export async function render(container, ctx) {
  clearElement(container);

  const datasetId = ctx.param || ctx.datasetId || store.currentDatasetId;

  if (!datasetId) {
    container.appendChild(createEmptyState({
      title: 'No Dataset Selected for Export',
      description: 'Select an existing dataset to generate and download comprehensive executive PDF or raw CSV reports.',
      icon: 'file',
      action: { text: 'Upload Energy Data', href: '#/upload' }
    }));
    return;
  }

  // Header Card
  const headerCard = el('div', { className: 'card' },
    el('h2', { className: 'card-title', text: 'Generate & Download Audit Reports' }),
    el('p', { className: 'card-subtitle', text: `Dataset ID: ${datasetId}` })
  );
  container.appendChild(headerCard);

  // Business & Privacy Sensitivity Notice
  container.appendChild(createNotice(
    'Audit reports contain statistical summaries, machine learning isolation scores, and sub-metered facility readings. Please treat generated PDF and CSV documents as business-sensitive data.',
    'info',
    'Notice on Data Sensitivity & Limitations:'
  ));

  // Export Cards Grid
  const exportGrid = el('div', {
    style: 'display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 1.5rem; margin-top: 1.25rem;'
  });

  // 1. PDF Executive Report Card
  const pdfCard = el('div', { className: 'card', style: 'display: flex; flex-direction: column; justify-content: space-between;' });
  const pdfContent = el('div', {},
    el('div', { style: 'display: flex; align-items: center; gap: 0.75rem; margin-bottom: 0.75rem;' },
      el('div', { className: 'metric-icon-wrap', style: 'color: var(--color-danger); background-color: var(--color-danger-subtle);' },
        svgIcon('file', '', 20)
      ),
      el('h3', { className: 'card-title', style: 'margin-bottom: 0;', text: 'Executive Energy Audit (PDF)' })
    ),
    el('p', {
      style: 'font-size: 0.88rem; color: var(--text-secondary); margin-bottom: 1rem; line-height: 1.5;',
      text: 'A formal executive summary document including statistical baselines, peak intervals, Isolation Forest anomaly distribution, and prioritized recommendations.'
    })
  );

  const pdfDownloadBtn = el('button', {
    type: 'button',
    className: 'btn btn-primary',
    style: 'width: 100%;',
    text: 'Download PDF Report',
    on: { click: () => handleDownloadPdf(pdfDownloadBtn, datasetId) }
  });

  pdfCard.appendChild(pdfContent);
  pdfCard.appendChild(pdfDownloadBtn);
  exportGrid.appendChild(pdfCard);

  // 2. CSV Anomaly Callset Card
  const csvCard = el('div', { className: 'card', style: 'display: flex; flex-direction: column; justify-content: space-between;' });
  const csvContent = el('div', {},
    el('div', { style: 'display: flex; align-items: center; gap: 0.75rem; margin-bottom: 0.75rem;' },
      el('div', { className: 'metric-icon-wrap', style: 'color: var(--color-primary); background-color: var(--color-primary-subtle);' },
        svgIcon('chart', '', 20)
      ),
      el('h3', { className: 'card-title', style: 'margin-bottom: 0;', text: 'Anomaly Screening Callset (CSV)' })
    ),
    el('p', {
      style: 'font-size: 0.88rem; color: var(--text-secondary); margin-bottom: 1rem; line-height: 1.5;',
      text: 'Tabular comma-separated values file containing all interval readings annotated with anomaly flags, Isolation Forest decision scores, severity tiers, and heuristic drivers.'
    })
  );

  const csvDownloadBtn = el('button', {
    type: 'button',
    className: 'btn btn-secondary',
    style: 'width: 100%;',
    text: 'Download Anomalies CSV',
    on: { click: () => handleDownloadCsv(csvDownloadBtn, datasetId) }
  });

  csvCard.appendChild(csvContent);
  csvCard.appendChild(csvDownloadBtn);
  exportGrid.appendChild(csvCard);

  container.appendChild(exportGrid);
}

async function handleDownloadPdf(btn, datasetId) {
  btn.disabled = true;
  btn.textContent = 'Generating PDF...';

  activeDownloadController = new AbortController();

  try {
    const blob = await api.downloadReportPdf(datasetId, activeDownloadController.signal);
    triggerBlobDownload(blob, 'executive_report', datasetId, 'pdf', 'application/pdf');
    showToast('Download Ready', 'Executive PDF report downloaded successfully.', 'success');
  } catch (err) {
    if (err.name === 'AbortError') return;
    showToast('Download Failed', err.message || 'Could not download PDF report.', 'error', err.requestId);
  } finally {
    btn.disabled = false;
    btn.textContent = 'Download PDF Report';
    activeDownloadController = null;
  }
}

async function handleDownloadCsv(btn, datasetId) {
  btn.disabled = true;
  btn.textContent = 'Generating CSV...';

  activeDownloadController = new AbortController();

  try {
    const blob = await api.downloadReportCsv(datasetId, activeDownloadController.signal);
    triggerBlobDownload(blob, 'anomalies_callset', datasetId, 'csv', 'text/csv');
    showToast('Download Ready', 'Anomaly CSV export downloaded successfully.', 'success');
  } catch (err) {
    if (err.name === 'AbortError') return;
    showToast('Download Failed', err.message || 'Could not download CSV export.', 'error', err.requestId);
  } finally {
    btn.disabled = false;
    btn.textContent = 'Download Anomalies CSV';
    activeDownloadController = null;
  }
}

export function destroy() {
  if (activeDownloadController) {
    activeDownloadController.abort();
    activeDownloadController = null;
  }
}
