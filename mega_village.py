import pygame
import random
import math
import time
import os
import re
import google.generativeai as genai

# --- API CONFIGURATION ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# --- Configuration Constants ---
WIN_WIDTH_PX = 1200
WIN_HEIGHT_PX = 900
UI_WIDTH = 300
SCREEN_WIDTH = WIN_WIDTH_PX + UI_WIDTH
SCREEN_HEIGHT = WIN_HEIGHT_PX

# WORLD CONFIG
WORLD_RADIUS = 25 

# AESTHETICS
COLOR_PARCHMENT = (245, 235, 215)
COLOR_INK = (40, 30, 20)
COLOR_WATER = (120, 160, 200)
COLOR_GRASS = (200, 220, 180)
COLOR_ROAD = (180, 160, 140)
COLOR_FOREST = (100, 140, 100)
LINE_THICKNESS = 2

# BUILDING TYPES
BUILDING_TYPES = {
    "inn": {"color": (200, 150, 100), "icon": "🏨", "near": ["road", "center"]},
    "tavern": {"color": (180, 130, 80), "icon": "🍺", "near": ["road", "center"]},
    "temple": {"color": (220, 220, 240), "icon": "⛪", "near": ["center"]},
    "market": {"color": (200, 180, 120), "icon": "🏪", "near": ["road", "center"]},
    "house": {"color": (190, 170, 150), "icon": "🏠", "near": ["road"]},
    "mill": {"color": (160, 140, 120), "icon": "⚙️", "near": ["water"]},
    "dock": {"color": (140, 120, 100), "icon": "⚓", "near": ["water"]},
    "smithy": {"color": (100, 100, 120), "icon": "🔨", "near": ["road"]},
    "stable": {"color": (180, 160, 120), "icon": "🐴", "near": ["outskirts"]},
    "farm": {"color": (200, 190, 140), "icon": "🌾", "near": ["outskirts"]},
    "well": {"color": (150, 180, 200), "icon": "🪣", "near": ["center"]},
    "chapel": {"color": (210, 210, 220), "icon": "✝️", "near": ["center"]},
}

# NAME GENERATORS
PREFIXES = ["Old", "Ye", "The", "Green", "Red", "Golden", "Silver", "Bronze", "Stone", "Oak"]
SUFFIXES = ["Dragon", "Griffin", "Rose", "Crown", "Shield", "Sword", "Barrel", "Wheel", "Anchor", "Star"]
PROFESSIONS = ["Thatcher", "Cooper", "Wright", "Smith", "Miller", "Fisher", "Baker", "Chandler"]
FIRST_NAMES = ["Tom", "Mary", "John", "Sarah", "William", "Emma", "James", "Alice", "Robert", "Margaret"]

# --- Data Structures ---
class Building:
    def __init__(self, hex_pos, building_type, name):
        self.hex_pos = hex_pos
        self.type = building_type
        self.name = name
        self.description = ""

class TerrainHex:
    def __init__(self, q, r):
        self.q = q
        self.r = r
        self.terrain = "grass"
        self.building = None

# --- Hex Math ---
def axial_to_pixel(q, r, hex_size):
    x = hex_size * (3/2 * q)
    y = hex_size * (math.sqrt(3)/2 * q + math.sqrt(3) * r)
    return (x, y)

def pixel_to_axial(x, y, hex_size):
    q = (2/3 * x) / hex_size
    r = (-1/3 * x + math.sqrt(3)/3 * y) / hex_size
    return axial_round(q, r)

def axial_round(q, r):
    x, y, z = q, r, -q-r
    rx, ry, rz = round(x), round(y), round(z)
    x_diff, y_diff, z_diff = abs(rx - x), abs(ry - y), abs(rz - z)
    
    if x_diff > y_diff and x_diff > z_diff:
        rx = -ry - rz
    elif y_diff > z_diff:
        ry = -rx - rz
    return (rx, ry)

def axial_distance(q1, r1, q2, r2):
    return (abs(q1 - q2) + abs(q1 + r1 - q2 - r2) + abs(r1 - r2)) // 2

