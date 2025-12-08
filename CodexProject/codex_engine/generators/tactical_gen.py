import pygame
import random
import math
import heapq

# --- SETTINGS FROM mega_dungeon.py ---
WORLD_WIDTH = 150
WORLD_HEIGHT = 150
MAX_ROOMS = 90
MIN_ROOM_SIZE = 4
MAX_ROOM_SIZE = 12
ROOM_PADDING = 3
TURN_PENALTY = 5
ADJACENCY_PENALTY = 20 

class Room:
    def __init__(self, x, y, width, height, id):
        self.id = id
        self.rect = pygame.Rect(x, y, width, height)
        self.center = self.rect.center
    def intersects(self, other_room):
        return self.rect.colliderect(other_room.rect.inflate(ROOM_PADDING * 2, ROOM_PADDING * 2))

class AStarNode:
    def __init__(self, parent=None, position=None, direction=(0,0)):
        self.parent, self.position, self.direction = parent, position, direction
        self.g, self.h, self.f = 0, 0, 0
    def __eq__(self, other): return self.position == other.position
    def __lt__(self, other): return self.f < other.f
    def __hash__(self): return hash(self.position)

class TacticalGenerator:
    def __init__(self, db):
        self.db = db

    def generate_tactical_map(self, parent_node, marker, campaign_id):
        print(f"Generating Tactical Map for: {marker['title']}")
        
        map_type = "building_interior"
        if "skull" in marker['symbol'] or "lair" in marker['symbol'].lower():
            map_type = "dungeon_level"
            grid, rooms = self._generate_dungeon_layout(WORLD_WIDTH, WORLD_HEIGHT)
        else:
            grid, rooms = self._generate_building_layout(30, 30)

        width = len(grid[0])
        height = len(grid)

        meta = {
            "grid_size": 15, 
            "theme": "parchment",
            "overview": f"A level of {marker['title']}",
            "cam_x": rooms[0].center[0] if rooms else width / 2,
            "cam_y": rooms[0].center[1] if rooms else height / 2,
            "zoom": 1.0
        }
        geo = {"width": width, "height": height, "grid": grid, "rooms": [list(r.rect) for r in rooms]}
        
        new_id = self.db.create_node(campaign_id, map_type, parent_node['id'], int(marker['world_x']), int(marker['world_y']), marker['title'])
        self.db.update_node_data(new_id, geometry=geo, metadata=meta)
        
        for room in rooms:
            self.db.add_marker(new_id, room.rect.x + 0.5, room.rect.y + 0.5, 'room_number', f"{room.id + 1}", "Unexplored.")

        return new_id

    def _generate_building_layout(self, w, h):
        grid = [[0 for _ in range(w)] for _ in range(h)]
        padding = 5
        for y in range(padding, h - padding):
            for x in range(padding, w - padding):
                grid[y][x] = 1 
        grid[h - padding - 1][w // 2] = 2 
        room = Room(padding, padding, w - (padding*2), h-(padding*2), 0)
        return grid, [room]

    def _generate_dungeon_layout(self, width, height):
        # EXACT COPY FROM mega_dungeon.py
        grid = [[0 for _ in range(width)] for _ in range(height)]
        rooms = []
        attempts = 15000
        
        for _ in range(attempts):
            if len(rooms) >= MAX_ROOMS: break
            w = random.randint(MIN_ROOM_SIZE, MAX_ROOM_SIZE)
            h = random.randint(MIN_ROOM_SIZE, MAX_ROOM_SIZE)
            x = random.randint(2, width - w - 2)
            y = random.randint(2, height - h - 2)
            new_room = Room(x, y, w, h, len(rooms))
            if not any(new_room.intersects(other) for other in rooms):
                rooms.append(new_room)
        
        rooms.sort(key=lambda r: (r.rect.y, r.rect.x))
        for i, r in enumerate(rooms): r.id = i
        
        # Fill rooms with 1
        for r in rooms:
            for ry in range(r.rect.height):
                for rx in range(r.rect.width):
                    grid[r.rect.y + ry][r.rect.x + rx] = 1

        # Route corridors
        if len(rooms) > 1:
            self._route_corridors(grid, rooms, width, height)

        return grid, rooms

    def _route_corridors(self, grid, rooms, width, height):
        # EXACT COPY FROM mega_dungeon.py route_corridors
        room_map = {r.id: r for r in rooms}
        edges = []
        for i, r1 in enumerate(rooms):
            for j in range(i + 1, len(rooms)):
                r2 = rooms[j]
                dist = math.hypot(r1.center[0] - r2.center[0], r1.center[1] - r2.center[1])
                edges.append((dist, r1.id, r2.id))
        
        edges.sort()
        connections, mst_pairs = [], set()
        parent = {r.id: r.id for r in rooms}
        
        def find(id):
            if parent[id] == id: return id
            parent[id] = find(parent[id])
            return parent[id]
            
        def union(id1, id2):
            r1, r2 = find(id1), find(id2)
            if r1 != r2: 
                parent[r1] = r2
                return True
            return False
            
        for _, r1_id, r2_id in edges:
            if union(r1_id, r2_id):
                connections.append((room_map[r1_id], room_map[r2_id]))
                mst_pairs.add(tuple(sorted((r1_id, r2_id))))
                
        extra_edges = [e for e in edges if tuple(sorted((e[1], e[2]))) not in mst_pairs]
        random.shuffle(extra_edges)
        connections.extend([(room_map[e[1]], room_map[e[2]]) for e in extra_edges[:len(rooms)//4]])

        for r1, r2 in connections:
            start_pos, end_pos = r1.center, r2.center
            path = self._find_path_a_star(grid, start_pos, end_pos, width, height)
            if path:
                for p in path:
                    if grid[p[1]][p[0]] == 0:
                        grid[p[1]][p[0]] = 2
            else:
                self._force_corridor_l_shape(grid, start_pos, end_pos, width, height)

    def _force_corridor_l_shape(self, grid, start, end, width, height):
        # EXACT COPY FROM mega_dungeon.py
        x, y = start
        target_x, target_y = end
        step_x = 1 if target_x > x else -1
        step_y = 1 if target_y > y else -1
        while x != target_x:
            if 0 <= x < width and 0 <= y < height and grid[y][x] == 0:
                grid[y][x] = 2
            x += step_x
        while y != target_y:
            if 0 <= x < width and 0 <= y < height and grid[y][x] == 0:
                grid[y][x] = 2
            y += step_y

    def _find_path_a_star(self, grid, start, end, width, height):
        # EXACT COPY FROM mega_dungeon.py
        start_node = AStarNode(None, start)
        open_list, closed_set = [start_node], set()
        iterations = 0
        max_iter = 10000
        
        while open_list:
            iterations += 1
            if iterations > max_iter: return None
            
            current = heapq.heappop(open_list)
            if current.position in closed_set: continue
            closed_set.add(current.position)
            
            if current.position == end:
                path = []
                while current:
                    path.append(current.position)
                    current = current.parent
                return path[::-1]
            
            (x, y) = current.position
            for dx, dy in [(0,-1), (0,1), (-1,0), (1,0)]:
                nx, ny = x + dx, y + dy
                if not (0 <= nx < width and 0 <= ny < height): continue
                
                cost = 1
                if grid[ny][nx] == 1: cost += 100
                if current.parent and (dx, dy) != current.direction: cost += TURN_PENALTY
                
                adj = 0
                for ax, ay in [(0,-1),(0,1),(-1,0),(1,0)]:
                    cx, cy = nx+ax, ny+ay
                    if 0 <= cx < width and 0 <= cy < height and grid[cy][cx] == 1:
                        adj = ADJACENCY_PENALTY
                        break
                
                new_node = AStarNode(current, (nx, ny), (dx, dy))
                new_node.g = current.g + cost + adj
                new_node.h = abs(nx - end[0]) + abs(ny - end[1])
                new_node.f = new_node.g + new_node.h
                heapq.heappush(open_list, new_node)
        
        return None
