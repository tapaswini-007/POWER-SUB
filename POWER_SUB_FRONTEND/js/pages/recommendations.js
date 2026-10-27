// Smart Energy Recommendations Page Module
import { api, ApiError } from '../api.js';
import { store } from '../state.js';
import { CONFIG } from '../config.js';
import { el, clearElement, svgIcon } from '../utils/dom.js';
import { formatNumber, formatCurrency, safeText } from '../utils/format.js';
import { isPositiveNumber } from '../utils/validate.js';
import { showToast } from '../components/toast.js';
import { createSpinner } from '../components/spinner.js';
import { createEmptyState } from '../components/emptyState.js';
import { createPriorityBadge } from '../components/statusBadge.js';
import { createNotice } from '../components/notice.js';

export async function render(container, ctx) {
  clearElement(container);

  const datasetId = ctx.param || ctx.datasetId || store.currentDatasetId;

  if (!datasetId) {
    container.appendChild(createEmptyState({
      title: 'No Dataset Selected',
      description: 'Select an energy dataset to inspect rule-based and AI recommendations.',
      icon: 'bulb',
      action: { text: 'Upload Energy Data', href: '#/upload' }
    }));
    return;
  }

  // Header Card
  const headerCard = el('div', { className: 'card' },
    el('div', { className: 'card-header' },
      el('div', {},
        el('h2', { className: 'card-title', text: 'Evidence-Based Energy Recommendations' }),
        el('p', { className: 'card-subtitle', text: `Generated from consumption metrics & anomaly diagnostics for dataset: ${datasetId}` })
      ),
      el('a', { className: 'btn btn-outline btn-sm', href: `#/reports/${encodeURIComponent(datasetId)}`, text: 'Export PDF Report' })
    )
  );
  container.appendChild(headerCard);

  // Tariff & Filtering Controls Toolbar
  const controlsBar = el('div', { className: 'controls-bar' });

  // Tariff Input
  const tariffInput = el('input', {
    type: 'number',
    className: 'form-input',
    id: 'tariff-input',
    step: '0.01',
    min: '0.01',
    placeholder: 'e.g. 8.50',
    style: 'max-width: 140px;'
  });

  const applyTariffBtn = el('button', {
    type: 'button',
    className: 'btn btn-secondary',
    text: 'Apply Tariff',
    on: {
      click: () => {
        const val = tariffInput.value.trim();
        let tariffVal = null;
        if (val) {
          if (!isPositiveNumber(val, 0)) {
            showToast('Validation Error', 'Tariff per kWh must be a positive number greater than 0.', 'error');
            return;
          }
          tariffVal = Number(val);
        }
        loadRecommendations(recListContainer, datasetId, tariffVal, ctx);
      }
    }
  });

  controlsBar.appendChild(el('div', { className: 'form-group', style: 'margin-bottom: 0;' },
    el('label', { className: 'form-label', htmlFor: 'tariff-input', text: 'Electricity Tariff Rate' }),
    el('div', { style: 'display: flex; gap: 0.5rem;' }, tariffInput, applyTariffBtn)
  ));

  // Priority Filter
  const prioritySelect = el('select', { className: 'form-select', style: 'max-width: 180px;' },
    el('option', { value: 'all' }, 'All Priorities'),
    el('option', { value: 'high' }, 'High Priority Only'),
    el('option', { value: 'medium' }, 'Medium Priority Only'),
    el('option', { value: 'low' }, 'Low Priority Only')
  );

  controlsBar.appendChild(el('div', { className: 'form-group', style: 'margin-bottom: 0;' },
    el('label', { className: 'form-label', text: 'Filter by Priority' }),
    prioritySelect
  ));

  container.appendChild(controlsBar);

  const recListContainer = el('div', { id: 'recommendations-list-container' });
  container.appendChild(recListContainer);

  let rawRecommendations = [];

  prioritySelect.addEventListener('change', () => {
    filterAndRenderRecommendations(recListContainer, rawRecommendations, prioritySelect.value);
  });

  async function loadData() {
    clearElement(recListContainer);
    recListContainer.appendChild(createSpinner('Generating evidence-based recommendations...'));

    try {
      const resp = await api.getRecommendations(datasetId, { signal: ctx.signal });
      clearElement(recListContainer);

      rawRecommendations = resp.recommendations || [];

      if (resp.limitations) {
        recListContainer.appendChild(createNotice(resp.limitations, 'info', 'Recommendation Limitations:'));
      }

      filterAndRenderRecommendations(recListContainer, rawRecommendations, prioritySelect.value);

    } catch (err) {
      if (ctx.signal.aborted) return;
      clearElement(recListContainer);
      recListContainer.appendChild(createEmptyState({
        title: 'Failed to Load Recommendations',
        description: err.message || 'Error communicating with backend.',
        icon: 'alert'
      }));
    }
  }

  await loadData();
}