def get_hex_corners(x, y, size):
    corners = []
    for i in range(6):
        angle = math.pi / 3 * i
        corners.append((x + size * math.cos(angle), y + size * math.sin(angle)))
    return corners

# --- Helper Functions ---
def generate_building_name(building_type):
    if building_type == "inn" or building_type == "tavern":
        return f"{random.choice(['The', 'Ye Olde'])} {random.choice(PREFIXES)} {random.choice(SUFFIXES)}"
    elif building_type == "house":
        return f"{random.choice(FIRST_NAMES)} {random.choice(PROFESSIONS)}'s Cottage"
    elif building_type == "smithy":
        return f"{random.choice(FIRST_NAMES)}'s Smithy"
    elif building_type == "mill":
        return f"{random.choice(['Water', 'Wind', 'Stone'])} Mill"
    elif building_type == "temple" or building_type == "chapel":
        return f"Chapel of {random.choice(['St. Cuthbert', 'the Light', 'Mercy', 'the Dawn'])}"
    elif building_type == "market":
        return "Market Square"
    elif building_type == "well":
        return "Village Well"
    elif building_type == "dock":
        return f"{random.choice(FIRST_NAMES)}'s Dock"
    elif building_type == "stable":
        return f"{random.choice(FIRST_NAMES)}'s Stables"
    elif building_type == "farm":
        return f"{random.choice(FIRST_NAMES)} Family Farm"
    return f"{building_type.title()}"

def get_sanitized_filename(topic):
    clean = re.sub(r'[^\w\s-]', '', topic).strip().replace(' ', '_')
    timestamp = time.strftime('%Y%m%d_%H%M%S')
    return f"{clean}_{timestamp}"

