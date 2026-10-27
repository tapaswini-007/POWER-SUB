// Upload Energy Data Page Module
import { api, ApiError } from '../api.js';
import { store } from '../state.js';
import { el, clearElement, svgIcon } from '../utils/dom.js';
import { validateFile } from '../utils/validate.js';
import { formatBytes, formatNumber, safeText } from '../utils/format.js';
import { showToast } from '../components/toast.js';
import { createNotice } from '../components/notice.js';

let activeUploadController = null;

export async function render(container, ctx) {
  clearElement(container);

  let selectedFile = null;

  // Header info card
  const introCard = el('div', { className: 'card' },
    el('h2', { className: 'card-title', text: 'Upload Electricity Consumption Reports' }),
    el('p', {
      className: 'card-subtitle',
      text: 'Submit sub-metered electricity readings in CSV, Excel (.xlsx/.xls), or PDF format. POWER-SUB validates headers, normalizes units, and performs automated schema mapping.'
    })
  );
  container.appendChild(introCard);

  // Upload Form Container
  const uploadFormCard = el('div', { className: 'card' });

  // Hidden real file input
  const fileInput = el('input', {
    type: 'file',
    id: 'energy-file-input',
    className: 'file-input-hidden',
    accept: '.csv,.xlsx,.xls,.pdf',
    on: {
      change: (e) => {
        if (e.target.files && e.target.files.length > 0) {
          handleFileSelection(e.target.files[0]);
        }
      }
    }
  });

  // Accessible Drag & Drop Zone (label for file input)
  const dropzone = el('label', {
    htmlFor: 'energy-file-input',
    className: 'dropzone',
    tabIndex: 0,
    role: 'button',
    'aria-label': 'Drop energy file here or press Enter to browse files',
    on: {
      keydown: (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          fileInput.click();
        }
      },
      dragover: (e) => {
        e.preventDefault();
        dropzone.classList.add('drag-active');
      },
      dragleave: () => {
        dropzone.classList.remove('drag-active');
      },
      drop: (e) => {
        e.preventDefault();
        dropzone.classList.remove('drag-active');
        if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
          handleFileSelection(e.dataTransfer.files[0]);
        }
      }
    }
  },
    svgIcon('upload', 'dropzone-icon', 48),
    el('div', { className: 'dropzone-title', text: 'Choose or drag & drop energy file here' },
    el('div', { className: 'dropzone-desc', text: 'Supported formats: .CSV, .XLSX, .XLS, .PDF (Max 10 MB)' }),
    el('span', { className: 'btn btn-outline btn-sm', text: 'Browse Local Files' }))
  );

  uploadFormCard.appendChild(fileInput);
  uploadFormCard.appendChild(dropzone);

  // File Details Box
  const fileDetailsBox = el('div', { className: 'upload-file-details', style: 'display: none;' });
  const fileNameDisplay = el('div', { style: 'font-weight: 600;' });
  const fileSizeDisplay = el('div', { style: 'font-size: 0.82rem; color: var(--text-muted);' });
  const fileInfoCol = el('div', {}, fileNameDisplay, fileSizeDisplay);

  const removeFileBtn = el('button', {
    type: 'button',
    className: 'btn btn-secondary btn-sm',
    text: 'Remove',
    on: {
      click: () => {
        selectedFile = null;
        fileInput.value = '';
        fileDetailsBox.style.display = 'none';
        submitBtn.disabled = true;
        validationErrorBox.style.display = 'none';
      }
    }
  });

  fileDetailsBox.appendChild(fileInfoCol);
  fileDetailsBox.appendChild(removeFileBtn);
  uploadFormCard.appendChild(fileDetailsBox);

  // Validation Error Box
  const validationErrorBox = el('div', { className: 'notice-banner notice-danger', style: 'display: none; margin-top: 1rem;' });
  uploadFormCard.appendChild(validationErrorBox);

  // Optional Parameters (supported by backend)
  const optionsGrid = el('div', {
    style: 'display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-top: 1.25rem;'
  });

  // Energy Unit Selector
  const unitSelect = el('select', { className: 'form-select', id: 'upload-energy-unit' },
    el('option', { value: 'kWh', selected: true }, 'kWh (Kilowatt-hours)'),
    el('option', { value: 'Wh' }, 'Wh (Watt-hours)'),
    el('option', { value: 'MWh' }, 'MWh (Megawatt-hours)')
  );
  optionsGrid.appendChild(el('div', { className: 'form-group' },
    el('label', { className: 'form-label', htmlFor: 'upload-energy-unit', text: 'Reported Energy Unit' }),
    unitSelect,
    el('span', { className: 'form-help', text: 'Values are converted automatically to standard kWh' })
  ));

  // Sheet Name for Excel
  const sheetInput = el('input', {
    type: 'text',
    className: 'form-input',
    id: 'upload-sheet-name',
    placeholder: 'Optional sheet name (Excel)'
  });
  optionsGrid.appendChild(el('div', { className: 'form-group' },
    el('label', { className: 'form-label', htmlFor: 'upload-sheet-name', text: 'Excel Sheet Name' }),
    sheetInput,
    el('span', { className: 'form-help', text: 'Leave blank to use the active or first sheet' })
  ));

  uploadFormCard.appendChild(optionsGrid);

  // Progress Bar Container
  const progressContainer = el('div', { style: 'display: none; margin-top: 1rem;' },
    el('div', { style: 'display: flex; justify-content: space-between; font-size: 0.85rem; font-weight: 600;' },
      el('span', { id: 'upload-status-label', text: 'Uploading & Processing...' }),
      el('span', { id: 'upload-percent-label', text: '0%' })
    ),
    el('div', { className: 'upload-progress-bar' },
      el('div', { id: 'upload-progress-fill', className: 'upload-progress-fill' })
    )
  );
  uploadFormCard.appendChild(progressContainer);

  // Action Buttons
  const submitBtn = el('button', {
    type: 'button',
    className: 'btn btn-primary',
    disabled: true,
    text: 'Upload and Process Dataset',
    on: { click: () => handleUpload() }
  });

  const cancelBtn = el('button', {
    type: 'button',
    className: 'btn btn-secondary',
    style: 'display: none;',
    text: 'Cancel Upload',
    on: {
      click: () => {
        if (activeUploadController) {
          activeUploadController.abort();
          activeUploadController = null;
        }
      }
    }
  });

  const actionsRow = el('div', { style: 'display: flex; gap: 0.75rem; margin-top: 1.25rem;' }, submitBtn, cancelBtn);
  uploadFormCard.appendChild(actionsRow);

  container.appendChild(uploadFormCard);

  // Results Container (for preview, quality report, columns)
  const resultsContainer = el('div', { id: 'upload-results-container' });
  container.appendChild(resultsContainer);

  function handleFileSelection(file) {
    validationErrorBox.style.display = 'none';
    clearElement(validationErrorBox);

    const validation = validateFile(file);
    if (!validation.valid) {
      validationErrorBox.style.display = 'flex';
      validationErrorBox.appendChild(svgIcon('alert', '', 20));
      validationErrorBox.appendChild(el('div', { text: validation.error }));
      submitBtn.disabled = true;
      fileDetailsBox.style.display = 'none';
      selectedFile = null;
      return;
    }

    selectedFile = file;
    fileNameDisplay.textContent = file.name;
    fileSizeDisplay.textContent = `${formatBytes(file.size)} • ${file.type || 'Document'}`;
    fileDetailsBox.style.display = 'flex';
    submitBtn.disabled = false;
  }

  async function handleUpload() {
    if (!selectedFile) return;

    clearElement(resultsContainer);
    validationErrorBox.style.display = 'none';
    submitBtn.disabled = true;
    cancelBtn.style.display = 'inline-flex';
    progressContainer.style.display = 'block';

    const progressFill = document.getElementById('upload-progress-fill');
    const percentLabel = document.getElementById('upload-percent-label');
    const statusLabel = document.getElementById('upload-status-label');

    progressFill.className = 'upload-progress-fill';
    progressFill.style.width = '0%';
    percentLabel.textContent = '0%';
    statusLabel.textContent = 'Uploading file to backend...';

    activeUploadController = new AbortController();

    try {
      const resp = await api.uploadFile(selectedFile, {
        energyUnit: unitSelect.value,
        sheetName: sheetInput.value.trim() || null,
        signal: activeUploadController.signal,
        onProgress: (percent) => {
          progressFill.style.width = `${percent}%`;
          percentLabel.textContent = `${percent}%`;
          if (percent >= 100) {
            statusLabel.textContent = 'Backend processing and data validation in progress...';
            progressFill.classList.add('indeterminate');
          }
        }
      });

      // Update state with newly uploaded dataset
      store.setCurrentDatasetId(resp.dataset_id);
      showToast('Upload Successful', `Successfully processed ${formatNumber(resp.record_count, 0)} energy records.`, 'success');

      renderUploadSuccess(resultsContainer, resp);

    } catch (err) {
      if (err.name === 'AbortError') {
        showToast('Upload Cancelled', 'File upload was aborted by the user.', 'info');
      } else {
        const errorMsg = err.message || 'File processing failed.';
        showToast('Upload Failed', errorMsg, 'error', err.requestId);

        validationErrorBox.style.display = 'flex';
        clearElement(validationErrorBox);
        validationErrorBox.appendChild(svgIcon('alert', '', 20));

        const errContent = el('div', {},
          el('p', { style: 'font-weight: 600;', text: 'Backend Processing Error:' }),
          el('p', { text: errorMsg })
        );

        if (err.requestId) {
          errContent.appendChild(el('p', {
            style: 'font-size: 0.78rem; font-family: monospace; margin-top: 0.35rem;',
            text: `Reference ID: ${err.requestId}`
          }));
        }

        // Special recommendation if PDF failed table extraction
        if (selectedFile.name.toLowerCase().endsWith('.pdf') && errorMsg.toLowerCase().includes('no extractable table')) {
          errContent.appendChild(el('p', {
            style: 'margin-top: 0.5rem; font-weight: 600; color: #7f1d1d;',
            text: 'Tip: Scanned or image-based PDFs cannot be converted into tables. Please export and upload directly as a CSV or Excel spreadsheet.'
          }));
        }

        validationErrorBox.appendChild(errContent);
      }
    } finally {
      submitBtn.disabled = false;
      cancelBtn.style.display = 'none';
      progressContainer.style.display = 'none';
      activeUploadController = null;
    }
  }
}

