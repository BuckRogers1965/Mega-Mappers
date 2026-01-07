import pygame
from codex_engine.config import SCREEN_WIDTH, SCREEN_HEIGHT, SIDEBAR_WIDTH
from codex_engine.core.db_manager import DBManager
from codex_engine.controllers.geo_controller import GeoController
from codex_engine.controllers.tactical_controller import TacticalController

# --- INSTRUMENTATION CONFIG ---
LOG_NONE  = 0
LOG_INFO  = 1 # Function Enter/Exit
LOG_DEBUG = 2 # Data Inspection
APP_VERBOSITY = LOG_DEBUG 

def log(level, message):
    if APP_VERBOSITY >= level:
        prefix = ""
        if level == LOG_INFO: prefix = "[APP INFO]"
        if level == LOG_DEBUG: prefix = "[APP DEBUG]"
        print(f"{prefix} {message}")

class MapViewer:
    def __init__(self, screen, theme_manager, ai_manager, db_manager):
        self.screen = screen
        self.theme = theme_manager
        self.ai = ai_manager
        self.db = db_manager
        
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
        
        props = node_data.get('properties', {})
        geo = props.get('geometry_data', {}) # Kept for legacy or future use
        node_type = node_data.get('type', 'world_map')
        
        # --- FIX: Ensure Party View Marker Exists ---
        markers = self.db.get_children(self.current_node['id'], type_filter='poi')
        view_marker_exists = any(m.get('properties', {}).get('is_view_marker') for m in markers)

        if not view_marker_exists:
            log(LOG_DEBUG, f"No Party View found for Node {self.current_node['id']}. Creating one.")
            
            # Determine center point for the new marker
            if node_type in ['dungeon_level', 'building_interior', 'tactical_map']:
                geom_props = props.get('geometry', {})
                center_x = geom_props.get('width', 30) / 2.0
                center_y = geom_props.get('height', 30) / 2.0
            else:
                center_x = props.get('width', SCREEN_WIDTH) / 2.0
                center_y = props.get('height', SCREEN_HEIGHT) / 2.0
                
            marker_props = {
                "world_x": center_x,
                "world_y": center_y,
                "symbol": "eye",
                "description": "The party's current position and view.",
                "is_view_marker": True,
                "is_active": True,
                "zoom": 1.5,
                "radius": 15,
                "explored_tiles": {},
                "facing_degrees": 270,
                "beam_degrees": 360
            }
            
            # This was the missing line:
            self.db.create_node('poi', 'Party View', self.current_node['id'], properties=marker_props)
        # --- END FIX ---

        # 1. Initialize Controller
        if node_type in ['dungeon_level', 'building_interior', 'tactical_map', 'compound', 'dungeon_complex']:
            self.controller = TacticalController(self, self.db, node_data, self.theme, self.ai)
        else:
            self.controller = GeoController(self, self.db, node_data, self.theme, self.ai)

        # 2. Camera Setup
        if 'cam_x' in props:
            self.cam_x, self.cam_y = props['cam_x'], props['cam_y']
            self.zoom = props.get('zoom', 1.0)
        elif node_type in ['dungeon_level', 'building_interior', 'tactical_map']:
            geom_props = props.get('geometry', {})
            self.cam_x = geom_props.get('width', 30) / 2
            self.cam_y = geom_props.get('height', 30) / 2
            self.zoom = 1.0
        else:
            map_w = props.get('width', SCREEN_WIDTH)
            map_h = props.get('height', SCREEN_HEIGHT)
            self.cam_x, self.cam_y = map_w / 2, map_h / 2
            self.zoom = 1.0
            
        # Refresh markers in controller after potential creation
        if self.controller:
            self.controller.markers = self.db.get_children(self.current_node['id'], type_filter='poi')
 
    def handle_zoom(self, direction, mouse_pos):
        if not self.controller: return
        zoom_speed = getattr(self.controller, 'zoom_factor', 1.2)
        if direction > 0: self.zoom = min(20.0, self.zoom * zoom_speed)
        else: self.zoom = max(0.05, self.zoom / zoom_speed)

    def save_current_state(self):
        if not self.current_node or not self.controller: return
        updates = self.controller.get_metadata_updates()
        updates['cam_x'] = self.cam_x
        updates['cam_y'] = self.cam_y
        updates['zoom'] = self.zoom
        current_meta = self.current_node.get('properties', {})
        current_meta.update(updates)
        self.db.update_node(self.current_node['id'], properties=current_meta)

    def handle_input(self, event):
        if not self.controller: return
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
        if self.show_ui:
            pygame.draw.rect(self.screen, (30,30,40), (0,0, SIDEBAR_WIDTH, SCREEN_HEIGHT))
            pygame.draw.rect(self.screen, (100,100,100), (0,0, SIDEBAR_WIDTH, SCREEN_HEIGHT), 2)
            if self.current_node: 
                title = self.current_node.get('name', 'Unknown')
                type_str = self.current_node.get('type', 'unknown').replace('_', ' ').title()
                self.screen.blit(self.font_title.render(f"{title}", True, (255,255,255)), (20,15))
                self.screen.blit(self.font_ui.render(f"({type_str})", True, (150,150,150)), (20,45))
            if self.controller:
                for widget in self.controller.widgets: widget.draw(self.screen)
                
        self.controller.draw_overlays(self.screen, self.cam_x, self.cam_y, self.zoom)
        self._draw_scale_bar()

    def _draw_scale_bar(self):
        map_width_m = self.current_node.get('geometry_data', {}).get('width', 100)
        if self.current_node['type'] == 'world_map': unit, scale_factor = "km", 1000
        else: unit, scale_factor = "m", map_width_m
        
        units_per_pixel = (scale_factor / self.current_node.get('metadata',{}).get('width', 1024)) / self.zoom
        bar_width_px = 100
        bar_units = bar_width_px * units_per_pixel

        text = f"{bar_units:.1f} {unit}"
        ts = self.font_ui.render(text, True, (200,200,200))
        
        bg_rect = pygame.Rect(SCREEN_WIDTH - 140, SCREEN_HEIGHT - 40, 120, 30)
        pygame.draw.rect(self.screen, (0,0,0,150), bg_rect, border_radius=5)
        
        line_y = bg_rect.centery + 5
        pygame.draw.line(self.screen, (200,200,200), (bg_rect.x + 10, line_y), (bg_rect.x + 10 + bar_width_px, line_y), 2)
        
        text_rect = ts.get_rect(midbottom=(bg_rect.centerx, line_y - 2))
        self.screen.blit(ts, text_rect)
