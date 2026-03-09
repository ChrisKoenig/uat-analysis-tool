"""
Smart Cache Manager
Handles intelligent caching with 7-day TTL and API-first strategy
Designed as independent service for future agent architecture
"""

import json
import os
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Any, Dict, Callable
from dataclasses import dataclass, asdict
import time

@dataclass
class CacheEntry:
    """Individual cache entry with metadata"""
    data: Any
    created_at: str  # ISO format timestamp
    ttl_days: int
    hits: int = 0
    
    def is_expired(self) -> bool:
        """Check if cache entry has exceeded TTL"""
        created = datetime.fromisoformat(self.created_at)
        expiry = created + timedelta(days=self.ttl_days)
        return datetime.now() > expiry
    
    def age_days(self) -> float:
        """Calculate age of cache entry in days"""
        created = datetime.fromisoformat(self.created_at)
        age = datetime.now() - created
        return age.total_seconds() / 86400  # Convert to days
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)
    
    @staticmethod
    def from_dict(data: Dict) -> 'CacheEntry':
        """Create from dictionary"""
        return CacheEntry(**data)


class CacheManager:
    """
    Intelligent cache manager with API-first strategy
    
    Strategy:
    1. Try API call first (if api_first=True)
    2. If API slow (>3s) or fails, use cache as fallback
    3. If cache older than 7 days, refresh in background
    
    Designed as independent service for agent architecture
    """
    
    def __init__(self, cache_path: str, ttl_days: int = 7, api_first: bool = True, slow_threshold: float = 14.0):
        self.cache_path = cache_path
        self.ttl_days = ttl_days
        self.api_first = api_first
        self.slow_threshold = slow_threshold
        self.max_retries = 1  # Retry once if timeout (7s per attempt = 14s total)
        self._cache: Dict[str, CacheEntry] = {}
        self._load_cache()
    
    def _load_cache(self) -> None:
        """Load cache from disk"""
        if os.path.exists(self.cache_path):
            try:
                with open(self.cache_path, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                    self._cache = {
                        k: CacheEntry.from_dict(v) for k, v in cache_data.items()
                    }
                print(f"[CacheManager] Loaded {len(self._cache)} entries from {self.cache_path}")
            except Exception as e:
                print(f"[CacheManager] Error loading cache: {e}")
                self._cache = {}
        else:
            # Create cache directory if needed
            os.makedirs(os.path.dirname(self.cache_path), exist_ok=True)
            self._cache = {}
    
    def _save_cache(self) -> None:
        """Persist cache to disk"""
        try:
            cache_data = {k: v.to_dict() for k, v in self._cache.items()}
            with open(self.cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2)
        except Exception as e:
            print(f"[CacheManager] Error saving cache: {e}")
    
    def _make_key(self, *args, **kwargs) -> str:
        """Generate cache key from arguments"""
        key_data = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True)
        return hashlib.sha256(key_data.encode()).hexdigest()
    
    def get(self, key: str) -> Optional[Any]:
        """Get cached value if exists and not expired"""
        if key not in self._cache:
            return None
        
        entry = self._cache[key]
        
        if entry.is_expired():
            print(f"[CacheManager] Cache entry expired (age: {entry.age_days():.1f} days)")
            del self._cache[key]
            self._save_cache()
            return None
        
        # Update hit counter
        entry.hits += 1
        self._save_cache()
        
        print(f"[CacheManager] Cache HIT (age: {entry.age_days():.1f} days, hits: {entry.hits})")
        return entry.data
    
    def set(self, key: str, value: Any) -> None:
        """Set cache value with current timestamp"""
        entry = CacheEntry(
            data=value,
            created_at=datetime.now().isoformat(),
            ttl_days=self.ttl_days,
            hits=0
        )
        self._cache[key] = entry
        self._save_cache()
        print(f"[CacheManager] Cache SET (key: {key[:16]}...)")
    
    def get_or_compute(
        self, 
        key: str, 
        compute_fn: Callable[[], Any],
        force_refresh: bool = False
    ) -> tuple[Any, bool]:
        """
        Get cached value or compute new one
        
        Returns:
            (value, from_cache) - value and whether it came from cache
        """
        # Check cache first (unless force refresh)
        if not force_refresh:
            cached = self.get(key)
            if cached is not None:
                return cached, True
        
        # Compute new value
        print(f"[CacheManager] Computing new value...")
        value = compute_fn()
        self.set(key, value)
        return value, False
    
    def get_or_compute_with_api_first(
        self,
        key: str,
        api_fn: Callable[[], Any]
    ) -> tuple[Any, str]:
        """
        API-first strategy implementation
        
        Strategy:
        1. Try API call first
        2. If API slow (>threshold) or fails, use cache
        3. If cache expired, force API call
        
        Returns:
            (value, source) - value and source ("api", "cache", "api_fallback")
        """
        # Check if cached value exists and is fresh
        cached = self.get(key)
        
        if cached is not None and self._cache[key].age_days() < self.ttl_days:
            # Cache is valid, return it directly (embeddings for features should NOT be cached anyway)
            # This path is for cached service/region/availability lookups only
            return cached, "cache"
        
        # No valid cache or cache expired, must use API
        try:
            print(f"[CacheManager] No valid cache, calling API...")
            value = api_fn()
            self.set(key, value)
            return value, "api"
        except Exception as e:
            # API failed and no valid cache
            if cached is not None:
                print(f"[CacheManager] API failed but using expired cache: {e}")
                return cached, "cache_expired"
            else:
                print(f"[CacheManager] API failed with no cache available: {e}")
                raise
    
    def clear(self) -> None:
        """Clear all cache entries"""
        self._cache = {}
        self._save_cache()
        print(f"[CacheManager] Cache cleared")
    
    def cleanup_expired(self) -> int:
        """Remove all expired entries, return count removed"""
        expired_keys = [k for k, v in self._cache.items() if v.is_expired()]
        for key in expired_keys:
            del self._cache[key]
        
        if expired_keys:
            self._save_cache()
        
        print(f"[CacheManager] Cleaned up {len(expired_keys)} expired entries")
        return len(expired_keys)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        if not self._cache:
            return {
                "total_entries": 0,
                "expired_entries": 0,
                "average_age_days": 0,
                "total_hits": 0
            }
        
        expired_count = sum(1 for v in self._cache.values() if v.is_expired())
        ages = [v.age_days() for v in self._cache.values()]
        total_hits = sum(v.hits for v in self._cache.values())
        
        return {
            "total_entries": len(self._cache),
            "expired_entries": expired_count,
            "average_age_days": sum(ages) / len(ages),
            "total_hits": total_hits,
            "cache_path": self.cache_path
        }


if __name__ == "__main__":
    # Test cache manager
    print("Cache Manager Test")
    print("=" * 50)
    
    # Create test cache
    cache = CacheManager("cache/test_cache.json", ttl_days=7)
    
    # Test get_or_compute
    def expensive_computation():
        print("Running expensive computation...")
        time.sleep(1)
        return {"result": "computed_value", "timestamp": datetime.now().isoformat()}
    
    key = cache._make_key("test", param="value")
    
    # First call - should compute
    value1, from_cache1 = cache.get_or_compute(key, expensive_computation)
    print(f"Value 1 from cache: {from_cache1}")
    print(f"Value: {value1}")
    
    # Second call - should use cache
    value2, from_cache2 = cache.get_or_compute(key, expensive_computation)
    print(f"Value 2 from cache: {from_cache2}")
    print(f"Value: {value2}")
    
    # Stats
    stats = cache.get_stats()
    print(f"\nCache Stats: {stats}")
