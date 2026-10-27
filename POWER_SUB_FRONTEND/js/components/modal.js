// Accessible Modal Dialog with Focus Trap & ESC Handling
import { el, clearElement, svgIcon } from '../utils/dom.js';

let activeModal = null;
let previousActiveElement = null;

/**
 * Opens an accessible confirmation modal.
 * @param {Object} options
 * @param {string} options.title
 * @param {string|Node} options.content
 * @param {string} [options.confirmText='Confirm']
 * @param {string} [options.cancelText='Cancel']
 * @param {'primary'|'danger'} [options.confirmVariant='primary']
 * @param {Function} options.onConfirm
 * @param {Function} [options.onCancel]
 */
export function openConfirmModal(options) {
  const {
    title,
    content,
    confirmText = 'Confirm',
    cancelText = 'Cancel',
    confirmVariant = 'primary',
    onConfirm,
    onCancel = null
  } = options;

  closeModal();

  previousActiveElement = document.activeElement;

  const titleEl = el('h2', { className: 'modal-title', id: 'modal-dialog-title', text: title });
  const closeBtn = el('button', {
    type: 'button',
    className: 'btn-icon',
    'aria-label': 'Close dialog',
    on: { click: () => handleClose(false) }
  }, svgIcon('close', '', 18));

  const header = el('div', { className: 'modal-header' }, titleEl, closeBtn);

  const bodyChildren = typeof content === 'string'
    ? [el('p', { text: content })]
    : [content];
  const body = el('div', { className: 'modal-body', id: 'modal-dialog-desc' }, ...bodyChildren);

  const cancelBtn = el('button', {
    type: 'button',
    className: 'btn btn-secondary',
    text: cancelText,
    on: { click: () => handleClose(false) }
  });

  const confirmBtn = el('button', {
    type: 'button',
    className: `btn btn-${confirmVariant}`,
    text: confirmText,
    on: {
      click: async () => {
        confirmBtn.disabled = true;
        try {
          await onConfirm();
          handleClose(true);
        } catch {
          confirmBtn.disabled = false;
        }
      }
    }
  });

  const footer = el('div', { className: 'modal-footer' }, cancelBtn, confirmBtn);

  const dialog = el('div', {
    className: 'modal-dialog',
    role: 'dialog',
    'aria-modal': 'true',
    'aria-labelledby': 'modal-dialog-title',
    'aria-describedby': 'modal-dialog-desc'
  }, header, body, footer);

  const backdrop = el('div', {
    className: 'modal-backdrop',
    on: {
      click: (e) => {
        if (e.target === backdrop) handleClose(false);
      }
    }
  }, dialog);

  // Keydown listener for ESC and Focus Trap
  function onKeyDown(e) {
    if (e.key === 'Escape') {
      e.preventDefault();
      handleClose(false);
      return;
    }

    if (e.key === 'Tab') {
      const focusables = dialog.querySelectorAll('button:not(:disabled), [tabindex="0"]');
      if (focusables.length === 0) return;
      const first = focusables[0];
      const last = focusables[focusables.length - 1];

      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    }
  }

  function handleClose(confirmed) {
    if (!confirmed && typeof onCancel === 'function') {
      onCancel();
    }
    closeModal();
  }

  document.addEventListener('keydown', onKeyDown);
  backdrop._cleanupKeyDown = () => document.removeEventListener('keydown', onKeyDown);

  document.body.appendChild(backdrop);
  activeModal = backdrop;

  // Auto focus confirm button
  setTimeout(() => confirmBtn.focus(), 50);
}

/**
 * Closes any currently active modal.
 */
export function closeModal() {
  if (activeModal) {
    if (activeModal._cleanupKeyDown) activeModal._cleanupKeyDown();
    if (activeModal.parentElement) {
      activeModal.parentElement.removeChild(activeModal);
    }
    activeModal = null;
    if (previousActiveElement && typeof previousActiveElement.focus === 'function') {
      previousActiveElement.focus();
      previousActiveElement = null;
    }
  }
}
