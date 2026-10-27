// High-Performance Accessible Data Table Component
import { el, clearElement, svgIcon } from '../utils/dom.js';
import { safeText } from '../utils/format.js';

const ROW_CAP = 1000;

/**
 * Creates a sortable, searchable, paginated data table.
 * @param {Object} options
 * @param {Array<Object>} options.columns - [{ key, label, sortable?, render?: (val, row) => Node|string, type?: 'string'|'number'|'date' }]
 * @param {Array<Object>} options.data - Raw row objects
 * @param {number} [options.initialPageSize=25]
 * @param {string} [options.searchPlaceholder='Search records...']
 * @param {string} [options.emptyMessage='No records found.']
 * @param {Array<Object>} [options.actions=[]] - Additional toolbar elements
 * @returns {HTMLElement}
 */
export function createDataTable(options) {
  const {
    columns,
    data = [],
    initialPageSize = 25,
    searchPlaceholder = 'Search records...',
    emptyMessage = 'No records found.',
    actions = []
  } = options;

  let currentData = [...data].slice(0, ROW_CAP);
  let filteredData = [...currentData];
  let sortKey = null;
  let sortAsc = true;
  let currentPage = 1;
  let pageSize = initialPageSize;
  let searchDebounceTimer = null;

  const container = el('div', { className: 'data-table-container' });

  // Toolbar
  const searchInput = el('input', {
    type: 'search',
    className: 'form-input table-search-input',
    placeholder: searchPlaceholder,
    'aria-label': searchPlaceholder,
    on: {
      input: (e) => {
        clearTimeout(searchDebounceTimer);
        searchDebounceTimer = setTimeout(() => {
          handleSearch(e.target.value);
        }, 250);
      }
    }
  });

  const toolbarLeft = el('div', { style: 'display: flex; gap: 0.75rem; align-items: center; flex-wrap: wrap;' }, searchInput, ...actions);

  const rowCountBadge = el('span', {
    style: 'font-size: 0.82rem; color: var(--text-muted); font-weight: 500;',
    text: `Total: ${data.length} records`
  });

  const toolbar = el('div', { className: 'table-toolbar' }, toolbarLeft, rowCountBadge);
  container.appendChild(toolbar);

  // Table Structure
  const table = el('table', { className: 'data-table', role: 'table' });
  const thead = el('thead');
  const theadRow = el('tr');

  columns.forEach((col) => {
    const isSortable = col.sortable !== false;
    const th = el('th', {
      scope: 'col',
      className: isSortable ? 'sortable' : '',
      'aria-sort': 'none',
      tabIndex: isSortable ? 0 : -1,
      role: 'columnheader',
      on: isSortable ? {
        click: () => handleSort(col.key, col.type),
        keydown: (e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            handleSort(col.key, col.type);
          }
        }
      } : {}
    }, col.label);
    theadRow.appendChild(th);
  });
  thead.appendChild(theadRow);
  table.appendChild(thead);

  const tbody = el('tbody');
  table.appendChild(tbody);

  const tableWrapper = el('div', { className: 'table-responsive' }, table);
  container.appendChild(tableWrapper);

  // Pagination Footer
  const pageInfo = el('span', { className: 'pagination-info' });

  const prevBtn = el('button', {
    type: 'button',
    className: 'btn btn-secondary btn-sm',
    text: 'Previous',
    on: { click: () => changePage(currentPage - 1) }
  });

  const nextBtn = el('button', {
    type: 'button',
    className: 'btn btn-secondary btn-sm',
    text: 'Next',
    on: { click: () => changePage(currentPage + 1) }
  });

  const pageSizeSelect = el('select', {
    className: 'form-select',
    style: 'width: auto; padding: 0.25rem 0.5rem; font-size: 0.8rem;',
    'aria-label': 'Rows per page',
    on: {
      change: (e) => {
        pageSize = Number(e.target.value);
        currentPage = 1;
        renderRows();
      }
    }
  },
    el('option', { value: 10, selected: pageSize === 10 }, '10 / page'),
    el('option', { value: 25, selected: pageSize === 25 }, '25 / page'),
    el('option', { value: 50, selected: pageSize === 50 }, '50 / page'),
    el('option', { value: 100, selected: pageSize === 100 }, '100 / page')
  );

  const paginationControls = el('div', { className: 'pagination-controls' }, pageSizeSelect, prevBtn, nextBtn);
  const paginationBar = el('div', { className: 'table-pagination' }, pageInfo, paginationControls);
  container.appendChild(paginationBar);

  // Internal Sorting
  function handleSort(key, type = 'string') {
    if (sortKey === key) {
      sortAsc = !sortAsc;
    } else {
      sortKey = key;
      sortAsc = true;
    }

    filteredData.sort((a, b) => {
      let valA = a[key];
      let valB = b[key];

      if (valA === null || valA === undefined) return 1;
      if (valB === null || valB === undefined) return -1;

      if (type === 'number') {
        const numA = Number(valA);
        const numB = Number(valB);
        return sortAsc ? numA - numB : numB - numA;
      }
      if (type === 'date') {
        const dateA = new Date(valA).getTime() || 0;
        const dateB = new Date(valB).getTime() || 0;
        return sortAsc ? dateA - dateB : dateB - dateA;
      }

      const strA = String(valA).toLowerCase();
      const strB = String(valB).toLowerCase();
      return sortAsc ? strA.localeCompare(strB) : strB.localeCompare(strA);
    });

    // Update aria-sort on headers
    const ths = theadRow.querySelectorAll('th');
    columns.forEach((col, idx) => {
      if (col.key === sortKey) {
        ths[idx].setAttribute('aria-sort', sortAsc ? 'ascending' : 'descending');
      } else {
        ths[idx].setAttribute('aria-sort', 'none');
      }
    });

    currentPage = 1;
    renderRows();
  }

  // Internal Search Filtering
  function handleSearch(term) {
    const q = String(term || '').trim().toLowerCase();
    if (!q) {
      filteredData = [...currentData];
    } else {
      filteredData = currentData.filter((row) => {
        return columns.some((col) => {
          const val = row[col.key];
          if (val === null || val === undefined) return false;
          return String(val).toLowerCase().includes(q);
        });
      });
    }

    currentPage = 1;
    renderRows();
  }

  function changePage(newPage) {
    const totalPages = Math.max(1, Math.ceil(filteredData.length / pageSize));
    if (newPage >= 1 && newPage <= totalPages) {
      currentPage = newPage;
      renderRows();
    }
  }

  // Render Rows using DocumentFragment for maximum performance
  function renderRows() {
    clearElement(tbody);

    const total = filteredData.length;
    const totalPages = Math.max(1, Math.ceil(total / pageSize));

    if (currentPage > totalPages) currentPage = totalPages;

    const startIdx = (currentPage - 1) * pageSize;
    const endIdx = Math.min(startIdx + pageSize, total);
    const pageRows = filteredData.slice(startIdx, endIdx);

    pageInfo.textContent = total === 0
      ? '0 of 0 records'
      : `Showing ${startIdx + 1}–${endIdx} of ${total} records`;

    prevBtn.disabled = currentPage <= 1;
    nextBtn.disabled = currentPage >= totalPages;

    if (pageRows.length === 0) {
      const emptyRow = el('tr', {},
        el('td', {
          colSpan: columns.length,
          style: 'text-align: center; padding: 2rem; color: var(--text-muted);',
          text: emptyMessage
        })
      );
      tbody.appendChild(emptyRow);
      return;
    }

    const fragment = document.createDocumentFragment();

    for (const row of pageRows) {
      const tr = el('tr');
      for (const col of columns) {
        const val = row[col.key];
        let tdContent;

        if (typeof col.render === 'function') {
          tdContent = col.render(val, row);
        } else {
          tdContent = safeText(val);
        }

        const td = el('td');
        if (tdContent instanceof Node) {
          td.appendChild(tdContent);
        } else {
          td.textContent = String(tdContent);
        }
        tr.appendChild(td);
      }
      fragment.appendChild(tr);
    }

    tbody.appendChild(fragment);
  }

  // Initial render
  renderRows();

  return container;
}
