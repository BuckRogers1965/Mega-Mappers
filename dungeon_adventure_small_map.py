import pygame
import random
import math
import time
import heapq
import os
import re
import google.generativeai as genai

# --- API CONFIGURATION ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# --- Configuration Constants ---
MAP_WIDTH_PX = 1200
MAP_HEIGHT_PX = 900
SCREEN_WIDTH = MAP_WIDTH_PX + 250
SCREEN_HEIGHT = MAP_HEIGHT_PX
CELL_SIZE = 30
GRID_WIDTH = MAP_WIDTH_PX // CELL_SIZE
GRID_HEIGHT = MAP_HEIGHT_PX // CELL_SIZE
MIN_ROOMS = 8
MAX_ROOMS = 15
MIN_ROOM_SIZE = 4
MAX_ROOM_SIZE = 10
ROOM_PADDING = 3
CORRIDOR_WIDTH = 1
TURN_PENALTY = 5
ADJACENCY_PENALTY = 10
COLOR_PARCHMENT = (245, 235, 215)
COLOR_INK = (40, 30, 20)
COLOR_GRID = (220, 210, 190)
LINE_THICKNESS = 3
HATCH_SPACING = 12

# --- Data Structures ---
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

# --- Helper Functions ---
def draw_hand_drawn_line(surface, start_pos, end_pos, color, thickness=1, wobble=2):
    distance = math.hypot(end_pos[0] - start_pos[0], end_pos[1] - start_pos[1])
    if distance == 0: return
    segments = max(2, int(distance / 10))
    points = []
    for i in range(segments + 1):
        t = i / segments
        x = start_pos[0] * (1 - t) + end_pos[0] * t
        y = start_pos[1] * (1 - t) + end_pos[1] * t
        if 0 < i < segments:
            angle = math.atan2(end_pos[1] - start_pos[1], end_pos[0] - start_pos[0]) + math.pi / 2
            x += random.uniform(-wobble, wobble) * math.cos(angle)
            y += random.uniform(-wobble, wobble) * math.sin(angle)
        points.append((x, y))
    for _ in range(thickness):
        stroke_points = [(p[0] + random.uniform(-wobble/2, wobble/2), p[1] + random.uniform(-wobble/2, wobble/2)) for p in points]
        pygame.draw.aalines(surface, color, False, stroke_points)

def get_sanitized_filename(topic):
    clean = re.sub(r'[^\w\s-]', '', topic).strip().replace(' ', '_')
    timestamp = time.strftime('%Y%m%d_%H%M%S')
    return f"{clean}_{timestamp}"

