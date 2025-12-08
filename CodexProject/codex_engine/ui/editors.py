import pygame
import json
from codex_engine.config import SCREEN_WIDTH, SCREEN_HEIGHT


def get_text_input(prompt):
    """A blocking function to get a single line of text input."""
    screen = pygame.display.get_surface()
    font = pygame.font.Font(None, 32)
    clock = pygame.time.Clock()
    
    text = ""
    running = True

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return None
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RETURN:
                    running = False
                elif event.key == pygame.K_ESCAPE:
                    return None
                elif event.key == pygame.K_BACKSPACE:
                    text = text[:-1]
                else:
                    text += event.unicode
        
        # Draw overlay
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        overlay.set_alpha(150)
        overlay.fill((0,0,0))
        screen.blit(overlay, (0,0))
        
        # Panel
        panel_rect = pygame.Rect(0, 0, 600, 150)
        panel_rect.center = (SCREEN_WIDTH//2, SCREEN_HEIGHT//2)
        pygame.draw.rect(screen, (40, 40, 50), panel_rect, border_radius=10)
        pygame.draw.rect(screen, (100, 100, 120), panel_rect, 2, border_radius=10)
        
        # Prompt
        prompt_surf = font.render(prompt, True, (255, 255, 255))
        screen.blit(prompt_surf, (panel_rect.x + 20, panel_rect.y + 20))
        
        # Input Box
        input_rect = pygame.Rect(panel_rect.x + 20, panel_rect.y + 60, panel_rect.width - 40, 40)
        pygame.draw.rect(screen, (20, 20, 25), input_rect)
        pygame.draw.rect(screen, (255, 255, 255), input_rect, 1)
        text_surf = font.render(text, True, (255, 255, 255))
        screen.blit(text_surf, (input_rect.x + 5, input_rect.y + 10))

        pygame.display.flip()
        clock.tick(30)
        
    return text


class PygameMarkerEditor:
    def __init__(self, marker_data, map_context, on_save, on_ai_gen=None):
        self.marker_data = marker_data
        self.on_save = on_save
        self.on_ai_gen = on_ai_gen
        
        self.screen = pygame.display.get_surface()
        self.font = pygame.font.Font(None, 24)
        self.font_title = pygame.font.Font(None, 32)
        self.clock = pygame.time.Clock()
        
        # --- Data State ---
        self.title_text = marker_data.get('title', '')
        self.desc_text = marker_data.get('description', '')
        self.symbol = marker_data.get('symbol', 'star')
        self.meta_json_text = json.dumps(marker_data.get('metadata', {}), indent=2)
        
        # --- Type Config ---
        if map_context == "world_map":
            self.type_opts = ["village", "lair", "landmark"]
            self.sym_map = {"village": "house", "lair": "skull", "landmark": "star"}
        else:
            self.type_opts = ["building", "lair", "portal", "note"]
            self.sym_map = {"building": "house", "lair": "skull", "portal": "star", "note": "star"}
            
        self.current_type_idx = 0
        # Try to match current symbol to type
        for i, t in enumerate(self.type_opts):
            if self.sym_map.get(t) == self.symbol:
                self.current_type_idx = i
                break

        # --- UI State ---
        self.active_field = "title" # Options: title, desc, meta
        self.cursor_blink = 0
        
        # Layout Constants
        self.panel_w = 500
        self.panel_h = 600
        self.x = (SCREEN_WIDTH - self.panel_w) // 2
        self.y = (SCREEN_HEIGHT - self.panel_h) // 2
        
        # Start Blocking Loop
        self.run_loop()

    def run_loop(self):
        running = True
        while running:
            dt = self.clock.tick(30)
            self.cursor_blink += dt
            
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                    return # Cancel without saving
                
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                        return
                    
                    if event.key == pygame.K_TAB:
                        self._cycle_field()
                    elif event.key == pygame.K_RETURN and not (pygame.key.get_mods() & pygame.KMOD_SHIFT):
                        # Enter saves if not in multiline field, Shift+Enter for newline
                        if self.active_field != "desc" and self.active_field != "meta":
                            self._save()
                            running = False
                        else:
                            self._handle_text_input(event)
                    else:
                        self._handle_text_input(event)
                        
                if event.type == pygame.MOUSEBUTTONDOWN:
                    self._handle_click(event.pos)
                    # Check buttons
                    mx, my = event.pos
                    # Save Button
                    if self.btn_save.collidepoint(mx, my):
                        self._save()
                        running = False
                    # Cancel Button
                    elif self.btn_cancel.collidepoint(mx, my):
                        running = False
                    # Type Button
                    elif self.btn_type.collidepoint(mx, my):
                        self.current_type_idx = (self.current_type_idx + 1) % len(self.type_opts)

            self.draw()
            pygame.display.flip()

    def _handle_text_input(self, event):
        if event.key == pygame.K_BACKSPACE:
            if self.active_field == "title": self.title_text = self.title_text[:-1]
            elif self.active_field == "desc": self.desc_text = self.desc_text[:-1]
            elif self.active_field == "meta": self.meta_json_text = self.meta_json_text[:-1]
        elif event.key == pygame.K_RETURN:
            if self.active_field == "desc": self.desc_text += "\n"
            elif self.active_field == "meta": self.meta_json_text += "\n"
        else:
            if self.active_field == "title": self.title_text += event.unicode
            elif self.active_field == "desc": self.desc_text += event.unicode
            elif self.active_field == "meta": self.meta_json_text += event.unicode

    def _cycle_field(self):
        fields = ["title", "desc", "meta"]
        idx = fields.index(self.active_field)
        self.active_field = fields[(idx + 1) % len(fields)]

    def _handle_click(self, pos):
        mx, my = pos
        # Simple hit detection for text areas
        if self.rect_title.collidepoint(mx, my): self.active_field = "title"
        elif self.rect_desc.collidepoint(mx, my): self.active_field = "desc"
        elif self.rect_meta.collidepoint(mx, my): self.active_field = "meta"

    def _save(self):
        # Parse JSON
        try:
            meta_obj = json.loads(self.meta_json_text)
        except:
            print("WARNING: Invalid JSON in metadata, saving as empty dict")
            meta_obj = {}
            
        chosen_type = self.type_opts[self.current_type_idx]
        symbol = self.sym_map.get(chosen_type, "star")
        
        self.on_save(
            self.marker_data.get('id'),
            symbol,
            self.title_text,
            self.desc_text,
            meta_obj
        )

    def draw(self):
        # Dim background
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        overlay.set_alpha(150)
        overlay.fill((0,0,0))
        self.screen.blit(overlay, (0,0))
        
        # Panel
        panel = pygame.Rect(self.x, self.y, self.panel_w, self.panel_h)
        pygame.draw.rect(self.screen, (40, 40, 50), panel, border_radius=10)
        pygame.draw.rect(self.screen, (100, 100, 120), panel, 2, border_radius=10)
        
        # Header
        head = self.font_title.render("Edit Details", True, (255, 255, 255))
        self.screen.blit(head, (self.x + 20, self.y + 20))
        
        # --- TITLE ---
        lbl_t = self.font.render("Title:", True, (200, 200, 200))
        self.screen.blit(lbl_t, (self.x + 20, self.y + 60))
        self.rect_title = pygame.Rect(self.x + 20, self.y + 85, self.panel_w - 40, 30)
        color = (255, 255, 255) if self.active_field == "title" else (200, 200, 200)
        pygame.draw.rect(self.screen, (20, 20, 25), self.rect_title)
        pygame.draw.rect(self.screen, color, self.rect_title, 1)
        
        t_surf = self.font.render(self.title_text, True, (255, 255, 255))
        self.screen.blit(t_surf, (self.rect_title.x + 5, self.rect_title.y + 5))

        # --- TYPE ---
        lbl_ty = self.font.render("Type:", True, (200, 200, 200))
        self.screen.blit(lbl_ty, (self.x + 20, self.y + 125))
        self.btn_type = pygame.Rect(self.x + 80, self.y + 120, 150, 30)
        pygame.draw.rect(self.screen, (60, 60, 80), self.btn_type, border_radius=5)
        type_txt = self.type_opts[self.current_type_idx].title()
        ts = self.font.render(type_txt, True, (255, 255, 255))
        self.screen.blit(ts, (self.btn_type.x + 10, self.btn_type.y + 7))

        # --- DESCRIPTION ---
        lbl_d = self.font.render("Description:", True, (200, 200, 200))
        self.screen.blit(lbl_d, (self.x + 20, self.y + 160))
        self.rect_desc = pygame.Rect(self.x + 20, self.y + 185, self.panel_w - 40, 100)
        color = (255, 255, 255) if self.active_field == "desc" else (200, 200, 200)
        pygame.draw.rect(self.screen, (20, 20, 25), self.rect_desc)
        pygame.draw.rect(self.screen, color, self.rect_desc, 1)
        
        self._draw_multiline(self.desc_text, self.rect_desc)

        # --- METADATA ---
        lbl_m = self.font.render("Metadata (JSON):", True, (200, 200, 200))
        self.screen.blit(lbl_m, (self.x + 20, self.y + 300))
        self.rect_meta = pygame.Rect(self.x + 20, self.y + 325, self.panel_w - 40, 180)
        color = (255, 255, 255) if self.active_field == "meta" else (200, 200, 200)
        pygame.draw.rect(self.screen, (20, 20, 25), self.rect_meta)
        pygame.draw.rect(self.screen, color, self.rect_meta, 1)
        
        self._draw_multiline(self.meta_json_text, self.rect_meta)

        # --- BUTTONS ---
        self.btn_save = pygame.Rect(self.x + 20, self.y + 530, 100, 40)
        self.btn_cancel = pygame.Rect(self.x + 140, self.y + 530, 100, 40)
        
        pygame.draw.rect(self.screen, (50, 150, 50), self.btn_save, border_radius=5)
        st = self.font.render("Save", True, (255, 255, 255))
        self.screen.blit(st, (self.btn_save.x + 30, self.btn_save.y + 12))
        
        pygame.draw.rect(self.screen, (150, 50, 50), self.btn_cancel, border_radius=5)
        ct = self.font.render("Cancel", True, (255, 255, 255))
        self.screen.blit(ct, (self.btn_cancel.x + 20, self.btn_cancel.y + 12))

    def _draw_multiline(self, text, rect):
        lines = text.split('\n')
        y_off = 5
        for line in lines:
            if y_off + 20 > rect.height: break
            surf = self.font.render(line, True, (220, 220, 220))
            self.screen.blit(surf, (rect.x + 5, rect.y + y_off))
            y_off += 20

# Replace the NativeMarkerEditor class name for compatibility
NativeMarkerEditor = PygameMarkerEditor
