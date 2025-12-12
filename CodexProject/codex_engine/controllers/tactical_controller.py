import pygame
import json
import math
import random
from codex_engine.controllers.base_controller import BaseController
from codex_engine.ui.renderers.tactical.tactical_renderer import TacticalRenderer
from codex_engine.generators.dungeon_content_manager import DungeonContentManager
from codex_engine.ui.editors import get_text_input 
from codex_engine.ui.widgets import Button, StructureBrowser
from codex_engine.ui.info_panel import InfoPanel
from codex_engine.ui.widgets import Button, StructureBrowser, ContextMenu
from codex_engine.content.managers import TacticalContent
from codex_engine.core.ai_manager import AIManager
from codex_engine.config import SCREEN_WIDTH, SCREEN_HEIGHT, SIDEBAR_WIDTH

class TacticalController(BaseController):
    def __init__(self, db_manager, node_data, theme_manager):
        super().__init__(db_manager, node_data, theme_manager)

        self.dragging_map = False
        self.drag_start_pos = (0, 0)
        self.drag_start_cam = (0, 0)

        self.zoom_factor = 1.05
        self.ai = AIManager()
        
        # Geometry setup
        geo = self.node['geometry_data']
        self.grid_data = geo.get('grid', [[]])
        self.markers = self.db.get_markers(self.node['id'])
        
        self.grid_width = geo.get('width', len(self.grid_data[0]) if self.grid_data else 10)
        self.grid_height = geo.get('height', len(self.grid_data) if self.grid_data else 10)
        self.cell_size = 32

        self.active_brush = 1
        self.painting = False
        self.active_tab = "LOC"
        self.hovered_marker = None

        self.selected_marker = None
        self.dragging_marker = None
        self.drag_offset = (0,0)
        self.drag_start_pos = (0, 0)
        self.context_menu = None
        self.pending_click_pos = None
        
        self.font_ui = pygame.font.Font(None, 24)
        self.font_small = pygame.font.Font(None, 20)
        
        self.content_manager = TacticalContent(self.db, self.node)
        self.info_panel = InfoPanel(self.content_manager, self.db, self.node, self.font_ui, self.font_small)
        self.structure_browser = None

        style = self.node['metadata'].get('render_style', 'hand_drawn')
        self.renderer = TacticalRenderer(self.node, self.cell_size, style)

        self.static_map_surf = None
        self._render_static_map()
        self._init_ui()

    def _render_static_map(self):
        if self.renderer:
            self.static_map_surf = self.renderer.render()

    def _init_ui(self):
        full_w = SIDEBAR_WIDTH - 40
        self.btn_back = Button(20, 50, 60, 25, "<- Up", self.font_ui, (80,80,90), (100,100,120), (255,255,255), self._go_up_level)
        
        tab_y = 90; tab_w = full_w // 4
        self.btn_tab_info   = Button(20, tab_y, tab_w, 30, "Info", self.font_ui, (60,60,70), (80,80,90), (255,255,255), lambda: self._set_tab("INFO"))
        self.btn_tab_tools  = Button(20+tab_w, tab_y, tab_w, 30, "Build", self.font_ui, (60,60,70), (80,80,90), (255,255,255), lambda: self._set_tab("TOOLS"))
        self.btn_tab_loc    = Button(20+(tab_w*2), tab_y, tab_w, 30, "Loc", self.font_ui, (60,60,70), (80,80,90), (255,255,255), lambda: self._set_tab("LOC"))
        self.btn_tab_config = Button(20+(tab_w*3), tab_y, tab_w, 30, "Set", self.font_ui, (60,60,70), (80,80,90), (255,255,255), lambda: self._set_tab("CONFIG"))

        self.brushes = [(20, 140, "Floor", 1), (100, 140, "Corridor", 2), (20, 180, "Void", 0)]
        self.brush_buttons  = []
        for x, y, lbl, val in self.brushes:
            btn = Button(x, y, 70, 30, lbl, self.font_ui, (100,100,100), (150,150,150), (255,255,255), lambda v=val: self._set_brush(v))
            self.brush_buttons.append(btn)
            
        self.btn_reset_view = Button(20, 140, full_w, 30, "Reset View", self.font_ui, (100,150,200), (150,200,250), (255,255,255), self._reset_view)
        self.btn_regen      = Button(20, 180, full_w, 30, "Regenerate Layout", self.font_ui, (150,100,100), (200,150,150), (255,255,255), self._regenerate_map)
        self.btn_gen_details = Button(20, 220, full_w, 30, "AI Gen Content", self.font_ui, (100,100,200), (150,150,250), (255,255,255), self._generate_ai_details)

        self.structure_browser = StructureBrowser(20, 140, full_w, 400, self.db, self.node['id'], self.font_small, lambda nid: {"action": "transition_node", "node_id": nid})

    def _set_tab(self, t): self.active_tab = t
    def _set_brush(self, val): self.active_brush = val
    def _go_up_level(self): return {"action": "go_up_level"}
    def _generate_ai_details(self):
        if self.node['type'] == 'dungeon_level':
            theme_prompt = get_text_input("Enter a theme for the rooms (e.g., 'Goblin infested'):")
            if not theme_prompt or not theme_prompt.strip(): return None
            manager = DungeonContentManager(self.node, self.db, self.ai)
            if manager.populate_descriptions(theme=theme_prompt): return {"action": "reload_node"}
        return None

    def update(self):
        self.widgets = [self.btn_back, self.btn_tab_tools, self.btn_tab_info, self.btn_tab_loc, self.btn_tab_config]
        ac, ic = (100, 100, 120), (60, 60, 70)
        self.btn_tab_tools.base_color = ac if self.active_tab == "TOOLS" else ic
        self.btn_tab_info.base_color = ac if self.active_tab == "INFO" else ic
        self.btn_tab_loc.base_color = ac if self.active_tab == "LOC" else ic
        self.btn_tab_config.base_color = ac if self.active_tab == "CONFIG" else ic
        if self.active_tab == "TOOLS": self.widgets.extend(self.brush_buttons)
        elif self.active_tab == "INFO": self.widgets.extend(self.info_panel.widgets)
        elif self.active_tab == "CONFIG": self.widgets.extend([self.btn_reset_view, self.btn_regen, self.btn_gen_details])

    def handle_input(self, event, cam_x, cam_y, zoom):
        # Handle context menu first
        if self.context_menu:
            if self.context_menu.handle_event(event):
                self.context_menu = None
            return

        for w in self.widgets:
            res = w.handle_event(event)
            if res: return res if isinstance(res, dict) else None
        
        if self.active_tab == "INFO" and self.info_panel.handle_event(event): return None
        if self.active_tab == "LOC":
            res = self.structure_browser.handle_event(event)
            if res: return res

        center_x, center_y = SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2
        sc = self.cell_size

        # --- MOUSE MOTION ---
        if event.type == pygame.MOUSEMOTION:
            world_x = ((event.pos[0] - center_x) / (zoom * sc)) + cam_x
            world_y = ((event.pos[1] - center_y) / (zoom * sc)) + cam_y
            
            if self.dragging_marker:
                self.dragging_marker['world_x'] = world_x - self.drag_offset[0]
                self.dragging_marker['world_y'] = world_y - self.drag_offset[1]
                return
            
            if self.painting: self._paint_tile(event.pos, cam_x, cam_y, zoom)
            elif self.dragging_map:
                dx = event.pos[0] - self.drag_start_pos[0]
                dy = event.pos[1] - self.drag_start_pos[1]
                return {"action": "pan", "pos": (self.drag_start_cam[0] - dx / (zoom * sc), self.drag_start_cam[1] - dy / (zoom * sc))}

        # --- MOUSE DOWN ---
        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.pos[0] < SIDEBAR_WIDTH: return None
            world_x = ((event.pos[0] - center_x) / (zoom * sc)) + cam_x
            world_y = ((event.pos[1] - center_y) / (zoom * sc)) + cam_y

            if event.button == 1: # Left Click
                self.drag_start_pos = event.pos
                self.drag_start_cam = (cam_x, cam_y)

                if self.hovered_marker:
                    self.selected_marker = self.hovered_marker
                    self.dragging_marker = self.hovered_marker
                    self.drag_offset = (world_x - self.hovered_marker['world_x'], world_y - self.hovered_marker['world_y'])
                    return
                
                if self.active_tab == "TOOLS":
                    if pygame.key.get_mods() & pygame.KMOD_SHIFT:
                        self._create_new_marker(world_x, world_y)
                        return
                    self.painting = True
                    self._paint_tile(event.pos, cam_x, cam_y, zoom)
                else: 
                    self.dragging_map = True
            
            elif event.button == 3: # Right Click
                if self.hovered_marker:
                    self._open_context_menu(event)

        # --- MOUSE UP ---
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            drag_dist = math.hypot(event.pos[0] - self.drag_start_pos[0], event.pos[1] - self.drag_start_pos[1])

            if self.dragging_marker:
                marker_being_dragged = self.dragging_marker
                self.db.update_marker(marker_being_dragged['id'], world_x=marker_being_dragged['world_x'], world_y=marker_being_dragged['world_y'])
                self.markers = self.db.get_markers(self.node['id']) # Refresh
                
                is_view_marker = marker_being_dragged.get('metadata', {}).get('is_view_marker', False)
                is_active = marker_being_dragged.get('metadata', {}).get('is_active', False)

                if is_view_marker and is_active and drag_dist > 8: # Only trigger on actual drag
                    self.dragging_marker = None
                    return {"action": "update_player_view"}
            
            if self.hovered_marker and drag_dist < 8 and not self.dragging_marker:
                return {"action": "enter_marker", "marker": self.hovered_marker}
            
            self.painting = False
            self.dragging_map = False
            self.dragging_marker = None

        return None
            
    def _paint_tile(self, screen_pos, cam_x, cam_y, zoom):
        center_x, center_y = SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2
        sc = self.cell_size * zoom
        c = int((screen_pos[0] - center_x) / sc + cam_x)
        r = int((screen_pos[1] - center_y) / sc + cam_y)
        if 0 <= c < self.grid_width and 0 <= r < self.grid_height:
            if self.grid_data[r][c] != self.active_brush:
                self.grid_data[r][c] = self.active_brush
                self._render_static_map()


    def _open_context_menu(self, event):
        if self.hovered_marker:
            self.selected_marker = self.hovered_marker
            menu_options = [
                ("Edit Details", self._open_edit_modal),
                ("", None),
                ("Delete Marker", self._delete_selected_marker)
            ]
            self.context_menu = ContextMenu(event.pos[0], event.pos[1], menu_options, self.font_ui)
    
    def _open_edit_modal(self):
        if self.selected_marker: 
            from codex_engine.ui.editors import NativeMarkerEditor
            NativeMarkerEditor(self.selected_marker, self.node['type'], self._save_marker)
            self.markers = self.db.get_markers(self.node['id'])

    def _delete_selected_marker(self):
        if self.selected_marker: 
            self.db.delete_marker(self.selected_marker['id'])
            self.markers = self.db.get_markers(self.node['id'])
            self.selected_marker = None
    
    def _save_marker(self, mid, sym, title, note, meta):
        if mid: 
            self.db.update_marker(mid, symbol=sym, title=title, description=note, metadata=meta)
        else: 
            self.db.add_marker(self.node['id'], self.pending_click_pos[0], self.pending_click_pos[1], sym, title, note, meta)
        self.markers = self.db.get_markers(self.node['id'])
        self.selected_marker = None

    def _create_new_marker(self, wx, wy):
        from codex_engine.ui.editors import NativeMarkerEditor
        self.pending_click_pos = (wx, wy)
        new_marker = {'title': 'New Item', 'description': '', 'metadata': {}, 'symbol': 'star'}
        NativeMarkerEditor(new_marker, self.node['type'], self._save_marker)
        self.markers = self.db.get_markers(self.node['id'])

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
        if self.active_tab == "INFO": self.info_panel.draw(screen)
        elif self.active_tab == "LOC": self.structure_browser.draw(screen)
        self._draw_markers(screen, cam_x, cam_y, zoom)
        if self.hovered_marker: self._draw_tooltip(screen, pygame.mouse.get_pos())
        if self.context_menu:
            self.context_menu.draw(screen)
    
    def _draw_markers(self, screen, cam_x, cam_y, zoom):
        center_x, center_y = SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2
        sc = self.cell_size * zoom
        mouse_pos = pygame.mouse.get_pos()
        self.hovered_marker = None
        
        font_room_num = pygame.font.Font(None, 40)
        COLOR_INK = (40, 30, 20)
        
        for m in self.markers:
            sx = center_x + (m['world_x'] - cam_x) * sc
            sy = center_y + (m['world_y'] - cam_y) * sc
            if not (-sc <= sx <= SCREEN_WIDTH + sc and -sc <= sy <= SCREEN_HEIGHT + sc): continue
            
            surf = font_room_num.render(m['title'], True, COLOR_INK)
            rect = surf.get_rect(topleft=(sx, sy))
            
            if rect.inflate(10, 10).collidepoint(mouse_pos): self.hovered_marker = m
            
            if m['symbol'] == 'room_number':
                screen.blit(surf, rect)
            else: # Render portals, etc.
                pygame.draw.circle(screen, (200, 200, 100), (sx, sy), 10)

    def _draw_tooltip(self, screen, pos):
        m = self.hovered_marker
        import textwrap
        wrapped_lines = textwrap.wrap(m.get('description', 'No details'), width=40)
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
        """Creates a radial gradient (White/High-Alpha Center -> Transparent Edge)."""
        r_val = max(1, int(radius))
        surf = pygame.Surface((r_val * 2, r_val * 2), pygame.SRCALPHA)
        
        # Increase steps for smoother gradient
        steps = 50
        
        # Draw from Outside (Large Radius) to Inside (Small Radius)
        # Painter's Algorithm: We draw the faint outer layers first, then the bright inner layers on top.
        for i in range(steps):
            # t goes from 0.0 (Edge) to 1.0 (Center)
            t = i / float(steps - 1)
            
            # Radius shrinks as t increases
            current_r = int(r_val * (1 - t))
            
            # Alpha increases as we get closer to center
            # Using t**2 makes the light "hot" in the center and fall off quickly
            alpha = int(255 * (t**2))
            
            if current_r > 0:
                # Draw white circle with calculated alpha
                pygame.draw.circle(surf, (255, 255, 255, alpha), (r_val, r_val), current_r)
            
        return surf
    
    def render_player_view_surface(self):
        # 1. FIND ACTIVE MARKER & SETUP
        view_marker = next((m for m in self.markers if m.get('metadata', {}).get('is_view_marker') and m['metadata'].get('is_active')), None)
        if not view_marker or not self.renderer:
            return None

        # Metadata
        meta = view_marker.get('metadata', {})
        radius = meta.get('radius', 15)
        zoom = meta.get('zoom', 1.5)
        
        # Dimensions
        w, h = 1920, 1080
        center_x, center_y = w // 2, h // 2
        
        # Render the base map
        temp_surface = pygame.Surface((w, h))
        self.draw_map(
            temp_surface,
            view_marker['world_x'],
            view_marker['world_y'],
            zoom,
            w, h
        )

        # --- RAYCASTING LIGHTING ---

        mx, my = view_marker['world_x'], view_marker['world_y']
        sc = self.cell_size * zoom
        px_radius = radius * sc
        
        # Create gradient: High Alpha Center -> Low Alpha Edge
        light_gradient = self.create_radial_gradient(px_radius)

        # 3. CAST RAYS
        polygon_points = []
        # Double the rays for smoother edges
        num_rays =  7200
        step_angle = (2 * math.pi) / num_rays
        
        for i in range(num_rays):
            angle = i * step_angle
            sin_a = math.sin(angle)
            cos_a = math.cos(angle)
            
            dist = 0
            max_dist = radius
            hit_wall = False
            step_size = 0.1 
            
            curr_x, curr_y = mx, my
            
            while dist < max_dist:
                dist += step_size
                curr_x += cos_a * step_size
                curr_y += sin_a * step_size
                
                grid_x, grid_y = int(curr_x), int(curr_y)
                
                if 0 <= grid_x < self.grid_width and 0 <= grid_y < self.grid_height:
                    tile_val = self.grid_data[grid_y][grid_x]
                    
                    if tile_val == 0: 
                        # --- THE FIX: PUSH INTO VOID ---
                        # Add a small buffer (e.g. 0.3 grid units) so light bleeds onto the wall face
                        overhang = 0.03 
                        curr_x += cos_a * overhang
                        curr_y += sin_a * overhang
                        
                        hit_wall = True
                        break
                else:
                    hit_wall = True
                    break
            
            screen_x = center_x + (curr_x - mx) * sc
            screen_y = center_y + (curr_y - my) * sc
            polygon_points.append((screen_x, screen_y))

        # 4. COMPOSITE
        
        # A. Darkness (Full Black Opaque)
        darkness = pygame.Surface((w, h), pygame.SRCALPHA)
        darkness.fill((0, 0, 0, 255))
        
        # B. Light Shape Mask
        light_shape = pygame.Surface((w, h), pygame.SRCALPHA)
        light_shape.fill((0, 0, 0, 0))
        if len(polygon_points) > 2:
            pygame.draw.polygon(light_shape, (255, 255, 255, 255), polygon_points)
            
        # C. Apply Gradient to Shape (Multiply)
        # This trims the gradient to fit inside the walls
        grad_rect = light_gradient.get_rect(center=(center_x, center_y))
        light_shape.blit(light_gradient, grad_rect, special_flags=pygame.BLEND_RGBA_MULT)
        
        # D. Cut Light from Darkness (Subtract)
        # High alpha in light_shape removes alpha from darkness (making it transparent)
        darkness.blit(light_shape, (0, 0), special_flags=pygame.BLEND_RGBA_SUB)
        
        # 5. Final Combine
        temp_surface.blit(darkness, (0, 0))

        return temp_surface

    def render_player_view_surface_old(self):
        view_marker = next((m for m in self.markers if m.get('metadata', {}).get('is_view_marker') and m['metadata'].get('is_active')), None)
        if not view_marker or not self.renderer:
            return None

        temp_surface = pygame.Surface((1920, 1080))
        
        self.draw_map(
            temp_surface,
            view_marker['world_x'],
            view_marker['world_y'],
            view_marker['metadata'].get('zoom', 1.5),
            temp_surface.get_width(),
            temp_surface.get_height()
        )
        return temp_surface

    def get_metadata_updates(self): return {}
    
    def cleanup(self):
        self.db.update_node_data(
            self.node['id'], 
            geometry={
                "grid": self.grid_data, 
                "width": self.grid_width, 
                "height": self.grid_height, 
                "footprints": self.node['geometry_data'].get('footprints', []),
                "rooms": self.node['geometry_data'].get('rooms', [])
            }
        )
