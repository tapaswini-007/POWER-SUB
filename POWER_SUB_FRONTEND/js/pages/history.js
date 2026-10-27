// Dataset History & Management Page Module
import { api, ApiError } from '../api.js';
import { store } from '../state.js';
import { el, clearElement, svgIcon } from '../utils/dom.js';
import { formatDate, formatNumber, safeText, shortenId } from '../utils/format.js';
import { showToast } from '../components/toast.js';
import { openConfirmModal } from '../components/modal.js';
import { createSpinner } from '../components/spinner.js';
import { createEmptyState } from '../components/emptyState.js';

export async function render(container, ctx) {
  clearElement(container);

  const headerCard = el('div', { className: 'card' },
    el('div', { className: 'card-header' },
      el('div', {},
        el('h2', { className: 'card-title', text: 'Dataset Ingestion History' }),
        el('p', { className: 'card-subtitle', text: 'Manage uploaded sub-metering datasets, inspect schema metadata, or remove datasets.' })
      ),
      el('a', { className: 'btn btn-primary btn-sm', href: '#/upload', text: '+ Upload New File' })
    )
  );
  container.appendChild(headerCard);

  const tableContainer = el('div', { id: 'history-table-container' });
  container.appendChild(tableContainer);

  await loadHistory(tableContainer, ctx);
}

async function loadHistory(container, ctx) {
  clearElement(container);
  container.appendChild(createSpinner('Loading datasets list...'));

  try {
    const res = await api.listDatasets(1, 50, ctx.signal);
    clearElement(container);

    const items = res.items || [];
    store.setDatasets(items);

    if (items.length === 0) {
      container.appendChild(createEmptyState({
        title: 'No Datasets Ingested',
        description: 'Upload your first electricity dataset to view historical records here.',
        icon: 'history',
        action: { text: 'Upload Dataset', href: '#/upload' }
      }));
      return;
    }

    const tableCard = el('div', { className: 'card' });
    const tableWrap = el('div', { className: 'table-responsive' });
    const table = el('table', { className: 'data-table' });

    // Table Header
    const thead = el('thead', {},
      el('tr', {},
        el('th', { text: 'Dataset ID' }),
        el('th', { text: 'Filename / Name' }),
        el('th', { text: 'Ingestion Date' }),
        el('th', { text: 'Record Count' }),
        el('th', { text: 'Status' }),
        el('th', { style: 'text-align: right;', text: 'Actions' })
      )
    );
    table.appendChild(thead);

    const tbody = el('tbody');
    items.forEach((item) => {
      const isSelected = item.dataset_id === store.currentDatasetId;
      const tr = el('tr', { style: isSelected ? 'background-color: var(--color-primary-subtle);' : '' });

      // ID Cell with Copy Button
      const idCell = el('td', { style: 'font-family: var(--font-mono); font-size: 0.82rem;' },
        el('span', { title: item.dataset_id, text: shortenId(item.dataset_id, 10) }),
        el('button', {
          type: 'button',
          className: 'btn-icon',
          title: 'Copy UUID',
          style: 'background: none; border: none; cursor: pointer; color: var(--text-muted); margin-left: 0.35rem;',
          on: {
            click: async () => {
              try {
                await navigator.clipboard.writeText(item.dataset_id);
                showToast('Copied', 'Dataset UUID copied to clipboard.', 'info');
              } catch {
                showToast('Clipboard Error', 'Could not copy to clipboard.', 'error');
              }
            }
          }
        }, svgIcon('file', '', 14))
      );

      // Name
      const nameCell = el('td', { style: 'font-weight: 600;', text: safeText(item.filename || item.name) });

      // Upload Date
      const dateCell = el('td', { text: formatDate(item.created_at || item.upload_date) });

      // Record Count
      const countCell = el('td', { text: formatNumber(item.record_count, 0) });

      // Status
      const statusBadge = el('span', {
        className: 'badge badge-normal',
        text: safeText(item.status || 'Ready')
      });
      const statusCell = el('td', {}, statusBadge);

      // Actions
      const actionsCell = el('td', { style: 'text-align: right; white-space: nowrap;' });

      // Details Modal Button
      const detailsBtn = el('button', {
        type: 'button',
        className: 'btn btn-secondary btn-sm',
        style: 'margin-right: 0.4rem;',
        text: 'Details',
        on: { click: () => showDatasetDetailsModal(item.dataset_id) }
      });

      // Analyze Button
      const analyzeBtn = el('a', {
        className: 'btn btn-primary btn-sm',
        style: 'margin-right: 0.4rem;',
        href: `#/analysis/${encodeURIComponent(item.dataset_id)}`,
        text: 'Analyze'
      });

      // Delete Button
      const deleteBtn = el('button', {
        type: 'button',
        className: 'btn btn-danger btn-sm',
        text: 'Delete',
        on: { click: () => confirmDeleteDataset(item.dataset_id, item.filename, container, ctx) }
      });

      actionsCell.appendChild(detailsBtn);
      actionsCell.appendChild(analyzeBtn);
      actionsCell.appendChild(deleteBtn);

      tr.appendChild(idCell);
      tr.appendChild(nameCell);
      tr.appendChild(dateCell);
      tr.appendChild(countCell);
      tr.appendChild(statusCell);
      tr.appendChild(actionsCell);

      tbody.appendChild(tr);
    });

    table.appendChild(tbody);
    tableWrap.appendChild(table);
    tableCard.appendChild(tableWrap);
    container.appendChild(tableCard);

  } catch (err) {
    if (ctx.signal.aborted) return;
    clearElement(container);
    container.appendChild(createEmptyState({
      title: 'Failed to Load Datasets',
      description: err.message || 'Could not retrieve datasets list from backend.',
      icon: 'alert',
      action: { text: 'Retry', onClick: () => loadHistory(container, ctx) }
    }));
  }
}

