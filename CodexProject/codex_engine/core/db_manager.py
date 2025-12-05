import sqlite3
import json
import logging
from typing import Optional, Dict, List, Any
from codex_engine.config import DB_PATH

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("DBManager")

class DBManager:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self._initialize_tables()

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Access columns by name
        return conn

    def _initialize_tables(self):
        """Creates the schema if it doesn't exist."""
        queries = [
            """CREATE TABLE IF NOT EXISTS campaigns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                theme_id TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                game_time_minutes INTEGER DEFAULT 0
            );""",
            
            """CREATE TABLE IF NOT EXISTS nodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                campaign_id INTEGER,
                parent_node_id INTEGER,
                type TEXT NOT NULL, 
                name TEXT,
                grid_x INTEGER,
                grid_y INTEGER,
                geometry_data TEXT, 
                metadata TEXT,
                is_visited BOOLEAN DEFAULT 0,
                FOREIGN KEY(campaign_id) REFERENCES campaigns(id),
                FOREIGN KEY(parent_node_id) REFERENCES nodes(id)
            );""",

            """CREATE TABLE IF NOT EXISTS entities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                node_id INTEGER,
                name TEXT,
                type TEXT,
                stats_block TEXT,
                lore_description TEXT,
                FOREIGN KEY(node_id) REFERENCES nodes(id)
            );""",
            
            # --- NEW TABLE FOR MARKERS ---
            """CREATE TABLE IF NOT EXISTS markers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                node_id INTEGER,
                world_x REAL,
                world_y REAL,
                symbol TEXT,
                title TEXT,
                description TEXT,
                FOREIGN KEY(node_id) REFERENCES nodes(id)
            );"""
        ]

        try:
            with self.get_connection() as conn:
                for q in queries:
                    conn.execute(q)
                conn.commit()
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")

    # --- CAMPAIGN METHODS ---
    def create_campaign(self, name: str, theme_id: str) -> int:
        with self.get_connection() as conn:
            cursor = conn.execute("INSERT INTO campaigns (name, theme_id) VALUES (?, ?)", (name, theme_id))
            conn.commit()
            return cursor.lastrowid

    def get_campaign(self, campaign_id: int) -> dict:
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM campaigns WHERE id = ?", (campaign_id,)).fetchone()
            return dict(row) if row else None
            
    def get_all_campaigns(self) -> List[dict]:
        with self.get_connection() as conn:
            rows = conn.execute("SELECT * FROM campaigns ORDER BY created_at DESC").fetchall()
            return [dict(row) for row in rows]

    # --- NODE METHODS ---
    def create_node(self, campaign_id: int, node_type: str, parent_id: Optional[int], x: int, y: int, name: str = "Unknown") -> int:
        with self.get_connection() as conn:
            cursor = conn.execute(
                """INSERT INTO nodes (campaign_id, parent_node_id, type, grid_x, grid_y, name, geometry_data, metadata) 
                   VALUES (?, ?, ?, ?, ?, ?, '{}', '{}')""",
                (campaign_id, parent_id, node_type, x, y, name)
            )
            conn.commit()
            return cursor.lastrowid

    def get_node_by_coords(self, campaign_id: int, parent_id: Optional[int], x: int, y: int) -> Optional[dict]:
        query = "SELECT * FROM nodes WHERE campaign_id=? AND grid_x=? AND grid_y=?"
        params = [campaign_id, x, y]
        if parent_id is None: query += " AND parent_node_id IS NULL"
        else: query += " AND parent_node_id=?"; params.append(parent_id)

        with self.get_connection() as conn:
            row = conn.execute(query, tuple(params)).fetchone()
            if row:
                data = dict(row)
                data['geometry_data'] = json.loads(data['geometry_data']) if data['geometry_data'] else {}
                data['metadata'] = json.loads(data['metadata']) if data['metadata'] else {}
                return data
            return None

    def update_node_data(self, node_id: int, geometry: dict = None, metadata: dict = None):
        updates = []
        params = []
        if geometry is not None: updates.append("geometry_data = ?"); params.append(json.dumps(geometry))
        if metadata is not None: updates.append("metadata = ?"); params.append(json.dumps(metadata))
        if not updates: return
        params.append(node_id)
        sql = f"UPDATE nodes SET {', '.join(updates)} WHERE id = ?"
        with self.get_connection() as conn: conn.execute(sql, tuple(params)); conn.commit()

    # --- NEW MARKER METHODS ---
    def add_marker(self, node_id, wx, wy, symbol, title, desc=""):
        with self.get_connection() as conn:
            conn.execute(
                "INSERT INTO markers (node_id, world_x, world_y, symbol, title, description) VALUES (?,?,?,?,?,?)",
                (node_id, wx, wy, symbol, title, desc)
            )
            conn.commit()
    
    def update_marker(self, marker_id, wx, wy, symbol, title, desc):
        """Saves changes to an existing marker."""
        with self.get_connection() as conn:
            conn.execute(
                "UPDATE markers SET world_x=?, world_y=?, symbol=?, title=?, description=? WHERE id=?",
                (wx, wy, symbol, title, desc, marker_id)
            )
            conn.commit()

    def get_markers(self, node_id):
        with self.get_connection() as conn:
            rows = conn.execute("SELECT * FROM markers WHERE node_id = ?", (node_id,)).fetchall()
            return [dict(r) for r in rows]
    
    def delete_marker(self, marker_id):
        with self.get_connection() as conn:
            conn.execute("DELETE FROM markers WHERE id = ?", (marker_id,))
            conn.commit()