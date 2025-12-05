import pygame

class Button:
    def __init__(self, x, y, w, h, text, font, base_color, hover_color, text_color, action=None):
        self.rect = pygame.Rect(x, y, w, h)
        self.text = text
        self.font = font
        self.base_color = base_color
        self.hover_color = hover_color
        self.text_color = text_color
        self.action = action
        self.is_hovered = False
    def handle_event(self, event):
        if event.type == pygame.MOUSEMOTION: self.is_hovered = self.rect.collidepoint(event.pos)
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.is_hovered and self.action: return self.action()
        return None
    def draw(self, surface):
        color = self.hover_color if self.is_hovered else self.base_color
        pygame.draw.rect(surface, color, self.rect, border_radius=5)
        pygame.draw.rect(surface, (0,0,0), self.rect, 2, border_radius=5)
        txt_surf = self.font.render(self.text, True, self.text_color)
        txt_rect = txt_surf.get_rect(center=self.rect.center)
        surface.blit(txt_surf, txt_rect)

class InputBox:
    def __init__(self, x, y, w, h, font, text=''):
        self.rect = pygame.Rect(x, y, w, h)
        self.color_inactive = pygame.Color('lightskyblue3')
        self.color_active = pygame.Color('dodgerblue2')
        self.color = self.color_inactive
        self.text = text
        self.font = font
        self.txt_surface = self.font.render(text, True, self.color)
        self.active = False
    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.rect.collidepoint(event.pos): self.active = not self.active
            else: self.active = False
            self.color = self.color_active if self.active else self.color_inactive
        if event.type == pygame.KEYDOWN:
            if self.active:
                if event.key == pygame.K_RETURN: return self.text
                elif event.key == pygame.K_BACKSPACE: self.text = self.text[:-1]
                else: self.text += event.unicode
                self.txt_surface = self.font.render(self.text, True, self.color)
    def draw(self, surface):
        surface.blit(self.txt_surface, (self.rect.x+5, self.rect.y+5))
        pygame.draw.rect(surface, self.color, self.rect, 2)

class Slider:
    def __init__(self, x, y, w, h, min_val, max_val, initial_val, label):
        self.rect = pygame.Rect(x, y, w, h)
        self.min_val = min_val
        self.max_val = max_val
        self.value = initial_val
        self.label = label
        self.font = pygame.font.Font(None, 24)
        self.dragging = False
        self.handle_w = 15
        self.update_handle()
    def update_handle(self):
        # Prevent division by zero if min==max
        if (self.max_val - self.min_val) == 0:
            ratio = 0
        else:
            ratio = (self.value - self.min_val) / (self.max_val - self.min_val)
        handle_x = self.rect.x + (self.rect.width * ratio) - (self.handle_w / 2)
        self.handle_rect = pygame.Rect(handle_x, self.rect.y - 5, self.handle_w, self.rect.height + 10)
    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.handle_rect.collidepoint(event.pos) or self.rect.collidepoint(event.pos):
                self.dragging = True
        elif event.type == pygame.MOUSEBUTTONUP: self.dragging = False
        elif event.type == pygame.MOUSEMOTION:
            if self.dragging:
                rel_x = event.pos[0] - self.rect.x
                rel_x = max(0, min(rel_x, self.rect.width))
                ratio = rel_x / self.rect.width
                self.value = self.min_val + (ratio * (self.max_val - self.min_val))
                self.update_handle()
    def draw(self, surface):
        lbl = self.font.render(f"{self.label}: {self.value:.2f}", True, (200, 200, 200))
        surface.blit(lbl, (self.rect.x, self.rect.y - 20))
        pygame.draw.rect(surface, (100, 100, 100), self.rect, border_radius=5)
        color = (200, 200, 200) if not self.dragging else (255, 255, 255)
        pygame.draw.rect(surface, color, self.handle_rect, border_radius=3)

class MarkerModal:
    def __init__(self, x, y, on_save, on_cancel, marker_data=None):
        self.is_editing = marker_data is not None
        self.marker_id = marker_data['id'] if self.is_editing else None
        
        self.rect = pygame.Rect(x, y, 300, 250)
        self.on_save = on_save
        self.on_cancel = on_cancel
        self.font = pygame.font.Font(None, 24)
        
        # Pre-fill fields if editing
        title = marker_data['title'] if self.is_editing else ""
        note = marker_data['description'] if self.is_editing else ""
        
        self.input_title = InputBox(x+20, y+50, 260, 32, self.font, text=title)
        self.input_note = InputBox(x+20, y+100, 260, 32, self.font, text=note)
        
        self.symbols = ["🏰", "⚔️", "🌲", "💀", "🏘️", "⛏️"]
        self.selected_symbol = marker_data['symbol'] if self.is_editing else "🏰"
        
        save_text = "Update" if self.is_editing else "Save"
        self.btn_save = Button(x+20, y+200, 100, 30, save_text, self.font, (100,200,100), (150,250,150), (0,0,0), self.trigger_save)
        self.btn_cancel = Button(x+180, y+200, 100, 30, "Cancel", self.font, (200,100,100), (250,150,150), (0,0,0), on_cancel)

    def trigger_save(self):
        if self.input_title.text:
            self.on_save(self.marker_id, self.selected_symbol, self.input_title.text, self.input_note.text)

    def handle_event(self, event):
        self.input_title.handle_event(event)
        self.input_note.handle_event(event)
        self.btn_save.handle_event(event)
        self.btn_cancel.handle_event(event)
        
        if event.type == pygame.MOUSEBUTTONDOWN:
            # Symbol Selection
            sx, sy = self.rect.x + 20, self.rect.y + 150
            for sym in self.symbols:
                r = pygame.Rect(sx, sy, 30, 30)
                if r.collidepoint(event.pos):
                    self.selected_symbol = sym
                sx += 40

    def draw(self, surface):
        pygame.draw.rect(surface, (50, 50, 60), self.rect, border_radius=10)
        pygame.draw.rect(surface, (200, 200, 200), self.rect, 2, border_radius=10)
        
        lbl = self.font.render("Add Map Note", True, (255,255,255))
        surface.blit(lbl, (self.rect.x+20, self.rect.y+10))
        
        lbl_t = self.font.render("Title:", True, (200,200,200))
        surface.blit(lbl_t, (self.rect.x+20, self.rect.y+35))
        self.input_title.draw(surface)
        
        lbl_n = self.font.render("Note:", True, (200,200,200))
        surface.blit(lbl_n, (self.rect.x+20, self.rect.y+85))
        self.input_note.draw(surface)
        
        sx, sy = self.rect.x + 20, self.rect.y + 150
        for sym in self.symbols:
            color = (100, 100, 150) if sym == self.selected_symbol else (70, 70, 80)
            pygame.draw.rect(surface, color, (sx, sy, 30, 30), border_radius=5)
            # You might need a font that supports emojis, default pygame font often doesn't. 
            # If squares appear, change font.
            txt = self.font.render(sym, True, (255,255,255))
            surface.blit(txt, (sx+5, sy+5))
            sx += 40
            
        self.btn_save.draw(surface)
        self.btn_cancel.draw(surface)