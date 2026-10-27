// Safe DOM Utilities - Guaranteed XSS Prevention

/**
 * Creates an HTML element safely without innerHTML.
 * @param {string} tag
 * @param {Object} [attrs={}]
 * @param {...(Node|string|number|Array)} children
 * @returns {HTMLElement}
 */
export function el(tag, attrs = {}, ...children) {
  const element = document.createElement(tag);

  if (attrs) {
    for (const [key, value] of Object.entries(attrs)) {
      if (value === null || value === undefined) continue;

      if (key === 'className' || key === 'class') {
        element.className = String(value);
      } else if (key === 'on' && typeof value === 'object') {
        for (const [event, handler] of Object.entries(value)) {
          if (typeof handler === 'function') {
            element.addEventListener(event, handler);
          }
        }
      } else if (key === 'dataset' && typeof value === 'object') {
        for (const [dataKey, dataVal] of Object.entries(value)) {
          if (dataVal !== null && dataVal !== undefined) {
            element.dataset[dataKey] = String(dataVal);
          }
        }
      } else if (key === 'text') {
        element.textContent = String(value);
      } else if (key.startsWith('aria-') || key.startsWith('data-') || key === 'role') {
        element.setAttribute(key, String(value));
      } else if (key === 'href') {
        // Prevent javascript: URLs
        const hrefStr = String(value).trim();
        if (/^javascript:/i.test(hrefStr)) {
          element.setAttribute('href', '#');
        } else {
          element.setAttribute('href', hrefStr);
        }
      } else if (['type', 'id', 'name', 'value', 'placeholder', 'title', 'for', 'tabIndex', 'rows', 'cols', 'step', 'min', 'max', 'accept', 'checked', 'disabled', 'selected'].includes(key)) {
        if (key === 'checked' || key === 'disabled' || key === 'selected') {
          if (Boolean(value)) {
            element.setAttribute(key, '');
            element[key] = true;
          } else {
            element.removeAttribute(key);
            element[key] = false;
          }
        } else if (key === 'for') {
          element.setAttribute('for', String(value));
        } else {
          element.setAttribute(key, String(value));
          if (key === 'value') {
            element.value = String(value);
          }
        }
      } else {
        // Safe generic attribute
        element.setAttribute(key, String(value));
      }
    }
  }

  appendChildren(element, children);
  return element;
}

/**
 * Appends children safely to a parent node.
 */
export function appendChildren(parent, children) {
  for (const child of children) {
    if (child === null || child === undefined || child === false) {
      continue;
    }
    if (Array.isArray(child)) {
      appendChildren(parent, child);
    } else if (child instanceof Node) {
      parent.appendChild(child);
    } else {
      parent.appendChild(document.createTextNode(String(child)));
    }
  }
}

/**
 * Safely clears all children from a DOM element.
 */
export function clearElement(container) {
  if (!container) return;
  while (container.firstChild) {
    container.removeChild(container.firstChild);
  }
}

/**
 * SVG icons registry for self-contained, offline accessible icons.
 */
const SVG_PATHS = {
  dashboard: 'M3 13h8V3H3v10zm0 8h8v-6H3v6zm10 0h8V11h-8v10zm0-18v6h8V3h-8z',
  upload: 'M9 16h6v-6h4l-7-7-7 7h4zm-4 4h14v2H5z',
  chart: 'M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zM9 17H7v-7h2v7zm4 0h-2V7h2v10zm4 0h-2v-4h2v4z',
  shield: 'M12 1L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4zm-2 16l-4-4 1.41-1.41L10 14.17l6.59-6.59L18 9l-8 8z',
  bulb: 'M12 2C8.13 2 5 5.13 5 9c0 2.38 1.19 4.47 3 5.74V17c0 .55.45 1 1 1h6c.55 0 1-.45 1-1v-2.26c1.81-1.27 3-3.36 3-5.74 0-3.87-3.13-7-7-7zm-2 17h4v1h-4v-1zm1 2h2v1h-2v-1z',
  file: 'M14 2H6c-1.1 0-1.99.9-1.99 2L4 20c0 1.1.89 2 1.99 2H18c1.1 0 2-.9 2-2V8l-6-6zm2 16H8v-2h8v2zm0-4H8v-2h8v2zm-3-5V3.5L18.5 9H13z',
  history: 'M13 3c-4.97 0-9 4.03-9 9H1l3.89 3.89.07.14L9 12H6c0-3.87 3.13-7 7-7s7 3.13 7 7-3.13 7-7 7c-1.93 0-3.68-.79-4.94-2.06l-1.42 1.42C8.27 19.99 10.51 21 13 21c4.97 0 9-4.03 9-9s-4.03-9-9-9zm-1 5v5l4.28 2.54.72-1.21-3.5-2.08V8H12z',
  settings: 'M19.14 12.94c.04-.3.06-.61.06-.94 0-.32-.02-.64-.07-.94l2.03-1.58c.18-.14.23-.41.12-.61l-1.92-3.32c-.12-.22-.37-.29-.59-.22l-2.39.96c-.5-.38-1.03-.7-1.62-.94l-.36-2.54c-.04-.24-.24-.41-.48-.41h-3.84c-.24 0-.43.17-.47.41l-.36 2.54c-.59.24-1.13.57-1.62.94l-2.39-.96c-.22-.08-.47 0-.59.22L2.74 8.87c-.12.21-.08.47.12.61l2.03 1.58c-.05.3-.09.63-.09.94s.02.64.07.94l-2.03 1.58c-.18.14-.23.41-.12.61l1.92 3.32c.12.22.37.29.59.22l2.39-.96c.5.38 1.03.7 1.62.94l.36 2.54c.05.24.24.41.48.41h3.84c.24 0 .44-.17.47-.41l.36-2.54c.59-.24 1.13-.56 1.62-.94l2.39.96c.22.08.47 0 .59-.22l1.92-3.32c.12-.22.07-.47-.12-.61l-2.01-1.58zM12 15.6c-1.98 0-3.6-1.62-3.6-3.6s1.62-3.6 3.6-3.6 3.6 1.62 3.6 3.6-1.62 3.6-3.6 3.6z',
  check: 'M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z',
  alert: 'M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z',
  info: 'M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-6h2v6zm0-8h-2V7h2v2z',
  refresh: 'M17.65 6.35C16.2 4.9 14.21 4 12 4c-4.42 0-7.99 3.58-7.99 8s3.57 8 7.99 8c3.73 0 6.84-2.55 7.73-6h-2.08c-.82 2.33-3.04 4-5.65 4-3.31 0-6-2.69-6-6s2.69-6 6-6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z',
  trash: 'M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z',
  close: 'M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z',
  menu: 'M3 18h18v-2H3v2zm0-5h18v-2H3v2zm0-7v2h18V6H3z',
  download: 'M19 9h-4V3H9v6H5l7 7 7-7zM5 18v2h14v-2H5z',
  lightning: 'M7 2v11h3v9l7-12h-4l4-8z'
};

/**
 * Creates an inline SVG icon.
 * @param {string} name
 * @param {string} [className='']
 * @param {number} [size=20]
 * @returns {SVGElement}
 */
export function svgIcon(name, className = '', size = 20) {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('viewBox', '0 0 24 24');
  svg.setAttribute('width', String(size));
  svg.setAttribute('height', String(size));
  svg.setAttribute('fill', 'currentColor');
  svg.setAttribute('aria-hidden', 'true');
  if (className) {
    svg.setAttribute('class', className);
  }

  const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
  path.setAttribute('d', SVG_PATHS[name] || SVG_PATHS.info);
  svg.appendChild(path);

  return svg;
}
