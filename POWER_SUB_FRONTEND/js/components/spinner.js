// Accessible Spinner & Skeleton Loaders
import { el } from '../utils/dom.js';

/**
 * Creates an accessible inline loading spinner.
 * @param {string} [label='Loading...']
 * @returns {HTMLElement}
 */
export function createSpinner(label = 'Loading...') {
  const spin = el('span', { className: 'spinner', 'aria-hidden': 'true' });
  const text = el('span', {
    style: 'position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0,0,0,0); border: 0;',
    text: label
  });
  return el('div', {
    className: 'spinner-wrapper',
    role: 'status',
    style: 'display: inline-flex; align-items: center; gap: 0.5rem; justify-content: center; padding: 1rem;'
  }, spin, text);
}

/**
 * Creates skeleton loader placeholders.
 * @param {number} [lines=3]
 * @returns {HTMLElement}
 */
export function createSkeleton(lines = 3) {
  const boxes = [];
  for (let i = 0; i < lines; i++) {
    const width = i === lines - 1 ? '60%' : '100%';
    boxes.push(el('div', {
      className: 'skeleton-box',
      style: `width: ${width}; height: 18px; margin-bottom: 0.65rem;`
    }));
  }
  return el('div', {
    className: 'skeleton-container',
    'aria-busy': 'true',
    'aria-label': 'Loading content'
  }, ...boxes);
}