# --- UI Functions ---
def pygame_terrain_modal(screen):
    font = pygame.font.Font(None, 32)
    font_small = pygame.font.Font(None, 24)
    
    biomes = ["Coastal Village", "Riverside Village", "Forest Clearing", "Desert Oasis", "Mountain Valley"]
    water_features = ["None", "Ocean (Edge)", "River (Through)", "Lake (Center)", "Creek"]
    
    selected_biome = 0
    selected_water = 0
    done = False
    
    overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
    overlay.set_alpha(200)
    overlay.fill((0, 0, 0))
    
    while not done:
        for event in pygame.event.get():
            if event.type == pygame.QUIT: return None, None
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RETURN: done = True
                elif event.key == pygame.K_ESCAPE: return None, None
                elif event.key == pygame.K_UP:
                    selected_biome = (selected_biome - 1) % len(biomes)
                elif event.key == pygame.K_DOWN:
                    selected_biome = (selected_biome + 1) % len(biomes)
                elif event.key == pygame.K_LEFT:
                    selected_water = (selected_water - 1) % len(water_features)
                elif event.key == pygame.K_RIGHT:
                    selected_water = (selected_water + 1) % len(water_features)
        
        screen.blit(overlay, (0,0))
        panel_rect = pygame.Rect(SCREEN_WIDTH//2 - 300, SCREEN_HEIGHT//2 - 250, 600, 500)
        pygame.draw.rect(screen, COLOR_PARCHMENT, panel_rect)
        pygame.draw.rect(screen, COLOR_INK, panel_rect, 3)
        
        title = font.render("Village Terrain Setup", True, COLOR_INK)
        screen.blit(title, (panel_rect.x + 150, panel_rect.y + 20))
        
        y_offset = 80
        biome_label = font_small.render("Biome (UP/DOWN):", True, COLOR_INK)
        screen.blit(biome_label, (panel_rect.x + 30, panel_rect.y + y_offset))
        
        for i, biome in enumerate(biomes):
            color = (200, 50, 50) if i == selected_biome else (100, 100, 100)
            prefix = "> " if i == selected_biome else "  "
            weight = pygame.font.Font(None, 30 if i == selected_biome else 24)
            biome_text = weight.render(f"{prefix}{biome}", True, color)
            screen.blit(biome_text, (panel_rect.x + 50, panel_rect.y + y_offset + 30 + i * 30))
        
        y_offset = 280
        water_label = font_small.render("Water Feature (LEFT/RIGHT):", True, COLOR_INK)
        screen.blit(water_label, (panel_rect.x + 30, panel_rect.y + y_offset))
        
        for i, feature in enumerate(water_features):
            color = (50, 50, 200) if i == selected_water else (100, 100, 100)
            prefix = "> " if i == selected_water else "  "
            weight = pygame.font.Font(None, 30 if i == selected_water else 24)
            feature_text = weight.render(f"{prefix}{feature}", True, color)
            screen.blit(feature_text, (panel_rect.x + 50, panel_rect.y + y_offset + 30 + i * 25))
        
        instr = font_small.render("Press ENTER to generate, ESC to cancel", True, (50, 50, 50))
        screen.blit(instr, (panel_rect.x + 100, panel_rect.y + 450))
        
        pygame.display.flip()
    
    pygame.event.clear()
    return biomes[selected_biome], water_features[selected_water]

# --- AI Logic ---
def get_best_available_model():
    try:
        print("Fetching model list...")
        all_models = list(genai.list_models())
        candidates = [m.name for m in all_models if 'generateContent' in m.supported_generation_methods]
        
        # STRICT FILTER: No Vision, No Image, No Pro
        valid_models = [c for c in candidates if "gemini-flash-latest" in c and "lite" not in c and "vision" not in c and "image" not in c and "pro" not in c]
        
        if valid_models:
            # Sort reverse alphabetically (picks highest version number automatically)
            valid_models.sort(reverse=True)
            print(f"Selected Model: {valid_models[0]}")
            return valid_models[0]

        # Absolute fallback if list is empty
        return "models/gemini-flash-latest"

    except Exception as e:
        print(f"Model list failed: {e}")
        return "models/gemini-flash-latest"

def create_village_guide_with_gemini(buildings, village_theme, biome, surface):
    if not GEMINI_API_KEY:
        print("ERROR: GEMINI_API_KEY not set.")
        return

    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model_name = get_best_available_model()
        model = genai.GenerativeModel(model_name)

        building_list = "\n".join([f"- {b.name} ({b.type})" for b in buildings])

        prompt = f"""
        Role: TTRPG Village Designer.
        Setting: {village_theme} - {biome}
        
        Buildings in village:
        {building_list}
        
        Create a comprehensive village guide in Markdown format:
        
        # {village_theme}
        
        ## Overview
        (Village atmosphere, history, current situation)
        
        ## Key Locations
        (Brief description of each building)
        
        ## Notable NPCs
        (3-5 important villagers with names, roles, personalities)
        
        ## Village Rumors
        (5-7 rumors or plot hooks)
        
        Keep it practical and immediately usable at the table.
        """

        print(f"Generating village guide...")
        response = model.generate_content(prompt)
        
        base_name = get_sanitized_filename(village_theme)
        md_filename = f"{base_name}_guide.md"
        with open(md_filename, "w", encoding='utf-8') as f:
            f.write(response.text)
            
        png_filename = f"{base_name}_map.png"
        pygame.image.save(surface, png_filename)

        print(f"SUCCESS. Saved {png_filename} and {md_filename}")
        return True

    except Exception as e:
        print(f"AI Error: {e}")
        return False

# --- World Generation ---
def generate_village(biome, water_feature):
    hexes = {}
    buildings = []
    
    # Create hex grid
    for q in range(-WORLD_RADIUS, WORLD_RADIUS + 1):
        for r in range(-WORLD_RADIUS, WORLD_RADIUS + 1):
            if abs(q + r) <= WORLD_RADIUS:
                hexes[(q, r)] = TerrainHex(q, r)
    
    # Generate water features
    if "Ocean" in water_feature:
        for q in range(-WORLD_RADIUS, WORLD_RADIUS + 1):
            for r in range(-WORLD_RADIUS, WORLD_RADIUS + 1):
                if (q, r) in hexes:
                    if r > WORLD_RADIUS - 8:
                        hexes[(q, r)].terrain = "water"
    
    elif "River" in water_feature:
        for q in range(-WORLD_RADIUS, WORLD_RADIUS + 1):
            r = -q + random.randint(-2, 2)
            if (q, r) in hexes:
                hexes[(q, r)].terrain = "water"
                for dr in [-1, 1]:
                    if (q, r + dr) in hexes:
                        hexes[(q, r + dr)].terrain = "water"
    
    elif "Lake" in water_feature:
        for q in range(-6, 7):
            for r in range(-6, 7):
                if abs(q + r) <= 6 and (q, r) in hexes:
                    hexes[(q, r)].terrain = "water"
    
    elif "Creek" in water_feature:
        q, r = -WORLD_RADIUS + 3, 5
        for _ in range(50):
            if (q, r) in hexes:
                hexes[(q, r)].terrain = "water"
            q += random.choice([0, 1])
            r += random.choice([-1, 0, 1])
    
    # Generate roads
    road_hexes = set()
    
    # Main road
    for q in range(-WORLD_RADIUS, WORLD_RADIUS + 1):
        r = random.randint(-1, 1)
        if (q, r) in hexes and hexes[(q, r)].terrain != "water":
            hexes[(q, r)].terrain = "road"
            road_hexes.add((q, r))
    
    # Cross road
    if random.random() > 0.3:
        q_center = random.randint(-3, 3)
        for r in range(-WORLD_RADIUS, WORLD_RADIUS + 1):
            if (q_center, r) in hexes and hexes[(q_center, r)].terrain != "water":
                hexes[(q_center, r)].terrain = "road"
                road_hexes.add((q_center, r))
    
    # Add forests
    if "Forest" in biome:
        for _ in range(80):
            q = random.randint(-WORLD_RADIUS, WORLD_RADIUS)
            r = random.randint(-WORLD_RADIUS, WORLD_RADIUS)
            if (q, r) in hexes and hexes[(q, r)].terrain == "grass":
                dist = axial_distance(0, 0, q, r)
                if dist > 6:
                    hexes[(q, r)].terrain = "forest"
    
    # Buildings placement logic
    center_hexes = [(q, r) for q, r in hexes.keys() if axial_distance(0, 0, q, r) <= 4]
    water_hexes = [(q, r) for q, r in hexes.keys() if hexes[(q, r)].terrain == "water"]
    outskirt_hexes = [(q, r) for q, r in hexes.keys() if 8 <= axial_distance(0, 0, q, r) <= 18]
    
    building_queue = [
        ("inn", "road"), ("tavern", "road"), ("temple", "center"),
        ("market", "center"), ("well", "center"),
    ]
    
    if water_hexes:
        building_queue.append(("mill", "water"))
        building_queue.append(("dock", "water"))
    
    building_queue.extend([("smithy", "road"), ("chapel", "center")])
    for _ in range(12): building_queue.append(("house", "road"))
    building_queue.extend([("stable", "outskirts"), ("farm", "outskirts"), ("farm", "outskirts")])
    
    for building_type, preference in building_queue:
        candidates = []
        if preference == "center":
            candidates = [pos for pos in center_hexes if hexes[pos].building is None and hexes[pos].terrain == "grass"]
        elif preference == "road":
            candidates = [pos for pos in road_hexes if hexes[pos].building is None]
        elif preference == "water":
            for water_pos in water_hexes:
                for dq, dr in [(1, 0), (-1, 0), (0, 1), (0, -1), (1, -1), (-1, 1)]:
                    adj_pos = (water_pos[0] + dq, water_pos[1] + dr)
                    if adj_pos in hexes and hexes[adj_pos].building is None and hexes[adj_pos].terrain != "water":
                        candidates.append(adj_pos)
        elif preference == "outskirts":
            candidates = [pos for pos in outskirt_hexes if hexes[pos].building is None and hexes[pos].terrain != "water"]
        
        if candidates:
            pos = random.choice(candidates)
            name = generate_building_name(building_type)
            building = Building(pos, building_type, name)
            buildings.append(building)
            hexes[pos].building = building
    
    return hexes, buildings

# --- Rendering ---
def generate_parchment_bg(width, height):
    surface = pygame.Surface((width, height))
    surface.fill(COLOR_PARCHMENT)
    for _ in range(int(width * height / 200)): # Density scaling
        x, y = random.randint(0, width-1), random.randint(0, height-1)
        c = random.randint(10, 20)
        orig = surface.get_at((x,y))
        new_color = (max(0, orig.r - c), max(0, orig.g - c), max(0, orig.b - c))
        surface.set_at((x, y), new_color)
    return surface

def render_village(hexes, buildings, camera_x, camera_y, hex_size, target_surface):
    font_name = pygame.font.Font(None, int(hex_size * 0.75))
    
    surf_w, surf_h = target_surface.get_size()
    
    # 1. Draw Hexes
    for (q, r), hex_obj in hexes.items():
        x, y = axial_to_pixel(q, r, hex_size)
        
        draw_x = x - camera_x
        draw_y = y - camera_y
        
        # Culling
        if draw_x < -hex_size*2 or draw_x > surf_w + hex_size*2: continue
        if draw_y < -hex_size*2 or draw_y > surf_h + hex_size*2: continue
        
        corners = get_hex_corners(draw_x, draw_y, hex_size)
        
        color = COLOR_GRASS
        if hex_obj.terrain == "water": color = COLOR_WATER
        elif hex_obj.terrain == "road": color = COLOR_ROAD
        elif hex_obj.terrain == "forest": color = COLOR_FOREST
        
        pygame.draw.polygon(target_surface, color, corners)
        pygame.draw.lines(target_surface, COLOR_INK, True, corners, 1)

    # 2. Draw Buildings
    for building in buildings:
        q, r = building.hex_pos
        x, y = axial_to_pixel(q, r, hex_size)
        draw_x = x - camera_x
        draw_y = y - camera_y
        
        if -50 < draw_x < surf_w + 50 and -50 < draw_y < surf_h + 50:
            building_info = BUILDING_TYPES.get(building.type, BUILDING_TYPES["house"])
            color = building_info["color"]
            
            size = hex_size * 0.6
            rect = pygame.Rect(draw_x - size/2, draw_y - size/2, size, size)
            pygame.draw.rect(target_surface, color, rect)
            pygame.draw.rect(target_surface, COLOR_INK, rect, 2)
            
            # Name tag
            name_surf = font_name.render(building.name, True, COLOR_INK, COLOR_PARCHMENT)
            name_rect = name_surf.get_rect(center=(draw_x, draw_y + hex_size))
            
            pygame.draw.rect(target_surface, COLOR_PARCHMENT, name_rect.inflate(4,2))
            target_surface.blit(name_surf, name_rect)

def render_minimap(hexes, buildings, camera_x, camera_y, current_hex_size):
    size = 200
    surf = pygame.Surface((size, size))
    surf.fill((200, 190, 170))
    
    # Scale world to fit minimap
    # We use a standard hex size for the math to determine the full world width
    scale = size / (WORLD_RADIUS * 2 * current_hex_size * 1.5)
    
    center_offset = size / 2
    
    for (q, r), hex_obj in hexes.items():
        x, y = axial_to_pixel(q, r, current_hex_size)
        mx = int(x * scale + center_offset)
        my = int(y * scale + center_offset)
        
        if 0 <= mx < size and 0 <= my < size:
            if hex_obj.terrain == "water":
                surf.set_at((mx, my), (100, 150, 200))
                if mx + 1 < size: surf.set_at((mx+1, my), (100, 150, 200))
            elif hex_obj.terrain == "road":
                 surf.set_at((mx, my), (150, 130, 100))
            elif hex_obj.building:
                pygame.draw.circle(surf, (200, 50, 50), (mx, my), 2)
            elif hex_obj.terrain == "forest":
                 surf.set_at((mx, my), COLOR_FOREST)
    
    # Camera indicator
    cx = int((camera_x) * scale + center_offset)
    cy = int((camera_y) * scale + center_offset)
    cw = int(WIN_WIDTH_PX * scale)
    ch = int(WIN_HEIGHT_PX * scale)
    
    pygame.draw.rect(surf, (255, 0, 0), (cx, cy, cw, ch), 1)
    
    return surf

# --- Main Game Loop ---

def main():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("MegaVillage Generator")
    clock = pygame.time.Clock()
    
    font = pygame.font.Font(None, 32)
    font_small = pygame.font.Font(None, 24)

    camera_x = -WIN_WIDTH_PX // 2
    camera_y = -WIN_HEIGHT_PX // 2
    
    # DYNAMIC ZOOM
    current_hex_size = 25
    
    show_minimap = True
    bg_surface = generate_parchment_bg(WIN_WIDTH_PX, WIN_HEIGHT_PX)
    
    village_hexes = None
    village_buildings = None
    village_theme = "Unnamed Village"
    biome = "Plain"
    
    running = True
    
    while running:
        # Event Handling
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            
            if event.type == pygame.KEYDOWN:
                # [N] New Village
                if event.key == pygame.K_n:
                    b_choice, w_choice = pygame_terrain_modal(screen)
                    if b_choice:
                        screen.fill(COLOR_INK)
                        loading = font.render(f"Generating {b_choice}...", True, COLOR_PARCHMENT)
                        screen.blit(loading, (SCREEN_WIDTH//2-100, SCREEN_HEIGHT//2))
                        pygame.display.flip()
                        
                        biome = b_choice
                        village_theme = f"{b_choice}"
                        village_hexes, village_buildings = generate_village(b_choice, w_choice)
                        
                        camera_x = -WIN_WIDTH_PX // 2
                        camera_y = -WIN_HEIGHT_PX // 2
                        current_hex_size = 25
                        print(f"Generated {len(village_buildings)} buildings.")

                # [M] Minimap
                elif event.key == pygame.K_m:
                    show_minimap = not show_minimap
                
                # ZOOM KEYS [ and ]
                elif event.key == pygame.K_LEFTBRACKET:
                    current_hex_size = max(10, current_hex_size - 2)
                elif event.key == pygame.K_RIGHTBRACKET:
                    current_hex_size = min(40, current_hex_size + 2)
                
                # [S] SUPER SAVE
                elif event.key == pygame.K_s and village_hexes:
                    screen.fill(COLOR_INK)
                    msg = font.render("Rendering High-Res Map...", True, COLOR_PARCHMENT)
                    screen.blit(msg, (SCREEN_WIDTH//2-100, SCREEN_HEIGHT//2))
                    pygame.display.flip()
                    
                    # 1. Create massive surface
                    super_size = 4500
                    super_surf = pygame.Surface((super_size, super_size))
                    super_surf.fill(COLOR_PARCHMENT) # Flat fill to save noise gen time
                    
                    # 2. Render with large hexes to fill space
                    # Radius 25 * 2 = 50 hex width. 4500 / 50 = 90px per hex max. 
                    # Let's use 60px to be safe and leave margin.
                    save_hex_size = 60 
                    
                    # Center the camera on this new surface
                    # We want (0,0) world to be at (2250, 2250)
                    save_cam_x = -(super_size // 2)
                    save_cam_y = -(super_size // 2)
                    
                    render_village(village_hexes, village_buildings, save_cam_x, save_cam_y, save_hex_size, super_surf)
                    
                    # 3. Downscale
                    final_size = 1200
                    final_surf = pygame.transform.smoothscale(super_surf, (final_size, final_size))
                    
                    # 4. Save
                    fname = f"village_{get_sanitized_filename(village_theme)}.png"
                    pygame.image.save(final_surf, fname)
                    print(f"Saved High-Res Map to {fname}")

                # [G] Generate AI Guide
                elif event.key == pygame.K_g and village_hexes and village_buildings:
                    if GEMINI_API_KEY:
                        screen.fill(COLOR_INK)
                        loading = font.render("Asking AI to write guide... (Check Console)", True, COLOR_PARCHMENT)
                        screen.blit(loading, (SCREEN_WIDTH//2-200, SCREEN_HEIGHT//2))
                        pygame.display.flip()
                        
                        # Use current view for the guide reference
                        temp_surf = bg_surface.copy()
                        render_village(village_hexes, village_buildings, camera_x, camera_y, current_hex_size, temp_surf)
                        create_village_guide_with_gemini(village_buildings, village_theme, biome, temp_surf)
                    else:
                        print("No GEMINI_API_KEY found.")

        # Camera Movement
        keys = pygame.key.get_pressed()
        speed = 15 if keys[pygame.K_LSHIFT] else 8
        
        if keys[pygame.K_LEFT]: camera_x -= speed
        if keys[pygame.K_RIGHT]: camera_x += speed
        if keys[pygame.K_UP]: camera_y -= speed
        if keys[pygame.K_DOWN]: camera_y += speed
        
        # --- Drawing ---
        screen.fill(COLOR_INK)
        
        if village_hexes:
            # Draw Viewport onto background copy
            view_surface = bg_surface.copy()
            render_village(village_hexes, village_buildings, camera_x, camera_y, current_hex_size, view_surface)
            screen.blit(view_surface, (0, 0))
        else:
            screen.blit(bg_surface, (0,0))
            welcome = font.render("Press [N] to Create New Village", True, COLOR_INK)
            welcome_rect = welcome.get_rect(center=(WIN_WIDTH_PX//2, WIN_HEIGHT_PX//2))
            screen.blit(welcome, welcome_rect)
        
        # UI Panel
        ui_rect = pygame.Rect(WIN_WIDTH_PX, 0, UI_WIDTH, SCREEN_HEIGHT)
        pygame.draw.rect(screen, (50, 40, 30), ui_rect)
        pygame.draw.line(screen, COLOR_PARCHMENT, (WIN_WIDTH_PX, 0), (WIN_WIDTH_PX, SCREEN_HEIGHT), 2)
        
        # Minimap
        if show_minimap and village_hexes:
            minimap = render_minimap(village_hexes, village_buildings, camera_x, camera_y, current_hex_size)
            mm_x = WIN_WIDTH_PX + (UI_WIDTH - minimap.get_width()) // 2
            screen.blit(minimap, (mm_x, 20))
        
        # UI Text
        y_off = 240 if show_minimap else 20
        screen.blit(font.render("Village Generator", True, COLOR_PARCHMENT), (WIN_WIDTH_PX + 20, y_off))
        
        if village_hexes:
            screen.blit(font_small.render(f"Theme: {village_theme}", True, (150, 200, 150)), (WIN_WIDTH_PX + 20, y_off + 35))
            screen.blit(font_small.render(f"Bldgs: {len(village_buildings)}", True, (150, 150, 150)), (WIN_WIDTH_PX + 20, y_off + 60))
            screen.blit(font_small.render(f"Zoom: {current_hex_size}px", True, (200, 200, 100)), (WIN_WIDTH_PX + 20, y_off + 85))

        # Controls Help
        help_y = y_off + 120
        controls = [
            ("ARROWS", "Move Camera"),
            ("[ ]", "Zoom In/Out"),
            ("SHIFT", "Move Faster"),
            ("[N]", "New Village"),
            ("[M]", "Toggle Map"),
            ("[S]", "Save HQ Map"),
            ("[G]", "AI Guide (API)")
        ]
        
        for key, desc in controls:
            screen.blit(font_small.render(key, True, COLOR_PARCHMENT), (WIN_WIDTH_PX + 20, help_y))
            screen.blit(font_small.render(desc, True, (180, 180, 180)), (WIN_WIDTH_PX + 120, help_y))
            help_y += 30
        
        pygame.display.flip()
        clock.tick(60)
    
    pygame.quit()

if __name__ == '__main__':
    main()