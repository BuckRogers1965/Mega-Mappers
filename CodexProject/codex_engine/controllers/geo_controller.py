
import pygame
import math
import json
from codex_engine.controllers.base_controller import BaseController
from codex_engine.ui.renderers.image_strategy import ImageMapStrategy
from codex_engine.ui.widgets import Slider, Button, ContextMenu
from codex_engine.ui.editors import NativeMarkerEditor
from codex_engine.ui.info_panel import InfoPanel
from codex_engine.content.managers import WorldContent, LocalContent
from codex_engine.generators.world_gen import WorldGenerator
from codex_engine.generators.local_gen import LocalGenerator 
from codex_engine.generators.village_manager import VillageContentManager
from codex_engine.core.ai_manager import AIManager
from codex_engine.config import SCREEN_WIDTH, SCREEN_HEIGHT, SIDEBAR_WIDTH

COLOR_RIVER = (80, 120, 255)
COLOR_ROAD = (160, 82, 45)

class GeoController(BaseController):
    def __init__(self, db_manager, node_data, theme_manager):
        super().__init__(db_manager, node_data, theme_manager)

        self.zoom_factor = 1.05
        self.ai = AIManager()
        
        if self.node['type'] == 'world_map':
            self.content_manager = WorldContent(self.db, self.node)
        else:
            self.content_manager = LocalContent(self.db, self.node)
        
        self.render_strategy = None
        if 'file_path' in self.node['metadata']:
            self.render_strategy = ImageMapStrategy(self.node['metadata'], self.theme)
            
        self.vectors = self.db.get_vectors(self.node['id'])
        self.markers = self.db.get_markers(self.node['id'])
        
        self.active_vector = None
        self.selected_point_idx = None
        self.dragging_point = False
        self.selected_marker = None
        self.hovered_marker = None
        
        self.dragging_map = False
        self.dragging_marker = None
        self.drag_start_pos = (0, 0)
        self.drag_start_cam = (0, 0)
        self.drag_offset = (0, 0)
        self.context_menu = None
        
        self.pending_click_pos = None
        
        self.show_grid = True
        self.grid_type = "HEX"
        self.grid_size = self.node['metadata'].get('grid_size', 64)

        self.active_tab = "INFO" 

        self.font_ui = pygame.font.Font(None, 24)
        self.font_small = pygame.font.Font(None, 20)
        
        self.info_panel = InfoPanel(self.content_manager, self.db, self.node, self.font_ui, self.font_small)
        self._init_ui()

    def _init_ui(self):
        meta = self.node['metadata']
        full_w = SIDEBAR_WIDTH - 40
        half_w = (full_w // 2) - 5
        
        self.btn_back = Button(20, 50, 60, 25, "<- Up", self.font_ui, (80,80,90), (100,100,120), (255,255,255), self._go_up_level)
        
        tab_y = 90; tab_w = full_w // 3
        self.btn_tab_info   = Button(20, tab_y, tab_w, 30, "Info", self.font_ui, (60,60,70), (80,80,90), (255,255,255), lambda: self._set_tab("INFO"))
        self.btn_tab_tools  = Button(20+tab_w, tab_y, tab_w, 30, "Tools", self.font_ui, (60,60,70), (80,80,90), (255,255,255), lambda: self._set_tab("TOOLS"))
        self.btn_tab_config = Button(20+(tab_w*2), tab_y, tab_w, 30, "Setup", self.font_ui, (60,60,70), (80,80,90), (255,255,255), lambda: self._set_tab("CONFIG"))

        self.btn_new_road   = Button(20, 140, half_w, 30, "+ Road", self.font_ui, (139,69,19), (160,82,45), (255,255,255), lambda: self.start_new_vector("road"))
        self.btn_new_river  = Button(20+half_w+10, 140, half_w, 30, "+ River", self.font_ui, (40,60,150), (60,80,180), (255,255,255), lambda: self.start_new_vector("river"))
        self.btn_save_vec   = Button(20, 140, full_w, 30, "Save Line", self.font_ui, (50,150,50), (80,200,80), (255,255,255), self.save_active_vector)
        self.btn_cancel_vec = Button(20, 180, half_w, 30, "Cancel", self.font_ui, (150,50,50), (200,80,80), (255,255,255), self.cancel_vector)
        self.btn_delete_vec = Button(20+half_w+10, 180, half_w, 30, "Delete", self.font_ui, (100,0,0), (150,0,0), (255,255,255), self.delete_vector)

        self.slider_water = Slider(20, 140, full_w, 15, -11000.0, 9000.0, meta.get('sea_level', 0.0), "Sea Level (m)")
        self.slider_azimuth = Slider(20, 180, full_w, 15, 0, 360, meta.get('light_azimuth', 315), "Light Dir")
        self.slider_altitude = Slider(20, 220, full_w, 15, 0, 90, meta.get('light_altitude', 45), "Light Height")
        self.slider_intensity = Slider(20, 260, full_w, 15, 0.0, 2.0, 1.2, "Light Power")
        self.slider_contour = Slider(20, 300, full_w, 15, 0, 500, meta.get('contour_interval', 0), "Contours (m)")
        
        self.btn_grid_minus = Button(140, 340, 30, 30, "-", self.font_ui, (100,100,100), (150,150,150), (255,255,255), self.dec_grid)
        self.btn_grid_plus = Button(180, 340, 30, 30, "+", self.font_ui, (100,100,100), (150,150,150), (255,255,255), self.inc_grid)
        self.btn_regen = Button(20, 380, full_w, 30, "Regenerate Map", self.font_ui, (100, 100, 100), (150, 150, 150), (255,255,255), self.regenerate_seed)
        self.btn_gen_details = Button(20, 420, full_w, 30, "AI Gen Content", self.font_ui, (100, 100, 200), (150, 150, 250), (255,255,255), self._generate_ai_details)

    def _set_tab(self, tab_name): self.active_tab = tab_name

    def update(self):
        self.widgets = []
        if self.node.get('parent_node_id'): self.widgets.append(self.btn_back)
        self.widgets.extend([self.btn_tab_tools, self.btn_tab_info, self.btn_tab_config])
        
        ac, ic = (100, 100, 120), (60, 60, 70)
        self.btn_tab_tools.base_color = ac if self.active_tab == "TOOLS" else ic
        self.btn_tab_info.base_color = ac if self.active_tab == "INFO" else ic
        self.btn_tab_config.base_color = ac if self.active_tab == "CONFIG" else ic

        if self.active_tab == "CONFIG":
            self.widgets.extend([self.slider_water, self.slider_azimuth, self.slider_altitude, self.slider_intensity, self.slider_contour, self.btn_grid_minus, self.btn_grid_plus, self.btn_regen, self.btn_gen_details])
        elif self.active_tab == "TOOLS":
            if self.active_vector: self.widgets.extend([self.btn_save_vec, self.btn_cancel_vec]); 
            if self.active_vector and self.active_vector.get('id'): self.widgets.append(self.btn_delete_vec)
            else: self.widgets.extend([self.btn_new_road, self.btn_new_river])
        elif self.active_tab == "INFO": self.widgets.extend(self.info_panel.widgets)

        if self.render_strategy:
            self.render_strategy.set_light_direction(self.slider_azimuth.value, self.slider_altitude.value)
            self.render_strategy.set_light_intensity(self.slider_intensity.value)



    def handle_input(self, event, cam_x, cam_y, zoom):
        # Universal Input (Widgets, Context Menu, Global Keys)
        if self.context_menu:
            if self.context_menu.handle_event(event): self.context_menu = None
            return None
        for widget in self.widgets:
            res = widget.handle_event(event)
            if res: return res if isinstance(res, dict) else None
        if self.active_tab == "INFO" and self.info_panel.handle_event(event): return None
        if event.type == pygame.KEYDOWN and event.key == pygame.K_DELETE and self.selected_point_idx is not None:
            if self.active_vector and 0 <= self.selected_point_idx < len(self.active_vector['points']):
                del self.active_vector['points'][self.selected_point_idx]
                self.selected_point_idx = None; return None

        center_x, center_y = SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2
        
        # MOUSE MOTION
        if event.type == pygame.MOUSEMOTION:
            world_x = ((event.pos[0] - center_x) / zoom) + cam_x
            world_y = ((event.pos[1] - center_y) / zoom) + cam_y
            if self.dragging_point and self.selected_point_idx is not None:
                self.active_vector['points'][self.selected_point_idx] = [world_x, world_y]; return None
            if self.dragging_marker:
                self.dragging_marker['world_x'] = world_x - self.drag_offset[0]
                self.dragging_marker['world_y'] = world_y - self.drag_offset[1]; return None
            if self.dragging_map:
                dx = event.pos[0] - self.drag_start_pos[0]; dy = event.pos[1] - self.drag_start_pos[1]
                return {"action": "pan", "pos": (self.drag_start_cam[0] - dx / zoom, self.drag_start_cam[1] - dy / zoom)}

        # MOUSE DOWN
        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.pos[0] < SIDEBAR_WIDTH: return None
            print(f"\n--- GEO: MOUSE DOWN at {event.pos} ---")
            print(f"  [State] Active Tab: {self.active_tab}, Hovered Marker: {self.hovered_marker['title'] if self.hovered_marker else 'None'}")
            world_x = ((event.pos[0] - center_x) / zoom) + cam_x
            world_y = ((event.pos[1] - center_y) / zoom) + cam_y

            if event.button == 1: # Left Click
                self.drag_start_pos = event.pos; self.drag_start_cam = (cam_x, cam_y)
                
                if self.active_vector:
                    print("  [Action] Vector editing in progress. Handling vector click.")
                    self._handle_vector_click(event, world_x, world_y, zoom)
                    return
                
                if self.hovered_marker:
                    print(f"  [Action] Clicked on hovered marker '{self.hovered_marker['title']}'.")
                    if self.active_tab == "TOOLS":
                        print("    -> In TOOLS tab. Starting marker drag.")
                        self.dragging_marker = self.hovered_marker
                        self.drag_offset = (world_x - self.hovered_marker['world_x'], world_y - self.hovered_marker['world_y'])
                    else:
                        print("    -> Not in TOOLS tab. Selecting marker for potential entry on mouse up.")
                    self.selected_marker = self.hovered_marker
                    return

                if self.active_tab == "TOOLS":
                    print("  [Action] In TOOLS tab, checking for vector pixel selection...")
                    if self._handle_pixel_selection(event, world_x, world_y, zoom):
                        return
                
                if pygame.key.get_mods() & pygame.KMOD_SHIFT:
                    print("  [Action] Shift key down. Creating new marker.")
                    self._create_new_marker(world_x, world_y)
                    return
                
                print("  [Action] Fallback: Starting map pan.")
                self.dragging_map = True

            elif event.button == 3: # Right Click
                self._open_context_menu(event)

        # MOUSE UP
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            drag_dist = math.hypot(event.pos[0] - self.drag_start_pos[0], event.pos[1] - self.drag_start_pos[1])

            if self.dragging_marker:
                print("\n--- GEO: MOUSE UP (DRAG END) ---")
                marker_being_dragged = self.dragging_marker
                print(f"  [1] Marker '{marker_being_dragged['title']}' drag ended. Dist: {drag_dist:.1f}")

                self.db.update_marker(marker_being_dragged['id'], world_x=marker_being_dragged['world_x'], world_y=marker_being_dragged['world_y'])
                self.markers = self.db.get_markers(self.node['id'])
                
                marker_being_dragged = self.dragging_marker
                is_view_marker = marker_being_dragged.get('metadata', {}).get('is_view_marker', False)
                is_active = marker_being_dragged.get('metadata', {}).get('is_active', False)
                print(f"  [2] Checking if moved marker is active view... is_view={is_view_marker}, is_active={is_active}")
                #if is_view_marker and is_active:
                if is_view_marker and is_active:
                    print("  [3] Action: Is active view marker. Returning 'update_player_view'.")
                    self.dragging_marker = None
                    return {"action": "update_player_view"}
            
            if self.hovered_marker and drag_dist < 5:
                print("\n--- GEO: MOUSE UP (SHORT CLICK) ---")
                print(f"  [1] Detected short click on '{self.hovered_marker['title']}'.")
                fresh_marker = next((m for m in self.markers if m['id'] == self.hovered_marker['id']), self.hovered_marker)
                print("  [2] Action: Returning 'enter_marker'.")
                return {"action": "enter_marker", "marker": fresh_marker}

            self.dragging_map = False
            self.dragging_point = False
            self.dragging_marker = None
        
        return None
        
    def _go_up_level(self): return {"action": "go_up_level"}
    def _open_context_menu(self, event):
        if self.hovered_marker:
            self.selected_marker = self.hovered_marker
            menu_options = [("Edit Details", self._open_edit_modal), ("", None), ("Delete Marker", self._delete_selected_marker), ("Center View", self._center_on_selected_marker)]
            self.context_menu = ContextMenu(event.pos[0], event.pos[1], menu_options, self.font_ui)
    
    def _handle_vector_click(self, event, wx, wy, zoom):
        center_x, center_y = SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2
        for i, pt in enumerate(self.active_vector['points']):
            sx, sy = center_x + (pt[0] - wx) * zoom, center_y + (pt[1] - wy) * zoom
            if math.hypot(sx - event.pos[0], sy - event.pos[1]) < 10:
                self.selected_point_idx, self.dragging_point = i, True
                return
        self.active_vector['points'].append([wx, wy])
        self.selected_point_idx = len(self.active_vector['points']) - 1
        self.dragging_point = True

    def _handle_pixel_selection(self, event, world_x, world_y, zoom):
        try:
            pixel = pygame.display.get_surface().get_at(event.pos)[:3]
            target_type = None
            if pixel == COLOR_ROAD: target_type = "road"
            elif pixel == COLOR_RIVER: target_type = "river"
            if target_type:
                closest, min_d = None, float('inf')
                for vec in self.vectors:
                    if vec['type'] != target_type: continue
                    for pt in vec['points']:
                        d = math.hypot(pt[0]-world_x, pt[1]-world_y)
                        if d < min_d: min_d, closest = d, vec
                if closest and min_d < (150 / zoom): 
                    self.active_vector = closest
                    self.selected_marker = None
                    return True
        except IndexError: pass
        return False

    def inc_grid(self): self.grid_size = min(256, self.grid_size + 8)
    def dec_grid(self): self.grid_size = max(16, self.grid_size - 8)

    def regenerate_seed(self):
        if self.node['type'] == 'world_map':
            gen = WorldGenerator(self.theme, self.db); gen.generate_world_node(self.node['campaign_id'])
            return {"action": "reload_node"}

    def start_new_vector(self, vtype): self.active_vector = {'points': [], 'type': vtype, 'width': 4 if vtype=='road' else 8, 'id': None}
    def save_active_vector(self):
        if self.active_vector and len(self.active_vector['points']) > 1: self.db.save_vector(self.node['id'], self.active_vector['type'], self.active_vector['points'], self.active_vector['width'], self.active_vector.get('id')); self.vectors = self.db.get_vectors(self.node['id'])
        self.active_vector = None
    def cancel_vector(self): self.active_vector = None
    def delete_vector(self):
        if self.active_vector and self.active_vector.get('id'):
            self.db.delete_vector(self.active_vector['id']); self.vectors = self.db.get_vectors(self.node['id'])
        self.active_vector = None

    def _open_edit_modal(self):
        if self.selected_marker: NativeMarkerEditor(self.selected_marker, self.node['type'], self._save_marker, self._handle_ai_gen_modal); self.markers = self.db.get_markers(self.node['id'])
    def _delete_selected_marker(self):
        if self.selected_marker: self.db.delete_marker(self.selected_marker['id']); self.markers = self.db.get_markers(self.node['id']); self.selected_marker = None
    def _center_on_selected_marker(self):
        if self.selected_marker: return {"action": "pan", "pos": (self.selected_marker['world_x'], self.selected_marker['world_y'])}
    def _save_marker(self, mid, sym, title, note, meta):
        if mid: self.db.update_marker(mid, world_x=self.selected_marker['world_x'], world_y=self.selected_marker['world_y'], symbol=sym, title=title, description=note, metadata=meta)
        else: self.db.add_marker(self.node['id'], self.pending_click_pos[0], self.pending_click_pos[1], sym, title, note, meta)
        self.markers = self.db.get_markers(self.node['id']); self.selected_marker = None
    def _handle_ai_gen_modal(self, mtype, title, context): return {} 

    def _generate_ai_details(self):
        if self.node['type'] == 'local_map':
            try: vm = VillageContentManager(self.node, self.db, self.ai); vm.generate_details(); return {"action": "reload_node"}
            except Exception as e: print(f"AI Error: {e}")

    def _create_new_marker(self, wx, wy):
        self.pending_click_pos = (wx, wy)
        new_marker = {'title': 'New Marker', 'description': '', 'metadata': {}, 'symbol': 'star'}
        NativeMarkerEditor(new_marker, self.node['type'], self._save_marker, self._handle_ai_gen_modal)
        self.markers = self.db.get_markers(self.node['id'])
        return {"action": "consumed"}

    def draw_map(self, screen, cam_x, cam_y, zoom, screen_w, screen_h):
        if self.render_strategy:
            self.render_strategy.draw(screen, cam_x, cam_y, zoom, screen_w, screen_h, self.slider_water.value, self.vectors, self.active_vector, self.selected_point_idx, self.slider_contour.value)
            if self.show_grid:
                cx, cy = screen_w//2, screen_h//2; msx, msy = cx-(cam_x*zoom), cy-(cam_y*zoom); mw, mh = self.render_strategy.width*zoom, self.render_strategy.height*zoom
                map_rect = pygame.Rect(msx, msy, mw, mh); screen.set_clip(map_rect)
                if self.grid_type == "HEX": self._draw_hex_grid(screen, msx, msy, zoom, screen_w, screen_h)
                else: self._draw_square_grid(screen, msx, msy, zoom, screen_w, screen_h)
                screen.set_clip(None); pygame.draw.rect(screen, (255, 255, 255), map_rect, 2)

    def draw_overlays(self, screen, cam_x, cam_y, zoom):
        self._draw_markers(screen, cam_x, cam_y, zoom)
        if self.active_tab == "INFO": self.info_panel.draw(screen)
        if self.hovered_marker and not self.dragging_marker and not self.context_menu:
             self._draw_tooltip(screen, pygame.mouse.get_pos())
        if self.context_menu:
            self.context_menu.draw(screen)

    def _draw_tooltip(self, screen, pos):
        m = self.hovered_marker; text = m.get('description', 'No details.')
        import textwrap
        wrapped_lines = textwrap.wrap(text, width=40)
        line_height = self.font_ui.get_height()
        bg_h = len(wrapped_lines) * line_height + 10
        bg_w = max(self.font_ui.size(line)[0] for line in wrapped_lines) + 20 if wrapped_lines else 100
        bg_rect = pygame.Rect(pos[0] + 15, pos[1] + 15, bg_w, bg_h)
        if bg_rect.right > SCREEN_WIDTH: bg_rect.right = pos[0] - 15
        if bg_rect.bottom > SCREEN_HEIGHT: bg_rect.bottom = pos[1] - 15
        pygame.draw.rect(screen, (20, 20, 30, 220), bg_rect)
        pygame.draw.rect(screen, (100, 100, 150), bg_rect, 1)
        y_off = 5
        for line in wrapped_lines:
            line_surf = self.font_ui.render(line, True, (200,200,200))
            screen.blit(line_surf, (bg_rect.x + 10, bg_rect.y + y_off))
            y_off += line_height

    def _draw_hex_grid(self, screen, start_x, start_y, zoom, sw, sh):
        hex_radius = self.grid_size * zoom;
        if hex_radius < 5: return
        hex_w = math.sqrt(3) * hex_radius; vert_spacing = (2 * hex_radius) * 0.75; screen_rel_x, screen_rel_y = -start_x, -start_y
        start_col = int(screen_rel_x/hex_w)-1; start_row = int(screen_rel_y/vert_spacing)-1; cols_vis = int(sw/hex_w)+3; rows_vis = int(sh/vert_spacing)+3; color = (255, 255, 255, 30)
        for r in range(start_row, start_row + rows_vis):
            for q in range(start_col, start_col + cols_vis):
                x_off = (r % 2) * (hex_w / 2); cx, cy = start_x+(q*hex_w)+x_off, start_y+(r*vert_spacing); points = []
                for i in range(6): angle = math.pi/3*i+(math.pi/6); points.append((cx+hex_radius*math.cos(angle), cy+hex_radius*math.sin(angle)))
                pygame.draw.lines(screen, color, True, points, 1)

    def _draw_square_grid(self, screen, start_x, start_y, zoom, sw, sh):
        size = self.grid_size * zoom; color = (255, 255, 255, 30);
        if size < 4: return
        map_w, map_h = self.render_strategy.width*zoom, self.render_strategy.height*zoom; x, y = start_x, start_y
        while x <= start_x+map_w:
            if 0<=x<=sw: pygame.draw.line(screen, color, (x,start_y), (x,start_y+map_h))
            x+=size
        while y <= start_y+map_h:
            if 0<=y<=sh: pygame.draw.line(screen, color, (start_x,y), (start_x+map_w,y))
            y+=size

    def _draw_markers(self, screen, cam_x, cam_y, zoom):
        center_x, center_y = SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2
        mouse_pos = pygame.mouse.get_pos()
        self.hovered_marker = None
        for m in self.markers:
            sx, sy = center_x+(m['world_x']-cam_x)*zoom, center_y+(m['world_y']-cam_y)*zoom
            if not (-50 <= sx <= SCREEN_WIDTH+50 and -50 <= sy <= SCREEN_HEIGHT+50): continue
            
            click_rect = pygame.Rect(sx-10, sy-10, 20, 20)
            if click_rect.collidepoint(mouse_pos) and not self.dragging_marker and not self.context_menu:
                self.hovered_marker = m

            sym = m['symbol'].lower()
            if "skull" in sym: pygame.draw.rect(screen, (50, 20, 20), click_rect); pygame.draw.rect(screen, (255, 100, 100), click_rect, 2)
            elif "house" in sym: pts = [(sx, sy - 12), (sx + 10, sy - 4), (sx + 7, sy + 10), (sx - 7, sy + 10), (sx - 10, sy - 4)]; pygame.draw.polygon(screen, (100, 150, 200), pts); pygame.draw.polygon(screen, (200, 200, 255), pts, 2)
            else: pygame.draw.circle(screen, (200, 200, 200), (int(sx), int(sy)), 8); pygame.draw.circle(screen, (50, 50, 50), (int(sx), int(sy)), 8, 2)
            
            if self.hovered_marker == m or (self.selected_marker and self.selected_marker['id'] == m['id']):
                pygame.draw.circle(screen, (255, 255, 0), (int(sx), int(sy)), 14, 2)
            
            title_surf = self.font_ui.render(m['title'], True, (255, 255, 255))
            t_rect = title_surf.get_rect(center=(sx, sy + 20))
            pygame.draw.rect(screen, (0,0,0,150), t_rect.inflate(4, 2))
            screen.blit(title_surf, t_rect)

    def render_player_view_surface(self):
        # 1. SETUP
        view_marker = next((m for m in self.markers if m.get('metadata', {}).get('is_view_marker') and m['metadata'].get('is_active')), None)
        if not view_marker or not self.render_strategy: return None
        if not hasattr(self.render_strategy, 'heightmap'): return None
        
        heightmap = self.render_strategy.heightmap
        h_map_h, h_map_w = heightmap.shape

        meta = view_marker.get('metadata', {})
        zoom = meta.get('zoom', 1.5)
        
        w, h = 1920, 1080
        center_x, center_y = w // 2, h // 2
        
        # Base Map
        temp_surface = pygame.Surface((w, h))
        self.draw_map(temp_surface, view_marker['world_x'], view_marker['world_y'], zoom, w, h)

        # --- HIGH GROUND RAYCASTING ---
        mx, my = view_marker['world_x'], view_marker['world_y']
        
        start_x_int, start_y_int = int(mx), int(my)

        # 1. DETERMINE EYE HEIGHT
        # We add a small buffer (0.01 = 1% of total world height) to simulate standing UP.
        STANDING_HEIGHT = 0.01 

        if 0 <= start_x_int < h_map_w and 0 <= start_y_int < h_map_h:
            ground_z = heightmap[start_y_int, start_x_int]
            eye_height = ground_z + STANDING_HEIGHT
        else:
            eye_height = 0.3

        # 2. VIEW DISTANCE (Screen Edge)
        max_dist = (math.sqrt(w**2 + h**2) / 2.0) / zoom

        polygon_points = []
        num_rays = 1800
        step_angle = (2 * math.pi) / num_rays
        step_size = 0.2 
        
        for i in range(num_rays):
            angle = i * step_angle
            sin_a = math.sin(angle)
            cos_a = math.cos(angle)
            
            curr_x, curr_y = mx, my
            dist = 0
            
            # Default to seeing the edge of the screen
            hit_x, hit_y = curr_x + (cos_a * max_dist), curr_y + (sin_a * max_dist)
            
            # Track previous height to detect peaks
            # We start at eye level.
            prev_z = eye_height

            while dist < max_dist:
                dist += step_size
                curr_x += cos_a * step_size
                curr_y += sin_a * step_size
                
                grid_x, grid_y = int(curr_x), int(curr_y)
                
                if 0 <= grid_x < h_map_w and 0 <= grid_y < h_map_h:
                    target_z = heightmap[grid_y, grid_x]
                    
                    # LOGIC:
                    # 1. If below eye level, it is always visible (valleys/plains).
                    # 2. If above eye level, it is visible ONLY if it is higher than the previous step (climbing).
                    # 3. If above eye level AND lower than previous step, we passed the peak. Blocked.

                    if target_z <= eye_height:
                        # We are looking down/straight. Visible.
                        # Reset prev_z to eye_height so if we hit a wall next, 
                        # we compare against eye level, not the valley floor.
                        prev_z = eye_height
                    else:
                        # We are looking UP (Obstruction candidate)
                        if target_z >= prev_z:
                            # It is climbing (facing us). Visible.
                            # Update prev_z so we keep climbing.
                            prev_z = target_z
                        else:
                            # It started decreasing while above eye level. 
                            # This is the "Backside" of the mountain. View Blocked.
                            hit_x, hit_y = curr_x, curr_y
                            break
                else:
                    # End of Map Data
                    hit_x, hit_y = curr_x, curr_y
                    break
            
            screen_x = center_x + (hit_x - mx) * zoom
            screen_y = center_y + (hit_y - my) * zoom
            polygon_points.append((screen_x, screen_y))

        # 4. COMPOSITE
        
        # Shadow Layer (Full Black)
        shadow_layer = pygame.Surface((w, h), pygame.SRCALPHA)
        shadow_layer.fill((0, 0, 0, 255)) 
        
        # Cut out the visible polygon
        if len(polygon_points) > 2:
            mask_surf = pygame.Surface((w, h), pygame.SRCALPHA) 
            mask_surf.fill((0,0,0,0)) 
            
            # Draw the visible area as Opaque White on the mask
            pygame.draw.polygon(mask_surf, (255, 255, 255, 255), polygon_points)
            
            # Subtract mask from shadow
            shadow_layer.blit(mask_surf, (0,0), special_flags=pygame.BLEND_RGBA_SUB)

        temp_surface.blit(shadow_layer, (0, 0))
        return temp_surface

    def render_player_view_surface_old(self):
        # 1. SETUP
        view_marker = next((m for m in self.markers if m.get('metadata', {}).get('is_view_marker') and m['metadata'].get('is_active')), None)
        if not view_marker or not self.render_strategy: return None
        if not hasattr(self.render_strategy, 'heightmap'): return None
        
        heightmap = self.render_strategy.heightmap
        h_map_h, h_map_w = heightmap.shape

        meta = view_marker.get('metadata', {})
        zoom = meta.get('zoom', 1.5)
        
        w, h = 1920, 1080
        center_x, center_y = w // 2, h // 2
        
        # Base Map
        temp_surface = pygame.Surface((w, h))
        self.draw_map(temp_surface, view_marker['world_x'], view_marker['world_y'], zoom, w, h)

        # --- HIGH GROUND RAYCASTING ---
        mx, my = view_marker['world_x'], view_marker['world_y']
        
        start_x_int, start_y_int = int(mx), int(my)

        # 1. DETERMINE EYE HEIGHT
        # Add a tiny buffer so we don't clip into the exact pixel we are standing on.
        STANDING_HEIGHT = 0.01 

        if 0 <= start_x_int < h_map_w and 0 <= start_y_int < h_map_h:
            ground_z = heightmap[start_y_int, start_x_int]
            eye_height = ground_z + STANDING_HEIGHT
        else:
            eye_height = 0.5

        # 2. VIEW DISTANCE
        max_dist = (math.sqrt(w**2 + h**2) / 2.0) / zoom

        polygon_points = []
        num_rays = 720
        step_angle = (2 * math.pi) / num_rays
        step_size = 1.0 
        
        for i in range(num_rays):
            angle = i * step_angle
            sin_a = math.sin(angle)
            cos_a = math.cos(angle)
            
            curr_x, curr_y = mx, my
            dist = 0
            
            # Default hit to max distance
            hit_x, hit_y = curr_x + (cos_a * max_dist), curr_y + (sin_a * max_dist)
            
            # Track the highest slope we've seen so far.
            # Start very low so we can see the ground immediately in front of us.
            max_slope = -9999.0
            
            while dist < max_dist:
                dist += step_size
                curr_x += cos_a * step_size
                curr_y += sin_a * step_size
                
                grid_x, grid_y = int(curr_x), int(curr_y)
                
                if 0 <= grid_x < h_map_w and 0 <= grid_y < h_map_h:
                    target_z = heightmap[grid_y, grid_x]
                    
                    # LOGIC: SLOPE CHECK
                    # We calculate the angle (slope) from our eye to the target.
                    # Multiplier 100.0 makes Z-height differences significant relative to distance.
                    current_slope = (target_z - eye_height) / dist * 100.0
                    
                    if current_slope >= max_slope:
                        # We are looking at the "front" of a hill or flat ground.
                        # It pushes the horizon up, so we update max_slope.
                        max_slope = current_slope
                    else:
                        # The slope dropped BELOW our max.
                        # This means we went over a peak and are looking into the "shadow" behind it.
                        # The view is blocked.
                        hit_x, hit_y = curr_x, curr_y
                        break
                else:
                    # End of Map Data
                    hit_x, hit_y = curr_x, curr_y
                    break
            
            screen_x = center_x + (hit_x - mx) * zoom
            screen_y = center_y + (hit_y - my) * zoom
            polygon_points.append((screen_x, screen_y))

        # 4. COMPOSITE
        
        # Shadow Layer (Full Black)
        shadow_layer = pygame.Surface((w, h), pygame.SRCALPHA)
        shadow_layer.fill((0, 0, 0, 255)) 
        
        # Cut out the visible polygon
        if len(polygon_points) > 2:
            mask_surf = pygame.Surface((w, h), pygame.SRCALPHA) 
            mask_surf.fill((0,0,0,0)) 
            
            # Draw the visible area as Opaque White on the mask
            pygame.draw.polygon(mask_surf, (255, 255, 255, 255), polygon_points)
            
            # Subtract mask from shadow (makes visible area transparent)
            shadow_layer.blit(mask_surf, (0,0), special_flags=pygame.BLEND_RGBA_SUB)

        temp_surface.blit(shadow_layer, (0, 0))
        return temp_surface

    def render_player_view_surface_old(self):
        # 1. SETUP
        view_marker = next((m for m in self.markers if m.get('metadata', {}).get('is_view_marker') and m['metadata'].get('is_active')), None)
        if not view_marker or not self.render_strategy: return None
        if not hasattr(self.render_strategy, 'heightmap'): return None
        
        heightmap = self.render_strategy.heightmap
        h_map_h, h_map_w = heightmap.shape

        meta = view_marker.get('metadata', {})
        zoom = meta.get('zoom', 1.5)
        
        w, h = 1920, 1080
        center_x, center_y = w // 2, h // 2
        
        # Base Map
        temp_surface = pygame.Surface((w, h))
        self.draw_map(temp_surface, view_marker['world_x'], view_marker['world_y'], zoom, w, h)

        # --- HIGH GROUND RAYCASTING ---
        mx, my = view_marker['world_x'], view_marker['world_y']
        
        start_x_int, start_y_int = int(mx), int(my)

        # 1. DETERMINE EYE HEIGHT
        # We add a small buffer (0.01 = 1% of total world height) to simulate standing UP.
        # This prevents the pixel immediately in front of your feet from blocking the view.
        STANDING_HEIGHT = 0.01 

        if 0 <= start_x_int < h_map_w and 0 <= start_y_int < h_map_h:
            ground_z = heightmap[start_y_int, start_x_int]
            eye_height = ground_z + STANDING_HEIGHT
        else:
            eye_height = 0.5

        # 2. VIEW DISTANCE (Screen Edge)
        max_dist = (math.sqrt(w**2 + h**2) / 2.0) / zoom

        polygon_points = []
        num_rays = 720
        step_angle = (2 * math.pi) / num_rays
        step_size = 1.0 
        
        for i in range(num_rays):
            angle = i * step_angle
            sin_a = math.sin(angle)
            cos_a = math.cos(angle)
            
            curr_x, curr_y = mx, my
            dist = 0
            
            # Default to seeing the edge of the screen
            hit_x, hit_y = curr_x + (cos_a * max_dist), curr_y + (sin_a * max_dist)
            
            while dist < max_dist:
                dist += step_size
                curr_x += cos_a * step_size
                curr_y += sin_a * step_size
                
                grid_x, grid_y = int(curr_x), int(curr_y)
                
                if 0 <= grid_x < h_map_w and 0 <= grid_y < h_map_h:
                    target_z = heightmap[grid_y, grid_x]
                    
                    # LOGIC: OBSTRUCTION CHECK
                    # If the terrain here is TALLER than my eyes, it blocks the view.
                    if target_z > eye_height:
                        hit_x, hit_y = curr_x, curr_y
                        break
                else:
                    # End of Map Data
                    hit_x, hit_y = curr_x, curr_y
                    break
            
            screen_x = center_x + (hit_x - mx) * zoom
            screen_y = center_y + (hit_y - my) * zoom
            polygon_points.append((screen_x, screen_y))

        # 4. COMPOSITE
        
        # Shadow Layer (Full Black)
        shadow_layer = pygame.Surface((w, h), pygame.SRCALPHA)
        shadow_layer.fill((0, 0, 0, 255)) 
        
        # Cut out the visible polygon
        if len(polygon_points) > 2:
            mask_surf = pygame.Surface((w, h), pygame.SRCALPHA) 
            mask_surf.fill((0,0,0,0)) 
            
            # Draw the visible area as Opaque White on the mask
            pygame.draw.polygon(mask_surf, (255, 255, 255, 255), polygon_points)
            
            # Subtract mask from shadow
            shadow_layer.blit(mask_surf, (0,0), special_flags=pygame.BLEND_RGBA_SUB)

        temp_surface.blit(shadow_layer, (0, 0))
        return temp_surface

    def get_metadata_updates(self):
        return {'sea_level': self.slider_water.value, 'light_azimuth': self.slider_azimuth.value, 'light_altitude': self.slider_altitude.value, 'contour_interval': self.slider_contour.value, 'grid_size': self.grid_size}

    def cleanup(self): pass

