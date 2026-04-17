import sqlite3
import json
import os
from typing import List, Dict, Any, Optional

class MemoryManager:
    """
    Persistence layer using SQLite.
    Stores task history, codebase awareness, and self-modification logs.
    """

    # Whitelisted table names to prevent SQL injection via dynamic table references
    VALID_TABLES = {
        "history", "codebase_map", "improvements",
        "actions_history", "user_preferences", "learned_patterns",
        "semantic_memory",
    }

    # Whitelisted column names for search queries
    VALID_COLUMNS = {
        "task_id", "query", "plan", "action", "result", "status",
        "file_path", "type", "name", "dependencies",
        "module_name", "device_id", "key", "value",
        "task_signature", "action_sequence",
    }

    def _validate_identifier(self, name: str, valid_set: set, kind: str = "identifier") -> str:
        """Validates that a dynamic SQL identifier is in the whitelist."""
        if name not in valid_set:
            raise ValueError(f"Invalid SQL {kind}: '{name}'. Allowed: {valid_set}")
        return name

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

            # Production action history table for device/network execution traces
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS actions_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    device_id TEXT,
                    action TEXT,
                    request_json TEXT,
                    response_json TEXT,
                    status TEXT,
                    latency_ms INTEGER
                )
            """)

            # User preference store for runtime behavior toggles
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_preferences (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Learned patterns for future plan shortcuts
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS learned_patterns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_signature TEXT,
                    action_sequence TEXT,
                    success_count INTEGER DEFAULT 0,
                    failure_count INTEGER DEFAULT 0,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Vector Semantic Database
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS semantic_memory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT,
                    metadata TEXT,
                    embedding BLOB,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def save_memory(self, table: str, data: Dict[str, Any]):
        """Saves a record to the specified table."""
        table = self._validate_identifier(table, self.VALID_TABLES, "table")
        columns = ", ".join(data.keys())
        placeholders = ", ".join(["?"] * len(data))
        values = tuple(data.values())
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(f"INSERT INTO {table} ({columns}) VALUES ({placeholders})", values)
            conn.commit()

    def recall_memory(self, table: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Recalls the most recent entries from a table."""
        table = self._validate_identifier(table, self.VALID_TABLES, "table")
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(f"SELECT * FROM {table} ORDER BY id DESC LIMIT ?", (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def search_memory(self, table: str, column: str, query: str) -> List[Dict[str, Any]]:
        """Searches memory for a specific term."""
        table = self._validate_identifier(table, self.VALID_TABLES, "table")
        column = self._validate_identifier(column, self.VALID_COLUMNS, "column")
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

    def log_action(self, device_id: str, action: str, request_obj: Dict[str, Any], response_obj: Dict[str, Any], latency_ms: int = 0):
        """Stores a normalized action trace for feedback-loop learning and audit."""
        status = response_obj.get("status", "unknown") if isinstance(response_obj, dict) else "unknown"
        payload = {
            "device_id": device_id,
            "action": action,
            "request_json": json.dumps(request_obj, ensure_ascii=False),
            "response_json": json.dumps(response_obj, ensure_ascii=False),
            "status": status,
            "latency_ms": int(latency_ms or 0)
        }
        self.save_memory("actions_history", payload)

    def set_preference(self, key: str, value: Any):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO user_preferences (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(key) DO UPDATE SET
                  value=excluded.value,
                  updated_at=CURRENT_TIMESTAMP
                """,
                (key, json.dumps(value, ensure_ascii=False))
            )
            conn.commit()

    def get_preference(self, key: str, default: Any = None) -> Any:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM user_preferences WHERE key = ?", (key,))
            row = cursor.fetchone()
            if not row:
                return default
            try:
                return json.loads(row[0])
            except Exception:
                return row[0]

    def update_learned_pattern(self, task_signature: str, action_sequence: Any, success: bool):
        action_seq_json = json.dumps(action_sequence, ensure_ascii=False)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, success_count, failure_count FROM learned_patterns WHERE task_signature = ?",
                (task_signature,)
            )
            row = cursor.fetchone()
            if row:
                pattern_id, success_count, failure_count = row
                if success:
                    success_count += 1
                else:
                    failure_count += 1
                cursor.execute(
                    """
                    UPDATE learned_patterns
                    SET action_sequence = ?, success_count = ?, failure_count = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (action_seq_json, success_count, failure_count, pattern_id)
                )
            else:
                cursor.execute(
                    """
                    INSERT INTO learned_patterns (task_signature, action_sequence, success_count, failure_count)
                    VALUES (?, ?, ?, ?)
                    """,
                    (task_signature, action_seq_json, 1 if success else 0, 0 if success else 1)
                )
            conn.commit()

    def get_learned_pattern(self, task_signature: str) -> Optional[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT task_signature, action_sequence, success_count, failure_count, updated_at
                FROM learned_patterns
                WHERE task_signature = ?
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                (task_signature,)
            )
            row = cursor.fetchone()
            if not row:
                return None

            item = dict(row)
            try:
                item["action_sequence"] = json.loads(item.get("action_sequence") or "[]")
            except Exception:
                item["action_sequence"] = []
            return item

    def get_replay_candidate(self, task_signature: str, min_success: int = 2) -> Optional[Dict[str, Any]]:
        """Returns a learned pattern only when reliability is high enough to shortcut planning."""
        pattern = self.get_learned_pattern(task_signature)
        if not pattern:
            return None

        success_count = int(pattern.get("success_count") or 0)
        failure_count = int(pattern.get("failure_count") or 0)
        if success_count < min_success:
            return None
        if success_count <= failure_count:
            return None
        if not pattern.get("action_sequence"):
            return None
        return pattern

    # ── VECTORS (Native RAG) ──
    def save_semantic_memory(self, content: str, embedding: List[float], metadata: Optional[Dict[str, Any]] = None):
        """Serializes and saves a vector to SQLite."""
        import numpy as np
        vector = np.array(embedding, dtype=np.float32)
        blob = vector.tobytes()
        meta_json = json.dumps(metadata or {}, ensure_ascii=False)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO semantic_memory (content, metadata, embedding) VALUES (?, ?, ?)",
                (content, meta_json, blob)
            )
            conn.commit()

    def search_semantic_memory(self, query_embedding: List[float], limit: int = 5, threshold: float = 0.5) -> List[Dict[str, Any]]:
        """Calculates fast dot-product cosine similarity over all semantic records."""
        import numpy as np
        
        # Query vector preparation
        q_vec = np.array(query_embedding, dtype=np.float32)
        q_norm = np.linalg.norm(q_vec)
        if q_norm == 0:
            return []
            
        results = []
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT id, content, metadata, embedding, timestamp FROM semantic_memory")
            
            for row in cursor.fetchall():
                try:
                    # Deserialize blob back to numpy array
                    mem_vec = np.frombuffer(row["embedding"], dtype=np.float32)
                    mem_norm = np.linalg.norm(mem_vec)
                    
                    if mem_norm == 0:
                        continue
                        
                    # Cosine Similarity
                    similarity = np.dot(q_vec, mem_vec) / (q_norm * mem_norm)
                    
                    if similarity >= threshold:
                        results.append({
                            "id": row["id"],
                            "content": row["content"],
                            "metadata": json.loads(row["metadata"]),
                            "timestamp": row["timestamp"],
                            "similarity": float(similarity)
                        })
                except Exception as e:
                    # Skip corrupted vector data
                    pass
                    
        # Sort aggressively by similarity score descending
        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:limit]
