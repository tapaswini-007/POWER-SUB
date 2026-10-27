// Reusable Accessible Empty State Component
import { el, svgIcon } from '../utils/dom.js';

/**
 * Creates an empty state illustration/message block.
 * @param {Object} options
 * @param {string} options.title
 * @param {string} options.description
 * @param {string} [options.icon='file']
 * @param {Object} [options.action=null] - { text: string, href?: string, onClick?: Function }
 * @returns {HTMLElement}
 */
export function createEmptyState(options) {
  const { title, description, icon = 'file', action = null } = options;

  const iconEl = el('div', {
    className: 'empty-state-icon-wrap',
    style: 'display: flex; justify-content: center; margin-bottom: 1rem;'
  }, svgIcon(icon, 'empty-state-icon', 48));

  const titleEl = el('h3', { className: 'empty-state-title', text: title });
  const descEl = el('p', { className: 'empty-state-desc', text: description });

  const children = [iconEl, titleEl, descEl];

  if (action) {
    if (action.href) {
      children.push(el('a', {
        className: 'btn btn-primary',
        href: action.href,
        text: action.text
      }));
    } else if (action.onClick) {
      children.push(el('button', {
        type: 'button',
        className: 'btn btn-primary',
        text: action.text,
        on: { click: action.onClick }
      }));
    }
  }

  return el('div', { className: 'empty-state card' }, ...children);
}
