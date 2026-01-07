import pygame
import json
import textwrap
from codex_engine.config import SCREEN_WIDTH, SCREEN_HEIGHT
from codex_engine.generators.building_gen import get_available_blueprints
from codex_engine.ui.widgets import Dropdown, InputBox

def get_text_input(prompt):
    screen = pygame.display.get_surface()
    font = pygame.font.Font(None, 32)
    clock = pygame.time.Clock()
    text = ""
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT: return None
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RETURN: running = False
                elif event.key == pygame.K_ESCAPE: return None
                elif event.key == pygame.K_BACKSPACE: text = text[:-1]
                else: text += event.unicode
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        overlay.set_alpha(150); overlay.fill((0,0,0)); screen.blit(overlay, (0,0))
        panel_rect = pygame.Rect(0, 0, 600, 150); panel_rect.center = (SCREEN_WIDTH//2, SCREEN_HEIGHT//2)
        pygame.draw.rect(screen, (40, 40, 50), panel_rect, border_radius=10)
        pygame.draw.rect(screen, (100, 100, 120), panel_rect, 2, border_radius=10)
        prompt_surf = font.render(prompt, True, (255, 255, 255))
        screen.blit(prompt_surf, (panel_rect.x + 20, panel_rect.y + 20))
        input_rect = pygame.Rect(panel_rect.x + 20, panel_rect.y + 60, panel_rect.width - 40, 40)
        pygame.draw.rect(screen, (20, 20, 25), input_rect)
        pygame.draw.rect(screen, (255, 255, 255), input_rect, 1)
        text_surf = font.render(text, True, (255, 255, 255))
        screen.blit(text_surf, (input_rect.x + 5, input_rect.y + 10))
        pygame.display.flip(); clock.tick(30)
    return text

class PygameMarkerEditor:
    def __init__(self, marker_data, map_context, on_save, on_ai_gen=None):
        print(f"[DEBUG EDITOR] --- INIT START ---")
        print(f"[DEBUG EDITOR] Map Context: {map_context}")
        print(f"[DEBUG EDITOR] Incoming Data Keys: {list(marker_data.keys())}")
        
        self.marker_data = marker_data
        self.on_save = on_save
        self.on_ai_gen = on_ai_gen
        self.screen = pygame.display.get_surface()
        self.font = pygame.font.Font(None, 24)
        self.font_title = pygame.font.Font(None, 32)
        self.clock = pygame.time.Clock()

        # --- Data Unpacking (Strictly follows the contract) ---
        self.name_text = marker_data.get('name', 'Unknown')
        properties = marker_data.get('properties', {})
        print(f"[DEBUG EDITOR] Properties to process: {list(properties.keys())}")

        self.desc_text = properties.get('description', '')
        
        # --- UI State ---
        self.scroll_y = 0 
        self.prop_widgets = {}
        blocklist = ['description', 'symbol', 'marker_type', 'world_x', 'world_y'] 
        
        for key, value in properties.items():
            if key in blocklist: continue
            
            # Prevent dictionaries from being turned into widgets
            if isinstance(value, dict):
                print(f"[DEBUG EDITOR] WARNING: Skipping dict key '{key}' from widget list.")
                continue

            str_val = json.dumps(value) if isinstance(value, list) else str(value)
            self.prop_widgets[key] = {
                'label': key.replace('_', ' ').title(), 
                'widget': InputBox(0, 0, 300, 30, self.font, str_val),
                'original_type': type(value)
            }
        print(f"[DEBUG EDITOR] Widgets created: {list(self.prop_widgets.keys())}")
        
        self.content_height = len(self.prop_widgets) * 40
        self.panel_w = 500; self.panel_h = 600
        self.x = (SCREEN_WIDTH - self.panel_w) // 2
        self.y = (SCREEN_HEIGHT - self.panel_h) // 2
        self.active_field = "name"
        self.cursor_blink = 0
        
        # --- Blueprint UI (Local Map Context ONLY) ---
        self.show_blueprints = (map_context == "local_map")
        self.all_blueprints = get_available_blueprints() if self.show_blueprints else []
        self.dd_blueprint = None
        if self.show_blueprints:
            self.dd_blueprint = Dropdown(
                self.x + 150, self.y + 125, self.panel_w - 180, 30,
                self.font, [], 
                initial_id=properties.get('blueprint_id')
            )
            self._update_dropdown_options(properties.get('marker_type'))
            
        print(f"[DEBUG EDITOR] --- INIT COMPLETE ---")
        self.run_loop()

    def _update_dropdown_options(self, marker_type):
        if not self.dd_blueprint: return
        target_context = "Structure" if marker_type in ['building', 'village'] else "Dungeon"
        
        filtered_blueprints = [b for b in self.all_blueprints if b['context'] == target_context]
        self.dd_blueprint.options = filtered_blueprints
        
        if not any(b.get('id') == self.dd_blueprint.get_selected_id() for b in filtered_blueprints):
             self.dd_blueprint.selected_idx = -1

    def run_loop(self):
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT: running = False; return
                
                # --- Event Handling for Widgets ---
                props_area = pygame.Rect(self.x + 20, self.y + 295, self.panel_w - 40, 220)
                if event.type == pygame.MOUSEWHEEL and props_area.collidepoint(pygame.mouse.get_pos()):
                    self.scroll_y -= event.y * 20
                    max_scroll = max(0, self.content_height - props_area.height)
                    self.scroll_y = max(0, min(self.scroll_y, max_scroll))
                
                for item in self.prop_widgets.values():
                    # Pass events with scroll-awareness
                    if event.type in [pygame.MOUSEBUTTONDOWN, pygame.MOUSEMOTION, pygame.MOUSEBUTTONUP]:
                        original_pos = event.pos
                        event.pos = (original_pos[0], original_pos[1] + self.scroll_y)
                        item['widget'].handle_event(event)
                        event.pos = original_pos
                    else:
                        item['widget'].handle_event(event)

                # --- Key/Mouse Input ---
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE: running = False; return
                    self._handle_text_input(event)
                        
                if event.type == pygame.MOUSEBUTTONDOWN:
                    self._handle_click(event.pos)
                    if self.btn_save.collidepoint(event.pos): self._save(); running = False
                    elif self.btn_cancel.collidepoint(event.pos): running = False

                if self.show_blueprints and self.dd_blueprint:
                    self.dd_blueprint.handle_event(event)               

            self.draw(); pygame.display.flip()

    def _handle_click(self, pos):
        if self.rect_name.collidepoint(pos): self.active_field = "name"
        elif self.rect_desc.collidepoint(pos): self.active_field = "desc"
        else: self.active_field = None

    def _handle_text_input(self, event):
        if self.active_field == "name":
            if event.key == pygame.K_BACKSPACE: self.name_text = self.name_text[:-1]
            else: self.name_text += event.unicode
        elif self.active_field == "desc":
            if event.key == pygame.K_BACKSPACE: self.desc_text = self.desc_text[:-1]
            elif event.key == pygame.K_RETURN: self.desc_text += "\n"
            else: self.desc_text += event.unicode

    def _save(self):
        print("[DEBUG EDITOR] --- SAVE START ---")
        
        # 1. Rebuild the properties dict from the widgets
        final_props = {}
        for key, item in self.prop_widgets.items():
            text_val = item['widget'].text
            orig_type = item['original_type']
            try:
                if orig_type == bool: val = text_val.lower() in ['true', '1', 'y', 'yes']
                elif orig_type in [dict, list]: val = json.loads(text_val)
                else: val = orig_type(text_val)
                final_props[key] = val
            except (ValueError, json.JSONDecodeError):
                final_props[key] = text_val # Save as string if cast fails

        # 2. Add back the fields with dedicated UI
        final_props['description'] = self.desc_text
        if self.show_blueprints and self.dd_blueprint:
            bp_id = self.dd_blueprint.get_selected_id()
            if bp_id: final_props['blueprint_id'] = bp_id
        
        # 3. Preserve essential fields that aren't editable in the list
        original_props = self.marker_data.get('properties', {})
        for key in ['symbol', 'marker_type', 'world_x', 'world_y']:
            if key in original_props:
                final_props[key] = original_props[key]
        
        print(f"[DEBUG EDITOR] Final properties to save: {list(final_props.keys())}")
        
        # 4. Call Controller with the stable signature
        self.on_save(self.marker_data.get('id'), self.name_text, final_props)
        print("[DEBUG EDITOR] --- SAVE COMPLETE ---")

    def draw(self, *args):
        # ... [Unchanged drawing logic from previous attempts] ...
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT)); overlay.set_alpha(150); overlay.fill((0,0,0)); self.screen.blit(overlay, (0,0))
        panel = pygame.Rect(self.x, self.y, self.panel_w, self.panel_h)
        pygame.draw.rect(self.screen, (40, 40, 50), panel, border_radius=10)
        pygame.draw.rect(self.screen, (100, 100, 120), panel, 2, border_radius=10)
        self.screen.blit(self.font_title.render("Edit Marker", True, (255, 255, 255)), (self.x + 20, self.y + 20))
        
        self.screen.blit(self.font.render("Name:", True, (200, 200, 200)), (self.x + 20, self.y + 60))
        self.rect_name = pygame.Rect(self.x + 20, self.y + 85, self.panel_w - 40, 30)
        pygame.draw.rect(self.screen, (20,20,25), self.rect_name); pygame.draw.rect(self.screen, (255,255,255) if self.active_field == "name" else (200,200,200), self.rect_name, 1)
        self.screen.blit(self.font.render(self.name_text, True, (255,255,255)), (self.rect_name.x + 5, self.rect_name.y + 5))
        
        self.screen.blit(self.font.render("Description:", True, (200, 200, 200)), (self.x + 20, self.y + 160))
        self.rect_desc = pygame.Rect(self.x + 20, self.y + 185, self.panel_w - 40, 100)
        pygame.draw.rect(self.screen, (20,20,25), self.rect_desc); pygame.draw.rect(self.screen, (255,255,255) if self.active_field == "desc" else (200,200,200), self.rect_desc, 1)
        self._draw_multiline(self.desc_text, self.rect_desc)

        self.screen.blit(self.font.render("Properties:", True, (200, 200, 200)), (self.x + 20, self.y + 300))
        props_area = pygame.Rect(self.x + 20, self.y + 325, self.panel_w - 40, 180)
        pygame.draw.rect(self.screen, (20,20,25), props_area)
        self.screen.set_clip(props_area)
        y_off = props_area.y - self.scroll_y
        for item in self.prop_widgets.values():
            self.screen.blit(self.font.render(item['label'] + ":", True, (200, 200, 200)), (self.x + 30, y_off + 5))
            item['widget'].rect.topleft = (self.x + 180, y_off); item['widget'].draw(self.screen); y_off += 40
        self.screen.set_clip(None)
        pygame.draw.rect(self.screen, (100,100,120), props_area, 1)

        self.btn_save = pygame.Rect(self.x + 20, self.y + 530, 100, 40)
        self.btn_cancel = pygame.Rect(self.x + 140, self.y + 530, 100, 40)
        pygame.draw.rect(self.screen, (50, 150, 50), self.btn_save, border_radius=5); self.screen.blit(self.font.render("Save", True, (255,255,255)), (self.btn_save.x + 30, self.btn_save.y + 12))
        pygame.draw.rect(self.screen, (150, 50, 50), self.btn_cancel, border_radius=5); self.screen.blit(self.font.render("Cancel", True, (255,255,255)), (self.btn_cancel.x + 20, self.btn_cancel.y + 12))

        if self.show_blueprints and self.dd_blueprint:
            self.screen.blit(self.font.render("Blueprint:", True, (200, 200, 200)), (self.x + 20, self.y + 130))
            self.dd_blueprint.rect.topleft = (self.x + 120, self.y + 125)
            self.dd_blueprint.draw(self.screen)

    # additional helper methods

    def _draw_multiline(self, text, rect):
        y_off = 5; char_width = 55 
        wrapped_lines = textwrap.wrap(text, width=char_width)
        for line in wrapped_lines:
            if y_off + self.font.get_height() > rect.height: break
            surf = self.font.render(line, True, (220, 220, 220)); self.screen.blit(surf, (rect.x + 5, rect.y + y_off)); y_off += self.font.get_height()

    def _handle_click(self, pos):
        if self.rect_name.collidepoint(pos): self.active_field = "name"
        elif self.rect_desc.collidepoint(pos): self.active_field = "desc"
        else: self.active_field = None

    def _handle_text_input(self, event):
        target_text = None
        if self.active_field == "name":
            target_text = self.name_text
        elif self.active_field == "desc":
            target_text = self.desc_text

        if target_text is not None:
            if event.key == pygame.K_BACKSPACE:
                target_text = target_text[:-1]
            elif event.key == pygame.K_RETURN and self.active_field == "desc":
                 target_text += "\n"
            else:
                target_text += event.unicode
        
        if self.active_field == "name":
            self.name_text = target_text
        elif self.active_field == "desc":
            self.desc_text = target_text
    
NativeMarkerEditor = PygameMarkerEditor
