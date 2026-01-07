import sqlite3
import json
from typing import Optional, Dict, List, Any

# VERBOSITY LEVELS: 0 = NONE, 1 = INFO (Entry/Exit), 2 = DEBUG (SQL/Data)
LOG_NONE  = 0
LOG_INFO  = 1 
LOG_DEBUG = 2 

class DBManager:
    def __init__(self, db_path, verbosity=2):
        self.db_path = db_path
        self.verbosity = verbosity
        self._initialize_tables()

    def _log(self, level, message):
        if self.verbosity >= level:
            prefix = "[DB INFO]" if level == LOG_INFO else "[DB DEBUG]"
            print(f"{prefix} {message}")

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.row_factory = sqlite3.Row
        return conn

    def _initialize_tables(self):
        self._log(LOG_INFO, "ENTER: _initialize_tables")
        query = """
        CREATE TABLE IF NOT EXISTS registry (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            parent_id INTEGER,
            type TEXT NOT NULL,
            name TEXT NOT NULL,
            properties TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(parent_id) REFERENCES registry(id) ON DELETE CASCADE
        ) STRICT;
        """
        with self.get_connection() as conn:
            conn.execute(query)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_parent ON registry(parent_id);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_type ON registry(type);")
            conn.commit()
        self._log(LOG_INFO, "EXIT: _initialize_tables")

    def create_node(self, type, name, parent_id=None, properties=None) -> int:
        self._log(LOG_INFO, f"ENTER: create_node (Type: {type})")
        self._log(LOG_DEBUG, f"ENTER: create_node (Type: {properties})")
        prop_json = json.dumps(properties if properties else {})
        sql = "INSERT INTO registry (parent_id, type, name, properties) VALUES (?, ?, ?, ?)"
        with self.get_connection() as conn:
            cursor = conn.execute(sql, (parent_id, type, name, prop_json))
            conn.commit()
            nid = cursor.lastrowid
            self._log(LOG_INFO, f"EXIT: create_node (New ID: {nid})")
            return nid
        
    def get_node(self, node_id: int) -> Optional[Dict]:
        # SILENCED: Log only on DEBUG level to prevent draw-loop spam
        #if self.verbosity >= LOG_DEBUG: print(f"[DB DEBUG] get_node (ID: {node_id})")
        sql = "SELECT * FROM registry WHERE id = ?"
        with self.get_connection() as conn:
            row = conn.execute(sql, (node_id,)).fetchone()
            if not row: return None
            data = dict(row)
            data['properties'] = json.loads(data['properties'])
            return data
    
    def get_node_by_coords(self, campaign_id, parent_id, x, y):
        """Finds a node by checking grid coordinates in its properties."""
        self._log(LOG_INFO, f"ENTER: get_node_by_coords (Target: {x}, {y})")
        
        search_parent = parent_id if parent_id is not None else campaign_id
        candidates = self.get_children(search_parent)
        
        for node in candidates:
            # Match against the new 'properties' column name
            m = node.get('properties', {})
            if m.get('grid_x') == x and m.get('grid_y') == y:
                self._log(LOG_INFO, f"EXIT: get_node_by_coords (Found ID: {node['id']})")
                return node
                
        self._log(LOG_INFO, "EXIT: get_node_by_coords (Not Found)")
        return None

    def find_node(self, type: str) -> Optional[Dict]:
        self._log(LOG_INFO, f"ENTER: find_node (Type: {type})")
        sql = "SELECT id FROM registry WHERE type = ? LIMIT 1"
        with self.get_connection() as conn:
            row = conn.execute(sql, (type,)).fetchone()
            if row:
                res = self.get_node(row['id'])
                self._log(LOG_INFO, f"EXIT: find_node (Found ID: {row['id']})")
                return res
            self._log(LOG_INFO, "EXIT: find_node (Not Found)")
            return None

    def update_node(self, node_id: int, name: str = None, properties: Dict = None):
        self._log(LOG_INFO, f"ENTER: update_node (ID: {node_id})")
        current = self.get_node(node_id)
        
        if not current: 
            return None # Return NULL on failure

        new_name = name if name is not None else current['name']
        
        if properties:
            for k, v in properties.items():
                if k in current['properties']:
                    target_type = type(current['properties'][k])
                    try:
                        if target_type in [int, float] and isinstance(v, str):
                            current['properties'][k] = target_type(v)
                        else:
                            current['properties'][k] = v
                    except (ValueError, TypeError):
                        current['properties'][k] = v
                else:
                    current['properties'][k] = v

        sql = "UPDATE registry SET name = ?, properties = ? WHERE id = ?"
        params = (new_name, json.dumps(current['properties']), node_id)
        
        try:
            with self.get_connection() as conn:
                conn.execute(sql, params)
                conn.commit()
            self._log(LOG_INFO, "EXIT: update_node")
            return node_id # Return the ID on success
        except:
            return None # Return NULL on SQL failure

    def delete_node(self, node_id: int):
        self._log(LOG_INFO, f"ENTER: delete_node (ID: {node_id})")
        with self.get_connection() as conn:
            conn.execute("DELETE FROM registry WHERE id = ?", (node_id,))
            conn.commit()
        self._log(LOG_INFO, "EXIT: delete_node")

    def get_children(self, parent_id: Optional[int], type_filter: str = None) -> List[Dict]:
        #if self.verbosity >= LOG_DEBUG: print(f"[DB DEBUG] get_children (Parent: {parent_id})")
        sql = "SELECT id FROM registry WHERE " + ("parent_id IS NULL" if parent_id is None else "parent_id = ?")
        params = [parent_id] if parent_id is not None else []
        if type_filter:
            sql += " AND type = ?"
            params.append(type_filter)
        with self.get_connection() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
            return [self.get_node(r['id']) for r in rows]
        
    def get_parent(self, node_id: int) -> Optional[Dict]:
        """Returns the parent node of the given node."""
        self._log(LOG_INFO, f"ENTER: get_parent (Child ID: {node_id})")
        node = self.get_node(node_id)
        if not node or node['parent_id'] is None:
            self._log(LOG_INFO, "EXIT: get_parent (No parent found)")
            return None
        
        parent_node = self.get_node(node['parent_id'])
        if parent_node:
            self._log(LOG_INFO, f"EXIT: get_parent (Found Parent ID: {node['parent_id']})")
        else:
            self._log(LOG_INFO, "EXIT: get_parent (Parent ID link broken)")
        return parent_node
