// Standard Notice & Disclaimer Blocks
import { CONFIG } from '../config.js';
import { el, svgIcon } from '../utils/dom.js';

/**
 * Creates the standard AI Anomaly disclaimer notice banner.
 * @param {string} [customLimitations=null]
 * @returns {HTMLElement}
 */
export function createAnomalyDisclaimerNotice(customLimitations = null) {
  const icon = el('div', { style: 'flex-shrink: 0; color: var(--color-warning); margin-top: 2px;' }, svgIcon('alert', '', 20));

  const textBlock = el('div', {},
    el('p', {
      style: 'font-weight: 600; margin-bottom: 0.25rem;',
      text: 'Notice: Operational Anomaly Interpretation'
    }),
    el('p', { text: CONFIG.DISCLAIMER_TEXT })
  );

  if (customLimitations) {
    textBlock.appendChild(el('p', {
      style: 'margin-top: 0.4rem; font-size: 0.82rem; opacity: 0.9;',
      text: `Model Limitations: ${customLimitations}`
    }));
  }

  return el('div', {
    className: 'notice-banner notice-warning',
    role: 'note',
    'aria-label': 'Energy anomaly detection disclaimer'
  }, icon, textBlock);
}

/**
 * Creates a generic notice banner.
 * @param {string} message
 * @param {'info'|'warning'|'danger'} [type='info']
 * @param {string} [title=null]
 * @returns {HTMLElement}
 */
export function createNotice(message, type = 'info', title = null) {
  const iconName = type === 'danger' || type === 'warning' ? 'alert' : 'info';
  const icon = el('div', { style: 'flex-shrink: 0;' }, svgIcon(iconName, '', 20));

  const children = [];
  if (title) {
    children.push(el('p', { style: 'font-weight: 600; margin-bottom: 0.2rem;', text: title }));
  }
  children.push(el('p', { text: message }));

  return el('div', {
    className: `notice-banner notice-${type}`,
    role: type === 'danger' ? 'alert' : 'note'
  }, icon, el('div', {}, ...children));
}
