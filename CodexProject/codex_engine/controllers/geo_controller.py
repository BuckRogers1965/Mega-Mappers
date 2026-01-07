import pygame
import math
import json

from codex_engine.controllers.base_controller import BaseController
from codex_engine.ui.renderers.image_strategy import ImageMapStrategy
from codex_engine.ui.widgets import Slider, Button, ContextMenu
from codex_engine.ui.editors import NativeMarkerEditor
from codex_engine.ui.generic_settings import GenericSettingsEditor
from codex_engine.ui.info_panel import InfoPanel
from codex_engine.content.managers import WorldContent, LocalContent
from codex_engine.generators.world_gen import WorldGenerator
from codex_engine.generators.local_gen import LocalGenerator 
from codex_engine.generators.village_manager import VillageContentManager
from codex_engine.core.ai_manager import AIManager
from codex_engine.config import SCREEN_WIDTH, SCREEN_HEIGHT, SIDEBAR_WIDTH

COLOR_RIVER = (80, 120, 255)
COLOR_ROAD = (160, 82, 45)


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

class GeoController(BaseController):
    def __init__(self, map_viewer, db_manager, node_data, theme_manager, ai_manager):
        super().__init__(db_manager, node_data, theme_manager)
        self.map_viewer = map_viewer # Restore map_viewer reference
        self.screen = map_viewer.screen # Get screen from map_viewer

        self.zoom_factor = 1.05
        self.ai = ai_manager

                
        # --- DATA INSPECTION ---
        log(LOG_DEBUG, f"Node received by controller: ID={self.node.get('id')}, Type='{self.node.get('type')}'")
        log(LOG_DEBUG, f"  > Available Keys: {list(self.node.keys())}")
        
        # --- RENDERER INITIALIZATION CHECK ---
        self.render_strategy = None
        #if 'file_path' in self.node:
        print (f" *** {self.node}")
        if 'file_path' in self.node['properties']:
            log(LOG_DEBUG, "SUCCESS: 'file_path' found. Creating ImageMapStrategy.")
            from codex_engine.ui.renderers.image_strategy import ImageMapStrategy
            self.render_strategy = ImageMapStrategy(self.node['properties'], self.theme)
            print (f" draw_map {self.render_strategy} ")
        else:
            log(LOG_DEBUG, "FAILURE: 'file_path' key is MISSING from the node dictionary. Map will be black.")
            
        # Continue with standard setup
        if self.node['type'] == 'world_map':
            self.content_manager = WorldContent(self.db, self.node)
        else:
            from codex_engine.content.managers import LocalContent
            self.content_manager = LocalContent(self.db, self.node)
        
        self.vectors = self.db.get_children(self.node['id'], type_filter='vector')
        self.markers = self.db.get_children(self.node['id'], type_filter='poi')
        
        self.dragging_map = False
        self.context_menu = None
        self.font_ui = pygame.font.Font(None, 24)
        
        self.info_panel = InfoPanel(self.content_manager, self.db, self.node, self.font_ui, pygame.font.Font(None, 20))
        self._init_ui()
        
        log(LOG_DEBUG, f"Final Render Strategy State: {type(self.render_strategy)}")
        log(LOG_INFO, "EXIT: GeoController.__init__")
            
        #self.vectors = self.db.get_vectors(self.node['id'])
        #self.markers = self.db.get_markers(self.node['id'])
        self.vectors = self.db.get_children(self.node['id'], type_filter='vector')
        self.markers = self.db.get_children(self.node['id'], type_filter='poi')
        
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
        #self.grid_size = float(self.node['metadata'].get('grid_size', 64))
        self.grid_size = float(self.node.get('grid_size', 64))

        self.active_tab = "INFO" 

        self.font_ui = pygame.font.Font(None, 24)
        self.font_small = pygame.font.Font(None, 20)
        
        self.info_panel = InfoPanel(self.content_manager, self.db, self.node, self.font_ui, self.font_small)

        self._init_ui()

    def _init_ui(self):
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
        
        self.slider_water = Slider(20, 140, full_w, 15, -11000.0, 9000.0, self.node.get('sea_level', 0.0), "Sea Level (m)")
        self.slider_azimuth = Slider(20, 180, full_w, 15, 0, 360, self.node.get('light_azimuth', 315), "Light Dir")
        self.slider_altitude = Slider(20, 220, full_w, 15, 0, 90, self.node.get('light_altitude', 45), "Light Height")
        self.slider_intensity = Slider(20, 260, full_w, 15, 0.0, 2.0, 1.2, "Light Power")
        self.slider_contour = Slider(20, 300, full_w, 15, 0, 500, self.node.get('contour_interval', 0), "Contours (m)")

        self.btn_grid_minus = Button(140, 340, 30, 30, "-", self.font_ui, (100,100,100), (150,150,150), (255,255,255), self.dec_grid)
        self.btn_grid_plus = Button(180, 340, 30, 30, "+", self.font_ui, (100,100,100), (150,150,150), (255,255,255), self.inc_grid)
        self.btn_regen = Button(20, 380, full_w, 30, "Regenerate Map", self.font_ui, (100, 100, 100), (150, 150, 150), (255,255,255), self.regenerate_seed)
        self.btn_gen_details = Button(20, 420, full_w, 30, "AI Gen Content", self.font_ui, (100, 100, 200), (150, 150, 250), (255,255,255), self._generate_ai_details)
        self.btn_settings = Button(20, 460, SIDEBAR_WIDTH - 40, 30, "Map Settings", self.font_ui, (100, 100, 100), (120, 120, 120), (255, 255, 255), self.open_map_settings)

    def open_map_settings(self):
        chain = [('node', self.node['id']), ('campaign', self.node['campaign_id'])]
        GenericSettingsEditor(pygame.display.get_surface(), self.ai.config, self.ai, context_chain=chain)

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
            self.widgets.extend([self.slider_water, self.slider_azimuth, self.slider_altitude, self.slider_intensity, self.slider_contour, self.btn_grid_minus, self.btn_grid_plus, self.btn_regen, self.btn_gen_details, self.btn_settings])
        elif self.active_tab == "TOOLS":
            if self.active_vector: self.widgets.extend([self.btn_save_vec, self.btn_cancel_vec]); 
            if self.active_vector and self.active_vector.get('id'): self.widgets.append(self.btn_delete_vec)
            else: self.widgets.extend([self.btn_new_road, self.btn_new_river])
        elif self.active_tab == "INFO": self.widgets.extend(self.info_panel.widgets)

        if self.render_strategy:
            self.render_strategy.set_light_direction(self.slider_azimuth.value, self.slider_altitude.value)
            self.render_strategy.set_light_intensity(self.slider_intensity.value)

    def handle_input(self, event, cam_x, cam_y, zoom):
        if self.context_menu:
            if self.context_menu.handle_event(event): self.context_menu = None
            return None
        for widget in self.widgets:
            res = widget.handle_event(event)
            if res: return res if isinstance(res, dict) else None
        if self.active_tab == "INFO" and self.info_panel.handle_event(event): return None
        
        if event.type == pygame.KEYDOWN and event.key == pygame.K_DELETE and self.selected_point_idx is not None:
            if self.active_vector:
                props = self.active_vector.get('properties', self.active_vector)
                points = props.get('points', [])
                if 0 <= self.selected_point_idx < len(points):
                    log(LOG_DEBUG, f"Deleting point index {self.selected_point_idx} from vector.")
                    del points[self.selected_point_idx]
                    self.selected_point_idx = None
                    return None

        center_x, center_y = SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2
        
        if event.type == pygame.MOUSEMOTION:
            world_x = ((event.pos[0] - center_x) / zoom) + cam_x
            world_y = ((event.pos[1] - center_y) / zoom) + cam_y
            
            if self.dragging_point and self.selected_point_idx is not None:
                props = self.active_vector.get('properties', self.active_vector)
                props['points'][self.selected_point_idx] = [world_x, world_y]
                return None
            
            if self.dragging_marker:
                props = self.dragging_marker.get('properties', self.dragging_marker)
                props['world_x'] = world_x - self.drag_offset[0]
                props['world_y'] = world_y - self.drag_offset[1]
                return None
                
            if self.dragging_map:
                dx = event.pos[0] - self.drag_start_pos[0]; dy = event.pos[1] - self.drag_start_pos[1]
                return {"action": "pan", "pos": (self.drag_start_cam[0] - dx / zoom, self.drag_start_cam[1] - dy / zoom)}

        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.pos[0] < SIDEBAR_WIDTH: return None
            world_x = ((event.pos[0] - center_x) / zoom) + cam_x
            world_y = ((event.pos[1] - center_y) / zoom) + cam_y

            if event.button == 1: 
                self.drag_start_pos = event.pos; self.drag_start_cam = (cam_x, cam_y)
                
                if self.active_vector:
                    self._handle_vector_click(event, world_x, world_y, zoom)
                    return
                
                if self.hovered_marker:
                    if self.active_tab == "TOOLS":
                        log(LOG_DEBUG, f"Started dragging marker: {self.hovered_marker.get('name')}")
                        self.dragging_marker = self.hovered_marker
                        m_props = self.hovered_marker.get('properties', {})
                        self.drag_offset = (world_x - m_props.get('world_x',0), world_y - m_props.get('world_y',0))
                    self.selected_marker = self.hovered_marker
                    return

                if self.active_tab == "TOOLS":
                    if self._handle_pixel_selection(event, world_x, world_y, zoom):
                        return
                
                if pygame.key.get_mods() & pygame.KMOD_SHIFT:
                    self._create_new_marker(world_x, world_y, event.pos)
                    return
                
                self.dragging_map = True

            elif event.button == 3:
                self._open_context_menu(event)

        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            drag_dist = math.hypot(event.pos[0] - self.drag_start_pos[0], event.pos[1] - self.drag_start_pos[1])

            if self.dragging_marker:
                m = self.dragging_marker
                p = m.get('properties', {})
                log(LOG_INFO, f"Updating Marker ID {m['id']} position to ({p['world_x']:.1f}, {p['world_y']:.1f})")
                
                self.db.update_node(m['id'], properties={'world_x': p['world_x'], 'world_y': p['world_y']})
                self.markers = self.db.get_children(self.node['id'], type_filter='poi')
                
                # Directly check properties (NO METADATA)
                if p.get('is_view_marker') and p.get('is_active'):
                    self.dragging_marker = None
                    return {"action": "update_player_view"}
            
            if self.hovered_marker and drag_dist < 5:
                props = self.hovered_marker.get('properties', {})
                
                # --- FIX: PARTY VIEW TOGGLE (NO METADATA) ---
                print (f"  *** props  {props}")
                if props.get('is_view_marker'):
                    new_state = not props.get('is_active', False)
                    log(LOG_INFO, f"Toggling Party View -> {new_state}")
                    self.db.update_node(self.hovered_marker['id'], properties={'is_active': new_state})
                    self.markers = self.db.get_children(self.node['id'], type_filter='poi')
                    return {"action": "update_player_view"}

                log(LOG_INFO, f"Short click on {self.hovered_marker.get('name')} detected. Triggering enter_marker.")
                fresh_marker = next((m for m in self.markers if m['id'] == self.hovered_marker['id']), self.hovered_marker)
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
        
        # Safely extract points from Node structure
        props = self.active_vector.get('properties', self.active_vector)
        points = props.get('points', [])
        
        for i, pt in enumerate(points):
            sx, sy = center_x + (pt[0] - wx) * zoom, center_y + (pt[1] - wy) * zoom
            if math.hypot(sx - event.pos[0], sy - event.pos[1]) < 10:
                self.selected_point_idx, self.dragging_point = i, True
                return
        
        # Append to the list reference inside properties
        points.append([wx, wy])
        self.selected_point_idx = len(points) - 1
        self.dragging_point = True

    def _handle_pixel_selection(self, event, world_x, world_y, zoom):
        try:
            pixel = pygame.display.get_surface().get_at(event.pos)[:3]
            target_type = None
            if pixel == COLOR_ROAD: target_type = "road"
            elif pixel == COLOR_RIVER: target_type = "river"
            
            if target_type:
                log(LOG_DEBUG, f"Pixel select detected type: {target_type}")
                closest, min_d = None, float('inf')
                
                for vec in self.vectors:
                    # Unwrap properties
                    props = vec.get('properties', vec)
                    
                    # Check type (might be on Node or in Props)
                    v_type = vec.get('type')
                    if v_type == 'vector': v_type = props.get('type')
                    
                    if v_type != target_type: continue
                    
                    pts = props.get('points', [])
                    for pt in pts:
                        d = math.hypot(pt[0]-world_x, pt[1]-world_y)
                        if d < min_d: min_d, closest = d, vec
                
                if closest and min_d < (150 / zoom): 
                    log(LOG_INFO, f"Selected vector ID: {closest.get('id')}")
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

    def start_new_vector(self, vtype): 
        log(LOG_INFO, f"ENTER: start_new_vector (Type: {vtype})")
        # Create a temporary local dict mimicking the DB Node structure
        # This ensures consistency with how we read nodes from the DB
        self.active_vector = {
            'id': None,
            'type': 'vector',
            'properties': {
                'points': [], 
                'type': vtype, 
                'width': 4 if vtype=='road' else 8
            }
        }
        log(LOG_DEBUG, f"Active vector initialized: {self.active_vector}")
        log(LOG_INFO, "EXIT: start_new_vector")

    def save_active_vector(self):
        log(LOG_INFO, "ENTER: save_active_vector")
        if self.active_vector:
            # Safely extract properties whether it's a raw dict or a node
            props = self.active_vector.get('properties', {})
            points = props.get('points', [])
            
            log(LOG_DEBUG, f"Processing vector with {len(points)} points.")

            if len(points) > 1:
                # payload for the 'properties' column
                v_props = {
                    "points": points,
                    "width": props.get('width', 4),
                    "type": props.get('type', 'vector')
                }
                
                if self.active_vector.get('id'):
                    nid = self.active_vector['id']
                    log(LOG_DEBUG, f"Updating existing Vector Node ID: {nid}")
                    self.db.update_node(nid, properties=v_props)
                else:
                    log(LOG_DEBUG, "Creating new Vector Node")
                    self.db.create_node(
                        type='vector', 
                        name=f"{v_props['type']} vector", 
                        parent_id=self.node['id'], 
                        properties=v_props
                    )
                
                # Refresh from DB
                self.vectors = self.db.get_children(self.node['id'], type_filter='vector')
                log(LOG_DEBUG, f"Vectors refreshed. Count: {len(self.vectors)}")
            else:
                log(LOG_DEBUG, "Vector too short to save. Discarding.")

        self.active_vector = None
        log(LOG_INFO, "EXIT: save_active_vector")

    def delete_vector(self):
        log(LOG_INFO, "ENTER: delete_vector")
        if self.active_vector and self.active_vector.get('id'):
            nid = self.active_vector['id']
            log(LOG_DEBUG, f"Deleting Vector Node ID: {nid}")
            self.db.delete_node(nid)
            
            self.vectors = self.db.get_children(self.node['id'], type_filter='vector')
            log(LOG_DEBUG, f"Vectors refreshed. Count: {len(self.vectors)}")
        else:
            log(LOG_DEBUG, "No active vector ID found (unsaved or null). Cannot delete.")
            
        self.active_vector = None
        log(LOG_INFO, "EXIT: delete_vector")

    def cancel_vector(self):
        log(LOG_INFO, "ENTER: cancel_vector")
        if self.active_vector:
            log(LOG_DEBUG, "Discarding active vector changes.")
        self.active_vector = None
        log(LOG_INFO, "EXIT: cancel_vector")

    def _open_edit_modal(self):
        if self.selected_marker: 
            print(f"[DEBUG GEO] Opening editor for Marker ID: {self.selected_marker['id']}")
            # This is the standard data structure, passed directly from the DB node.
            editor_input = {
                'id': self.selected_marker['id'],
                'name': self.selected_marker.get('name', 'Unknown'),
                'properties': self.selected_marker.get('properties', {})
            }
            
            from codex_engine.ui.editors import NativeMarkerEditor
            NativeMarkerEditor(editor_input, self.node['type'], self._save_marker)

    def _delete_selected_marker(self):
        log(LOG_INFO, "ENTER: _delete_selected_marker")
        if self.selected_marker: 
            nid = self.selected_marker['id']
            log(LOG_DEBUG, f"Deleting Marker Node {nid}")
            
            self.db.delete_node(nid)
            
            self.markers = self.db.get_children(self.node['id'], type_filter='poi')
            self.selected_marker = None
        log(LOG_INFO, "EXIT: _delete_selected_marker")

    def _center_on_selected_marker(self):
        log(LOG_INFO, "ENTER: _center_on_selected_marker")
        if self.selected_marker:
            p = self.selected_marker.get('properties', {})
            x = p.get('world_x', 0)
            y = p.get('world_y', 0)
            log(LOG_DEBUG, f"Panning to ({x}, {y})")
            return {"action": "pan", "pos": (x, y)}

    def _save_marker(self, marker_id, name, final_properties):
        print(f"[DEBUG GEO] Save. Marker ID: {marker_id}, Name: {name}")
        
        if marker_id: 
            print(f"[DEBUG GEO] Updating Node {marker_id}. Keys: {list(final_properties.keys())}")
            self.db.update_node(marker_id, name=name, properties=final_properties)
        else: 
            # This is a new marker, use the temp data for context
            temp_data = self.marker_data_for_editor
            
            # The editor doesn't handle these, so we re-apply them from the creation context.
            final_properties['world_x'] = temp_data['properties']['world_x']
            final_properties['world_y'] = temp_data['properties']['world_y']
            final_properties['symbol'] = temp_data['properties']['symbol']
            final_properties['marker_type'] = temp_data['properties']['marker_type']
            
            print(f"[DEBUG GEO] Creating New Node. Keys: {list(final_properties.keys())}")
            self.db.create_node(type='poi', name=name, parent_id=self.node['id'], properties=final_properties)

        self.markers = self.db.get_children(self.node['id'], type_filter='poi')
        self.selected_marker = None

    def _generate_ai_details(self):
        if self.node['type'] == 'local_map':
            try: vm = VillageContentManager(self.node, self.db, self.ai, self.screen); vm.generate_details(); return {"action": "reload_node"}
            except Exception as e: print(f"AI Error: {e}")

    def _create_new_marker(self, wx, wy, screen_pos):
        log(LOG_INFO, f"ENTER: _create_new_marker at ({wx:.1f}, {wy:.1f})")
        self.pending_click_pos = (wx, wy)
        sx, sy = screen_pos # Use the original screen position directly

        # Define options based on map context
        if self.node['type'] == 'world_map':
            menu_options = [
                ("Add Village", lambda: self._create_specific_marker("village")),
                ("Add Lair", lambda: self._create_specific_marker("lair")),
                ("Add Landmark", lambda: self._create_specific_marker("landmark"))
            ]
        else: # local_map
            menu_options = [
                ("Add Building", lambda: self._create_specific_marker("building")),
                ("Add Lair", lambda: self._create_specific_marker("lair")),
                ("Add Portal", lambda: self._create_specific_marker("portal")),
                ("Add Note", lambda: self._create_specific_marker("note"))
            ]

        from codex_engine.ui.widgets import ContextMenu
        self.context_menu = ContextMenu(sx, sy, menu_options, self.font_ui)
        return {"action": "consumed"}

    def _create_specific_marker(self, mtype):
        print(f"[DEBUG GEO] Creating specific marker of type: {mtype}")
        self.context_menu = None # Close menu
        
        title = f"New {mtype.title()}"
        symbol_map = {"village": "house", "lair": "skull", "landmark": "star", "building": "house", "portal": "door", "note": "star"}
        
        props = {
            'world_x': self.pending_click_pos[0],
            'world_y': self.pending_click_pos[1],
            'marker_type': mtype,
            'description': '',
            'symbol': symbol_map.get(mtype, 'star'),
        }
        
        # This is the standard data structure the Editor expects.
        marker_data = {'id': None, 'name': title, 'properties': props}
        
        # Store for the save function to access.
        self.marker_data_for_editor = marker_data 
        
        from codex_engine.ui.editors import NativeMarkerEditor
        NativeMarkerEditor(marker_data, self.node['type'], self._save_marker)

    def draw_map(self, screen, cam_x, cam_y, zoom, screen_w, screen_h):

        #print (f" draw_map {self.render_strategy} ")
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
        #  m = self.hovered_marker; text = m.get('description', 'No details.')
        m = self.hovered_marker; props = m.get('properties', {}); text = props.get('description', 'No details.')
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
        
        # Reset hover state for this frame
        prev_hover = self.hovered_marker
        self.hovered_marker = None

        for m in self.markers:
            props = m.get('properties', {})
            
            wx = props.get('world_x', 0)
            wy = props.get('world_y', 0)
            
            sx = center_x + (wx - cam_x) * zoom
            sy = center_y + (wy - cam_y) * zoom

            # Viewport Culling
            if not (-50 <= sx <= SCREEN_WIDTH+50 and -50 <= sy <= SCREEN_HEIGHT+50): 
                continue
            
            # Hitbox
            click_rect = pygame.Rect(sx-10, sy-10, 20, 20)
            
            # Check Hover
            if click_rect.collidepoint(mouse_pos) and not self.dragging_marker and not self.context_menu:
                self.hovered_marker = m

            # Render Logic
            sym = props.get('symbol', 'star').lower()
            if "skull" in sym: 
                pygame.draw.rect(screen, (50, 20, 20), click_rect)
                pygame.draw.rect(screen, (255, 100, 100), click_rect, 2)
            elif "house" in sym: 
                pts = [(sx, sy - 12), (sx + 10, sy - 4), (sx + 7, sy + 10), (sx - 7, sy + 10), (sx - 10, sy - 4)]
                pygame.draw.polygon(screen, (100, 150, 200), pts)
                pygame.draw.polygon(screen, (200, 200, 255), pts, 2)
            else: 
                pygame.draw.circle(screen, (200, 200, 200), (int(sx), int(sy)), 8)
                pygame.draw.circle(screen, (50, 50, 50), (int(sx), int(sy)), 8, 2)
            
            # Highlight Selection/Hover
            if self.hovered_marker == m or (self.selected_marker and self.selected_marker['id'] == m['id']):
                pygame.draw.circle(screen, (255, 255, 0), (int(sx), int(sy)), 14, 2)
            
            # Draw Title Label
            title_surf = self.font_ui.render(m['name'], True, (255, 255, 255))
            t_rect = title_surf.get_rect(center=(sx, sy + 20))
            pygame.draw.rect(screen, (0,0,0,150), t_rect.inflate(4, 2))
            screen.blit(title_surf, t_rect)

        # Log only on state change to avoid console spam
        if prev_hover != self.hovered_marker:
            if self.hovered_marker:
                log(LOG_DEBUG, f"Hover Start: {self.hovered_marker.get('name')}")
            else:
                log(LOG_DEBUG, "Hover End")

    def render_player_view_surface(self):
        # 1. Find the active eye marker using the properties dictionary
        print (f" *** render_player_view_surface { self.markers }")
        view_marker = next((m for m in self.markers if m.get('properties', {}).get('is_view_marker') and m.get('properties', {}).get('is_active')), None)
        
        #print (f" *** render_player_view_surface is view marker { self.markers.get('properties', {}).get('is_view_marker') }")
        #print (f" *** render_player_view_surface { self.markers.get('properties', {}).get('is_active') }")

        if not view_marker or not self.render_strategy: return None
        if not hasattr(self.render_strategy, 'heightmap'): return None
        
        # 2. Extract values from properties (NO METADATA)
        props = view_marker.get('properties', {})
        mx, my = props.get('world_x', 0), props.get('world_y', 0)
        zoom = props.get('zoom', 1.5)
        
        heightmap = self.render_strategy.heightmap
        h_map_h, h_map_w = heightmap.shape

        w, h = 1920, 1080
        center_x, center_y = w // 2, h // 2
        
        # 3. Create surface and draw map using extracted mx, my
        temp_surface = pygame.Surface((w, h))
        self.draw_map(temp_surface, mx, my, zoom, w, h)

        # 4. Raycasting setup using extracted coordinates
        start_x_int, start_y_int = int(mx), int(my)

        STANDING_HEIGHT = 0.01 

        if 0 <= start_x_int < h_map_w and 0 <= start_y_int < h_map_h:
            ground_z = heightmap[start_y_int, start_x_int]
            eye_height = ground_z + STANDING_HEIGHT
        else:
            eye_height = 0.3

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
            
            hit_x, hit_y = curr_x + (cos_a * max_dist), curr_y + (sin_a * max_dist)
            prev_z = eye_height

            while dist < max_dist:
                dist += step_size
                curr_x += cos_a * step_size
                curr_y += sin_a * step_size
                
                grid_x, grid_y = int(curr_x), int(curr_y)
                
                if 0 <= grid_x < h_map_w and 0 <= grid_y < h_map_h:
                    target_z = heightmap[grid_y, grid_x]
                    
                    if target_z <= eye_height:
                        prev_z = eye_height
                    else:
                        if target_z >= prev_z:
                            prev_z = target_z
                        else:
                            hit_x, hit_y = curr_x, curr_y
                            break
                else:
                    hit_x, hit_y = curr_x, curr_y
                    break
            
            screen_x = center_x + (hit_x - mx) * zoom
            screen_y = center_y + (hit_y - my) * zoom
            polygon_points.append((screen_x, screen_y))

        shadow_layer = pygame.Surface((w, h), pygame.SRCALPHA)
        shadow_layer.fill((0, 0, 0, 255)) 
        
        if len(polygon_points) > 2:
            mask_surf = pygame.Surface((w, h), pygame.SRCALPHA) 
            mask_surf.fill((0,0,0,0)) 
            
            pygame.draw.polygon(mask_surf, (255, 255, 255, 255), polygon_points)
            
            shadow_layer.blit(mask_surf, (0,0), special_flags=pygame.BLEND_RGBA_SUB)

        temp_surface.blit(shadow_layer, (0, 0))
        return temp_surface

    def get_metadata_updates(self):
        return {'sea_level': self.slider_water.value, 'light_azimuth': self.slider_azimuth.value, 'light_altitude': self.slider_altitude.value, 'contour_interval': self.slider_contour.value, 'grid_size': self.grid_size}

    def cleanup(self): pass
