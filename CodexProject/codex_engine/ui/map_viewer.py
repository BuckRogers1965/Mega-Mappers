import pygame
import math
from codex_engine.config import SCREEN_WIDTH, SCREEN_HEIGHT
from codex_engine.ui.renderers.image_strategy import ImageMapStrategy
from codex_engine.ui.widgets import Slider, Button, MarkerModal
from codex_engine.generators.world_gen import WorldGenerator
from codex_engine.core.db_manager import DBManager

class MapViewer:
    def __init__(self, screen, theme_manager):
        self.screen = screen
        self.theme = theme_manager
        
        # Camera & Grid
        self.cam_x, self.cam_y, self.zoom = 0, 0, 1.0
        self.show_grid, self.grid_type, self.grid_size = True, "HEX", 64
        
        # State
        self.current_node = None
        self.render_strategy = None
        self.markers, self.selected_marker, self.dragging_marker = [], None, None
        self.drag_offset, self.active_modal, self.pending_click_pos = (0,0), None, None
        self.hovered_marker = None
        
        # UI Resources
        self.font_ui = pygame.font.Font(None, 24)
        self.font_title = pygame.font.Font(None, 32)
        try: self.font_icon = pygame.font.SysFont("segoeuiemoji", 30)
        except: self.font_icon = pygame.font.Font(None, 30)
        self.show_ui = True
        
        # UI Controls
        self.slider_water = Slider(20, 60, 200, 20, -11000.0, 9000.0, 0.0, "Sea Level (m)")
        self.slider_azimuth = Slider(20, 110, 200, 20, 0, 360, 315, "Light Dir")
        self.slider_altitude = Slider(20, 160, 200, 20, 0, 90, 45, "Light Height")
        self.slider_intensity = Slider(20, 210, 200, 20, 0.0, 2.0, 1.2, "Light Power")
        self.btn_grid_minus = Button(140, 260, 30, 30, "-", self.font_ui, (100,100,100), (150,150,150), (255,255,255), self.dec_grid)
        self.btn_grid_plus = Button(180, 260, 30, 30, "+", self.font_ui, (100,100,100), (150,150,150), (255,255,255), self.inc_grid)
        self.btn_regen = Button(20, 310, 120, 40, "New Map", self.font_ui, (100, 100, 100), (150, 150, 150), (255,255,255), self.regenerate_seed)
        
        self.db = DBManager()

    def inc_grid(self): self.grid_size = min(256, self.grid_size + 8)
    def dec_grid(self): self.grid_size = max(16, self.grid_size - 8)

    def _create_marker_buttons(self):
        y = SCREEN_HEIGHT - 120
        self.btn_edit_marker = Button(20, y, 80, 30, "Edit", self.font_ui, (100,150,200), (150,200,250), (0,0,0), self._open_edit_modal)
        self.btn_delete_marker = Button(110, y, 80, 30, "Delete", self.font_ui, (200,100,100), (250,150,150), (0,0,0), self._delete_selected_marker)
        self.btn_center_marker = Button(200, y, 80, 30, "Center", self.font_ui, (150,150,150), (200,200,200), (0,0,0), self._center_on_selected_marker)

    def set_node(self, node_data):
        self.current_node = node_data
        metadata = node_data.get('metadata', {})
        if 'sea_level' in metadata: self.slider_water.value = metadata['sea_level']; self.slider_water.update_handle()
        if 'file_path' in metadata:
            self.render_strategy = ImageMapStrategy(metadata, self.theme)
            map_w, map_h = self.render_strategy.width, self.render_strategy.height
            self.cam_x, self.cam_y = map_w / 2, map_h / 2
            scale_x, scale_y = (SCREEN_WIDTH - 50) / map_w, (SCREEN_HEIGHT - 50) / map_h
            self.zoom = min(scale_x, scale_y)
            self.markers = self.db.get_markers(self.current_node['id'])
        else: self.render_strategy = None
        self.selected_marker = None

    def regenerate_seed(self):
        if not self.current_node: return
        cid = self.current_node['campaign_id']
        gen = WorldGenerator(self.theme, self.db)
        nid, metadata = gen.generate_world_node(cid)
        metadata['sea_level'] = self.slider_water.value
        self.db.update_node_data(nid, metadata=metadata)
        node = self.db.get_node_by_coords(cid, None, 0, 0)
        self.set_node(node)

    def handle_input(self, event):
        if self.active_modal:
            self.active_modal.handle_event(event)
            return

        # Handle UI events
        if self.show_ui:
            self.slider_water.handle_event(event)
            self.slider_azimuth.handle_event(event)
            self.slider_altitude.handle_event(event)
            self.slider_intensity.handle_event(event)
            self.btn_grid_plus.handle_event(event)
            self.btn_grid_minus.handle_event(event)
            if self.btn_regen.handle_event(event): return
            if self.render_strategy:
                self.render_strategy.set_light_direction(self.slider_azimuth.value, self.slider_altitude.value)
                self.render_strategy.set_light_intensity(self.slider_intensity.value)
        if self.selected_marker:
            if self.btn_edit_marker: self.btn_edit_marker.handle_event(event)
            if self.btn_delete_marker: self.btn_delete_marker.handle_event(event)
            if self.btn_center_marker: self.btn_center_marker.handle_event(event)

        # Keyboard camera
        keys = pygame.key.get_pressed()
        speed = 20 / self.zoom 
        if keys[pygame.K_LSHIFT]: speed *= 3
        if keys[pygame.K_LEFT]: self.cam_x -= speed
        if keys[pygame.K_RIGHT]: self.cam_x += speed
        if keys[pygame.K_UP]: self.cam_y -= speed
        if keys[pygame.K_DOWN]: self.cam_y += speed
        
        # Keyboard toggles & hotkeys
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_LEFTBRACKET: self.zoom = max(0.01, self.zoom * 0.9)
            if event.key == pygame.K_RIGHTBRACKET: self.zoom = min(10.0, self.zoom * 1.1)
            if event.key == pygame.K_h: self.show_ui = not self.show_ui
            if event.key == pygame.K_g: self.show_grid = not self.show_grid
            if event.key == pygame.K_t: self.grid_type = "SQUARE" if self.grid_type == "HEX" else "HEX"
            if event.key == pygame.K_MINUS: self.dec_grid()
            if event.key == pygame.K_EQUALS: self.inc_grid()
            if event.key == pygame.K_s and self.current_node:
                meta = self.current_node.get('metadata', {}); meta['sea_level'] = self.slider_water.value
                self.db.update_node_data(self.current_node['id'], metadata=meta); print("Saved.")

        # Mouse Dragging
        if event.type == pygame.MOUSEMOTION and self.dragging_marker:
            center_x, center_y = SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2
            world_x = ((event.pos[0] - center_x) / self.zoom) + self.cam_x
            world_y = ((event.pos[1] - center_y) / self.zoom) + self.cam_y
            self.dragging_marker['world_x'] = world_x - self.drag_offset[0]
            self.dragging_marker['world_y'] = world_y - self.drag_offset[1]
            return

        if event.type == pygame.MOUSEBUTTONUP and event.button == 1 and self.dragging_marker:
            m = self.dragging_marker
            self.db.update_marker(m['id'], m['world_x'], m['world_y'], m['symbol'], m['title'], m['description'])
            self.dragging_marker = None
            return

        # Mouse Click Logic
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.hovered_marker:
                self.selected_marker = self.hovered_marker
                self._create_marker_buttons()
                self.dragging_marker = self.selected_marker
                center_x, center_y = SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2
                world_x = ((event.pos[0] - center_x) / self.zoom) + self.cam_x
                world_y = ((event.pos[1] - center_y) / self.zoom) + self.cam_y
                self.drag_offset = (world_x - self.dragging_marker['world_x'], world_y - self.dragging_marker['world_y'])
                return
            
            if self.show_ui and event.pos[0] < 260 and event.pos[1] < 400: return
            if self.selected_marker and event.pos[0] < 300 and event.pos[1] > SCREEN_HEIGHT-160: return

            self.selected_marker = None
            center_x, center_y = SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2
            world_x = ((event.pos[0] - center_x) / self.zoom) + self.cam_x
            world_y = ((event.pos[1] - center_y) / self.zoom) + self.cam_y
            
            if pygame.key.get_mods() & pygame.KMOD_SHIFT:
                self.pending_click_pos = (world_x, world_y)
                self.active_modal = MarkerModal(SCREEN_WIDTH//2-150, SCREEN_HEIGHT//2-125, self._save_marker, self._close_modal)
            else:
                self.cam_x, self.cam_y = world_x, world_y
                self.zoom = min(10.0, self.zoom * 2.5)

    def _save_marker(self, marker_id, symbol, title, note):
        if marker_id: # Update
            m = self.selected_marker
            self.db.update_marker(marker_id, m['world_x'], m['world_y'], symbol, title, note)
        else: # Create
            wx, wy = self.pending_click_pos
            self.db.add_marker(self.current_node['id'], wx, wy, symbol, title, note)
        self.markers = self.db.get_markers(self.current_node['id'])
        self.active_modal, self.selected_marker = None, None

    def _close_modal(self): self.active_modal = None
    def _open_edit_modal(self):
        if self.selected_marker: self.active_modal = MarkerModal(SCREEN_WIDTH//2-150, SCREEN_HEIGHT//2-125, self._save_marker, self._close_modal, self.selected_marker)
    def _delete_selected_marker(self):
        if self.selected_marker:
            self.db.delete_marker(self.selected_marker['id'])
            self.markers = self.db.get_markers(self.current_node['id'])
            self.selected_marker = None
    def _center_on_selected_marker(self):
        if self.selected_marker: self.cam_x, self.cam_y = self.selected_marker['world_x'], self.selected_marker['world_y']

    def draw(self):
        self.screen.fill((10, 10, 15)) 
        if self.render_strategy:
            self.render_strategy.draw(self.screen, self.cam_x, self.cam_y, self.zoom, SCREEN_WIDTH, SCREEN_HEIGHT, sea_level_meters=self.slider_water.value)
        if self.show_grid and self.render_strategy:
            center_x, center_y = SCREEN_WIDTH//2, SCREEN_HEIGHT//2
            map_sx, map_sy = center_x-(self.cam_x*self.zoom), center_y-(self.cam_y*self.zoom)
            map_w, map_h = self.render_strategy.width*self.zoom, self.render_strategy.height*self.zoom
            map_rect = pygame.Rect(map_sx, map_sy, map_w, map_h)
            self.screen.set_clip(map_rect)
            if self.grid_type == "HEX": self._draw_hex_grid(map_sx, map_sy)
            else: self._draw_square_grid(map_sx, map_sy)
            self.screen.set_clip(None)
            pygame.draw.rect(self.screen, (255, 255, 255), map_rect, 2)
        
        self._draw_markers()
        self._draw_scale_bar()
        if self.show_ui: self._draw_ui()
        if self.active_modal: self.active_modal.draw(self.screen)

    def _draw_hex_grid(self, start_x, start_y):
        hex_radius = self.grid_size * self.zoom
        if hex_radius < 5: return
        hex_w = math.sqrt(3) * hex_radius; vert_spacing = (2 * hex_radius) * 0.75
        screen_rel_x, screen_rel_y = -start_x, -start_y
        start_col, start_row = int(screen_rel_x/hex_w)-1, int(screen_rel_y/vert_spacing)-1
        cols_vis, rows_vis = int(SCREEN_WIDTH/hex_w)+3, int(SCREEN_HEIGHT/vert_spacing)+3
        color = (255, 255, 255, 30)
        for r in range(start_row, start_row + rows_vis):
            for q in range(start_col, start_col + cols_vis):
                x_off = (r % 2) * (hex_w / 2)
                cx, cy = start_x+(q*hex_w)+x_off, start_y+(r*vert_spacing)
                points = []
                for i in range(6):
                    angle = math.pi/3*i+(math.pi/6)
                    points.append((cx+hex_radius*math.cos(angle), cy+hex_radius*math.sin(angle)))
                pygame.draw.lines(self.screen, color, True, points, 1)

    def _draw_square_grid(self, start_x, start_y):
        size = self.grid_size * self.zoom; color = (255, 255, 255, 30)
        if size < 4: return
        map_w, map_h = self.render_strategy.width*self.zoom, self.render_strategy.height*self.zoom
        x, y = start_x, start_y
        while x <= start_x+map_w:
            if 0<=x<=SCREEN_WIDTH: pygame.draw.line(self.screen, color, (x,start_y), (x,start_y+map_h))
            x+=size
        while y <= start_y+map_h:
            if 0<=y<=SCREEN_HEIGHT: pygame.draw.line(self.screen, color, (start_x,y), (start_x+map_w,y))
            y+=size

    def _draw_markers(self):
        center_x, center_y = SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2
        mouse_pos = pygame.mouse.get_pos()
        self.hovered_marker = None
        for m in self.markers:
            sx, sy = center_x+(m['world_x']-self.cam_x)*self.zoom, center_y+(m['world_y']-self.cam_y)*self.zoom
            if 0<=sx<=SCREEN_WIDTH and 0<=sy<=SCREEN_HEIGHT:
                is_selected = self.selected_marker and self.selected_marker['id']==m['id']
                if is_selected and not self.dragging_marker:
                    pygame.draw.circle(self.screen, (255,255,0,100), (sx,sy), 20)
                    pygame.draw.circle(self.screen, (255,255,0), (sx,sy), 20, 2)
                t_main = self.font_icon.render(m['symbol'], True, (255,255,100))
                rect = t_main.get_rect(center=(sx,sy))
                self.screen.blit(t_main, rect)
                if rect.collidepoint(mouse_pos) and not self.active_modal and not self.dragging_marker: self.hovered_marker = m
        if self.hovered_marker:
            txt = f"{self.hovered_marker['symbol']} {self.hovered_marker['title']}"
            surf = self.font_ui.render(txt, True, (255,255,255))
            bg = pygame.Rect(mouse_pos[0]+15, mouse_pos[1]+15, surf.get_width()+10, surf.get_height()+10)
            pygame.draw.rect(self.screen, (0,0,0), bg); pygame.draw.rect(self.screen, (255,255,255), bg, 1)
            self.screen.blit(surf, (bg.x+5, bg.y+5))

    def _draw_scale_bar(self):
        km_per_hex = (self.grid_size / self.zoom) * 1.0 # 1px=1km
        text = f"Scale: 1 Hex = {km_per_hex:.2f} km"
        ts = self.font_ui.render(text, True, (200,200,200))
        bg = ts.get_rect(bottomright=(SCREEN_WIDTH-20, SCREEN_HEIGHT-20)); bg.inflate_ip(20,10)
        pygame.draw.rect(self.screen, (0,0,0,150), bg, border_radius=5)
        self.screen.blit(ts, (bg.x+10, bg.y+5))

    def _draw_ui(self):
        pygame.draw.rect(self.screen, (30,30,40), (0,0,260, SCREEN_HEIGHT)); pygame.draw.rect(self.screen, (100,100,100), (0,0,260, SCREEN_HEIGHT),2)
        if self.current_node: self.screen.blit(self.font_title.render("World Controls", True, (255,255,255)), (20,15))
        self.slider_water.draw(self.screen); self.slider_azimuth.draw(self.screen); self.slider_altitude.draw(self.screen); self.slider_intensity.draw(self.screen)
        self.screen.blit(self.font_ui.render(f"Grid Size: {self.grid_size}", True, (200,200,200)), (20,265))
        self.btn_grid_minus.draw(self.screen); self.btn_grid_plus.draw(self.screen)
        self.btn_regen.draw(self.screen)
        if self.selected_marker and not self.dragging_marker:
            panel_y = SCREEN_HEIGHT-160
            pygame.draw.rect(self.screen, (40,40,50), (10,panel_y,240,150), border_radius=5)
            pygame.draw.rect(self.screen, (150,150,150), (10,panel_y,240,150),1,border_radius=5)
            self.screen.blit(self.font_title.render(self.selected_marker['title'], True, (255,255,100)), (20, panel_y+10))
            self.screen.blit(self.font_ui.render(self.selected_marker['description'], True, (200,200,200)), (20,panel_y+45))
            self.btn_edit_marker.draw(self.screen); self.btn_delete_marker.draw(self.screen); self.btn_center_marker.draw(self.screen)