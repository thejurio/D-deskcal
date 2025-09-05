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
    
    def cleanup_old_cache(self):
        """Clean up cache entries outside the sliding window, but protect current month"""
        current_date = datetime.date.today()
        current_year, current_month = current_date.year, current_date.month
        
        # Use the same sliding window calculation as the actual caching logic
        # MAX_CACHE_SIZE = 13 months (current month ±6 months)
        radius = 6  # ±6 months around current month
        
        # Calculate sliding window using the same logic as _calculate_sliding_window
        window_months = []
        center_date = datetime.date(current_year, current_month, 1)
        
        for i in range(-radius, radius + 1):
            # Calculate target month
            target_year = current_year
            target_month = current_month + i
            
            # Handle year overflow/underflow
            while target_month <= 0:
                target_month += 12
                target_year -= 1
            while target_month > 12:
                target_month -= 12
                target_year += 1
                
            window_months.append((target_year, target_month))
        
        # Get the start and end boundaries
        window_months.sort()
        start_year, start_month = window_months[0]
        end_year, end_month = window_months[-1]
        
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
            
            # Delete cache entries outside the sliding window
            # BUT always protect the current month (even if it's outside the normal window)
            window_months_set = set(window_months)
            
            # Get all current cache entries
            cursor.execute("SELECT year, month FROM event_cache")
            all_cache_entries = cursor.fetchall()
            
            # Find entries to delete (outside window but protect current month)
            entries_to_delete = []
            for year, month in all_cache_entries:
                if (year, month) not in window_months_set and (year, month) != (current_year, current_month):
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
            
            window_range = f"[{start_year}-{start_month:02d} to {end_year}-{end_month:02d}]"
            logger.info(f"Cache cleanup: sliding window ±6 months = 13 months total {window_range}")
            logger.info(f"Current month protected: {current_year}-{current_month:02d}")
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