import pygame
from codex_engine.config import SCREEN_WIDTH, SCREEN_HEIGHT
from codex_engine.core.db_manager import DBManager
from codex_engine.controllers.geo_controller import GeoController
from codex_engine.controllers.tactical_controller import TacticalController

class MapViewer:
    def __init__(self, screen, theme_manager):
        self.screen = screen
        self.theme = theme_manager
        self.db = DBManager()
        
        self.cam_x, self.cam_y, self.zoom = 0, 0, 1.0
        self.current_node = None
        self.controller = None
        
        self.show_ui = True
        self.font_title = pygame.font.Font(None, 32)
        self.font_ui = pygame.font.Font(None, 24)

    def set_node(self, node_data):
        if self.controller:
            self.save_current_state()
            self.controller.cleanup()
            
        self.current_node = node_data
        metadata = node_data.get('metadata', {})
        geo = node_data.get('geometry_data', {})

        node_type = node_data.get('type', 'world_map')
        
        if node_type in ['world_map', 'local_map']:
            self.controller = GeoController(self.db, node_data, self.theme)
        elif node_type in ['dungeon_level', 'building_interior']:
            self.controller = TacticalController(self.db, node_data, self.theme)
        else:
            self.controller = GeoController(self.db, node_data, self.theme)

        # Restore Camera or set default
        if 'cam_x' in metadata:
            self.cam_x, self.cam_y = metadata['cam_x'], metadata['cam_y']
            self.zoom = metadata.get('zoom', 1.0)
        elif node_type in ['dungeon_level', 'building_interior']:
            # FIX: Center camera on tactical maps if not set
            self.cam_x = geo.get('width', 30) / 2
            self.cam_y = geo.get('height', 30) / 2
            self.zoom = 1.0
        else:
            self.cam_x, self.cam_y, self.zoom = 0, 0, 1.0

    def save_current_state(self):
        if not self.current_node or not self.controller: return
        updates = self.controller.get_metadata_updates()
        updates['cam_x'] = self.cam_x
        updates['cam_y'] = self.cam_y
        updates['zoom'] = self.zoom
        current_meta = self.current_node.get('metadata', {})
        current_meta.update(updates)
        self.db.update_node_data(self.current_node['id'], metadata=current_meta)

    def handle_input(self, event):
        if not self.controller: return

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_h: self.show_ui = not self.show_ui; return
            if event.key == pygame.K_s: self.save_current_state(); return

        keys = pygame.key.get_pressed()
        speed = 5 / self.zoom 
        if keys[pygame.K_LSHIFT]: speed *= 3
        if keys[pygame.K_LEFT]: self.cam_x -= speed
        if keys[pygame.K_RIGHT]: self.cam_x += speed
        if keys[pygame.K_UP]: self.cam_y -= speed
        if keys[pygame.K_DOWN]: self.cam_y += speed
        
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_LEFTBRACKET: self.zoom = max(0.1, self.zoom * 0.9)
            if event.key == pygame.K_RIGHTBRACKET: self.zoom = min(10.0, self.zoom * 1.1)

        result = self.controller.handle_input(event, self.cam_x, self.cam_y, self.zoom)
        
        if result:
            if result.get("action") == "pan":
                self.cam_x, self.cam_y = result['pos']
            elif result.get("action") == "reload_node":
                updated_node = self.db.get_node(self.current_node['id'])
                self.set_node(updated_node)
            return result 

    def draw(self):
        self.screen.fill((10, 10, 15))
        if not self.controller: return
        self.controller.update()
        self.controller.draw_map(self.screen, self.cam_x, self.cam_y, self.zoom, SCREEN_WIDTH, SCREEN_HEIGHT)
        if self.show_ui: self._draw_sidebar()
        self.controller.draw_overlays(self.screen, self.cam_x, self.cam_y, self.zoom)
        self._draw_scale_bar()

    def _draw_sidebar(self):
        pygame.draw.rect(self.screen, (30,30,40), (0,0,260, SCREEN_HEIGHT))
        pygame.draw.rect(self.screen, (100,100,100), (0,0,260, SCREEN_HEIGHT), 2)
        if self.current_node: 
            title = "Unknown"
            if self.current_node['type'] == 'local_map': title = "Local Map"
            elif self.current_node['type'] == 'world_map': title = "World Map"
            elif self.current_node['type'] in ['dungeon_level', 'building_interior']: title = "Tactical Map"
            self.screen.blit(self.font_title.render(title, True, (255,255,255)), (20,15))

        if self.controller:
            for widget in self.controller.widgets: widget.draw(self.screen)
            if hasattr(self.controller, 'active_vector') and self.controller.active_vector:
                lbl = self.font_ui.render(f"EDIT: {self.controller.active_vector['type'].upper()}", True, (255,200,100))
                self.screen.blit(lbl, (20, 370))

    def _draw_scale_bar(self):
        grid_size = getattr(self.controller, 'grid_size', 32)
        km_per_unit = (grid_size / self.zoom) * 1.0 
        text = f"Scale: 1 Unit = {km_per_unit:.2f} m" if self.current_node['type'] != 'world_map' else f"Scale: 1 Unit = {km_per_unit:.2f} km"
        ts = self.font_ui.render(text, True, (200,200,200))
        bg = ts.get_rect(bottomright=(SCREEN_WIDTH-20, SCREEN_HEIGHT-20)); bg.inflate_ip(20,10)
        pygame.draw.rect(self.screen, (0,0,0,150), bg, border_radius=5)
        self.screen.blit(ts, (bg.x+10, bg.y+5))
