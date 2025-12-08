import pygame
import json
import math
import random
from codex_engine.controllers.base_controller import BaseController
from codex_engine.ui.renderers.grid_strategy import GridMapStrategy
from codex_engine.ui.widgets import Button
from codex_engine.ui.info_panel import InfoPanel
from codex_engine.content.managers import TacticalContent
from codex_engine.core.ai_manager import AIManager
from codex_engine.config import SCREEN_WIDTH, SCREEN_HEIGHT

# AESTHETICS FROM mega_dungeon.py
COLOR_PARCHMENT = (245, 235, 215)
COLOR_INK = (40, 30, 20)
COLOR_GRID = (220, 210, 190)
LINE_THICKNESS = 3
HATCH_SPACING = 12

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

class TacticalController(BaseController):
    def __init__(self, db_manager, node_data, theme_manager):
        super().__init__(db_manager, node_data, theme_manager)
        
        self.ai = AIManager()
        self.render_strategy = GridMapStrategy(self.node, self.theme)
        
        self.grid_data = self.node['geometry_data']['grid']
        self.markers = self.db.get_markers(self.node['id'])
        self.rooms = [pygame.Rect(r) for r in self.node['geometry_data'].get('rooms', [])]
        
        self.active_brush = 1
        self.painting = False
        self.active_tab = "TOOLS"
        self.hovered_marker = None
        
        self.font_ui = pygame.font.Font(None, 24)
        self.font_small = pygame.font.Font(None, 20)
        
        self.content_manager = TacticalContent(self.db, self.node)
        self.info_panel = InfoPanel(self.content_manager, self.db, self.node, self.font_ui, self.font_small)
        
        self.static_map_surf = None
        self._render_static_map()
        
        self._init_ui()

    def _init_ui(self):
        self.btn_back = Button(20, 50, 60, 25, "<- Up", self.font_ui, (80,80,90), (100,100,120), (255,255,255), self._go_up_level)
        tab_y = 90
        self.btn_tab_tools = Button(20, tab_y, 70, 30, "Build", self.font_ui, (60,60,70), (80,80,90), (255,255,255), lambda: self._set_tab("TOOLS"))
        self.btn_tab_info = Button(95, tab_y, 70, 30, "Info", self.font_ui, (60,60,70), (80,80,90), (255,255,255), lambda: self._set_tab("INFO"))
        self.btn_tab_config = Button(170, tab_y, 70, 30, "Setup", self.font_ui, (60,60,70), (80,80,90), (255,255,255), lambda: self._set_tab("CONFIG"))

        self.brushes = [(20, 140, "Floor", 1), (100, 140, "Corridor", 2), (20, 180, "Void", 0)]
        self.brush_buttons = []
        for x, y, lbl, val in self.brushes:
            btn = Button(x, y, 70, 30, lbl, self.font_ui, (100,100,100), (150,150,150), (255,255,255), lambda v=val: self._set_brush(v))
            self.brush_buttons.append(btn)
            
        self.btn_reset_view = Button(20, 140, 220, 30, "Reset View", self.font_ui, (100,150,200), (150,200,250), (255,255,255), self._reset_view)
        self.btn_regen = Button(20, 180, 220, 30, "Regenerate Layout", self.font_ui, (150,100,100), (200,150,150), (255,255,255), self._regenerate_map)
        #self.btn_gen_details = Button(20, 220, 220, 30, "AI Gen Content", self.font_ui, (100,100,200), (150,150,250), (255,255,255), self._generate_ai_details)
        self.btn_gen_details = Button(20, 220, 220, 30, "AI Gen Content", self.font_ui, (100,100,200), (150,150,250), (255,255,255), None)

    def _set_tab(self, t): self.active_tab = t
    def _set_brush(self, val): self.active_brush = val
    def _go_up_level(self): return {"action": "go_up_level"}

    def update(self):
        self.widgets = [self.btn_back, self.btn_tab_tools, self.btn_tab_info, self.btn_tab_config]
        ac, ic = (100, 100, 120), (60, 60, 70)
        self.btn_tab_tools.base_color = ac if self.active_tab == "TOOLS" else ic
        self.btn_tab_info.base_color = ac if self.active_tab == "INFO" else ic
        self.btn_tab_config.base_color = ac if self.active_tab == "CONFIG" else ic
        
        if self.active_tab == "TOOLS":
            self.widgets.extend(self.brush_buttons)
        elif self.active_tab == "INFO":
            self.widgets.extend(self.info_panel.widgets)
        elif self.active_tab == "CONFIG":
            self.widgets.extend([self.btn_reset_view, self.btn_regen, self.btn_gen_details])
            
    def handle_input(self, event, cam_x, cam_y, zoom):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.btn_gen_details in self.widgets and self.btn_gen_details.rect.collidepoint(event.pos):
                return self._generate_ai_details(cam_x, cam_y, zoom)

        for w in self.widgets:
            res = w.handle_event(event)
            if res: 
                if isinstance(res, dict): return res
                return None

        if self.active_tab == "INFO" and self.info_panel.handle_event(event): return None

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if event.pos[0] > 260:
                if self.active_tab == "TOOLS":
                    self.painting = True
                    self._paint_tile(event.pos, cam_x, cam_y, zoom)
                else: 
                    return {"action": "click_zoom"}
        
        if event.type == pygame.MOUSEBUTTONUP: self.painting = False
        if event.type == pygame.MOUSEMOTION and self.painting: self._paint_tile(event.pos, cam_x, cam_y, zoom)
        return None
        
    def _paint_tile(self, screen_pos, cam_x, cam_y, zoom):
        center_x, center_y = SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2
        sc = self.render_strategy.cell_size * zoom
        c = int((screen_pos[0] - center_x) / sc + cam_x)
        r = int((screen_pos[1] - center_y) / sc + cam_y)
        if 0 <= c < self.render_strategy.width and 0 <= r < self.render_strategy.height:
            if self.grid_data[r][c] != self.active_brush:
                self.grid_data[r][c] = self.active_brush
                self._render_static_map()

    def _get_visible_markers(self, cam_x, cam_y, zoom):
        visible = []
        sc = self.render_strategy.cell_size * zoom
        view_w = (SCREEN_WIDTH - 260) / sc 
        view_h = SCREEN_HEIGHT / sc
        
        view_rect = pygame.Rect(cam_x - view_w/2, cam_y - view_h/2, view_w, view_h)

        for marker in self.markers:
            if view_rect.collidepoint(marker['world_x'], marker['world_y']):
                visible.append(marker)
        return visible

    def _generate_ai_details(self, cam_x, cam_y, zoom):
        # This is now the only required import for this function
        from codex_engine.ui.editors import get_text_input
        
        # 1. GET USER INPUT FOR THEME
        theme_prompt = get_text_input("Enter a theme for these rooms (e.g., 'Flooded Crypt'):")
        if not theme_prompt or not theme_prompt.strip():
            print("AI generation cancelled.")
            return None # Abort if user cancels or enters nothing

        # 2. GATHER CONTEXT (same as before)
        visible_markers = self._get_visible_markers(cam_x, cam_y, zoom)
        if not visible_markers:
            print("No rooms visible to describe.")
            return None

        parent = self.db.get_node(self.node['parent_node_id'])
        parent_context = f"This location, '{self.node['name']}', is part of '{parent['name']}'."
        
        room_list_str = "\n".join([f"- {m['title']}: (Current: '{m['description']}')" for m in visible_markers])

        # 3. BUILD AND SEND PROMPT (with theme)
        prompt = f"""
        Role: TTRPG Dungeon Designer, be concise and evocative.
        Context: {parent_context}
        Theme: "{theme_prompt}"
        Task: Enhance the descriptions for the visible rooms based on the theme. Do not change room names.
        
        Rooms:
        {room_list_str}
        
        Return a single JSON object where keys are room titles and values are the new descriptions.
        """
        schema = '{"Room 1": "description...", "Room 2": "..."}'
        response = self.ai.generate_json(prompt, schema)

        # 4. PERSIST RESPONSE (same as before)
        if response:
            print("AI response received, updating room descriptions...")
            self.db.update_node_data(self.node['id'], metadata=response)
            for marker in self.markers:
                if marker['title'] in response:
                    new_desc = response[marker['title']]
                    self.db.update_marker(marker['id'], description=new_desc)
            return {"action": "reload_node"}
        return None

    def _generate_ai_details_old(self):
        room_markers = [m for m in self.markers if m['symbol'] == 'room_number']
        map_desc = f"Dungeon Level: {self.node['name']}\nTotal Rooms: {len(room_markers)}\n"
        for m in room_markers: map_desc += f"- {m['title']}\n"
        
        prompt = f"""
        Role: TTRPG Dungeon Designer.
        Topic: "Populate a dungeon level with descriptions."
        Context: The following rooms exist in the level '{self.node['name']}'. 
        Provide a short, atmospheric description for each room.
        Map Data: {map_desc}
        
        Return a single JSON object where keys are room titles (e.g., "Room 1") 
        and values are the string descriptions. Example: {{"Room 1": "A dusty crypt...", "Room 2": "..."}}
        """
        schema = '{"Room 1": "description...", "Room 2": "..."}'
        response = self.ai.generate_json(prompt, schema)
        if response:
            for marker in self.markers:
                if marker['title'] in response:
                    self.db.update_marker(marker['id'], description=response[marker['title']])
            return {"action": "reload_node"}
        return None

    def _reset_view(self): return {"action": "reset_view"}
    def _regenerate_map(self): return {"action": "regenerate_tactical"}

    def _render_static_map(self):
        """EXACT COPY OF mega_dungeon.py render_viewport logic"""
        sc = self.render_strategy.cell_size
        map_w = self.render_strategy.width * sc
        map_h = self.render_strategy.height * sc
        self.static_map_surf = pygame.Surface((map_w, map_h))
        self.static_map_surf.fill(COLOR_PARCHMENT)
        
        # Texture noise
        for _ in range(5000):
            x, y = random.randint(0, map_w-1), random.randint(0, map_h-1)
            c = random.randint(10, 20)
            self.static_map_surf.set_at((x, y), tuple(max(0, val - c) for val in COLOR_PARCHMENT))

        # Hatching for rooms
        for r in self.rooms:
            screen_rect = pygame.Rect(r.x * sc, r.y * sc, r.width * sc, r.height * sc)
            for i in range(screen_rect.left - screen_rect.height, screen_rect.right, HATCH_SPACING):
                start_pos = (i, screen_rect.top)
                end_pos = (i + screen_rect.height, screen_rect.bottom)
                clipped = screen_rect.clipline(start_pos, end_pos)
                if clipped: pygame.draw.aaline(self.static_map_surf, (225, 215, 195), clipped[0], clipped[1])

        # Grid & Walls - EXACT SAME LOOP STRUCTURE AS ORIGINAL
        for y in range(self.render_strategy.height):
            for x in range(self.render_strategy.width):
                sx, sy = x * sc, y * sc
                
                # Grid lines for all non-void
                if self.grid_data[y][x] > 0:
                    pygame.draw.rect(self.static_map_surf, COLOR_GRID, (sx, sy, sc, sc), 1)
                
                # Walls for all non-void (separate condition just like original)
                if self.grid_data[y][x] != 0:
                    if y == 0 or self.grid_data[y-1][x] == 0: 
                        draw_hand_drawn_line(self.static_map_surf, (sx, sy), (sx+sc, sy), COLOR_INK, LINE_THICKNESS)
                    if y == self.render_strategy.height-1 or self.grid_data[y+1][x] == 0: 
                        draw_hand_drawn_line(self.static_map_surf, (sx, sy+sc), (sx+sc, sy+sc), COLOR_INK, LINE_THICKNESS)
                    if x == 0 or self.grid_data[y][x-1] == 0: 
                        draw_hand_drawn_line(self.static_map_surf, (sx, sy), (sx, sy+sc), COLOR_INK, LINE_THICKNESS)
                    if x == self.render_strategy.width-1 or self.grid_data[y][x+1] == 0: 
                        draw_hand_drawn_line(self.static_map_surf, (sx+sc, sy), (sx+sc, sy+sc), COLOR_INK, LINE_THICKNESS)

    def draw_map(self, screen, cam_x, cam_y, zoom, screen_w, screen_h):
        center_x, center_y = screen_w // 2, screen_h // 2
        sc = self.render_strategy.cell_size

        scaled_w = int(self.static_map_surf.get_width() * zoom)
        scaled_h = int(self.static_map_surf.get_height() * zoom)
        
        draw_x = center_x - (cam_x * sc * zoom)
        draw_y = center_y - (cam_y * sc * zoom)
        
        if scaled_w > 0 and scaled_h > 0:
            scaled_surf = pygame.transform.scale(self.static_map_surf, (scaled_w, scaled_h))
            screen.blit(scaled_surf, (draw_x, draw_y))

    def draw_overlays(self, screen, cam_x, cam_y, zoom):
        if self.active_tab == "INFO": self.info_panel.draw(screen)
        self._draw_markers(screen, cam_x, cam_y, zoom)
        if self.hovered_marker: self._draw_tooltip(screen, pygame.mouse.get_pos())
    
    def _draw_markers(self, screen, cam_x, cam_y, zoom):
        center_x, center_y = SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2
        sc = self.render_strategy.cell_size * zoom
        mouse_pos = pygame.mouse.get_pos()
        self.hovered_marker = None
        
        font_size = max(8, int(40 * zoom))
        try:
            font_room_num = pygame.font.Font(None, font_size)
        except pygame.error:
            font_room_num = self.font_small

        for m in self.markers:
            sx = center_x + (m['world_x'] - cam_x) * sc
            sy = center_y + (m['world_y'] - cam_y) * sc
            if not (-sc <= sx <= SCREEN_WIDTH + sc and -sc <= sy <= SCREEN_HEIGHT + sc): continue
            
            surf = font_room_num.render(m['title'], True, COLOR_INK)
            rect = surf.get_rect(topleft=(sx, sy))
            
            hover_rect = rect.inflate(10, 10) 
            if hover_rect.collidepoint(mouse_pos): self.hovered_marker = m
            screen.blit(surf, rect)

    def _draw_tooltip(self, screen, pos):
        m = self.hovered_marker
        
        # FIX: Wrap the description text
        import textwrap
        wrapped_lines = textwrap.wrap(m.get('description', 'No details'), width=40)
        
        rendered = [self.font_small.render(l, True, (20,20,20)) for l in wrapped_lines]
        mw = max(s.get_width() for s in rendered) if rendered else 0
        mh = sum(s.get_height() for s in rendered) + 10
        
        bg_rect = pygame.Rect(pos[0]+15, pos[1]+15, mw+20, mh)
        if bg_rect.right > SCREEN_WIDTH: bg_rect.x -= (bg_rect.width+30)
        
        pygame.draw.rect(screen, COLOR_PARCHMENT, bg_rect)
        pygame.draw.rect(screen, COLOR_INK, bg_rect, 1)
        
        y_off = 5
        for s in rendered:
            screen.blit(s, (bg_rect.x+10, bg_rect.y+y_off))
            y_off += s.get_height()
            
    def _draw_tooltip_broke(self, screen, pos):
        m = self.hovered_marker
        lines = m.get('description', 'No details').split('\n')
        
        rendered = [self.font_small.render(l, True, (20,20,20)) for l in lines]
        mw = max(s.get_width() for s in rendered) if rendered else 0
        mh = sum(s.get_height() for s in rendered) + 10
        
        bg_rect = pygame.Rect(pos[0]+15, pos[1]+15, mw+20, mh)
        if bg_rect.right > SCREEN_WIDTH: bg_rect.x -= (bg_rect.width+30)
        
        pygame.draw.rect(screen, COLOR_PARCHMENT, bg_rect)
        pygame.draw.rect(screen, COLOR_INK, bg_rect, 1)
        
        y_off = 5
        for s in rendered:
            screen.blit(s, (bg_rect.x+10, bg_rect.y+y_off))
            y_off += s.get_height()

    def get_metadata_updates(self):
        return {}

    def cleanup(self):
        print(f"CLEANUP: Saving grid geometry for node {self.node['id']}")
        self.db.update_node_data(
            self.node['id'], 
            geometry={
                "grid": self.grid_data, 
                "width": self.render_strategy.width, 
                "height": self.render_strategy.height,
                "rooms": [list(r) for r in self.rooms]
            }
        )