# --- Pygame Text Input (No Tkinter) ---
def pygame_input_popup(screen, prompt):
    font = pygame.font.Font(None, 32)
    input_box = pygame.Rect(SCREEN_WIDTH//2 - 200, SCREEN_HEIGHT//2 - 25, 400, 50)
    color_active = pygame.Color('black')
    color_bg = pygame.Color(245, 235, 215)
    text = ''
    done = False
    overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
    overlay.set_alpha(150)
    overlay.fill((0, 0, 0))

    while not done:
        for event in pygame.event.get():
            if event.type == pygame.QUIT: return None
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RETURN: done = True
                elif event.key == pygame.K_BACKSPACE: text = text[:-1]
                elif event.key == pygame.K_ESCAPE: return None
                else: text += event.unicode
        
        screen.blit(overlay, (0,0))
        panel_rect = pygame.Rect(SCREEN_WIDTH//2 - 250, SCREEN_HEIGHT//2 - 100, 500, 200)
        pygame.draw.rect(screen, color_bg, panel_rect)
        pygame.draw.rect(screen, color_active, panel_rect, 3)
        prompt_surf = font.render(prompt, True, color_active)
        screen.blit(prompt_surf, (panel_rect.x + 20, panel_rect.y + 20))
        txt_surface = font.render(text, True, color_active)
        width = max(350, txt_surface.get_width()+10)
        input_box.w = width
        input_box.centerx = SCREEN_WIDTH // 2
        pygame.draw.rect(screen, color_active, input_box, 2)
        screen.blit(txt_surface, (input_box.x+5, input_box.y+15))
        pygame.display.flip()
    return text

# --- AI Adventure Generation ---
def get_best_available_model():
    """
    Intelligently picks a model.
    Prioritizes 2.5/2.0 as requested.
    Filters out 'vision'/'image' models that cause 429 Quota errors on text prompts.
    """
    try:
        print("Fetching model list...")
        all_models = list(genai.list_models())
        candidates = [m.name for m in all_models if 'generateContent' in m.supported_generation_methods]
        # Filter out vision/image specific models to avoid quota errors on text prompts
        candidates = [c for c in candidates if "vision" not in c and "image" not in c and "pro" not in c]

        print(f"Found {len(candidates)} valid text models.")
        
        for m in candidates:
            if "gemini-2.5" in m: return m
        for m in candidates:
            if "gemini-2.0" in m: return m
        for m in candidates:
            if "gemini-1.5-pro" in m: return m
        for m in candidates:
            if "gemini-1.5-flash" in m: return m
            
        return "models/gemini-pro"
        
    except Exception as e:
        print(f"Model list failed: {e}")
        return "models/gemini-1.5-flash"

def create_adventure_with_gemini(rooms, topic, surface):
    if not GEMINI_API_KEY:
        print("ERROR: GEMINI_API_KEY not set.")
        return

    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model_name = get_best_available_model()
        model = genai.GenerativeModel(model_name)

        map_desc = f"Dungeon with {len(rooms)} rooms. 5ft Grid Scale.\n"
        for i, r in enumerate(rooms):
            width_ft, height_ft = r.rect.width * 5, r.rect.height * 5
            map_desc += f"- Room {i+1}: {width_ft}x{height_ft}ft\n"

        prompt = f"""
        Role: TTRPG Adventure Designer.
        Topic: "{topic}"
        Map: {map_desc}
        
        Create a detailed Markdown adventure.
        Structure:
        # [Adventure Title]
        **Hook & Theme**
        ## Room Descriptions (Match Room numbers in Map Data)
        **Room 1**
        - Visuals
        - Encounters/Traps
        (Repeat for all rooms)
        ## Conclusion
        """

        print(f"Generating using: {model_name}...")
        response = model.generate_content(prompt)
        
        base_name = get_sanitized_filename(topic)
        md_filename = f"{base_name}.md"
        with open(md_filename, "w", encoding='utf-8') as f:
            f.write(response.text)
            
        png_filename = f"{base_name}.png"
        pygame.image.save(surface, png_filename)

        print(f"SUCCESS. Saved {png_filename} and {md_filename}")
        return True

    except Exception as e:
        print(f"AI Error: {e}")
        return False

# --- Logic & Rendering ---
def generate_rooms():
    rooms = []
    num_to_gen = random.randint(MIN_ROOMS, MAX_ROOMS)
    for _ in range(2000):
        if len(rooms) >= num_to_gen: break
        width, height = random.randint(MIN_ROOM_SIZE, MAX_ROOM_SIZE), random.randint(MIN_ROOM_SIZE, MAX_ROOM_SIZE)
        x, y = random.randint(1, GRID_WIDTH - width - 2), random.randint(1, GRID_HEIGHT - height - 2)
        new_room = Room(x, y, width, height, len(rooms))
        if not any(new_room.intersects(other) for other in rooms): rooms.append(new_room)
    return rooms

def find_path_a_star(grid, start, end):
    start_node = AStarNode(None, start)
    open_list, closed_set = [start_node], set()
    while open_list:
        current_node = heapq.heappop(open_list)
        if current_node.position in closed_set: continue
        closed_set.add(current_node.position)
        if current_node.position == end:
            path = []
            while current_node: path.append(current_node.position); current_node = current_node.parent
            return path[::-1]
        (x, y) = current_node.position
        for dx, dy in [(0,-1), (0,1), (-1,0), (1,0)]:
            node_pos = (x + dx, y + dy)
            if not (0 <= node_pos[0] < GRID_WIDTH and 0 <= node_pos[1] < GRID_HEIGHT): continue
            movement_cost, turn_cost, adjacency_cost = 1, 0, 0
            if grid[node_pos[1]][node_pos[0]] == 1: movement_cost += 50
            if current_node.parent and (dx, dy) != current_node.direction: turn_cost = TURN_PENALTY
            for ax, ay in [(0,-1), (0,1), (-1,0), (1,0)]:
                check_pos = (node_pos[0] + ax, node_pos[1] + ay)
                if (0 <= check_pos[0] < GRID_WIDTH and 0 <= check_pos[1] < GRID_HEIGHT and grid[check_pos[1]][check_pos[0]] == 1):
                    adjacency_cost = ADJACENCY_PENALTY; break
            new_node = AStarNode(current_node, node_pos, (dx, dy))
            new_node.g = current_node.g + movement_cost + turn_cost + adjacency_cost
            new_node.h = abs(node_pos[0] - end[0]) + abs(node_pos[1] - end[1])
            new_node.f = new_node.g + new_node.h
            heapq.heappush(open_list, new_node)
    return None

def route_corridors(grid, rooms):
    if len(rooms) < 2: return
    room_map = {r.id: r for r in rooms}
    edges = [(math.hypot(r1.center[0] - r2.center[0], r1.center[1] - r2.center[1]), r1.id, r2.id) for i, r1 in enumerate(rooms) for r2 in rooms[i+1:]]
    edges.sort()
    connections, mst_pairs = [], set()
    parent = {r.id: r.id for r in rooms}
    def find(id):
        if parent[id] == id: return id
        parent[id] = find(parent[id]); return parent[id]
    def union(id1, id2):
        r1, r2 = find(id1), find(id2)
        if r1 != r2: parent[r1] = r2; return True
        return False
    for _, r1_id, r2_id in edges:
        if union(r1_id, r2_id):
            connections.append((room_map[r1_id], room_map[r2_id])); mst_pairs.add(tuple(sorted((r1_id, r2_id))))
    potential_loops = [(room_map[r1_id], room_map[r2_id]) for _, r1_id, r2_id in edges if tuple(sorted((r1_id, r2_id))) not in mst_pairs]
    random.shuffle(potential_loops)
    connections.extend(potential_loops[:random.randint(1, min(3, len(potential_loops)))])
    for room1, room2 in connections:
        c1_x, c1_y = room1.center; c2_x, c2_y = room2.center
        if abs(c1_x - c2_x) > abs(c1_y - c2_y):
            r_left, r_right = (room1, room2) if c1_x < c2_x else (room2, room1)
            start_pos, end_pos = (r_left.rect.right, r_left.rect.centery), (r_right.rect.left - 1, r_right.rect.centery)
        else:
            r_top, r_bot = (room1, room2) if c1_y < c2_y else (room2, room1)
            start_pos, end_pos = (r_top.rect.centerx, r_top.rect.bottom), (r_bot.rect.centerx, r_bot.rect.top - 1)
        path = find_path_a_star(grid, start_pos, end_pos)
        if path:
            for pos in path:
                if grid[pos[1]][pos[0]] == 0: grid[pos[1]][pos[0]] = 2

def render_dungeon(grid, rooms, font):
    surface = pygame.Surface((MAP_WIDTH_PX, MAP_HEIGHT_PX))
    surface.fill(COLOR_PARCHMENT)
    for _ in range(7000):
        x, y = random.randint(0, MAP_WIDTH_PX - 1), random.randint(0, MAP_HEIGHT_PX - 1)
        c = random.randint(10, 20)
        surface.set_at((x, y), tuple(max(0, val - c) for val in COLOR_PARCHMENT))
    for room in rooms:
        pixel_rect = pygame.Rect(room.rect.x * CELL_SIZE, room.rect.y * CELL_SIZE, room.rect.width * CELL_SIZE, room.rect.height * CELL_SIZE)
        for i in range(pixel_rect.left - pixel_rect.height, pixel_rect.right, HATCH_SPACING):
            start_pos, end_pos = (i, pixel_rect.top), (i + pixel_rect.height, pixel_rect.bottom)
            clipped = pixel_rect.clipline(start_pos, end_pos)
            if clipped: pygame.draw.aaline(surface, (225, 215, 195), clipped[0], clipped[1])
    for y in range(GRID_HEIGHT):
        for x in range(GRID_WIDTH):
            if grid[y][x] > 0:
                rect = pygame.Rect(x * CELL_SIZE, y * CELL_SIZE, CELL_SIZE, CELL_SIZE)
                pygame.draw.rect(surface, COLOR_GRID, rect, 1)
    for y in range(GRID_HEIGHT):
        for x in range(GRID_WIDTH):
            if grid[y][x] == 0: continue
            if y == 0 or grid[y - 1][x] == 0: draw_hand_drawn_line(surface, (x*CELL_SIZE, y*CELL_SIZE), ((x+1)*CELL_SIZE, y*CELL_SIZE), COLOR_INK, LINE_THICKNESS)
            if y == GRID_HEIGHT - 1 or grid[y + 1][x] == 0: draw_hand_drawn_line(surface, (x*CELL_SIZE, (y+1)*CELL_SIZE), ((x+1)*CELL_SIZE, (y+1)*CELL_SIZE), COLOR_INK, LINE_THICKNESS)
            if x == 0 or grid[y][x - 1] == 0: draw_hand_drawn_line(surface, (x*CELL_SIZE, y*CELL_SIZE), (x*CELL_SIZE, (y+1)*CELL_SIZE), COLOR_INK, LINE_THICKNESS)
            if x == GRID_WIDTH - 1 or grid[y][x + 1] == 0: draw_hand_drawn_line(surface, ((x+1)*CELL_SIZE, y*CELL_SIZE), ((x+1)*CELL_SIZE, (y+1)*CELL_SIZE), COLOR_INK, LINE_THICKNESS)
    
    for i, room in enumerate(rooms):
        number_text = str(i + 1)
        # CRITICAL FIX: Explicitly set background color to flatten transparency for PNG export
        text_surface = font.render(number_text, True, COLOR_INK, COLOR_PARCHMENT)
        pos_x, pos_y = room.rect.x * CELL_SIZE + 5, room.rect.y * CELL_SIZE + 5
        surface.blit(text_surface, (pos_x, pos_y))
    return surface

def generate_dungeon_data(font):
    grid = [[0 for _ in range(GRID_WIDTH)] for _ in range(GRID_HEIGHT)]
    rooms = generate_rooms()
    if not rooms: return None, None, None
    rooms.sort(key=lambda r: (r.rect.y, r.rect.x))
    for room in rooms:
        for y in range(room.rect.height):
            for x in range(room.rect.width):
                grid[room.rect.y + y][room.rect.x + x] = 1
    route_corridors(grid, rooms)
    surface = render_dungeon(grid, rooms, font)
    return surface, rooms, grid

def main():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Hand-Drawn Dungeon Generator")
    clock = pygame.time.Clock()
    font, font_small = pygame.font.Font(None, 36), pygame.font.Font(None, 28)
    font_map_numbers = pygame.font.Font(None, 24)
    dungeon_surface, current_rooms, _ = generate_dungeon_data(font_map_numbers)
    
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT: running = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_r: 
                    dungeon_surface, current_rooms, _ = generate_dungeon_data(font_map_numbers)
                
                # --- RESTORED SAVE FEATURE ---
                if event.key == pygame.K_s and dungeon_surface:
                    fname = f"dungeon_map_{time.strftime('%Y%m%d_%H%M%S')}.png"
                    pygame.image.save(dungeon_surface, fname)
                    print(f"Map saved as {fname}")

                if event.key == pygame.K_c and current_rooms:
                    topic = pygame_input_popup(screen, "Enter Dungeon Theme:")
                    if topic and topic.strip():
                        loading = font.render(f"Querying Gemini (best available model)...", True, COLOR_INK)
                        pygame.draw.rect(screen, COLOR_PARCHMENT, (SCREEN_WIDTH//2-250, SCREEN_HEIGHT//2, 500, 50))
                        screen.blit(loading, (SCREEN_WIDTH//2-220, SCREEN_HEIGHT//2+10))
                        pygame.display.flip()
                        create_adventure_with_gemini(current_rooms, topic, dungeon_surface)

        screen.fill(COLOR_INK)
        if dungeon_surface: screen.blit(dungeon_surface, (0, 0))
        
        ui_panel = pygame.Rect(MAP_WIDTH_PX, 0, 250, SCREEN_HEIGHT)
        pygame.draw.rect(screen, (50, 40, 30), ui_panel)
        pygame.draw.line(screen, COLOR_PARCHMENT, (MAP_WIDTH_PX, 0), (MAP_WIDTH_PX, SCREEN_HEIGHT), 2)
        screen.blit(font.render("Dungeon Generator", True, COLOR_PARCHMENT), (MAP_WIDTH_PX + 20, 20))
        screen.blit(font_small.render("[R] - Regenerate", True, COLOR_PARCHMENT), (MAP_WIDTH_PX + 20, 80))
        screen.blit(font_small.render("[S] - Save Map", True, COLOR_PARCHMENT), (MAP_WIDTH_PX + 20, 120))
        screen.blit(font_small.render("[C] - Create Adventure", True, (100, 200, 255)), (MAP_WIDTH_PX + 20, 160))
        
        pygame.display.flip()
        clock.tick(60)
    pygame.quit()

if __name__ == '__main__':
    main()
