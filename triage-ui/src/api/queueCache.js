/**
 * Queue Data Cache
 * =================
 *
 * Module-level cache for Queue page data so navigating away and back
 * doesn't trigger a full reload from ADO every time.
 *
 * Data is considered fresh for CACHE_TTL_MS (2 minutes).
 * The Refresh button bypasses the cache.
 */

const CACHE_TTL_MS = 2 * 60 * 1000; // 2 minutes

/** Per-team cache keyed by ADO query ID */
const _cacheMap = new Map();

/**
 * Get cached queue data for a specific query/team if it exists and is still fresh.
 * @param {string} key  — typically the ADO query ID (activeQueryId)
 * @returns {{ items, queryName, totalAvailable, analysisMap, timestamp } | null}
 */
export function getCachedQueue(key) {
  if (!key) return null;
  const entry = _cacheMap.get(key);
  if (!entry) return null;
  const age = Date.now() - entry.timestamp;
  if (age > CACHE_TTL_MS) {
    _cacheMap.delete(key);
    return null;
  }
  return entry;
}

/**
 * Store queue data in the per-team cache.
 * @param {string} key  — typically the ADO query ID
 */
export function setCachedQueue(key, { items, queryName, totalAvailable, analysisMap, queryColumns }) {
  _cacheMap.set(key, {
    items,
    queryName,
    totalAvailable,
    analysisMap: analysisMap || {},
    queryColumns: queryColumns || [],
    timestamp: Date.now(),
  });
}

/**
 * Invalidate the cache.
 * @param {string} [key]  — if provided, clear only that team's cache; otherwise clear all.
 */
export function clearQueueCache(key) {
  if (key) {
    _cacheMap.delete(key);
  } else {
    _cacheMap.clear();
  }
}
