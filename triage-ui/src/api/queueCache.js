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

let _cache = null;

/**
 * Get cached queue data if it exists and is still fresh.
 * @returns {{ items, queryName, totalAvailable, analysisMap, timestamp } | null}
 */
export function getCachedQueue() {
  if (!_cache) return null;
  const age = Date.now() - _cache.timestamp;
  if (age > CACHE_TTL_MS) {
    _cache = null;
    return null;
  }
  return _cache;
}

/**
 * Store queue data in the cache.
 */
export function setCachedQueue({ items, queryName, totalAvailable, analysisMap }) {
  _cache = {
    items,
    queryName,
    totalAvailable,
    analysisMap: analysisMap || {},
    timestamp: Date.now(),
  };
}

/**
 * Invalidate the cache (called on explicit Refresh or after mutations).
 */
export function clearQueueCache() {
  _cache = null;
}
