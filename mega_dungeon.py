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
WIN_WIDTH_PX = 1200
WIN_HEIGHT_PX = 900
UI_WIDTH = 250
SCREEN_WIDTH = WIN_WIDTH_PX + UI_WIDTH
SCREEN_HEIGHT = WIN_HEIGHT_PX

# Default size (can be changed in app)
DEFAULT_CELL_SIZE = 15

# WORLD SIZE
WORLD_WIDTH = 150
WORLD_HEIGHT = 150

# GENERATION SETTINGS
MIN_ROOMS = 50
MAX_ROOMS = 90
MIN_ROOM_SIZE = 4
MAX_ROOM_SIZE = 12
ROOM_PADDING = 3
CORRIDOR_WIDTH = 1
TURN_PENALTY = 5
ADJACENCY_PENALTY = 20 

# AESTHETICS
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

# --- Pygame Text Input ---
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

# --- AI Logic ---

def get_best_available_model():
    try:
        print("Fetching model list...")
        all_models = list(genai.list_models())
        candidates = [m.name for m in all_models if 'generateContent' in m.supported_generation_methods]
        
        # STRICT FILTER: No Vision, No Image, No Pro
        valid_models = [c for c in candidates if "gemini-flash-latest" in c and "lite" not in c and "vision" not in c and "image" not in c and "pro" not in c]
        
        if valid_models:
            valid_models.sort(reverse=True)
            print(f"Selected Model: {valid_models[0]}")
            return valid_models[0]

        return "models/gemini-flash-latest"
        
    except Exception as e:
        print(f"Model list failed: {e}")
        return "models/gemini-flash-latest"

def create_adventure_with_gemini(visible_rooms, topic, surface, camera_pos):
    if not GEMINI_API_KEY:
        print("ERROR: GEMINI_API_KEY not set.")
        return

    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model_name = get_best_available_model()
        model = genai.GenerativeModel(model_name)

        map_desc = f"SECTOR ({camera_pos[0]},{camera_pos[1]}) of a Megadungeon.\n"
        map_desc += f"Visible Rooms: {len(visible_rooms)}\n"
        for r in visible_rooms:
            width_ft, height_ft = r.rect.width * 5, r.rect.height * 5
            map_desc += f"- Room ID {r.id+1}: {width_ft}x{height_ft}ft\n"

        prompt = f"""
        Role: TTRPG Adventure Designer.
        Topic: "{topic}"
        Context: Specific sector of a megadungeon.
        Map Data: {map_desc}
        
        Create a detailed Markdown adventure for JUST this sector.
        Structure:
        # [Sector Title]
        **Theme**
        ## Room Descriptions
        (Describe visible rooms)
        ## Connections
        (Corridors lead to other sectors)
        """

        print(f"Generating sector adventure using {model_name}...")
        response = model.generate_content(prompt)
        
        base_name = get_sanitized_filename(topic)
        md_filename = f"{base_name}.md"
        with open(md_filename, "w", encoding='utf-8') as f:
            f.write(response.text)
            
        png_filename = f"{base_name}_view.png"
        pygame.image.save(surface, png_filename)

        print(f"SUCCESS. Saved {png_filename} and {md_filename}")
        return True

    except Exception as e:
        print(f"AI Error: {e}")
        return False

# --- World Generation ---
def generate_world_data():
    grid = [[0 for _ in range(WORLD_WIDTH)] for _ in range(WORLD_HEIGHT)]
    rooms = []
    attempts = 15000 
    
    for _ in range(attempts):
        if len(rooms) >= MAX_ROOMS: break
        w = random.randint(MIN_ROOM_SIZE, MAX_ROOM_SIZE)
        h = random.randint(MIN_ROOM_SIZE, MAX_ROOM_SIZE)
        x = random.randint(2, WORLD_WIDTH - w - 2)
        y = random.randint(2, WORLD_HEIGHT - h - 2)
        new_room = Room(x, y, w, h, len(rooms))
        if not any(new_room.intersects(other) for other in rooms):
            rooms.append(new_room)
    
    rooms.sort(key=lambda r: (r.rect.y, r.rect.x))
    for i, r in enumerate(rooms): r.id = i
    
    for r in rooms:
        for ry in range(r.rect.height):
            for rx in range(r.rect.width):
                grid[r.rect.y + ry][r.rect.x + rx] = 1

    if len(rooms) > 1:
        route_corridors(grid, rooms)

    return grid, rooms