function renderUploadSuccess(container, data) {
  clearElement(container);

  const card = el('div', { className: 'card', style: 'margin-top: 1.5rem;' });

  // Header & Navigation Action
  const cardHeader = el('div', { className: 'card-header' },
    el('div', {},
      el('h2', { className: 'card-title', style: 'color: var(--color-success);', text: '✓ Dataset Ingestion Complete' }),
      el('p', { className: 'card-subtitle', text: `Dataset ID: ${data.dataset_id}` })
    ),
    el('a', {
      className: 'btn btn-primary',
      href: `#/analysis/${encodeURIComponent(data.dataset_id)}`,
      text: 'Open Energy Analysis →'
    })
  );
  card.appendChild(cardHeader);

  // Quality Stats Grid
  const dq = data.data_quality || {};
  const statsGrid = el('div', { className: 'quality-grid' },
    createStatBox('Total Records', formatNumber(data.record_count, 0)),
    createStatBox('Accepted Rows', formatNumber(dq.accepted_rows_count ?? data.record_count, 0)),
    createStatBox('Corrected Rows', formatNumber(dq.corrected_rows_count ?? 0, 0)),
    createStatBox('Rejected Rows', formatNumber(dq.rejected_rows_count ?? 0, 0))
  );
  card.appendChild(statsGrid);

  // Limitations Banner if provided by backend
  if (data.limitations) {
    card.appendChild(createNotice(data.limitations, 'info', 'Dataset & Parser Limitations:'));
  }

  // Warnings list
  const warnings = data.warnings || [];
  if (warnings.length > 0) {
    const warnList = el('ul', { style: 'padding-left: 1.25rem; font-size: 0.85rem;' });
    warnings.forEach((w) => warnList.appendChild(el('li', { text: String(w) })));
    card.appendChild(createNotice('The following warnings were noted during ingestion:', 'warning', 'Ingestion Warnings:'));
    card.appendChild(warnList);
  }

  // Schema Mapping Summary
  const cols = data.columns || {};
  const schemaSummary = el('div', { style: 'margin: 1.25rem 0;' },
    el('h3', { style: 'font-size: 0.95rem; font-weight: 700; margin-bottom: 0.5rem;', text: 'Column Mapping Summary' }),
    el('div', { style: 'font-size: 0.85rem; display: flex; flex-wrap: wrap; gap: 0.5rem;' },
      el('span', { className: 'badge badge-info', text: `Timestamp: ${cols.timestamp || 'Not detected'}` }),
      el('span', { className: 'badge badge-info', text: `Consumption: ${cols.consumption || 'Not detected'}` }),
      cols.building ? el('span', { className: 'badge badge-neutral', text: `Building: ${cols.building}` }) : null,
      cols.department ? el('span', { className: 'badge badge-neutral', text: `Department: ${cols.department}` }) : null,
      cols.equipment ? el('span', { className: 'badge badge-neutral', text: `Equipment: ${cols.equipment}` }) : null
    )
  );
  card.appendChild(schemaSummary);

  // First Rows Preview Table (Safely escaped with textContent)
  const previewRows = data.preview_rows || [];
  if (previewRows.length > 0) {
    const previewHeader = el('h3', {
      style: 'font-size: 0.95rem; font-weight: 700; margin: 1rem 0 0.5rem;',
      text: `Data Preview (First ${previewRows.length} Rows)`
    });
    card.appendChild(previewHeader);

    const keys = Object.keys(previewRows[0]);
    const tableWrap = el('div', { className: 'table-responsive' });
    const table = el('table', { className: 'data-table' });
    const thead = el('thead');
    const theadRow = el('tr');

    keys.forEach((k) => theadRow.appendChild(el('th', { text: k })));
    thead.appendChild(theadRow);
    table.appendChild(thead);

    const tbody = el('tbody');
    previewRows.forEach((row) => {
      const tr = el('tr');
      keys.forEach((k) => {
        tr.appendChild(el('td', { text: safeText(row[k]) }));
      });
      tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    tableWrap.appendChild(table);
    card.appendChild(tableWrap);
  }

  container.appendChild(card);
}

function createStatBox(label, val) {
  return el('div', { className: 'quality-stat' },
    el('div', { className: 'quality-stat-label', text: label }),
    el('div', { className: 'quality-stat-val', text: val })
  );
}

export function destroy() {
  if (activeUploadController) {
    activeUploadController.abort();
    activeUploadController = null;
  }
}