function filterAndRenderRecommendations(container, items, filterPriority) {
  // Clear any previous cards except notice
  const existingCards = container.querySelectorAll('.rec-card, .empty-state');
  existingCards.forEach((c) => c.remove());

  const filtered = filterPriority === 'all'
    ? items
    : items.filter((r) => String(r.priority || '').toLowerCase() === filterPriority);

  if (filtered.length === 0) {
    container.appendChild(createEmptyState({
      title: 'No Recommendations Available',
      description: filterPriority === 'all'
        ? 'No energy optimization actions flagged for this consumption profile.'
        : `No recommendations matching "${filterPriority}" priority.`,
      icon: 'bulb'
    }));
    return;
  }

  const list = el('div', { className: 'rec-list' });

  filtered.forEach((rec) => {
    const priority = String(rec.priority || 'medium').toLowerCase();
    const card = el('div', { className: `rec-card priority-${priority}` });

    // Header: Title + Priority Badge
    const header = el('div', { className: 'rec-header' },
      el('h3', { className: 'rec-title', text: rec.title || rec.category || 'Efficiency Recommendation' }),
      createPriorityBadge(priority)
    );
    card.appendChild(header);

    // Issue Description
    if (rec.issue || rec.description) {
      card.appendChild(el('p', {
        style: 'font-weight: 600; margin-bottom: 0.35rem; color: var(--text-primary);',
        text: rec.issue || rec.description
      }));
    }

    // Supporting Measurements Box
    if (rec.supporting_measurements && Object.keys(rec.supporting_measurements).length > 0) {
      const measurementsBox = el('div', { className: 'rec-measurements' });
      const itemsList = [];
      for (const [k, v] of Object.entries(rec.supporting_measurements)) {
        itemsList.push(`${k.replace(/_/g, ' ')}: ${v}`);
      }
      measurementsBox.textContent = `Evidence Metrics → ${itemsList.join(' | ')}`;
      card.appendChild(measurementsBox);
    }

    // Action Recommended
    if (rec.action || rec.recommendation) {
      card.appendChild(el('div', { className: 'rec-action' },
        el('strong', { text: 'Suggested Action: ' }),
        el('span', { text: rec.action || rec.recommendation })
      ));
    }

    // Estimated Savings (Defensible - only if non-null)
    const savings = rec.estimated_savings;
    if (savings !== null && savings !== undefined && typeof savings === 'number' && !Number.isNaN(savings)) {
      const currency = rec.currency || 'INR';
      const savingsBox = el('div', {
        className: 'rec-savings-box',
        text: `Estimated Savings: ${formatCurrency(savings, currency)}`
      });
      card.appendChild(savingsBox);
    } else {
      const unavailableBox = el('div', {
        className: 'rec-savings-box unavailable',
        text: CONFIG.SAVINGS_UNAVAILABLE_TEXT
      });
      card.appendChild(unavailableBox);
    }

    // Meta details (Evidence Level, Limitations, Required Data)
    const metaRow = el('div', { className: 'rec-meta' });

    if (rec.evidence_level) {
      metaRow.appendChild(el('span', {},
        el('strong', { text: 'Evidence Level: ' }),
        el('span', { text: String(rec.evidence_level).toUpperCase() })
      ));
    }

    if (rec.limitations) {
      metaRow.appendChild(el('span', {},
        el('strong', { text: 'Caveats: ' }),
        el('span', { text: rec.limitations })
      ));
    }

    if (rec.required_additional_data) {
      metaRow.appendChild(el('span', {},
        el('strong', { text: 'Required for Audit: ' }),
        el('span', { text: rec.required_additional_data })
      ));
    }

    card.appendChild(metaRow);
    list.appendChild(card);
  });

  container.appendChild(list);
}

export function destroy() {
  // Cleanup
}
