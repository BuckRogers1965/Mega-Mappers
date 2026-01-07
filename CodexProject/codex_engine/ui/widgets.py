import pygame

class SimpleDropdown:
    def __init__(self, x, y, w, h, font, options, initial_val=None):
        self.rect = pygame.Rect(x, y, w, h)
        self.font = font
        self.options = options # List of strings
        self.is_open = False
        self.selected_idx = -1
        if initial_val and initial_val in options:
            self.selected_idx = options.index(initial_val)
        
        self.color_bg = (60, 60, 80)
        self.color_border = (100, 100, 120)
        self.color_hover = (90, 90, 110)

    def get_selected_id(self):
        return self.options[self.selected_idx]

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.is_open:
                for i in range(len(self.options)):
                    opt_rect = pygame.Rect(self.rect.x, self.rect.bottom + (i * 30), self.rect.width, 30)
                    if opt_rect.collidepoint(event.pos):
                        self.selected_idx = i
                        self.is_open = False
                        return True
                self.is_open = False
            else:
                if self.rect.collidepoint(event.pos):
                    self.is_open = True
                    return True
        return False

    def draw(self, surface):
        pygame.draw.rect(surface, self.color_bg, self.rect)
        pygame.draw.rect(surface, self.color_border, self.rect, 1)

        if self.selected_idx == -1:
            text = "Choose a Theme..."
            color = (180, 180, 180) # Greyed out
        else:
            text = self.options[self.selected_idx].title()
            color = (255, 255, 255)
        
        surf = self.font.render(text, True, (255, 255, 255))
        surface.blit(surf, (self.rect.x + 10, self.rect.y + 8))
        
        pygame.draw.polygon(surface, (200, 200, 200), [
            (self.rect.right - 20, self.rect.y + 12),
            (self.rect.right - 10, self.rect.y + 12),
            (self.rect.right - 15, self.rect.y + 22)
        ])

        if self.is_open:
            list_h = len(self.options) * 30
            list_rect = pygame.Rect(self.rect.x, self.rect.bottom, self.rect.width, list_h)
            pygame.draw.rect(surface, (25, 25, 30), list_rect)
            pygame.draw.rect(surface, self.color_border, list_rect, 1)
            mx, my = pygame.mouse.get_pos()
            for i, opt in enumerate(self.options):
                r = pygame.Rect(self.rect.x, self.rect.bottom + (i * 30), self.rect.width, 30)
                if r.collidepoint((mx, my)):
                    pygame.draw.rect(surface, self.color_hover, r)
                txt = self.font.render(opt.title(), True, (220, 220, 220))
                surface.blit(txt, (r.x + 10, r.y + 8))

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
        if (self.max_val - self.min_val) == 0: ratio = 0
        else: ratio = (self.value - self.min_val) / (self.max_val - self.min_val)
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

