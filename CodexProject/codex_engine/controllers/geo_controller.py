import pygame
import math
import json
from codex_engine.controllers.base_controller import BaseController
from codex_engine.ui.renderers.image_strategy import ImageMapStrategy
from codex_engine.ui.widgets import Slider, Button
from codex_engine.ui.editors import NativeMarkerEditor
from codex_engine.ui.info_panel import InfoPanel
from codex_engine.content.managers import WorldContent, LocalContent
from codex_engine.generators.world_gen import WorldGenerator
from codex_engine.generators.local_gen import LocalGenerator 
from codex_engine.generators.village_manager import VillageContentManager
from codex_engine.core.ai_manager import AIManager
from codex_engine.config import SCREEN_WIDTH, SCREEN_HEIGHT

class GeoController(BaseController):
    def __init__(self, db_manager, node_data, theme_manager):
        super().__init__(db_manager, node_data, theme_manager)
        
        self.ai = AIManager()
        
        # 1. SETUP CONTENT MANAGER (Polymorphism)
        if self.node['type'] == 'world_map':
            self.content_manager = WorldContent(self.db, self.node)
        else:
            # Handles Village, Lair, Note
            self.content_manager = LocalContent(self.db, self.node)
        
        # Render Strategy
        self.render_strategy = None
        if 'file_path' in self.node['metadata']:
            self.render_strategy = ImageMapStrategy(self.node['metadata'], self.theme)
            
        # Data
        self.vectors = self.db.get_vectors(self.node['id'])
        self.markers = self.db.get_markers(self.node['id'])
        
        # Interaction State
        self.active_vector = None
        self.selected_point_idx = None
        self.dragging_point = False
        self.selected_marker = None
        self.dragging_marker = None
        self.hovered_marker = None
        self.drag_offset = (0,0)
        self.pending_click_pos = None
        
        # Visual Settings
        self.show_grid = True
        self.grid_type = "HEX"
        self.grid_size = self.node['metadata'].get('grid_size', 64)

        # UI State
        self.active_tab = "TOOLS" 

        # Fonts
        self.font_ui = pygame.font.Font(None, 24)
        self.font_small = pygame.font.Font(None, 20)
        try: self.font_icon = pygame.font.SysFont("segoeuiemoji", 30)
        except: self.font_icon = pygame.font.Font(None, 30)

        # Initialize Sub-Components
        self.info_panel = InfoPanel(self.content_manager, self.db, self.node, self.font_ui, self.font_small)
        self._init_ui()

    def _init_ui(self):
        meta = self.node['metadata']
        
        # --- NAVIGATION ---
        self.btn_back = Button(20, 50, 60, 25, "<- Up", self.font_ui, (80,80,90), (100,100,120), (255,255,255), self._go_up_level)

        # --- TABS ---
        tab_y = 90
        self.btn_tab_tools = Button(20, tab_y, 70, 30, "Tools", self.font_ui, (60,60,70), (80,80,90), (255,255,255), lambda: self._set_tab("TOOLS"))
        self.btn_tab_info = Button(95, tab_y, 70, 30, "Info", self.font_ui, (60,60,70), (80,80,90), (255,255,255), lambda: self._set_tab("INFO"))
        self.btn_tab_config = Button(170, tab_y, 70, 30, "Setup", self.font_ui, (60,60,70), (80,80,90), (255,255,255), lambda: self._set_tab("CONFIG"))

        # --- TAB: TOOLS ---
        self.btn_new_road = Button(20, 140, 105, 30, "+ Road", self.font_ui, (139,69,19), (160,82,45), (255,255,255), lambda: self.start_new_vector("road"))
        self.btn_new_river = Button(135, 140, 105, 30, "+ River", self.font_ui, (40,60,150), (60,80,180), (255,255,255), lambda: self.start_new_vector("river"))
        self.btn_save_vec = Button(20, 140, 220, 30, "Save Line", self.font_ui, (50,150,50), (80,200,80), (255,255,255), self.save_active_vector)
        self.btn_cancel_vec = Button(20, 180, 105, 30, "Cancel", self.font_ui, (150,50,50), (200,80,80), (255,255,255), self.cancel_vector)
        self.btn_delete_vec = Button(135, 180, 105, 30, "Delete", self.font_ui, (100,0,0), (150,0,0), (255,255,255), self.delete_vector)

        # --- TAB: CONFIG ---
        self.slider_water = Slider(20, 140, 220, 15, -11000.0, 9000.0, meta.get('sea_level', 0.0), "Sea Level (m)")
        self.slider_azimuth = Slider(20, 180, 220, 15, 0, 360, meta.get('light_azimuth', 315), "Light Dir")
        self.slider_altitude = Slider(20, 220, 220, 15, 0, 90, meta.get('light_altitude', 45), "Light Height")
        self.slider_intensity = Slider(20, 260, 220, 15, 0.0, 2.0, 1.2, "Light Power")
        self.slider_contour = Slider(20, 300, 220, 15, 0, 500, meta.get('contour_interval', 0), "Contours (m)")
        self.btn_grid_minus = Button(140, 340, 30, 30, "-", self.font_ui, (100,100,100), (150,150,150), (255,255,255), self.dec_grid)
        self.btn_grid_plus = Button(180, 340, 30, 30, "+", self.font_ui, (100,100,100), (150,150,150), (255,255,255), self.inc_grid)
        self.btn_regen = Button(20, 380, 220, 30, "Regenerate Map", self.font_ui, (100, 100, 100), (150, 150, 150), (255,255,255), self.regenerate_seed)
        self.btn_gen_details = Button(20, 420, 220, 30, "AI Gen Content", self.font_ui, (100, 100, 200), (150, 150, 250), (255,255,255), self._generate_ai_details)

        # --- MARKER TOOLS ---
        self.btn_edit_marker = Button(20, SCREEN_HEIGHT - 110, 80, 30, "Edit", self.font_ui, (100,150,200), (150,200,250), (0,0,0), self._open_edit_modal)
        self.btn_delete_marker = Button(110, SCREEN_HEIGHT - 110, 80, 30, "Delete", self.font_ui, (200,100,100), (250,150,150), (0,0,0), self._delete_selected_marker)
        self.btn_center_marker = Button(200, SCREEN_HEIGHT - 110, 80, 30, "Center", self.font_ui, (150,150,150), (200,200,200), (0,0,0), self._center_on_selected_marker)

    def _set_tab(self, tab_name): self.active_tab = tab_name

    def update(self):
        self.widgets = []
        if self.node.get('parent_node_id'): self.widgets.append(self.btn_back)
        self.widgets.extend([self.btn_tab_tools, self.btn_tab_info, self.btn_tab_config])
        
        # Tab Styles
        ac, ic = (100, 100, 120), (60, 60, 70)
        self.btn_tab_tools.base_color = ac if self.active_tab == "TOOLS" else ic
        self.btn_tab_info.base_color = ac if self.active_tab == "INFO" else ic
        self.btn_tab_config.base_color = ac if self.active_tab == "CONFIG" else ic

        if self.active_tab == "CONFIG":
            self.widgets.extend([
                self.slider_water, self.slider_azimuth, self.slider_altitude,
                self.slider_intensity, self.slider_contour,
                self.btn_grid_minus, self.btn_grid_plus, self.btn_regen,
                self.btn_gen_details
            ])
        elif self.active_tab == "TOOLS":
            if self.active_vector:
                self.widgets.extend([self.btn_save_vec, self.btn_cancel_vec])
                if self.active_vector.get('id'): self.widgets.append(self.btn_delete_vec)
            else:
                self.widgets.extend([self.btn_new_road, self.btn_new_river])
        elif self.active_tab == "INFO":
            self.widgets.extend(self.info_panel.widgets)

        if self.selected_marker and not self.dragging_marker:
            self.widgets.extend([self.btn_edit_marker, self.btn_delete_marker, self.btn_center_marker])

        if self.render_strategy:
            self.render_strategy.set_light_direction(self.slider_azimuth.value, self.slider_altitude.value)
            self.render_strategy.set_light_intensity(self.slider_intensity.value)

    # --- INPUT ---
    def handle_input(self, event, cam_x, cam_y, zoom):
        # 1. Widgets
        for widget in self.widgets:
            res = widget.handle_event(event)
            if res:
                if isinstance(res, dict): return res
                return None 

        # 2. Info Panel Scrolling
        if self.active_tab == "INFO":
            if self.info_panel.handle_event(event):
                return None

        center_x, center_y = SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2
        
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_g: self.show_grid = not self.show_grid
            if event.key == pygame.K_ESCAPE and self.active_vector: self.cancel_vector()

        if event.type == pygame.MOUSEMOTION:
            world_x = ((event.pos[0] - center_x) / zoom) + cam_x
            world_y = ((event.pos[1] - center_y) / zoom) + cam_y
            if self.active_vector and self.dragging_point and self.selected_point_idx is not None:
                self.active_vector['points'][self.selected_point_idx] = (world_x, world_y)
                return None
            if self.dragging_marker:
                self.dragging_marker['world_x'] = world_x - self.drag_offset[0]
                self.dragging_marker['world_y'] = world_y - self.drag_offset[1]
                return None

        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.dragging_marker:
                m = self.dragging_marker
                self.db.update_marker(m['id'], m['world_x'], m['world_y'], m['symbol'], m['title'], m['description'])
                self.dragging_marker = None
            if self.dragging_point: self.dragging_point = False

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if event.pos[0] < 260: return None 
            world_x = ((event.pos[0] - center_x) / zoom) + cam_x
            world_y = ((event.pos[1] - center_y) / zoom) + cam_y

            if self.active_vector: return self._handle_vector_click(world_x, world_y, zoom)
            res = self._handle_marker_click(event, world_x, world_y)
            if res: return res
            if self.active_tab == "TOOLS" or self.active_vector: self._handle_pixel_selection(event, world_x, world_y, zoom)
            if pygame.key.get_mods() & pygame.KMOD_SHIFT: return self._create_new_marker(world_x, world_y)
            return {"action": "pan", "pos": (world_x, world_y)}
        return None

    # --- ACTIONS ---
    def _go_up_level(self): return {"action": "go_up_level"}
    def inc_grid(self): self.grid_size = min(256, self.grid_size + 8)
    def dec_grid(self): self.grid_size = max(16, self.grid_size - 8)

    def regenerate_seed(self):
        print(f"Regenerating {self.node['type']}...")
        if self.node['type'] == 'world_map':
            gen = WorldGenerator(self.theme, self.db)
            nid, metadata = gen.generate_world_node(self.node['campaign_id'])
            metadata['sea_level'] = self.slider_water.value
            self.db.update_node_data(nid, metadata=metadata)
            return {"action": "reload_node"}
        elif self.node['type'] == 'local_map':
            parent_id = self.node['parent_node_id']
            parent_node = self.db.get_node(parent_id)
            if not parent_node: return None
            mock_marker = {'world_x': self.node['grid_x'], 'world_y': self.node['grid_y'], 'title': self.node['name'], 'symbol': 'regen'}
            gen = LocalGenerator(self.db)
            temp_node_id = gen.generate_local_map(parent_node, mock_marker, self.node['campaign_id'])
            temp_node = self.db.get_node(temp_node_id)
            new_vectors = self.db.get_vectors(temp_node_id)
            new_markers = self.db.get_markers(temp_node_id)
            current_id = self.node['id']
            merged_meta = temp_node['metadata']
            merged_meta['sea_level'] = self.slider_water.value 
            self.db.update_node_data(current_id, metadata=merged_meta, geometry=temp_node['geometry_data'])
            with self.db.get_connection() as conn:
                conn.execute("DELETE FROM vectors WHERE node_id=?", (current_id,))
                conn.execute("DELETE FROM markers WHERE node_id=?", (current_id,))
                conn.commit()
            for v in new_vectors: self.db.save_vector(current_id, v['type'], v['points'], v['width'])
            for m in new_markers: self.db.add_marker(current_id, m['world_x'], m['world_y'], m['symbol'], m['title'], m['description'], m['metadata'])
            with self.db.get_connection() as conn: conn.execute("DELETE FROM nodes WHERE id=?", (temp_node_id,)); conn.commit()
            return {"action": "reload_node"}
        return None

    def start_new_vector(self, vtype):
        self.selected_marker = None
        self.active_vector = {'points': [], 'type': vtype, 'width': 4 if vtype=='road' else 8, 'id': None}
        self.selected_point_idx = None
        return True 
    def save_active_vector(self):
        if self.active_vector and len(self.active_vector['points']) > 1:
            self.db.save_vector(self.node['id'], self.active_vector['type'], self.active_vector['points'], self.active_vector['width'], self.active_vector.get('id'))
            self.vectors = self.db.get_vectors(self.node['id'])
        self.active_vector = None
        return True
    def cancel_vector(self): self.active_vector = None; return True
    def delete_vector(self):
        if self.active_vector.get('id'):
            self.db.delete_vector(self.active_vector['id'])
            self.vectors = self.db.get_vectors(self.node['id'])
        self.active_vector = None
        return True

    def _open_edit_modal(self):
        if self.selected_marker:
            NativeMarkerEditor(self.selected_marker, self.node['type'], self._save_marker, self._handle_ai_gen_modal)
            self.markers = self.db.get_markers(self.node['id'])
        return True
    def _delete_selected_marker(self):
        if self.selected_marker:
            self.db.delete_marker(self.selected_marker['id'])
            self.markers = self.db.get_markers(self.node['id'])
            self.selected_marker = None
        return True
    def _center_on_selected_marker(self):
        if self.selected_marker: return {"action": "pan", "pos": (self.selected_marker['world_x'], self.selected_marker['world_y'])}
        return True
    def _save_marker(self, mid, sym, title, note, meta):
        if mid: self.db.update_marker(mid, self.selected_marker['world_x'], self.selected_marker['world_y'], sym, title, note, meta)
        else: self.db.add_marker(self.node['id'], self.pending_click_pos[0], self.pending_click_pos[1], sym, title, note, meta)
        self.markers = self.db.get_markers(self.node['id'])
        self.selected_marker = None
    def _handle_ai_gen_modal(self, mtype, title, context): return {} 

    def _generate_ai_details(self):
        if self.node['type'] == 'local_map':
            try:
                vm = VillageContentManager(self.node, self.db, self.ai)
                vm.generate_details()
                return {"action": "reload_node"}
            except Exception as e: print(f"AI Error: {e}")
        else:
            print(f"needs code added at this level ({self.node['type']})")
        return True

    def _handle_vector_click(self, wx, wy, zoom):
        hit = False
        for i, pt in enumerate(self.active_vector['points']):
            if math.hypot(pt[0]-wx, pt[1]-wy) < 10/zoom:
                self.selected_point_idx, self.dragging_point, hit = i, True, True
                break
        if not hit:
            self.active_vector['points'].append((wx, wy))
            self.selected_point_idx = len(self.active_vector['points']) - 1
        return None
    def _handle_marker_click(self, event, wx, wy):
        if self.hovered_marker:
            if pygame.key.get_mods() & pygame.KMOD_SHIFT: return {"action": "enter_marker", "marker": self.hovered_marker}
            self.selected_marker = self.hovered_marker
            self.dragging_marker = self.selected_marker
            self.drag_offset = (wx - self.dragging_marker['world_x'], wy - self.dragging_marker['world_y'])
            return {"action": "marker_selected"}
        if self.selected_marker and event.pos[0] < 300 and event.pos[1] > SCREEN_HEIGHT-160: pass
        else: self.selected_marker = None
        return None
    def _handle_pixel_selection(self, event, wx, wy, zoom):
        closest, min_d = None, float('inf')
        for vec in self.vectors:
            for pt in vec['points']:
                d = math.hypot(pt[0]-wx, pt[1]-wy)
                if d < min_d: min_d, closest = d, vec
        if closest and min_d < 10/zoom: self.active_vector, self.selected_marker = closest, None
    def _create_new_marker(self, wx, wy):
        self.pending_click_pos = (wx, wy)
        new_marker = {'title': 'New', 'description': '', 'metadata': {}, 'symbol': 'star'}
        NativeMarkerEditor(new_marker, self.node['type'], self._save_marker, self._handle_ai_gen_modal)
        self.markers = self.db.get_markers(self.node['id'])
        return {"action": "consumed"}

    # --- RENDERING ---
    def draw_map(self, screen, cam_x, cam_y, zoom, screen_w, screen_h):
        if self.render_strategy:
            self.render_strategy.draw(screen, cam_x, cam_y, zoom, screen_w, screen_h, self.slider_water.value, self.vectors, self.active_vector, self.selected_point_idx, self.slider_contour.value)
            if self.show_grid:
                cx, cy = screen_w//2, screen_h//2
                msx, msy = cx-(cam_x*zoom), cy-(cam_y*zoom)
                mw, mh = self.render_strategy.width*zoom, self.render_strategy.height*zoom
                map_rect = pygame.Rect(msx, msy, mw, mh)
                screen.set_clip(map_rect)
                if self.grid_type == "HEX": self._draw_hex_grid(screen, msx, msy, zoom, screen_w, screen_h)
                else: self._draw_square_grid(screen, msx, msy, zoom, screen_w, screen_h)
                screen.set_clip(None)
                pygame.draw.rect(screen, (255, 255, 255), map_rect, 2)

    def draw_overlays(self, screen, cam_x, cam_y, zoom):
        self._draw_markers(screen, cam_x, cam_y, zoom)
        if self.active_tab == "INFO": self.info_panel.draw(screen)
        if self.selected_marker and not self.dragging_marker: self._draw_marker_panel(screen)

    def _draw_marker_panel(self, screen):
        panel_y = SCREEN_HEIGHT-160
        pygame.draw.rect(screen, (40,40,50), (10,panel_y,240,150), border_radius=5)
        pygame.draw.rect(screen, (150,150,150), (10,panel_y,240,150),1,border_radius=5)
        title_s = self.font_ui.render(self.selected_marker['title'], True, (255,255,100))
        screen.blit(title_s, (20, panel_y+10))
        desc = self.selected_marker.get('description', '')[:30] + "..."
        screen.blit(self.font_ui.render(desc, True, (200,200,200)), (20,panel_y+45))

    def _draw_tooltip(self, screen, pos):
        m = self.hovered_marker
        lines = [m.get('description', '')[:50] + "...", "(Shift+Click to Enter)"]
        rendered = [self.font_ui.render(l, True, (200,200,200)) for l in lines]
        mw = max(s.get_width() for s in rendered)
        mh = len(rendered) * 20 + 10
        bg = pygame.Rect(pos[0]+15, pos[1]+15, mw+20, mh)
        if bg.right > SCREEN_WIDTH: bg.x -= (bg.width+30)
        pygame.draw.rect(screen, (20,20,30), bg)
        pygame.draw.rect(screen, (100,100,150), bg, 1)
        for i, s in enumerate(rendered):
            screen.blit(s, (bg.x+10, bg.y+5 + i*20))

    def _draw_hex_grid(self, screen, start_x, start_y, zoom, sw, sh):
        hex_radius = self.grid_size * zoom
        if hex_radius < 5: return
        hex_w = math.sqrt(3) * hex_radius
        vert_spacing = (2 * hex_radius) * 0.75
        screen_rel_x, screen_rel_y = -start_x, -start_y
        start_col = int(screen_rel_x/hex_w)-1
        start_row = int(screen_rel_y/vert_spacing)-1
        cols_vis = int(sw/hex_w)+3
        rows_vis = int(sh/vert_spacing)+3
        color = (255, 255, 255, 30)
        for r in range(start_row, start_row + rows_vis):
            for q in range(start_col, start_col + cols_vis):
                x_off = (r % 2) * (hex_w / 2)
                cx, cy = start_x+(q*hex_w)+x_off, start_y+(r*vert_spacing)
                points = []
                for i in range(6):
                    angle = math.pi/3*i+(math.pi/6)
                    points.append((cx+hex_radius*math.cos(angle), cy+hex_radius*math.sin(angle)))
                pygame.draw.lines(screen, color, True, points, 1)

    def _draw_square_grid(self, screen, start_x, start_y, zoom, sw, sh):
        size = self.grid_size * zoom; color = (255, 255, 255, 30)
        if size < 4: return
        map_w, map_h = self.render_strategy.width*zoom, self.render_strategy.height*zoom
        x, y = start_x, start_y
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
            is_selected = self.selected_marker and self.selected_marker['id']==m['id']
            sym = m['symbol'].lower()
            click_rect = None
            if "dungeon" in sym or "skull" in sym or "lair" in sym: # RENAMED TO LAIR
                r = pygame.Rect(sx - 10, sy - 10, 20, 20)
                pygame.draw.rect(screen, (50, 20, 20), r)
                pygame.draw.rect(screen, (255, 100, 100), r, 2)
                click_rect = r
            elif "house" in sym:
                pts = [(sx, sy - 12), (sx + 10, sy - 4), (sx + 7, sy + 10), (sx - 7, sy + 10), (sx - 10, sy - 4)]
                pygame.draw.polygon(screen, (100, 150, 200), pts)
                pygame.draw.polygon(screen, (200, 200, 255), pts, 2)
                click_rect = pygame.Rect(sx-10, sy-12, 20, 22)
            else:
                pygame.draw.circle(screen, (200, 200, 200), (int(sx), int(sy)), 8)
                pygame.draw.circle(screen, (50, 50, 50), (int(sx), int(sy)), 8, 2)
                click_rect = pygame.Rect(sx-8, sy-8, 16, 16)
            if is_selected and not self.dragging_marker:
                pygame.draw.circle(screen, (255, 255, 0), (int(sx), int(sy)), 18, 2)
            title_surf = self.font_ui.render(m['title'], True, (255, 255, 255))
            t_x, t_y = sx - title_surf.get_width() // 2, sy + 12
            pygame.draw.rect(screen, (0,0,0,150), (t_x-2, t_y-1, title_surf.get_width()+4, title_surf.get_height()+2))
            screen.blit(title_surf, (t_x, t_y))
            if click_rect.collidepoint(mouse_pos) and not self.dragging_marker:
                self.hovered_marker = m
        if self.hovered_marker:
            self._draw_tooltip(screen, mouse_pos)

    def get_metadata_updates(self):
        updates = {}
        if self.slider_water.value != self.node['metadata'].get('sea_level'):
            updates['sea_level'] = self.slider_water.value
        updates['light_azimuth'] = self.slider_azimuth.value
        updates['light_altitude'] = self.slider_altitude.value
        updates['contour_interval'] = self.slider_contour.value
        updates['grid_size'] = self.grid_size
        return updates

    def cleanup(self):
        pass
