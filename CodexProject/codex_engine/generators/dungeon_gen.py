import pygame
import random
import math
import heapq
import json
import os
from codex_engine.config import DATA_DIR

class DungeonGenerator:
    def __init__(self, db_manager):
        self.db = db_manager
        self.bp_path = DATA_DIR / "blueprints" / "dungeons"

    def _load_complex(self, bp_id):
        path = self.bp_path / "complexes" / f"{bp_id}.json"
        if path.exists():
            with open(path, 'r') as f: return json.load(f)
        return None

    def _load_definition(self, bp_id):
        path = self.bp_path / "definitions" / f"{bp_id}.json"
        if path.exists():
            with open(path, 'r') as f: return json.load(f)
        return None

    def generate_dungeon_complex(self, parent_node, marker, campaign_id, levels=None):

        print (f" ** ** ** ** ** marker {marker}")

        print (f" ** ** ** ** ** marker.id {marker['id']}")
        bp_id = marker.get('blueprint_id')
        
        if not bp_id:
            # Fallback for generic "Skull" markers
            return self._generate_fallback(parent_node, marker, campaign_id)

        complex_bp = self._load_complex(bp_id)
        # Handle case where a user selects a Definition directly instead of a Complex
        if not complex_bp:
            def_bp = self._load_definition(bp_id)
            if def_bp:
                complex_bp = {"name": def_bp['name'], "levels": [{"depth": 1, "blueprint_id": bp_id}]}
            else:
                return self._generate_fallback(parent_node, marker, campaign_id)

        print(f"--- Generating Dungeon: {complex_bp['name']} ---")

        # PARENT IS THE LOCAL MAP DIRECTLY (No intermediate container)
        levels_parent_id = parent_node['id']
        
        previous_level_node_id = levels_parent_id
        first_level_id = None
        
        for level_config in complex_bp['levels']:
            depth = level_config['depth']
            def_id = level_config['blueprint_id']
            
            level_def = self._load_definition(def_id)
            if not level_def: continue

            level_name = level_config.get('name_override', f"Level {depth}")
            
            new_props = {
                "world_x": int(marker['world_x']),
                "world_y": int(marker['world_y']),
            }
            # Create Node

            node_id = self.db.create_node(
                type="dungeon_level",
                name=level_name,
                parent_id=marker['id'],
                properties=new_props
            )

            '''
            node_id = self.db.create_node(
                campaign_id, "dungeon_level", levels_parent_id,
                int(marker['world_x']), int(marker['world_y']), level_name
            )
            ''' 

            if depth == 1: first_level_id = node_id

            # Generate Geometry
            gen_config = level_def.get('generator_config', {})
            grid, rooms = self._generate_layout(gen_config)
            
            # --- METADATA & GEOMETRY STORAGE ---

                        # Prepare properties
            new_props = {
                "render_style": level_config.get('theme_override', 'hand_drawn'),
                "overview": complex_bp.get('description', 'A dark and dangerous place.'),
                "source_marker_id": marker['id'], # CRITICAL: Links siblings together
                "depth": depth,
                "geometry": {
                    "grid": grid, 
                    "width": len(grid[0]), 
                    "height": len(grid),
                    "rooms": [list(r) for r in rooms]
                }
            }
            
            # Create Local Map Node
            self.db.update_node(
                node_id, properties=new_props
            )

            '''
            self.db.update_node_data(node_id, 
                geometry={
                    "grid": grid, 
                    "width": len(grid[0]), 
                    "height": len(grid),
                    "rooms": [list(r) for r in rooms]
                },
                metadata={
                    "render_style": level_config.get('theme_override', 'hand_drawn'),
                    "overview": complex_bp.get('description', 'A dark and dangerous place.'),
                    "source_marker_id": marker['id'], # CRITICAL: Links siblings together
                    "depth": depth
                }
            )
            '''

            # --- Markers (Room Numbers and Navigation) ---
            if rooms:
                # 1. Room Numbers
                for i, r in enumerate(rooms):
                    room_props = {
                        "world_x": r[0] + 0.5,
                        "world_y": r[1] + 0.5,
                        "symbol": "room_number",
                        "description": "An unexplored chamber."
                    }
                    # Room name is the number for display in the tactical view
                    self.db.create_node(type='poi', name=str(i+1), parent_id=node_id, properties=room_props)

                # 2. Stairs Up (Exit to previous level or Map)
                up_room = rooms[0]
                cx, cy = up_room[0] + up_room[2]//2, up_room[1] + up_room[3]//2
                up_props = {
                    "world_x": float(cx),
                    "world_y": float(cy),
                    "symbol": "stairs_up",
                    "portal_to": previous_level_node_id,
                    "description": "Stirs leading up...",
                }
                self.db.create_node(type='poi', name="Stairs Up", parent_id=node_id, properties=up_props)

            # 3. Stairs Down (If more levels exist)
            if depth < len(complex_bp['levels']):
                down_room = rooms[-1]
                dx, dy = down_room[0] + down_room[2]//2, down_room[1] + down_room[3]//2
                down_props = {
                    "world_x": float(dx),
                    "world_y": float(dy),
                    "symbol": "stairs_down",
                    "description": "Leads deeper...",
                }
                self.db.create_node(type='poi', name="Stairs Down", parent_id=node_id, properties=down_props)

            # 4. Link the previous level's "Stairs Down" to this new level
            if depth > 1:
                self._link_down_stairs(previous_level_node_id, node_id)

            previous_level_node_id = node_id

        return first_level_id

    def _link_down_stairs(self, from_node_id, to_node_id):
        potential_markers = self.db.get_children(from_node_id, type_filter='poi')
        for m in potential_markers:
            props = m.get('properties', {})
            if props.get('symbol') == 'stairs_down':
                props['description'] = "Leads deeper..."
                # FIXED: portal_to stored directly in properties
                self.db.update_node(m['id'], properties={'portal_to': to_node_id})
                break

    def _generate_fallback(self, parent_node, marker, campaign_id):
        w, h = 40, 40
        grid = [[0]*w for _ in range(h)]
        for y in range(10, 30):
            for x in range(10, 30): grid[y][x] = 1
        
            new_props = {
                "render_style": "hand_drawn", 
                "source_marker_id": marker['id'],
                "world_x": int(marker['world_x']),
                "world_y": int(marker['world_y']),
                "geometry": {"grid": grid, 
                             "width": w, 
                             "height": h, 
                             "rooms": [[10,10,20,20]]},
            }
            # Create Node

            nid = self.db.create_node(
                type="dungeon_level",
                name="A dark dungeon",
                parent_id=parent_node['id'],
                properties=new_props
            )

        #nid = self.db.create_node(campaign_id, "dungeon_level", parent_node['id'], int(marker['world_x']), int(marker['world_y']), "Unknown Lair")
        #self.db.update_node(nid, 
        #    geometry={"grid": grid, "width": w, "height": h, "rooms": [[10,10,20,20]]},
        #    metadata={"render_style": "hand_drawn", "source_marker_id": marker['id']}
        #)
        #self.db.add_marker(nid, 20, 20, "stairs_up", "Exit", "", metadata={"portal_to": parent_node['id']})
        return nid

    def _generate_layout(self, config):
        width = config.get('width', 60); height = config.get('height', 60)
        min_size = config.get('min_room_size', 6); max_size = config.get('max_room_size', 12)
        room_count = config.get('room_count', 15)
        grid = [[0 for _ in range(width)] for _ in range(height)]
        rooms = []
        for _ in range(100):
            if len(rooms) >= room_count: break
            w = random.randint(min_size, max_size); h = random.randint(min_size, max_size)
            x = random.randint(2, width - w - 2); y = random.randint(2, height - h - 2)
            new_rect = pygame.Rect(x, y, w, h)
            if not any(new_rect.colliderect(pygame.Rect(r).inflate(2,2)) for r in rooms):
                rooms.append([x, y, w, h])
                for ry in range(y, y+h):
                    for rx in range(x, x+w): grid[ry][rx] = 1
        if len(rooms) > 1:
            for i in range(len(rooms)-1):
                r1 = rooms[i]; r2 = rooms[i+1]
                c1 = (r1[0] + r1[2]//2, r1[1] + r1[3]//2); c2 = (r2[0] + r2[2]//2, r2[1] + r2[3]//2)
                self._carve_corridor(grid, c1, c2, width, height)
        return grid, rooms

    def _carve_corridor(self, grid, start, end, max_w, max_h):
        x1, y1 = start; x2, y2 = end
        if random.random() > 0.5:
            self._line(grid, x1, y1, x2, y1, max_w, max_h); self._line(grid, x2, y1, x2, y2, max_w, max_h)
        else:
            self._line(grid, x1, y1, x1, y2, max_w, max_h); self._line(grid, x1, y2, x2, y2, max_w, max_h)

    def _line(self, grid, x1, y1, x2, y2, w, h):
        if x1 == x2:
            for y in range(min(y1, y2), max(y1, y2) + 1):
                if 0 <= x1 < w and 0 <= y < h and grid[y][x1] == 0: grid[y][x1] = 2
        elif y1 == y2:
            for x in range(min(x1, x2), max(x1, x2) + 1):
                if 0 <= x < w and 0 <= y1 < h and grid[y1][x] == 0: grid[y1][x] = 2
