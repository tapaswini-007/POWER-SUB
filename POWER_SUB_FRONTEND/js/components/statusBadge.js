// Accessible Status Badges with Icon + Text Pairing
import { el, svgIcon } from '../utils/dom.js';

/**
 * Creates an anomaly/record status badge.
 * @param {'normal'|'anomaly'|'investigate'|boolean} status
 * @returns {HTMLElement}
 */
export function createAnomalyBadge(status) {
  let label = 'Normal';
  let badgeClass = 'badge-normal';
  let iconName = 'check';

  if (status === true || status === 'anomaly' || status === 'Potential Anomaly') {
    label = 'Flagged Anomaly';
    badgeClass = 'badge-anomaly';
    iconName = 'alert';
  } else if (status === 'investigate' || status === 'Requires Investigation') {
    label = 'Requires Investigation';
    badgeClass = 'badge-warning';
    iconName = 'alert';
  }

  return el('span', { className: `badge ${badgeClass}` }, svgIcon(iconName, '', 14), label);
}

/**
 * Creates a priority badge (High, Medium, Low).
 * @param {'high'|'medium'|'low'|string} priority
 * @returns {HTMLElement}
 */
export function createPriorityBadge(priority) {
  const p = String(priority || '').toLowerCase();
  let badgeClass = 'badge-info';
  let iconName = 'info';
  let text = 'Low';

  if (p === 'high') {
    badgeClass = 'badge-danger';
    iconName = 'alert';
    text = 'High Priority';
  } else if (p === 'medium') {
    badgeClass = 'badge-warning';
    iconName = 'alert';
    text = 'Medium Priority';
  } else {
    badgeClass = 'badge-normal';
    iconName = 'check';
    text = 'Low Priority';
  }

  return el('span', { className: `badge ${badgeClass}` }, svgIcon(iconName, '', 14), text);
}

/**
 * Creates a distinct method badge (AI vs Rule-based fallback).
 * @param {string} method
 * @returns {HTMLElement}
 */
export function createMethodBadge(method) {
  const m = String(method || '').toLowerCase();
  const isAi = m.includes('isolation_forest') || m.includes('ai');

  if (isAi) {
    return el('span', {
      className: 'badge badge-info',
      style: 'font-weight: 700; padding: 0.35rem 0.65rem;'
    }, svgIcon('lightning', '', 14), 'AI (Isolation Forest)');
  }

  return el('span', {
    className: 'badge badge-warning',
    style: 'font-weight: 700; padding: 0.35rem 0.65rem;'
  }, svgIcon('shield', '', 14), 'Rule-based fallback (IQR)');
}
