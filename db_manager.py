# db_manager.py
"""
Database management system with separate cache and local calendar storage
"""

import sqlite3
import json
import datetime
import logging
from contextlib import contextmanager
from config import DB_FILE, MAX_CACHE_SIZE

logger = logging.getLogger(__name__)

class DatabaseManager:
    """Manages separate cache and local calendar databases with automatic cleanup"""
    
    def __init__(self):
        self.db_file = DB_FILE
        self.cache_db_file = DB_FILE.replace('.db', '_cache.db')
        self._init_databases()
    
    def _init_databases(self):
        """Initialize both cache and local calendar databases"""
        # Initialize main database for local calendar data
        with self.get_local_connection() as conn:
            cursor = conn.cursor()
            
            # Local calendar events table (persistent)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS local_events (
                    id TEXT PRIMARY KEY,
                    start_date TEXT NOT NULL,
                    end_date TEXT NOT NULL,
                    rrule TEXT,
                    event_json TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Event exceptions for recurring events
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS event_exceptions (
                    original_event_id TEXT NOT NULL,
                    exception_date TEXT NOT NULL,
                    PRIMARY KEY (original_event_id, exception_date)
                )
            """)
            
            # Completed events tracking
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS completed_events (
                    event_id TEXT PRIMARY KEY,
                    completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.commit()
        
        # Initialize cache database for temporary data
        with self.get_cache_connection() as conn:
            cursor = conn.cursor()
            
            # Event cache by month (temporary, cleaned up regularly)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS event_cache (
                    year INTEGER NOT NULL,
                    month INTEGER NOT NULL,
                    events_json TEXT NOT NULL,
                    cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (year, month)
                )
            """)
            
            conn.commit()
    
    @contextmanager
    def get_local_connection(self):
        """Get connection to local calendar database"""
        conn = sqlite3.connect(self.db_file)
        try:
            yield conn
        finally:
            conn.close()
    
    @contextmanager
    def get_cache_connection(self):
        """Get connection to cache database"""
        conn = sqlite3.connect(self.cache_db_file)
        try:
            yield conn
        finally:
            conn.close()
    
    def migrate_existing_data(self):
        """Migrate existing calendar.db data to separated structure"""
        logger.info("Starting database migration...")
        
        try:
            # Check if migration is needed
            with sqlite3.connect(self.db_file) as old_conn:
                cursor = old_conn.cursor()
                
                # Check if old structure exists
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cursor.fetchall()]
                
                if 'events' in tables and 'event_cache' in tables:
                    logger.info("Found old database structure, migrating...")
                    
                    # Migrate local events
                    cursor.execute("SELECT id, start_date, end_date, rrule, event_json FROM events")
                    local_events = cursor.fetchall()
                    
                    # Migrate event exceptions
                    if 'event_exceptions' in tables:
                        cursor.execute("SELECT original_event_id, exception_date FROM event_exceptions")
                        exceptions = cursor.fetchall()
                    else:
                        exceptions = []
                    
                    # Migrate completed events
                    if 'completed_events' in tables:
                        cursor.execute("SELECT event_id FROM completed_events")
                        completed = cursor.fetchall()
                    else:
                        completed = []
                    
                    # Migrate cache data
                    cursor.execute("SELECT year, month, events_json FROM event_cache")
                    cache_data = cursor.fetchall()
                    
                    # Write to new structure
                    with self.get_local_connection() as local_conn:
                        local_cursor = local_conn.cursor()
                        
                        # Insert local events (renamed table)
                        for event in local_events:
                            local_cursor.execute("""
                                INSERT OR REPLACE INTO local_events 
                                (id, start_date, end_date, rrule, event_json, created_at, updated_at)
                                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                            """, event)
                        
                        # Insert exceptions
                        for exc in exceptions:
                            local_cursor.execute("""
                                INSERT OR REPLACE INTO event_exceptions 
                                (original_event_id, exception_date) VALUES (?, ?)
                            """, exc)
                        
                        # Insert completed events
                        for comp in completed:
                            local_cursor.execute("""
                                INSERT OR REPLACE INTO completed_events 
                                (event_id, completed_at) VALUES (?, CURRENT_TIMESTAMP)
                            """, comp)
                        
                        local_conn.commit()
                    
                    # Write cache data to separate database
                    with self.get_cache_connection() as cache_conn:
                        cache_cursor = cache_conn.cursor()
                        for cache_entry in cache_data:
                            cache_cursor.execute("""
                                INSERT OR REPLACE INTO event_cache 
                                (year, month, events_json, cached_at)
                                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                            """, cache_entry)
                        cache_conn.commit()
                    
                    # Drop old tables from main database
                    cursor.execute("DROP TABLE IF EXISTS event_cache")
                    old_conn.commit()
                    
                    logger.info(f"Migration completed: {len(local_events)} local events, {len(cache_data)} cache entries")
                    
                    # Clean up old cache immediately after migration
                    self.cleanup_old_cache()
                
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            raise
    
    def cleanup_old_cache(self, center_year=None, center_month=None):
        """Clean up cache entries to maintain maximum 13 months, but protect today's month"""
        # 오늘 날짜는 항상 보호 (영구 보존)
        today = datetime.date.today()
        today_year, today_month = today.year, today.month
        
        # 캐시 정리 기준: 사용자가 보는 월 (동적) 또는 오늘 날짜 (기본값)
        if center_year is None or center_month is None:
            center_year, center_month = today_year, today_month
        
        # 📦 새로운 정책: 최대 13개월 보존 (캐시 윈도우와 별개)
        # 캐시 윈도우: 3개월 (±1개월) | 최대 보존: 13개월 (±6개월)
        max_keep_radius = 6  # ±6개월 = 총 13개월 보존
        
        # Calculate maximum keep window (13개월 범위)
        keep_months = []
        center_date = datetime.date(center_year, center_month, 1)
        
        for i in range(-max_keep_radius, max_keep_radius + 1):
            # Calculate target month
            target_year = center_year
            target_month = center_month + i
            
            # Handle year overflow/underflow
            while target_month <= 0:
                target_month += 12
                target_year -= 1
            while target_month > 12:
                target_month -= 12
                target_year += 1
                
            keep_months.append((target_year, target_month))
        
        # Get the start and end boundaries for keep window
        keep_months.sort()
        keep_start_year, keep_start_month = keep_months[0]
        keep_end_year, keep_end_month = keep_months[-1]
        
        with self.get_cache_connection() as conn:
            cursor = conn.cursor()
            
            # Count entries before cleanup
            cursor.execute("SELECT COUNT(*) FROM event_cache")
            before_count = cursor.fetchone()[0]
            
            # Show current cache range
            cursor.execute("SELECT year, month FROM event_cache ORDER BY year, month")
            all_cache_entries = cursor.fetchall()
            if all_cache_entries:
                cache_months = [f"{year}-{month:02d}" for year, month in all_cache_entries]
                logger.info(f"Current cache months: {cache_months}")
            
            # Delete cache entries outside the 13-month keep window
            # BUT always protect the current month (even if it's outside the normal window)
            keep_months_set = set(keep_months)
            
            # Get all current cache entries
            cursor.execute("SELECT year, month FROM event_cache")
            all_cache_entries = cursor.fetchall()
            
            # Find entries to delete (outside 13-month keep window but protect today's month)
            entries_to_delete = []
            for year, month in all_cache_entries:
                # 보호 조건: 1) 13개월 보존 범위 안에 있거나 2) 오늘 날짜가 포함된 달
                is_in_keep_window = (year, month) in keep_months_set
                is_today_month = (year, month) == (today_year, today_month)
                
                if not is_in_keep_window and not is_today_month:
                    entries_to_delete.append((year, month))
            
            # Delete entries outside the window
            deleted_count = 0
            for year, month in entries_to_delete:
                cursor.execute("DELETE FROM event_cache WHERE year = ? AND month = ?", (year, month))
                deleted_count += cursor.rowcount
            
            conn.commit()
            
            # Count entries after cleanup
            cursor.execute("SELECT COUNT(*) FROM event_cache")
            after_count = cursor.fetchone()[0]
            
            keep_range = f"[{keep_start_year}-{keep_start_month:02d} to {keep_end_year}-{keep_end_month:02d}]"
            logger.info(f"Cache cleanup: maximum keep ±6 months = 13 months total {keep_range}")
            logger.info(f"Cache center: {center_year}-{center_month:02d}, Today protected: {today_year}-{today_month:02d}")
            logger.info(f"Cache cleanup result: {before_count} → {after_count} entries ({deleted_count} deleted)")
            
            if entries_to_delete:
                deleted_months = [f"{y}-{m:02d}" for y, m in entries_to_delete]
                logger.info(f"Deleted cache months: {', '.join(deleted_months)}")
            
            return deleted_count
    
    def clear_all_cache(self):
        """Clear all cache data (used during logout)"""
        with self.get_cache_connection() as conn:
            cursor = conn.cursor()
            
            # Count entries before clearing
            cursor.execute("SELECT COUNT(*) FROM event_cache")
            before_count = cursor.fetchone()[0]
            
            # Delete all cache entries
            cursor.execute("DELETE FROM event_cache")
            deleted_count = cursor.rowcount
            conn.commit()
            
            logger.info(f"Cache cleared completely: removed {deleted_count} entries (logout cleanup)")
            return deleted_count
    
    def get_cache_stats(self):
        """Get cache database statistics"""
        stats = {}
        
        try:
            with self.get_cache_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("SELECT COUNT(*) FROM event_cache")
                stats['cache_entries'] = cursor.fetchone()[0]
                
                cursor.execute("SELECT MIN(year), MIN(month), MAX(year), MAX(month) FROM event_cache")
                min_year, min_month, max_year, max_month = cursor.fetchone()
                
                if min_year:
                    stats['cache_range'] = {
                        'start': f"{min_year}-{min_month:02d}",
                        'end': f"{max_year}-{max_month:02d}"
                    }
                else:
                    stats['cache_range'] = None
                    
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            stats['error'] = str(e)
        
        try:
            with self.get_local_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("SELECT COUNT(*) FROM local_events")
                stats['local_events'] = cursor.fetchone()[0]
                
        except Exception as e:
            logger.error(f"Error getting local stats: {e}")
            stats['local_error'] = str(e)
        
        return stats

# Singleton instance
_db_manager = None

def get_db_manager():
    """Get singleton database manager instance"""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
    return _db_manager