import pygame
import json
import math
import random
from codex_engine.controllers.base_controller import BaseController
from codex_engine.ui.renderers.tactical.tactical_renderer import TacticalRenderer
from codex_engine.generators.dungeon_content_manager import DungeonContentManager
from codex_engine.ui.ai_request_editor import AIRequestEditor
from codex_engine.ui.widgets import Button, StructureBrowser, ContextMenu
from codex_engine.ui.generic_settings import GenericSettingsEditor
from codex_engine.content.managers import TacticalContent
from codex_engine.core.ai_manager import AIManager
from codex_engine.config import SCREEN_WIDTH, SCREEN_HEIGHT, SIDEBAR_WIDTH

class TacticalController(BaseController):
    def __init__(self, map_viewer, db_manager, node_data, theme_manager, ai_manager):
        super().__init__(db_manager, node_data, theme_manager)
        self.map_viewer = map_viewer
        self.screen = map_viewer.screen
        
        self.dragging_map = False
        self.drag_start_pos = (0, 0)
        self.drag_start_cam = (0, 0)

        self.zoom_factor = 1.05
        self.ai = ai_manager

        properties = self.node['properties']
        geo = properties['geometry']
        self.grid_data = geo.get('grid', [[]])
        self.markers = self.db.get_children(self.node['id'], type_filter='poi')

        self.grid_width = geo.get('width', len(self.grid_data[0]) if self.grid_data else 10)
        self.grid_height = geo.get('height', len(self.grid_data) if self.grid_data else 10)
        self.cell_size = 32

        self.active_brush = 1
        self.painting = False
        self.active_tab = "LOC"
        self.hovered_marker = None
        self.dragging_rotation = False

        self.selected_marker = None
        self.dragging_marker = None
        self.drag_offset = (0,0)
        self.drag_start_pos = (0, 0)
        self.context_menu = None
        self.pending_click_pos = None
        
        self.font_ui = pygame.font.Font(None, 24)
        self.font_small = pygame.font.Font(None, 20)
        
        self.content_manager = TacticalContent(self.db, self.node)
        self.structure_browser = None
        self.dungeon_content_manager = DungeonContentManager(self.node, self.db, self.ai)

        style = self.node['properties'].get('render_style', 'hand_drawn')
        self.renderer = TacticalRenderer(self.node, self.cell_size, style)

        self.static_map_surf = None
        self._render_static_map()
        self._init_ui()

    def _render_static_map(self):
        if self.renderer:
            self.static_map_surf = self.renderer.render()

    def _toggle_triggers(self): self.show_triggers = not self.show_triggers

    def _update_door_occlusion(self, door_marker):
        props = door_marker['properties']
        state = props.get('state')
        coords = props.get('links_to_grid')
        if coords:
            x, y = coords
            # In this grid system, non 1 or 2 values block light (Void, etc)
            self.grid_data[y][x] = 1 if state == 'open' else 0 
            self._render_static_map()

    def _world_to_screen(self, wx, wy, cam_x, cam_y, zoom):
        center_x, center_y = SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2
        sc = self.cell_size * zoom
        sx = center_x + (wx - cam_x) * sc
        sy = center_y + (wy - cam_y) * sc
        return sx, sy

    def _init_ui(self):
        full_w = SIDEBAR_WIDTH - 40
        self.btn_back = Button(20, 50, 60, 25, "<- Up", self.font_ui, (80,80,90), (100,100,120), (255,255,255), self._go_up_level)
        
        tab_y = 90; tab_w = full_w // 4
        self.btn_tab_info   = Button(20, tab_y, tab_w, 30, "Info", self.font_ui, (60,60,70), (80,80,90), (255,255,255), lambda: self._set_tab("INFO"))
        self.btn_tab_tools  = Button(20+tab_w, tab_y, tab_w, 30, "Build", self.font_ui, (60,60,70), (80,80,90), (255,255,255), lambda: self._set_tab("TOOLS"))
        self.btn_tab_loc    = Button(20+(tab_w*2), tab_y, tab_w, 30, "Loc", self.font_ui, (60,60,70), (80,80,90), (255,255,255), lambda: self._set_tab("LOC"))
        self.btn_tab_config = Button(20+(tab_w*3), tab_y, tab_w, 30, "Set", self.font_ui, (60,60,70), (80,80,90), (255,255,255), lambda: self._set_tab("CONFIG"))

        self.brushes = [(20, 140, "Floor", 1), (100, 140, "Corridor", 2), (20, 180, "Void", 0), (100, 180, "Door", 4)]
        self.brush_buttons  = []
        for x, y, lbl, val in self.brushes:
            btn = Button(x, y, 70, 30, lbl, self.font_ui, (100,100,100), (150,150,150), (255,255,255), lambda v=val: self._set_brush(v))
            self.brush_buttons.append(btn)
            
        self.btn_reset_view = Button(20, 140, full_w, 30, "Reset View", self.font_ui, (100,150,200), (150,200,250), (255,255,255), self._reset_view)
        self.btn_regen      = Button(20, 180, full_w, 30, "Regenerate Layout", self.font_ui, (150,100,100), (200,150,150), (255,255,255), self._regenerate_map)
        self.btn_gen_details = Button(20, 220, full_w, 30, "AI Gen Content", self.font_ui, (100,100,200), (150,150,250), (255,255,255), self._generate_ai_details)
        self.btn_settings = Button(20, 260, full_w, 30, "Map Settings", self.font_ui, (100, 100, 100), (120, 120, 120), (255, 255, 255), self.open_map_settings)
        self.btn_show_triggers = Button(20, 220, full_w, 30, "Toggle Triggers", self.font_ui, (100, 150, 100), (120, 180, 120), (255,255,255), self._toggle_triggers)
        self.show_triggers = False

        self.structure_browser = StructureBrowser(20, 140, full_w, 400, self.db, self.node['id'], self.font_small, lambda nid: {"action": "transition_node", "node_id": nid})

    def open_map_settings(self):
        chain = [('node', self.node['id']), ('campaign', self.node['campaign_id'])]
        GenericSettingsEditor(pygame.display.get_surface(), self.ai.config, self.ai, context_chain=chain)

    def _set_tab(self, t): self.active_tab = t
    def _set_brush(self, val): self.active_brush = val
    def _go_up_level(self): return {"action": "go_up_level"}

    def get_visible_room_markers(self):
        """Returns a list of room markers currently inside the camera viewport."""
        sc = self.cell_size
        screen_w_world = self.screen.get_width() / (self.map_viewer.zoom * sc)
        screen_h_world = self.screen.get_height() / (self.map_viewer.zoom * sc)
        
        view_rect = pygame.Rect(
            self.map_viewer.cam_x - screen_w_world / 2,
            self.map_viewer.cam_y - screen_h_world / 2,
            screen_w_world,
            screen_h_world
        )
        
        visible = []
        for m in self.markers:
            props = m.get('properties', {})
            # FIX: Access from properties
            if props.get('symbol') == 'room_number':
                if view_rect.collidepoint(props.get('world_x', 0), props.get('world_y', 0)):
                    visible.append(m)
        return visible

    def _generate_ai_details(self):
        if self.node['type'] == 'dungeon_level':
            visible_markers = self.get_visible_room_markers()
            if not visible_markers:
                print("No room markers visible on screen.")
                return None
            
            print(f"[CONTROLLER] Found {len(visible_markers)} visible room markers.")

            def on_generation_complete(result):
                print(f"[CALLBACK in Controller] Received result for {len(visible_markers)} markers.")
                if result:
                    for m in visible_markers:
                        if m['title'] in result:
                            self.db.update_marker(m['id'], description=result[m['title']])
                    pygame.event.post(pygame.event.Event(pygame.USEREVENT, {"action": "reload_node"}))
                else:
                    print("[CALLBACK in Controller] AI generation failed.")

            chain = [('node', self.node['id']), ('campaign', self.node['campaign_id'])]
            editor = AIRequestEditor(pygame.display.get_surface(), self.ai.config, self.ai, chain, "Dungeon Theme")
            
            if editor.result:
                prompt, svc, model, persist = editor.result
                if persist:
                    scope, scope_id = chain[0]
                    self.ai.config.set("active_service_id", svc, scope, scope_id)
                    self.ai.config.set(f"service_{svc}_model", model, scope, scope_id)
                
                context = {"name": self.node['name'], "rooms": [{'title': m['title']} for m in visible_markers]}
                self.dungeon_content_manager.start_generation(
                    theme=prompt, 
                    context_for_ai=context,
                    callback=on_generation_complete,
                    service_override=svc, 
                    model_override=model
                )
        return None

    def update(self):
        self.widgets = [self.btn_back, self.btn_tab_tools, self.btn_tab_info, self.btn_tab_loc, self.btn_tab_config]
        ac, ic = (100, 100, 120), (60, 60, 70)
        self.btn_tab_tools.base_color = ac if self.active_tab == "TOOLS" else ic
        self.btn_tab_info.base_color = ac if self.active_tab == "INFO" else ic
        self.btn_tab_loc.base_color = ac if self.active_tab == "LOC" else ic
        self.btn_tab_config.base_color = ac if self.active_tab == "CONFIG" else ic
        if self.active_tab == "TOOLS": self.widgets.extend([*self.brush_buttons, self.btn_show_triggers])
        elif self.active_tab == "CONFIG": self.widgets.extend([self.btn_reset_view, self.btn_regen, self.btn_gen_details, self.btn_settings])

    def updateold(self):
        self.widgets = [self.btn_back, self.btn_tab_tools, self.btn_tab_info, self.btn_tab_loc, self.btn_tab_config]
        ac, ic = (100, 100, 120), (60, 60, 70)
        self.btn_tab_tools.base_color = ac if self.active_tab == "TOOLS" else ic
        self.btn_tab_info.base_color = ac if self.active_tab == "INFO" else ic
        self.btn_tab_loc.base_color = ac if self.active_tab == "LOC" else ic
        self.btn_tab_config.base_color = ac if self.active_tab == "CONFIG" else ic
        if self.active_tab == "TOOLS": self.widgets.extend(self.brush_buttons)
        elif self.active_tab == "CONFIG": self.widgets.extend([self.btn_reset_view, self.btn_regen, self.btn_gen_details, self.btn_settings])

    def handle_input(self, event, cam_x, cam_y, zoom):
        if event.type == pygame.USEREVENT and event.dict.get("action") == "reload_node":
            return {"action": "reload_node"}

        if self.context_menu:
            if self.context_menu.handle_event(event): self.context_menu = None
            return

        for w in self.widgets:
            res = w.handle_event(event)
            if res: return res if isinstance(res, dict) else None
        
        if self.active_tab == "LOC":
            res = self.structure_browser.handle_event(event)
            if res: return res

        center_x, center_y = SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2
        sc = self.cell_size

        if event.type == pygame.MOUSEMOTION:
            world_x = ((event.pos[0] - center_x) / (zoom * sc)) + cam_x
            world_y = ((event.pos[1] - center_y) / (zoom * sc)) + cam_y
            
            if self.dragging_rotation:
                view_marker = self.dragging_rotation
                props = view_marker['properties']
                angle = math.degrees(math.atan2(world_y - props['world_y'], world_x - props['world_x']))
                props['facing_degrees'] = (angle + 360) % 360
                return {"action": "update_player_view"}

            if self.dragging_marker:
                self.dragging_marker['properties']['world_x'] = world_x - self.drag_offset[0]
                self.dragging_marker['properties']['world_y'] = world_y - self.drag_offset[1]
                return
            
            if self.painting: self._paint_tile(event.pos, cam_x, cam_y, zoom)
            elif self.dragging_map:
                dx = event.pos[0] - self.drag_start_pos[0]
                dy = event.pos[1] - self.drag_start_pos[1]
                return {"action": "pan", "pos": (self.drag_start_cam[0] - dx / (zoom * sc), self.drag_start_cam[1] - dy / (zoom * sc))}

        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.pos[0] < SIDEBAR_WIDTH: return None
            world_x = ((event.pos[0] - center_x) / (zoom * sc)) + cam_x
            world_y = ((event.pos[1] - center_y) / (zoom * sc)) + cam_y

            if event.button == 1:
                self.drag_start_pos = event.pos
                self.drag_start_cam = (cam_x, cam_y)

                # Rotation Handle Check
                view_marker = next((m for m in self.markers if m.get('properties', {}).get('is_view_marker')), None)
                if view_marker:
                    props = view_marker['properties']
                    sx, sy = self._world_to_screen(props['world_x'], props['world_y'], cam_x, cam_y, zoom)
                    rads = math.radians(props.get('facing_degrees', 0))
                    handle_x = sx + math.cos(rads) * 25
                    handle_y = sy + math.sin(rads) * 25
                    if math.hypot(event.pos[0] - handle_x, event.pos[1] - handle_y) < 8:
                        self.dragging_rotation = view_marker
                        return

                if self.hovered_marker:
                    self.selected_marker = self.hovered_marker
                    self.dragging_marker = self.hovered_marker
                    m_props = self.hovered_marker.get('properties', {})
                    self.drag_offset = (world_x - m_props.get('world_x', 0), world_y - m_props.get('world_y', 0))
                    return
                
                if self.active_tab == "TOOLS":
                    if pygame.key.get_mods() & pygame.KMOD_SHIFT:
                        # Default to context menu for new marker
                        self._create_new_marker(world_x, world_y)
                        return
                    self.painting = True
                    self._paint_tile(event.pos, cam_x, cam_y, zoom)
                else: 
                    self.dragging_map = True
            
            elif event.button == 3:
                if self.hovered_marker:
                    self._open_context_menu(event)
                elif self.active_tab == "TOOLS":
                    # Right click on map also opens create menu
                    self._create_new_marker(world_x, world_y)

        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            drag_dist = math.hypot(event.pos[0] - self.drag_start_pos[0], event.pos[1] - self.drag_start_pos[1])

            if self.dragging_rotation:
                self.db.update_node(self.dragging_rotation['id'], properties=self.dragging_rotation['properties'])
                self.dragging_rotation = None
                return

            marker_to_process = self.dragging_marker
            self.dragging_marker = None 

            if marker_to_process:
                props = marker_to_process.get('properties', {})
                
                if drag_dist > 5:
                    # Handle Drag End
                    self.db.update_node(marker_to_process['id'], properties={
                        'world_x': props.get('world_x'), 
                        'world_y': props.get('world_y')
                    })
                    self.markers = self.db.get_children(self.node['id'], type_filter='poi')
                    
                    if props.get('is_view_marker') and props.get('is_active'):
                        return {"action": "update_player_view"}
                else:
                    # Handle Click (Toggle/Interact)
                    m_type = props.get('marker_type')
                    
                    if props.get('is_view_marker'):
                        new_state = not props.get('is_active', False)
                        self.db.update_node(marker_to_process['id'], properties={'is_active': new_state})
                        self.markers = self.db.get_children(self.node['id'], type_filter='poi')
                        return {"action": "update_player_view"}
                    
                    elif m_type == 'door':
                        new_state = 'open' if props.get('state') != 'open' else 'closed'
                        self.db.update_node(marker_to_process['id'], properties={'state': new_state})
                        marker_to_process['properties']['state'] = new_state
                        self._update_door_occlusion(marker_to_process)
                        self.markers = self.db.get_children(self.node['id'], type_filter='poi')
                        return {"action": "update_player_view"}
                    
                    elif m_type == 'trap':
                        new_state = 'detected' if props.get('state') == 'hidden' else 'hidden'
                        self.db.update_node(marker_to_process['id'], properties={'state': new_state})
                        self.markers = self.db.get_children(self.node['id'], type_filter='poi')
                        return {"action": "update_player_view"}
                    
                    elif m_type == 'light_source':
                        new_state = not props.get('active', True)
                        self.db.update_node(marker_to_process['id'], properties={'active': new_state})
                        self.markers = self.db.get_children(self.node['id'], type_filter='poi')
                        return {"action": "update_player_view"}

                    elif m_type in ['stairs_up', 'stairs_down', 'portal']:
                        # Only these types trigger a map transition
                        return {"action": "enter_marker", "marker": marker_to_process}
                    
                    else:
                        print(f"[DEBUG] Clicked marker type '{m_type}'. No action defined.")
            
            self.painting = False
            self.dragging_map = False

        return None

    def _paint_tile(self, screen_pos, cam_x, cam_y, zoom):
        center_x, center_y = SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2
        sc = self.cell_size * zoom
        c = int((screen_pos[0] - center_x) / sc + cam_x)
        r = int((screen_pos[1] - center_y) / sc + cam_y)
        if 0 <= c < self.grid_width and 0 <= r < self.grid_height:
            if self.grid_data[r][c] != self.active_brush:
                self.grid_data[r][c] = self.active_brush
                if self.active_brush == 4: # If placing a door tile
                    self.db.create_node('poi', 'Door', self.node['id'], properties={
                        'marker_type': 'door', 'symbol': 'door', 'state': 'closed',
                        'world_x': c + 0.5, 'world_y': r + 0.5,
                        'links_to_grid': [c, r]
                    })
                    self.markers = self.db.get_children(self.node['id'], type_filter='poi')
                    # Also set the grid cell back to non-blocking so the renderer draws it right
                    self.grid_data[r][c] = 0
                self._render_static_map()

    def _open_context_menu(self, event):
        if self.hovered_marker:
            self.selected_marker = self.hovered_marker
            menu_options = [("Edit Details", self._open_edit_modal), ("", None), ("Delete Marker", self._delete_selected_marker)]
            self.context_menu = ContextMenu(event.pos[0], event.pos[1], menu_options, self.font_ui)
    
    def _open_edit_modal(self):
        if self.selected_marker:
            print(f"[DEBUG TACTICAL] Opening editor for Marker ID: {self.selected_marker['id']}")
            editor_input = {
                'id': self.selected_marker['id'],
                'name': self.selected_marker.get('name', 'Unknown'),
                'properties': self.selected_marker.get('properties', {})
            }
            
            from codex_engine.ui.editors import NativeMarkerEditor
            NativeMarkerEditor(editor_input, self.node['type'], self._save_marker)

    def _delete_selected_marker(self):
        if self.selected_marker: 
            # Use the unified delete_node method
            self.db.delete_node(self.selected_marker['id'])
            
            # Refresh the local markers list from the database
            self.markers = self.db.get_children(self.node['id'], type_filter='poi')
            self.selected_marker = None

    def _save_marker(self, marker_id, name, final_properties):
        print(f"[DEBUG TACTICAL] Save. Marker ID: {marker_id}, Name: {name}")
        
        if marker_id: 
            print(f"[DEBUG TACTICAL] Updating Node {marker_id}. Keys: {list(final_properties.keys())}")
            self.db.update_node(marker_id, name=name, properties=final_properties)
        else: 
            temp_data = self.marker_data_for_editor
            
            final_properties['world_x'] = temp_data['properties']['world_x']
            final_properties['world_y'] = temp_data['properties']['world_y']
            final_properties['symbol'] = temp_data['properties']['symbol']
            final_properties['marker_type'] = temp_data['properties']['marker_type']
            
            print(f"[DEBUG TACTICAL] Creating New Node. Keys: {list(final_properties.keys())}")
            self.db.create_node(type='poi', name=name, parent_id=self.node['id'], properties=final_properties)

        self.markers = self.db.get_children(self.node['id'], type_filter='poi')
        self.selected_marker = None

    def _create_new_marker(self, wx, wy):
        self.pending_click_pos = (wx, wy)
        # Instead of opening editor directly, show a type selection menu
        sx, sy = self._world_to_screen(wx, wy, self.map_viewer.cam_x, self.map_viewer.cam_y, self.map_viewer.zoom)
        
        menu_options = [
            ("Add Note", lambda: self._create_specific_marker("note")),
            ("Add Door", lambda: self._create_specific_marker("door")),
            ("Add Trap", lambda: self._create_specific_marker("trap")),
            ("Add Light", lambda: self._create_specific_marker("light_source")),
            ("Add Stairs Up", lambda: self._create_specific_marker("stairs_up")),
            ("Add Stairs Down", lambda: self._create_specific_marker("stairs_down"))
        ]
        
        from codex_engine.ui.widgets import ContextMenu
        self.context_menu = ContextMenu(sx, sy, menu_options, self.font_ui)
        return {"action": "consumed"}   

    def _create_specific_marker(self, mtype):
        print(f"[DEBUG TACTICAL] Creating specific marker of type: {mtype}")
        self.context_menu = None # Close menu
        
        title = f"New {mtype.title()}"
        props = {
            'world_x': self.pending_click_pos[0],
            'world_y': self.pending_click_pos[1],
            'marker_type': mtype,
            'description': ''
        }
        
        symbol_map = {"trap": "trap", "note": "star", "door": "door", "portal": "stairs_up", "light_source": "💡", "stairs_up": "stairs_up", "stairs_down": "stairs_down"}
        props['symbol'] = symbol_map.get(mtype, 'star')

        if mtype == 'door': props.update({'state': 'closed'})
        elif mtype == 'trap': props.update({'state': 'hidden'})
        elif mtype == 'light_source': props.update({'radius': 15, 'color': [255, 200, 100], 'active': True})
            
        marker_data = {'id': None, 'name': title, 'properties': props}
        self.marker_data_for_editor = marker_data
        
        from codex_engine.ui.editors import NativeMarkerEditor
        NativeMarkerEditor(marker_data, 'tactical_map', self._save_marker)

    def _reset_view(self): return {"action": "reset_view"}
    def _regenerate_map(self): return {"action": "regenerate_tactical"}

    def draw_map(self, screen, cam_x, cam_y, zoom, screen_w, screen_h):
        if not self.static_map_surf: return
        center_x, center_y = screen_w // 2, screen_h // 2
        scaled_w = int(self.static_map_surf.get_width() * zoom)
        scaled_h = int(self.static_map_surf.get_height() * zoom)
        sc = self.cell_size
        draw_x = center_x - (cam_x * sc * zoom)
        draw_y = center_y - (cam_y * sc * zoom)
        if scaled_w > 0 and scaled_h > 0:
            scaled_surf = pygame.transform.scale(self.static_map_surf, (scaled_w, scaled_h))
            screen.blit(scaled_surf, (draw_x, draw_y))

    def draw_overlays(self, screen, cam_x, cam_y, zoom):
        if self.active_tab == "LOC": self.structure_browser.draw(screen)
        if self.active_tab == "TOOLS" and self.show_triggers: self._draw_trigger_areas(screen, cam_x, cam_y, zoom)
        self._draw_markers(screen, cam_x, cam_y, zoom)
        if self.hovered_marker: self._draw_tooltip(screen, pygame.mouse.get_pos())
        if self.context_menu: self.context_menu.draw(screen)

    def _draw_markers(self, screen, cam_x, cam_y, zoom):
        center_x, center_y = SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2
        sc = self.cell_size * zoom
        mouse_pos = pygame.mouse.get_pos()
        self.hovered_marker = None
        
        font_room_num = pygame.font.Font(None, 40)
        COLOR_INK = (40, 30, 20)
        
        for m in self.markers:
            props = m.get('properties', {})
            world_x = props.get('world_x', 0)
            world_y = props.get('world_y', 0)
            symbol = props.get('symbol', '')
            marker_type = props.get('marker_type', '')

            sx, sy = self._world_to_screen(world_x, world_y, cam_x, cam_y, zoom)
            
            if not (-sc <= sx <= SCREEN_WIDTH + sc and -sc <= sy <= SCREEN_HEIGHT + sc): 
                continue
            
            rect = pygame.Rect(sx - 15, sy - 15, 30, 30)
            if rect.collidepoint(mouse_pos): 
                self.hovered_marker = m
            
            if props.get('is_view_marker'):
                facing = math.radians(props.get('facing_degrees', 0))
                beam = props.get('beam_degrees', 360)
                radius = 20
                pygame.draw.circle(screen, (255, 255, 0) if props.get('is_active') else (100,100,0), (sx, sy), 10)
                pygame.draw.line(screen, (0,0,0), (sx, sy), (sx + math.cos(facing)*radius, sy + math.sin(facing)*radius), 3)
                handle_x = sx + math.cos(facing) * 25
                handle_y = sy + math.sin(facing) * 25
                pygame.draw.circle(screen, (255,255,255), (handle_x, handle_y), 5)
            elif marker_type == 'door':
                state = props.get('state', 'closed')
                door_rect = pygame.Rect(sx-sc/2, sy-sc/2, sc, sc)
                colors = {'closed': (139,69,19), 'open': (244,164,96), 'locked': (139,0,0)}
                pygame.draw.rect(screen, colors.get(state, (255,0,255)), door_rect.inflate(-10, -10))
                pygame.draw.rect(screen, (0,0,0), door_rect.inflate(-10,-10), 2)
            elif marker_type == 'trap':
                state = props.get('state', 'hidden')
                if state == 'hidden':
                    s = pygame.Surface((16,16), pygame.SRCALPHA)
                    s.fill((255,0,0,100))
                    screen.blit(s, (sx-8, sy-8))
                else:
                    pygame.draw.circle(screen, (255, 0, 0), (sx, sy), 8)
            elif symbol == 'stairs_up':
                pygame.draw.polygon(screen, (100,200,100), [(sx, sy+8), (sx-8, sy-8), (sx+8, sy-8)])
            elif symbol == 'stairs_down':
                pygame.draw.polygon(screen, (200,100,100), [(sx, sy-8), (sx-8, sy+8), (sx+8, sy+8)])
            elif symbol == 'room_number':
                surf = font_room_num.render(m['name'], True, COLOR_INK)
                screen.blit(surf, (sx, sy))
            else:
                pygame.draw.circle(screen, (200, 200, 100), (int(sx), int(sy)), 10)
                pygame.draw.circle(screen, (0, 0, 0), (int(sx), int(sy)), 10, 2)
 
    def _draw_tooltip(self, screen, pos):
        m = self.hovered_marker
        # FIX: Extract description from the properties dictionary
        props = m.get('properties', {})
        description = props.get('description', 'No details')
        
        import textwrap
        wrapped_lines = textwrap.wrap(description, width=40)
        rendered = [self.font_small.render(l, True, (20,20,20)) for l in wrapped_lines]
        
        mw = max(s.get_width() for s in rendered) if rendered else 0
        mh = sum(s.get_height() for s in rendered) + 10
        bg_rect = pygame.Rect(pos[0]+15, pos[1]+15, mw+20, mh)
        
        if bg_rect.right > SCREEN_WIDTH: bg_rect.x -= (bg_rect.width+30)
        
        COLOR_PARCHMENT = (245, 235, 215); COLOR_INK = (40, 30, 20)
        pygame.draw.rect(screen, COLOR_PARCHMENT, bg_rect)
        pygame.draw.rect(screen, COLOR_INK, bg_rect, 1)
        
        y_off = 5
        for s in rendered:
            screen.blit(s, (bg_rect.x+10, bg_rect.y+y_off))
            y_off += s.get_height()

    def create_radial_gradient(self, radius):
        r_val = max(1, int(radius))
        surf = pygame.Surface((r_val * 2, r_val * 2), pygame.SRCALPHA)
        steps = 50
        for i in range(steps):
            t = i / float(steps - 1)
            current_r = int(r_val * (1 - t))
            alpha = int(255 * (t**2))
            if current_r > 0:
                pygame.draw.circle(surf, (255, 255, 255, alpha), (r_val, r_val), current_r)
        return surf 
 
    def render_player_view_surface(self):
        view_marker = next((m for m in self.markers if m.get('properties', {}).get('is_view_marker') and m['properties'].get('is_active')), None)
        
        if not view_marker or not self.renderer:
            return None

        p = view_marker.get('properties', {})
        mx, my = p.get('world_x', 0), p.get('world_y', 0)
        radius = p.get('radius', 15)
        zoom = p.get('zoom', 1.5)
        facing = p.get('facing_degrees', 0)
        beam = p.get('beam_degrees', 360)
        
        w, h = 1920, 1080
        center_x, center_y = w // 2, h // 2
        
        temp_surface = pygame.Surface((w, h))
        self.draw_map(temp_surface, mx, my, zoom, w, h)

        sc = self.cell_size * zoom
        px_radius = radius * sc
        
        light_gradient = self.create_radial_gradient(px_radius)

        polygon_points = []
        num_rays =  7200
        step_angle = (2 * math.pi) / num_rays
        
        start_angle_rad = math.radians(facing - beam / 2)
        end_angle_rad = math.radians(facing + beam / 2)

        for i in range(num_rays):
            angle = i * step_angle
            
            if beam < 360:
                norm_angle = (angle - start_angle_rad + 2*math.pi) % (2*math.pi)
                norm_beam = (end_angle_rad - start_angle_rad + 2*math.pi) % (2*math.pi)
                if norm_angle > norm_beam:
                    continue

            sin_a = math.sin(angle)
            cos_a = math.cos(angle)
            
            dist, max_dist, step_size = 0, radius, 0.1 
            curr_x, curr_y = mx, my
            
            while dist < max_dist:
                dist += step_size
                curr_x += cos_a * step_size
                curr_y += sin_a * step_size
                
                grid_x, grid_y = int(curr_x), int(curr_y)
                
                if 0 <= grid_x < self.grid_width and 0 <= grid_y < self.grid_height:
                    if self.grid_data[grid_y][grid_x] not in [1, 2]: 
                        overhang = 0.03 
                        curr_x += cos_a * overhang
                        curr_y += sin_a * overhang
                        break
                else: break
            
            screen_x = center_x + (curr_x - mx) * sc
            screen_y = center_y + (curr_y - my) * sc
            polygon_points.append((screen_x, screen_y))

        darkness = pygame.Surface((w, h), pygame.SRCALPHA)
        darkness.fill((0, 0, 0, 255))
        
        light_shape = pygame.Surface((w, h), pygame.SRCALPHA)
        light_shape.fill((0, 0, 0, 0))
        if len(polygon_points) > 2:
            pygame.draw.polygon(light_shape, (255, 255, 255, 255), polygon_points)
            
        grad_rect = light_gradient.get_rect(center=(center_x, center_y))
        light_shape.blit(light_gradient, grad_rect, special_flags=pygame.BLEND_RGBA_MULT)
        
        darkness.blit(light_shape, (0, 0), special_flags=pygame.BLEND_RGBA_SUB)
        
        temp_surface.blit(darkness, (0, 0))

        return temp_surface

    def get_metadata_updates(self): return {}
    
    def cleanup(self):
        print(f"*** tac controller *** cleanup *** node {self.node}")
        
        # 1. Get all current properties so we don't overwrite/lose them
        # (This keeps 'overview', 'render_style', etc. intact)
        new_properties = dict(self.node.get('properties', {}))
        
        # 2. Get the existing geometry dictionary to preserve rooms/footprints
        existing_geom = new_properties.get('geometry', {})
        
        # 3. Build the updated geometry dictionary
        updated_geometry = {
            "grid": self.grid_data, 
            "width": self.grid_width, 
            "height": self.grid_height, 
            "footprints": existing_geom.get('footprints', []),
            "rooms": existing_geom.get('rooms', [])
        }
        
        # 4. Put the updated geometry back into our properties copy
        new_properties['geometry'] = updated_geometry
        
        # 5. Pass the whole properties dictionary to the database
        self.db.update_node(
            self.node['id'], 
            properties=new_properties
        )
