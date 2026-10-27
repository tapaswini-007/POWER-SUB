// Safe formatting utilities for POWER-SUB Dashboard

const DEFAULT_LOCALE = 'en-IN';

/**
 * Checks if a value is valid displayable numeric data.
 */
export function isValidNumber(val) {
  return typeof val === 'number' && !Number.isNaN(val) && Number.isFinite(val);
}

/**
 * Ensures null, undefined, NaN, or Infinity are rendered as a safe placeholder dash ('—').
 * @param {*} val
 * @param {string} [fallback='—']
 * @returns {string}
 */
export function safeText(val, fallback = '—') {
  if (val === null || val === undefined) return fallback;
  if (typeof val === 'number') {
    if (Number.isNaN(val) || !Number.isFinite(val)) return fallback;
    return String(val);
  }
  const str = String(val).trim();
  return str === '' ? fallback : str;
}

/**
 * Formats a number with locale commas and decimal precision.
 * @param {number|null|undefined} val
 * @param {number} [decimals=2]
 * @param {string} [locale=DEFAULT_LOCALE]
 * @returns {string}
 */
export function formatNumber(val, decimals = 2, locale = DEFAULT_LOCALE) {
  if (!isValidNumber(val)) return '—';
  try {
    return new Intl.NumberFormat(locale, {
      minimumFractionDigits: 0,
      maximumFractionDigits: decimals
    }).format(val);
  } catch {
    return val.toFixed(decimals);
  }
}

/**
 * Formats an energy value in kWh with units.
 * @param {number|null|undefined} val
 * @param {string} [unit='kWh']
 * @param {number} [decimals=2]
 * @returns {string}
 */
export function formatKwh(val, unit = 'kWh', decimals = 2) {
  if (!isValidNumber(val)) return '—';
  return `${formatNumber(val, decimals)} ${unit}`;
}

/**
 * Formats a percentage with optional +/- sign.
 * @param {number|null|undefined} val
 * @param {boolean} [includeSign=false]
 * @param {number} [decimals=1]
 * @returns {string}
 */
export function formatPercent(val, includeSign = false, decimals = 1) {
  if (!isValidNumber(val)) return '—';
  const formatted = formatNumber(Math.abs(val), decimals);
  if (includeSign) {
    if (val > 0) return `+${formatted}%`;
    if (val < 0) return `-${formatted}%`;
    return `0.0%`;
  }
  return `${formatNumber(val, decimals)}%`;
}

/**
 * Formats currency or cost with unit if provided.
 * @param {number|null|undefined} val
 * @param {string|null} [currencyUnit=null]
 * @returns {string}
 */
export function formatCurrency(val, currencyUnit = null) {
  if (!isValidNumber(val)) return '—';
  const numStr = formatNumber(val, 2);
  if (currencyUnit && currencyUnit.trim() !== '') {
    return `${currencyUnit} ${numStr}`;
  }
  return numStr;
}

/**
 * Formats ISO date string defensively.
 * @param {string|Date|null|undefined} val
 * @param {boolean} [includeTime=true]
 * @param {string} [locale=DEFAULT_LOCALE]
 * @returns {string}
 */
export function formatDate(val, includeTime = true, locale = DEFAULT_LOCALE) {
  if (!val) return '—';
  try {
    const date = val instanceof Date ? val : new Date(val);
    if (Number.isNaN(date.getTime())) return '—';

    const options = {
      year: 'numeric',
      month: 'short',
      day: 'numeric'
    };
    if (includeTime) {
      options.hour = '2-digit';
      options.minute = '2-digit';
    }
    return new Intl.DateTimeFormat(locale, options).format(date);
  } catch {
    return '—';
  }
}

/**
 * Formats byte size into human readable string (KB, MB, GB).
 * @param {number|null|undefined} bytes
 * @returns {string}
 */
export function formatBytes(bytes) {
  if (!isValidNumber(bytes) || bytes < 0) return '0 B';
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  const val = parseFloat((bytes / Math.pow(k, i)).toFixed(2));
  return `${val} ${sizes[i] || 'B'}`;
}

/**
 * Truncates a UUID or long string for clean UI display.
 * @param {string|null|undefined} str
 * @param {number} [len=8]
 * @returns {string}
 */
export function shortenId(str, len = 8) {
  if (!str) return '—';
  const s = String(str);
  return s.length > len ? `${s.substring(0, len)}...` : s;
}