async function showDatasetDetailsModal(datasetId) {
  try {
    const data = await api.getDataset(datasetId);

    const body = el('div', { style: 'font-size: 0.88rem; line-height: 1.6;' });

    body.appendChild(el('p', {},
      el('strong', { text: 'Full Dataset UUID: ' }),
      el('span', { style: 'font-family: monospace;', text: data.dataset_id })
    ));

    body.appendChild(el('p', {},
      el('strong', { text: 'Original Filename: ' }),
      el('span', { text: safeText(data.filename) })
    ));

    body.appendChild(el('p', {},
      el('strong', { text: 'Ingested: ' }),
      el('span', { text: formatDate(data.created_at) })
    ));

    body.appendChild(el('p', {},
      el('strong', { text: 'Total Rows: ' }),
      el('span', { text: formatNumber(data.record_count, 0) })
    ));

    if (data.limitations) {
      body.appendChild(el('div', {
        className: 'notice-banner notice-info',
        style: 'margin-top: 1rem;'
      }, el('p', { text: `Limitations: ${data.limitations}` })));
    }

    openConfirmModal({
      title: 'Dataset Metadata Details',
      content: body,
      confirmText: 'Analyze Dataset',
      cancelText: 'Close',
      onConfirm: () => {
        store.setCurrentDatasetId(datasetId);
        window.location.hash = `#/analysis/${encodeURIComponent(datasetId)}`;
      }
    });

  } catch (err) {
    showToast('Details Error', err.message || 'Could not fetch metadata.', 'error');
  }
}

function confirmDeleteDataset(datasetId, filename, container, ctx) {
  const content = el('div', {},
    el('p', { style: 'margin-bottom: 0.5rem;', text: `Are you sure you want to permanently delete dataset "${filename || datasetId}"?` }),
    el('p', { style: 'font-size: 0.82rem; color: var(--color-danger); font-weight: 600;', text: 'This action will delete all stored energy records, analysis metrics, anomaly run history, and reports for this dataset.' })
  );

  openConfirmModal({
    title: 'Confirm Dataset Deletion',
    content,
    confirmText: 'Delete Permanently',
    confirmVariant: 'danger',
    onConfirm: async () => {
      try {
        await api.deleteDataset(datasetId);
        showToast('Deleted', 'Dataset deleted successfully.', 'success');

        if (store.currentDatasetId === datasetId) {
          store.setCurrentDatasetId(null);
        }

        await loadHistory(container, ctx);
      } catch (err) {
        showToast('Delete Failed', err.message || 'Could not delete dataset.', 'error');
        throw err;
      }
    }
  });
}

export function destroy() {
  // Cleanup if needed
}
