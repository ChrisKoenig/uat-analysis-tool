/**
 * Helper Utilities
 * ================
 *
 * Small utility functions used throughout the Triage UI.
 */

/**
 * Format an ISO timestamp into a human-readable date/time string.
 * Uses the browser's locale for localization.
 *
 * @param {string} isoString - ISO 8601 timestamp
 * @returns {string} Formatted date/time or empty string if invalid
 */
export function formatDateTime(isoString) {
  if (!isoString) return '';
  try {
    return new Date(isoString).toLocaleString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return isoString;
  }
}


/**
 * Format a date-only string (no time component).
 *
 * @param {string} isoString - ISO 8601 timestamp
 * @returns {string} Formatted date
 */
export function formatDate(isoString) {
  if (!isoString) return '';
  try {
    return new Date(isoString).toLocaleDateString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  } catch {
    return isoString;
  }
}


/**
 * Truncate a string to maxLen characters, appending "…" if truncated.
 *
 * @param {string} str - Input string
 * @param {number} [maxLen=80] - Maximum length
 * @returns {string} Truncated string
 */
export function truncate(str, maxLen = 80) {
  if (!str || str.length <= maxLen) return str || '';
  return str.slice(0, maxLen - 1) + '…';
}


/**
 * Deep-clone a plain object/array using structured clone.
 * Falls back to JSON parse/stringify for older browsers.
 *
 * @param {*} obj - Object to clone
 * @returns {*} Deep copy
 */
export function deepClone(obj) {
  if (typeof structuredClone === 'function') {
    return structuredClone(obj);
  }
  return JSON.parse(JSON.stringify(obj));
}


/**
 * Generate a simple random ID for temporary client-side keys.
 * NOT for database IDs — those come from the backend.
 *
 * @param {string} [prefix='temp'] - ID prefix
 * @returns {string} Random ID string
 */
export function tempId(prefix = 'temp') {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}


/**
 * Debounce a function call.
 *
 * @param {Function} fn - Function to debounce
 * @param {number} [delay=300] - Delay in milliseconds
 * @returns {Function} Debounced function
 */
export function debounce(fn, delay = 300) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), delay);
  };
}


/**
 * Capitalize the first letter of a string.
 *
 * @param {string} str - Input string
 * @returns {string} Capitalized string
 */
export function capitalize(str) {
  if (!str) return '';
  return str.charAt(0).toUpperCase() + str.slice(1);
}


/**
 * Extract a human-readable field name from an ADO field reference.
 * E.g., "Custom.SolutionArea" → "Solution Area"
 *       "System.AreaPath" → "Area Path"
 *
 * @param {string} refName - ADO field reference name
 * @returns {string} Human-readable name
 */
export function humanizeFieldName(refName) {
  if (!refName) return '';
  // Take the part after the last dot
  const name = refName.includes('.') ? refName.split('.').pop() : refName;
  // Insert spaces before capital letters
  return name.replace(/([a-z])([A-Z])/g, '$1 $2');
}


/**
 * Sort an array of objects by a key, handling undefined values.
 *
 * @param {Array} arr - Array to sort (mutated)
 * @param {string} key - Property key to sort by
 * @param {'asc'|'desc'} [dir='asc'] - Sort direction
 * @returns {Array} Sorted array (same reference)
 */
export function sortBy(arr, key, dir = 'asc') {
  return arr.sort((a, b) => {
    const va = a[key] ?? '';
    const vb = b[key] ?? '';
    if (va < vb) return dir === 'asc' ? -1 : 1;
    if (va > vb) return dir === 'asc' ? 1 : -1;
    return 0;
  });
}


/**
 * Convert a trigger expression object into a readable DSL string.
 * Used by the "View Code" toggle.
 *
 * @param {Object|string} expr - Expression (and/or/not/string)
 * @param {Map<string,string>} [nameMap] - Optional ID→name lookup
 * @param {number} [indent=0] - Current indentation level
 * @returns {string} DSL representation
 */
export function expressionToDsl(expr, nameMap = new Map(), indent = 0) {
  const pad = '  '.repeat(indent);

  if (typeof expr === 'string') {
    // Leaf: rule reference
    const name = nameMap.get(expr) || expr;
    return `${pad}${name}`;
  }

  if (expr.not) {
    const inner = expressionToDsl(expr.not, nameMap, 0);
    return `${pad}NOT ${inner.trim()}`;
  }

  const operator = expr.and ? 'AND' : expr.or ? 'OR' : '???';
  const children = expr.and || expr.or || [];

  if (children.length === 0) return `${pad}${operator} (empty)`;

  const childLines = children.map(
    (child) => expressionToDsl(child, nameMap, indent + 1)
  );

  return `${pad}${operator}\n${childLines.join('\n')}`;
}
