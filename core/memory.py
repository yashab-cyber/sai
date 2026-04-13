import sqlite3
import json
import os
from typing import List, Dict, Any, Optional

class MemoryManager:
    """
    Persistence layer using SQLite.
    Stores task history, codebase awareness, and self-modification logs.
    """
    
    def __init__(self, db_path: str = "logs/sai_memory.db"):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # Table for tasks and decisions
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    task_id TEXT,
                    query TEXT,
                    plan TEXT,
                    action TEXT,
                    result TEXT,
                    status TEXT
                )
            """)
            # Table for codebase map (functions, classes, dependencies)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS codebase_map (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_path TEXT,
                    type TEXT, -- 'function' or 'class'
                    name TEXT,
                    dependencies TEXT,
                    last_scanned DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # Table for self-improvements
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS improvements (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    module_name TEXT,
                    original_version TEXT,
                    improved_version TEXT,
                    metrics TEXT,
                    core_evolution BOOLEAN DEFAULT 0,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def save_memory(self, table: str, data: Dict[str, Any]):
        """Saves a record to the specified table."""
        columns = ", ".join(data.keys())
        placeholders = ", ".join(["?"] * len(data))
        values = tuple(data.values())
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(f"INSERT INTO {table} ({columns}) VALUES ({placeholders})", values)
            conn.commit()

    def recall_memory(self, table: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Recalls the most recent entries from a table."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(f"SELECT * FROM {table} ORDER BY id DESC LIMIT ?", (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def search_memory(self, table: str, column: str, query: str) -> List[Dict[str, Any]]:
        """Searches memory for a specific term."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(f"SELECT * FROM {table} WHERE {column} LIKE ?", (f"%{query}%",))
            return [dict(row) for row in cursor.fetchall()]
            
    def clear_codebase_map(self):
        """Clears the codebase map before a re-scan."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM codebase_map")
            conn.commit()