def route_corridors(grid, rooms):
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
        parent[id] = find(parent[id]); return parent[id]
    def union(id1, id2):
        r1, r2 = find(id1), find(id2)
        if r1 != r2: parent[r1] = r2; return True
        return False
        
    for _, r1_id, r2_id in edges:
        if union(r1_id, r2_id):
            connections.append((room_map[r1_id], room_map[r2_id])); mst_pairs.add(tuple(sorted((r1_id, r2_id))))
            
    extra_edges = [e for e in edges if tuple(sorted((e[1], e[2]))) not in mst_pairs]
    random.shuffle(extra_edges)
    connections.extend([(room_map[e[1]], room_map[e[2]]) for e in extra_edges[:len(rooms)//4]])

    for r1, r2 in connections:
        start_pos, end_pos = r1.center, r2.center
        path = find_path_a_star(grid, start_pos, end_pos)
        if path:
            for p in path:
                if grid[p[1]][p[0]] == 0: grid[p[1]][p[0]] = 2
        else:
            force_corridor_l_shape(grid, start_pos, end_pos)

def force_corridor_l_shape(grid, start, end):
    x, y = start
    target_x, target_y = end
    step_x = 1 if target_x > x else -1
    step_y = 1 if target_y > y else -1
    while x != target_x:
        if 0 <= x < WORLD_WIDTH and 0 <= y < WORLD_HEIGHT and grid[y][x] == 0: grid[y][x] = 2
        x += step_x
    while y != target_y:
        if 0 <= x < WORLD_WIDTH and 0 <= y < WORLD_HEIGHT and grid[y][x] == 0: grid[y][x] = 2
        y += step_y

def find_path_a_star(grid, start, end):
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
            while current: path.append(current.position); current = current.parent
            return path[::-1]
        (x, y) = current.position
        for dx, dy in [(0,-1), (0,1), (-1,0), (1,0)]:
            nx, ny = x + dx, y + dy
            if not (0 <= nx < WORLD_WIDTH and 0 <= ny < WORLD_HEIGHT): continue
            cost = 1
            if grid[ny][nx] == 1: cost += 100 
            if current.parent and (dx, dy) != current.direction: cost += TURN_PENALTY
            adj = 0
            for ax, ay in [(0,-1),(0,1),(-1,0),(1,0)]:
                cx, cy = nx+ax, ny+ay
                if 0 <= cx < WORLD_WIDTH and 0 <= cy < WORLD_HEIGHT and grid[cy][cx] == 1:
                    adj = ADJACENCY_PENALTY; break
            new_node = AStarNode(current, (nx, ny), (dx, dy))
            new_node.g = current.g + cost + adj
            new_node.h = abs(nx - end[0]) + abs(ny - end[1])
            new_node.f = new_node.g + new_node.h
            heapq.heappush(open_list, new_node)
    return None

# --- RENDERERS ---

def render_viewport(grid, rooms, camera_x, camera_y, current_cell_size):
    """Renders the screen view with dynamic cell size."""
    surface = pygame.Surface((WIN_WIDTH_PX, WIN_HEIGHT_PX))
    surface.fill(COLOR_PARCHMENT)
    
    # Calculate visible area in cells
    view_width = WIN_WIDTH_PX // current_cell_size
    view_height = WIN_HEIGHT_PX // current_cell_size
    
    # Dynamic font size
    font_nums = pygame.font.Font(None, int(current_cell_size * 1.5))

    for _ in range(5000):
        x, y = random.randint(0, WIN_WIDTH_PX-1), random.randint(0, WIN_HEIGHT_PX-1)
        c = random.randint(10, 20)
        surface.set_at((x, y), tuple(max(0, val - c) for val in COLOR_PARCHMENT))

    start_x = max(0, camera_x)
    end_x = min(WORLD_WIDTH, camera_x + view_width + 1)
    start_y = max(0, camera_y)
    end_y = min(WORLD_HEIGHT, camera_y + view_height + 1)
    
    visible_rooms = []
    
    # Hatching
    for r in rooms:
        if r.rect.right > start_x and r.rect.left < end_x and r.rect.bottom > start_y and r.rect.top < end_y:
            visible_rooms.append(r)
            screen_rect = pygame.Rect((r.rect.x - camera_x) * current_cell_size, (r.rect.y - camera_y) * current_cell_size, r.rect.width * current_cell_size, r.rect.height * current_cell_size)
            screen_rect = screen_rect.clip(pygame.Rect(0, 0, WIN_WIDTH_PX, WIN_HEIGHT_PX))
            if screen_rect.width > 0 and screen_rect.height > 0:
                for i in range(screen_rect.left - screen_rect.height, screen_rect.right, HATCH_SPACING):
                    start_pos = (i, screen_rect.top)
                    end_pos = (i + screen_rect.height, screen_rect.bottom)
                    clipped = screen_rect.clipline(start_pos, end_pos)
                    if clipped: pygame.draw.aaline(surface, (225, 215, 195), clipped[0], clipped[1])

    # Grid & Walls
    for y in range(start_y, end_y):
        for x in range(start_x, end_x):
            if grid[y][x] > 0:
                sx, sy = (x - camera_x) * current_cell_size, (y - camera_y) * current_cell_size
                pygame.draw.rect(surface, COLOR_GRID, (sx, sy, current_cell_size, current_cell_size), 1)
            
            if grid[y][x] != 0:
                sx, sy = (x - camera_x) * current_cell_size, (y - camera_y) * current_cell_size
                if y == 0 or grid[y-1][x] == 0: draw_hand_drawn_line(surface, (sx, sy), (sx+current_cell_size, sy), COLOR_INK, LINE_THICKNESS)
                if y == WORLD_HEIGHT-1 or grid[y+1][x] == 0: draw_hand_drawn_line(surface, (sx, sy+current_cell_size), (sx+current_cell_size, sy+current_cell_size), COLOR_INK, LINE_THICKNESS)
                if x == 0 or grid[y][x-1] == 0: draw_hand_drawn_line(surface, (sx, sy), (sx, sy+current_cell_size), COLOR_INK, LINE_THICKNESS)
                if x == WORLD_WIDTH-1 or grid[y][x+1] == 0: draw_hand_drawn_line(surface, (sx+current_cell_size, sy), (sx+current_cell_size, sy+current_cell_size), COLOR_INK, LINE_THICKNESS)

    # Room Numbers
    for r in visible_rooms:
        number_text = str(r.id + 1)
        text_surface = font_nums.render(number_text, True, COLOR_INK, COLOR_PARCHMENT)
        sx = (r.rect.x - camera_x) * current_cell_size + (current_cell_size//3)
        sy = (r.rect.y - camera_y) * current_cell_size + (current_cell_size//3)
        if -50 < sx < WIN_WIDTH_PX and -50 < sy < WIN_HEIGHT_PX:
            surface.blit(text_surface, (sx, sy))
            
    return surface, visible_rooms

def render_full_map_high_res(grid, rooms):
    """Renders the entire world at high resolution (fixed cell size for consistency), then scales down."""
    cell_size = 15 # Fixed size for rendering high res map
    full_w = WORLD_WIDTH * cell_size
    full_h = WORLD_HEIGHT * cell_size
    print(f"Creating High-Res Surface: {full_w}x{full_h}px...")
    
    surf = pygame.Surface((full_w, full_h))
    surf.fill(COLOR_PARCHMENT)
    
    # 1. Hatching
    for r in rooms:
        pixel_rect = pygame.Rect(r.rect.x * cell_size, r.rect.y * cell_size, r.rect.width * cell_size, r.rect.height * cell_size)
        for i in range(pixel_rect.left - pixel_rect.height, pixel_rect.right, HATCH_SPACING):
            start_pos = (i, pixel_rect.top)
            end_pos = (i + pixel_rect.height, pixel_rect.bottom)
            clipped = pixel_rect.clipline(start_pos, end_pos)
            if clipped: pygame.draw.aaline(surf, (225, 215, 195), clipped[0], clipped[1])

    # 2. Grid & Walls
    for y in range(WORLD_HEIGHT):
        for x in range(WORLD_WIDTH):
            if grid[y][x] > 0:
                sx, sy = x * cell_size, y * cell_size
                pygame.draw.rect(surf, COLOR_GRID, (sx, sy, cell_size, cell_size), 1)
            
            if grid[y][x] != 0:
                sx, sy = x * cell_size, y * cell_size
                if y == 0 or grid[y-1][x] == 0: draw_hand_drawn_line(surf, (sx, sy), (sx+cell_size, sy), COLOR_INK, LINE_THICKNESS)
                if y == WORLD_HEIGHT-1 or grid[y+1][x] == 0: draw_hand_drawn_line(surf, (sx, sy+cell_size), (sx+cell_size, sy+cell_size), COLOR_INK, LINE_THICKNESS)
                if x == 0 or grid[y][x-1] == 0: draw_hand_drawn_line(surf, (sx, sy), (sx, sy+cell_size), COLOR_INK, LINE_THICKNESS)
                if x == WORLD_WIDTH-1 or grid[y][x+1] == 0: draw_hand_drawn_line(surf, (sx+cell_size, sy), (sx+cell_size, sy+cell_size), COLOR_INK, LINE_THICKNESS)
    
    # 3. MASSIVE NUMBERS
    huge_font = pygame.font.Font(None, 45)
    for r in rooms:
        number_text = str(r.id + 1)
        text_surface = huge_font.render(number_text, True, COLOR_INK, COLOR_PARCHMENT)
        sx = r.rect.x * cell_size + 15
        sy = r.rect.y * cell_size + 15
        surf.blit(text_surface, (sx, sy))

    print("Scaling down to 1200x1200...")
    scaled_surf = pygame.transform.smoothscale(surf, (1200, 1200))
    return scaled_surf

def render_minimap(grid, camera_x, camera_y, view_w, view_h, draw_viewport=True):
    scale = 2 
    w, h = WORLD_WIDTH * scale, WORLD_HEIGHT * scale
    surf = pygame.Surface((w, h))
    surf.fill((200, 190, 170))
    for y in range(WORLD_HEIGHT):
        for x in range(WORLD_WIDTH):
            if grid[y][x] == 1: pygame.draw.rect(surf, (100, 80, 60), (x*scale, y*scale, scale, scale))
            elif grid[y][x] == 2: pygame.draw.rect(surf, (150, 140, 130), (x*scale, y*scale, scale, scale))
    
    if draw_viewport:
        rect = pygame.Rect(camera_x*scale, camera_y*scale, view_w*scale, view_h*scale)
        pygame.draw.rect(surf, (255, 0, 0), rect, 2)
    return surf

# --- Main ---
def main():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Megadungeon Generator")
    clock = pygame.time.Clock()
    font = pygame.font.Font(None, 36)
    font_small = pygame.font.Font(None, 28)
    
    # Zoom State
    current_cell_size = DEFAULT_CELL_SIZE

    camera_x, camera_y = 0, 0
    show_minimap = True
    view_surface = None
    visible_rooms = []
    view_dirty = True 

    print("Generating Megadungeon...")
    world_grid, world_rooms = generate_world_data()
    
    # Initial View Calcs for Camera positioning
    init_view_w = WIN_WIDTH_PX // current_cell_size
    init_view_h = WIN_HEIGHT_PX // current_cell_size
    if world_rooms:
        camera_x = max(0, world_rooms[0].rect.x - init_view_w // 2)
        camera_y = max(0, world_rooms[0].rect.y - init_view_h // 2)
    
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT: running = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_r:
                    print("Regenerating World...")
                    world_grid, world_rooms = generate_world_data()
                    camera_x, camera_y = 0, 0
                    view_dirty = True
                
                if event.key == pygame.K_m:
                    show_minimap = not show_minimap
                
                # ZOOM CONTROLS
                if event.key == pygame.K_LEFTBRACKET: # Zoom Out
                    current_cell_size = max(5, current_cell_size - 2)
                    view_dirty = True
                if event.key == pygame.K_RIGHTBRACKET: # Zoom In
                    current_cell_size = min(40, current_cell_size + 2)
                    view_dirty = True
                    
                if event.key == pygame.K_s:
                    if view_surface:
                        # 1. Save View
                        fname = f"megadungeon_view_{time.strftime('%Y%m%d_%H%M%S')}.png"
                        pygame.image.save(view_surface, fname)
                        
                        # 2. Save Clean Minimap (No Red Box)
                        # Need to calc current view dims for func arg even if drawing off
                        curr_vw = WIN_WIDTH_PX // current_cell_size
                        curr_vh = WIN_HEIGHT_PX // current_cell_size
                        mm_surf = render_minimap(world_grid, camera_x, camera_y, curr_vw, curr_vh, draw_viewport=False)
                        fname_mm = f"megadungeon_pixel_map_{time.strftime('%Y%m%d_%H%M%S')}.png"
                        pygame.image.save(mm_surf, fname_mm)

                        # 3. Save High-Res Scaled Map (WITH NUMBERS)
                        high_res_surf = render_full_map_high_res(world_grid, world_rooms)
                        fname_hr = f"megadungeon_sketch_map_{time.strftime('%Y%m%d_%H%M%S')}.png"
                        pygame.image.save(high_res_surf, fname_hr)

                        print("Saved: View, Pixel Map, and High-Res Sketch (with numbers).")

                if event.key == pygame.K_c and visible_rooms:
                    topic = pygame_input_popup(screen, "Sector Theme:")
                    if topic and topic.strip():
                        loading = font.render(f"AI Generating Sector Adventure...", True, COLOR_INK)
                        pygame.draw.rect(screen, COLOR_PARCHMENT, (SCREEN_WIDTH//2-200, SCREEN_HEIGHT//2, 400, 50))
                        screen.blit(loading, (SCREEN_WIDTH//2-180, SCREEN_HEIGHT//2+10))
                        pygame.display.flip()
                        create_adventure_with_gemini(visible_rooms, topic, view_surface, (camera_x, camera_y))

        # Update view dims based on zoom
        view_w_cells = WIN_WIDTH_PX // current_cell_size
        view_h_cells = WIN_HEIGHT_PX // current_cell_size

        keys = pygame.key.get_pressed()
        speed = 1
        if keys[pygame.K_LSHIFT]: speed = 3
        
        old_cx, old_cy = camera_x, camera_y
        if keys[pygame.K_LEFT]: camera_x = max(0, camera_x - speed)
        # Fix camera clamping using dynamic view width
        if keys[pygame.K_RIGHT]: camera_x = min(WORLD_WIDTH - view_w_cells, camera_x + speed)
        if keys[pygame.K_UP]: camera_y = max(0, camera_y - speed)
        if keys[pygame.K_DOWN]: camera_y = min(WORLD_HEIGHT - view_h_cells, camera_y + speed)
        
        # Ensure camera stays in bounds if zoom changed
        camera_x = max(0, min(camera_x, WORLD_WIDTH - view_w_cells))
        camera_y = max(0, min(camera_y, WORLD_HEIGHT - view_h_cells))

        if camera_x != old_cx or camera_y != old_cy:
            view_dirty = True

        screen.fill(COLOR_INK)
        
        if view_dirty:
            view_surface, visible_rooms = render_viewport(world_grid, world_rooms, camera_x, camera_y, current_cell_size)
            view_dirty = False
            
        screen.blit(view_surface, (0, 0))
        
        ui_rect = pygame.Rect(WIN_WIDTH_PX, 0, UI_WIDTH, SCREEN_HEIGHT)
        pygame.draw.rect(screen, (50, 40, 30), ui_rect)
        pygame.draw.line(screen, COLOR_PARCHMENT, (WIN_WIDTH_PX, 0), (WIN_WIDTH_PX, SCREEN_HEIGHT), 2)
        
        if show_minimap:
            minimap = render_minimap(world_grid, camera_x, camera_y, view_w_cells, view_h_cells, draw_viewport=True)
            mm_x = WIN_WIDTH_PX + (UI_WIDTH - minimap.get_width()) // 2
            screen.blit(minimap, (mm_x, 20))
            coord_text = font_small.render(f"Pos: {camera_x}, {camera_y}", True, COLOR_PARCHMENT)
            screen.blit(coord_text, (WIN_WIDTH_PX + 20, minimap.get_height() + 30))

        y_off = 350 if show_minimap else 20
        screen.blit(font.render("Megadungeon", True, COLOR_PARCHMENT), (WIN_WIDTH_PX + 20, y_off))
        screen.blit(font_small.render("Arrows: Move Camera", True, (200, 200, 200)), (WIN_WIDTH_PX + 20, y_off + 40))
        screen.blit(font_small.render("[ ] : Zoom In/Out", True, (200, 200, 200)), (WIN_WIDTH_PX + 20, y_off + 70))
        screen.blit(font_small.render("[M]: Toggle Minimap", True, COLOR_PARCHMENT), (WIN_WIDTH_PX + 20, y_off + 100))
        screen.blit(font_small.render("[R]: New World", True, COLOR_PARCHMENT), (WIN_WIDTH_PX + 20, y_off + 130))
        screen.blit(font_small.render("[S]: Save Maps", True, COLOR_PARCHMENT), (WIN_WIDTH_PX + 20, y_off + 160))
        screen.blit(font_small.render("[C]: AI Sector Adv.", True, (100, 200, 255)), (WIN_WIDTH_PX + 20, y_off + 190))
        
        zoom_text = font_small.render(f"Zoom: {current_cell_size}px", True, (150, 150, 100))
        screen.blit(zoom_text, (WIN_WIDTH_PX + 20, SCREEN_HEIGHT - 30))

        pygame.display.flip()
        clock.tick(60)
    
    pygame.quit()

if __name__ == '__main__':
    main()