class Dropdown:
    def __init__(self, x, y, w, h, font, options, initial_id=None, max_visible=25):
        self.rect = pygame.Rect(x, y, w, h)
        self.font = font
        self.options = options # List of dicts {'id': 'x', 'name': 'Y'}
        self.is_open = False
        self.selected_idx = -1
        self.max_visible = max_visible
        self.scroll_offset = 0
        
        # Styles
        self.color_bg = (30, 30, 40)
        self.color_border = (100, 100, 120)
        self.color_hover = (60, 60, 80)
        self.item_height = 30

        if initial_id:
            self.set_selection_by_id(initial_id)

    def set_selection_by_id(self, id_val):
        for i, opt in enumerate(self.options):
            if opt['id'] == id_val:
                self.selected_idx = i
                return
        self.selected_idx = -1

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.is_open:
                # 1. Check Scrollbar/List Area
                list_h = min(len(self.options), self.max_visible) * self.item_height
                list_rect = pygame.Rect(self.rect.x, self.rect.bottom, self.rect.width, list_h)
                
                if list_rect.collidepoint(event.pos):
                    # Calculate index based on scroll
                    local_y = event.pos[1] - list_rect.y
                    idx = (local_y // self.item_height) + self.scroll_offset
                    
                    if 0 <= idx < len(self.options):
                        self.selected_idx = idx
                        self.is_open = False
                        return True
                else:
                    self.is_open = False # Clicked outside
            else:
                if self.rect.collidepoint(event.pos):
                    self.is_open = True
                    return True
                    
        elif event.type == pygame.MOUSEWHEEL and self.is_open:
            if len(self.options) > self.max_visible:
                self.scroll_offset -= event.y
                self.scroll_offset = max(0, min(self.scroll_offset, len(self.options) - self.max_visible))
                return True
                
        return False

    def get_selected_id(self):
        if self.selected_idx >= 0 and self.selected_idx < len(self.options):
            return self.options[self.selected_idx]['id']
        return None

    def draw(self, surface):
        # Draw Main Box
        pygame.draw.rect(surface, self.color_bg, self.rect)
        pygame.draw.rect(surface, self.color_border, self.rect, 1)
        
        text = "Select..."
        if self.selected_idx >= 0 and self.selected_idx < len(self.options):
            text = self.options[self.selected_idx]['name']
        
        # Truncate text if too long
        if len(text) > 25: text = text[:22] + "..."
        
        surf = self.font.render(text, True, (255, 255, 255))
        surface.blit(surf, (self.rect.x + 5, self.rect.y + 8))
        
        # Arrow
        pygame.draw.polygon(surface, (200, 200, 200), [
            (self.rect.right - 15, self.rect.y + 10),
            (self.rect.right - 5, self.rect.y + 10),
            (self.rect.right - 10, self.rect.y + 20)
        ])

        # Draw Open List
        if self.is_open:
            visible_count = min(len(self.options), self.max_visible)
            list_h = visible_count * self.item_height
            list_rect = pygame.Rect(self.rect.x, self.rect.bottom, self.rect.width, list_h)
            
            # Background
            pygame.draw.rect(surface, (25, 25, 30), list_rect)
            pygame.draw.rect(surface, self.color_border, list_rect, 1)
            
            mx, my = pygame.mouse.get_pos()
            
            # Draw Items
            for i in range(visible_count):
                real_idx = i + self.scroll_offset
                if real_idx >= len(self.options): break
                
                opt = self.options[real_idx]
                item_y = list_rect.y + (i * self.item_height)
                item_rect = pygame.Rect(list_rect.x, item_y, list_rect.width, self.item_height)
                
                # Hover
                if item_rect.collidepoint((mx, my)):
                    pygame.draw.rect(surface, self.color_hover, item_rect)
                
                # Selection Highlight
                if real_idx == self.selected_idx:
                     pygame.draw.rect(surface, (50, 80, 50), item_rect, 1)

                label = opt['name']
                if len(label) > 30: label = label[:27] + "..."
                
                txt = self.font.render(label, True, (220, 220, 220))
                surface.blit(txt, (item_rect.x + 5, item_rect.y + 8))

            # Draw Scrollbar
            if len(self.options) > self.max_visible:
                sb_width = 8
                sb_track = pygame.Rect(list_rect.right - sb_width, list_rect.top, sb_width, list_rect.height)
                pygame.draw.rect(surface, (40, 40, 50), sb_track)
                
                # Thumb
                ratio = visible_count / len(self.options)
                thumb_h = max(20, list_rect.height * ratio)
                scroll_ratio = self.scroll_offset / (len(self.options) - visible_count)
                thumb_y = list_rect.top + scroll_ratio * (list_rect.height - thumb_h)
                
                sb_thumb = pygame.Rect(list_rect.right - sb_width, thumb_y, sb_width, thumb_h)
                pygame.draw.rect(surface, (150, 150, 150), sb_thumb, border_radius=4)

class ContextMenu:
    def __init__(self, x, y, options, font):
        self.options = options  # List of tuples: ("Label", callback_function)
        self.font = font
        self.item_height = 30
        
        # Calculate dimensions
        max_width = max(font.size(opt[0])[0] for opt in options) + 20
        self.rect = pygame.Rect(x, y, max_width, len(options) * self.item_height)
        
        # Style
        self.bg_color = (40, 40, 50)
        self.border_color = (100, 100, 120)
        self.hover_color = (60, 60, 80)
        self.text_color = (220, 220, 220)

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.rect.collidepoint(event.pos):
                # Click is inside the menu, find which item
                item_index = (event.pos[1] - self.rect.y) // self.item_height
                if 0 <= item_index < len(self.options):
                    self.options[item_index][1]() # Call the callback function
                return True # Event handled, close menu
            else:
                # Click is outside, close menu
                return True 
        return False

    def draw(self, surface):
        pygame.draw.rect(surface, self.bg_color, self.rect)
        pygame.draw.rect(surface, self.border_color, self.rect, 1)
        
        mx, my = pygame.mouse.get_pos()

        for i, (label, _) in enumerate(self.options):
            item_rect = pygame.Rect(self.rect.x, self.rect.y + i * self.item_height, self.rect.width, self.item_height)
            
            # Skip drawing/interaction for separator
            if label == "":
                continue

            if item_rect.collidepoint(mx, my):
                pygame.draw.rect(surface, self.hover_color, item_rect)
            
            text_surf = self.font.render(label, True, self.text_color)
            surface.blit(text_surf, (item_rect.x + 10, item_rect.y + 7))
        
        """
        for i, (label, _) in enumerate(self.options):
            item_rect = pygame.Rect(self.rect.x, self.rect.y + i * self.item_height, self.rect.width, self.item_height)
            if item_rect.collidepoint(mx, my):
                pygame.draw.rect(surface, self.hover_color, item_rect)
            
            text_surf = self.font.render(label, True, self.text_color)
            surface.blit(text_surf, (item_rect.x + 10, item_rect.y + 7))
"""

class StructureBrowser:
    def __init__(self, x, y, w, h, db, current_node_id, font, on_navigate):
        self.rect = pygame.Rect(x, y, w, h)
        self.db = db
        self.font = font
        self.on_navigate = on_navigate
        self.buttons = []
        btn_h = 30

        # 1. DISCOVERY: Find the logical root of this structure
        current_node = self.db.get_node(current_node_id)
        
        # If we are inside a level, the 'Root' is actually our parent (the POI marker)
        if current_node['type'] in ['dungeon_level', 'building_interior', 'tactical_map']:
            root_id = current_node['parent_id']
            self.root_node = self.db.get_node(root_id)
            # Siblings + Self
            self.structure_data = self.db.get_children(root_id)
        else:
            # We are at a Map level looking at markers
            self.root_node = current_node
            self.structure_data = self.db.get_children(current_node_id)

        # 2. Add the ROOT node as the first "Info" entry
        if self.root_node:
            self._add_button(
                x, y, w, btn_h, 
                f"ℹ️ {self.root_node['name']}", 
                (80, 80, 100), # Distinct color for the Header/Info
                self.root_node['id'],
                is_root=True
            )

        # 3. Add the levels/markers
        for i, item in enumerate(self.structure_data):
            # Skip the party view marker in the list
            if item.get('properties', {}).get('is_view_marker'):
                continue

            label_text = item.get('name', 'Unknown')
            is_active_level = item['id'] == current_node_id
            
            icon = "📍" if item.get('type') == 'poi' else "•"
            label = f"{icon} {label_text}"
            
            # Active level is highlighted green
            base_col = (100, 150, 100) if is_active_level else (60, 60, 70)
            
            # Offset y by (i+1) because root is at index 0
            self._add_button(x, y + ((i + 1) * (btn_h + 5)), w, btn_h, label, base_col, item['id'])

    def _add_button(self, x, y, w, h, label, color, node_id, is_root=False):
        indent = 15
        btn = Button(
            x + indent, y, w - indent - 20, h, 
            label, self.font, 
            color, (90, 90, 110), (255, 255, 255),
            lambda nid=node_id: self.on_navigate(nid)
        )
        self.buttons.append(btn)

    def handle_event(self, event):
        for btn in self.buttons:
            res = btn.handle_event(event)
            if res: return res
        return None

    def draw(self, surface):
        surface.set_clip(self.rect)
        for btn in self.buttons:
            btn.draw(surface)
        surface.set_clip(None)

class UIScrollPanel:
    def __init__(self, x, y, w, h, content_height):
        self.rect = pygame.Rect(x, y, w, h)
        self.content_height = max(content_height, h)
        self.surface = pygame.Surface((w, self.content_height))
        self.surface.fill((40, 40, 50)) # Match panel BG
        self.scroll_y = 0
        self.dragging = False
        
        # Scrollbar
        self.sb_width = 10
        self.update_scrollbar()

    def update_scrollbar(self):
        ratio = self.rect.height / self.content_height
        thumb_h = max(20, self.rect.height * ratio)
        scroll_ratio = self.scroll_offset_ratio()
        thumb_y = self.rect.y + (scroll_ratio * (self.rect.height - thumb_h))
        self.sb_rect = pygame.Rect(self.rect.right - self.sb_width, thumb_y, self.sb_width, thumb_h)

    def scroll_offset_ratio(self):
        if self.content_height <= self.rect.height: return 0
        return self.scroll_y / (self.content_height - self.rect.height)

    def handle_event(self, event):
        if event.type == pygame.MOUSEWHEEL:
            if self.rect.collidepoint(pygame.mouse.get_pos()):
                self.scroll_y -= event.y * 20
                self.scroll_y = max(0, min(self.scroll_y, self.content_height - self.rect.height))
                self.update_scrollbar()
                return True # Consumed
        return False

    def draw_background(self):
        self.surface.fill((40, 40, 50))

    def draw_to_screen(self, screen):
        # Blit the visible portion of the surface to the screen
        area = pygame.Rect(0, self.scroll_y, self.rect.width, self.rect.height)
        screen.blit(self.surface, self.rect, area)
        
        # Draw Scrollbar track and thumb
        if self.content_height > self.rect.height:
            track = pygame.Rect(self.rect.right - self.sb_width, self.rect.y, self.sb_width, self.rect.height)
            pygame.draw.rect(screen, (30, 30, 35), track)
            pygame.draw.rect(screen, (100, 100, 100), self.sb_rect, border_radius=5)

import textwrap

class Checkbox:
    def __init__(self, x, y, size, label, font, checked=False):
        self.rect = pygame.Rect(x, y, size, size)
        self.label = label
        self.font = font
        self.checked = checked
        
    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and self.rect.collidepoint(event.pos):
            self.checked = not self.checked
            return True
        return False
        
    def draw(self, surface):
        # Box
        pygame.draw.rect(surface, (200, 200, 200), self.rect, 2)
        if self.checked:
            inner = self.rect.inflate(-6, -6)
            pygame.draw.rect(surface, (100, 200, 100), inner)
        
        # Label
        if self.label:
            lbl = self.font.render(self.label, True, (220, 220, 220))
            surface.blit(lbl, (self.rect.right + 10, self.rect.y + (self.rect.height//2 - lbl.get_height()//2)))

class TextArea:
    def __init__(self, x, y, w, h, font, text=''):
        self.rect = pygame.Rect(x, y, w, h)
        self.font = font
        self.text = text
        self.active = False
        self.color_inactive = (60, 60, 70)
        self.color_active = (30, 30, 40)
        self.border_color = (100, 100, 120)

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            self.active = self.rect.collidepoint(event.pos)
        
        if event.type == pygame.KEYDOWN and self.active:
            if event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
            elif event.key == pygame.K_RETURN:
                self.text += '\n'
            else:
                self.text += event.unicode

    def draw(self, surface):
        # Draw BG
        color = self.color_active if self.active else self.color_inactive
        pygame.draw.rect(surface, color, self.rect)
        pygame.draw.rect(surface, self.border_color, self.rect, 1)
        
        # Wrap and Draw Text
        # Estimate chars per line based on width (approximate)
        char_w = self.font.size('A')[0]
        chars_per_line = max(10, (self.rect.width - 10) // char_w)
        
        lines = []
        for paragraph in self.text.split('\n'):
            lines.extend(textwrap.wrap(paragraph, width=chars_per_line))
        
        y_off = 5
        for line in lines:
            if y_off + self.font.get_height() > self.rect.height: break
            ts = self.font.render(line, True, (255, 255, 255))
            surface.blit(ts, (self.rect.x + 5, self.rect.y + y_off))
            y_off += self.font.get_height() + 2
