// Client-Side Input & File Validation Utilities
import { CONFIG } from '../config.js';

const UUID_REGEX = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

/**
 * Validates a file before attempting upload.
 * @param {File} file
 * @returns {{ valid: boolean, error: string|null }}
 */
export function validateFile(file) {
  if (!file) {
    return { valid: false, error: 'No file selected. Please choose an energy dataset file.' };
  }

  if (file.size === 0) {
    return { valid: false, error: 'The selected file is empty (0 bytes).' };
  }

  if (file.size > CONFIG.MAX_FILE_SIZE_BYTES) {
    const limitMb = Math.round(CONFIG.MAX_FILE_SIZE_BYTES / (1024 * 1024));
    return { valid: false, error: `File size exceeds the allowed limit of ${limitMb} MB.` };
  }

  const fileName = file.name.toLowerCase();
  const hasValidExt = CONFIG.ALLOWED_EXTENSIONS.some((ext) => fileName.endsWith(ext));
  if (!hasValidExt) {
    return {
      valid: false,
      error: `Unsupported file format. Supported file types: ${CONFIG.ALLOWED_EXTENSIONS.join(', ')}.`
    };
  }

  return { valid: true, error: null };
}

/**
 * Validates and normalizes an API Base URL.
 * @param {string} urlStr
 * @returns {{ valid: boolean, normalizedUrl: string|null, isUnencryptedRemote: boolean, error: string|null }}
 */
export function validateApiUrl(urlStr) {
  if (!urlStr || typeof urlStr !== 'string' || urlStr.trim() === '') {
    return { valid: false, normalizedUrl: null, isUnencryptedRemote: false, error: 'API URL cannot be empty.' };
  }

  try {
    const parsed = new URL(urlStr.trim());
    if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') {
      return { valid: false, normalizedUrl: null, isUnencryptedRemote: false, error: 'Protocol must be http: or https:.' };
    }

    // Strip credentials, query, hash, and trailing slashes
    const normalized = `${parsed.protocol}//${parsed.host}`;

    // Check if unencrypted remote origin
    const isLocal = parsed.hostname === '127.0.0.1' || parsed.hostname === 'localhost';
    const isUnencryptedRemote = parsed.protocol === 'http:' && !isLocal;

    return {
      valid: true,
      normalizedUrl: normalized,
      isUnencryptedRemote,
      error: null
    };
  } catch {
    return { valid: false, normalizedUrl: null, isUnencryptedRemote: false, error: 'Invalid URL format.' };
  }
}

/**
 * Validates UUID v4 format.
 * @param {string} id
 * @returns {boolean}
 */
export function isValidUuid(id) {
  if (!id || typeof id !== 'string') return false;
  return UUID_REGEX.test(id.trim());
}

/**
 * Validates a positive numeric value.
 * @param {*} val
 * @param {number} [min=0]
 * @returns {boolean}
 */
export function isPositiveNumber(val, min = 0) {
  const num = Number(val);
  return typeof num === 'number' && !Number.isNaN(num) && Number.isFinite(num) && num > min;
}
