// Accessible Toast Notifications Component
import { el, clearElement, svgIcon } from '../utils/dom.js';

let toastContainer = null;

function getToastContainer() {
  if (!toastContainer || !document.body.contains(toastContainer)) {
    toastContainer = el('div', {
      className: 'toast-container',
      'aria-live': 'polite',
      'aria-atomic': 'false'
    });
    document.body.appendChild(toastContainer);
  }
  return toastContainer;
}

/**
 * Displays a toast notification.
 * @param {string} title
 * @param {string} message
 * @param {'success'|'error'|'info'|'warning'} [type='info']
 * @param {string|null} [requestId=null]
 * @param {number} [duration=5000]
 */
export function showToast(title, message, type = 'info', requestId = null, duration = 5000) {
  const container = getToastContainer();

  const isError = type === 'error';
  const role = isError ? 'alert' : 'status';
  const ariaLive = isError ? 'assertive' : 'polite';

  const iconName = isError ? 'alert' : type === 'success' ? 'check' : 'info';

  const titleEl = el('div', { className: 'toast-title', text: title });
  const bodyEl = el('div', { className: 'toast-body', text: message });

  const children = [titleEl, bodyEl];
  if (requestId) {
    children.push(el('div', { className: 'toast-ref', text: `Reference: ${requestId}` }));
  }

  const contentCol = el('div', { style: 'flex: 1;' }, ...children);

  const closeBtn = el('button', {
    type: 'button',
    className: 'toast-close',
    'aria-label': 'Close notification',
    on: {
      click: () => removeToast(toastEl)
    }
  }, svgIcon('close', '', 16));

  const toastEl = el('div', {
    className: `toast toast-${type}`,
    role,
    'aria-live': ariaLive
  }, svgIcon(iconName, `toast-icon text-${type}`, 20), contentCol, closeBtn);

  container.appendChild(toastEl);

  let timer = null;
  if (duration > 0) {
    timer = setTimeout(() => {
      removeToast(toastEl);
    }, duration);
  }

  function removeToast(node) {
    if (timer) clearTimeout(timer);
    node.style.opacity = '0';
    node.style.transform = 'translateY(10px)';
    node.style.transition = 'all 0.2s ease';
    setTimeout(() => {
      if (node.parentElement) {
        node.parentElement.removeChild(node);
      }
    }, 200);
  }
}
