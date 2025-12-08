import pygame
from codex_engine.ui.widgets import Button
from codex_engine.ui.editors import NativeMarkerEditor
from codex_engine.config import SCREEN_HEIGHT

class InfoPanel:
    def __init__(self, content_manager, db_manager, node_data, font_ui, font_small):
        self.content = content_manager
        self.db = db_manager
        self.node = node_data
        self.font_ui = font_ui
        self.font_small = font_small
        
        self.widgets = []
        self._init_ui()
        
        # SCROLL STATE
        self.scroll_y = 0
        self.max_scroll = 0
        self.view_rect = pygame.Rect(10, 180, 240, SCREEN_HEIGHT - 280) # Visible text area
        
        # Scrollbar interaction
        self.scrollbar_rect = pygame.Rect(250, 180, 5, 100)  # Will be updated in draw()
        self.dragging_scrollbar = False
        self.drag_start_y = 0
        self.drag_start_scroll = 0

    def _init_ui(self):
        self.btn_edit_node = Button(20, 140, 220, 30, "Edit Map Details", self.font_ui, (100, 100, 150), (120, 120, 180), (255,255,255), self._edit_current_node)
        self.widgets.append(self.btn_edit_node)

    def handle_event(self, event):
        """Called by controller to handle scrolling."""
        mx, my = pygame.mouse.get_pos()
        
        # Only handle events if mouse is over the sidebar
        if mx >= 260:
            return False
        
        # Mouse wheel scrolling
        if event.type == pygame.MOUSEWHEEL:
            if mx < 260:
                self.scroll_y -= event.y * 20
                self.scroll_y = max(0, min(self.scroll_y, self.max_scroll))
                return True
        
        # Arrow key scrolling (when mouse is over info panel)
        if event.type == pygame.KEYDOWN:
            if self.view_rect.collidepoint(mx, my) or self.scrollbar_rect.collidepoint(mx, my):
                if event.key == pygame.K_UP:
                    self.scroll_y -= 20
                    self.scroll_y = max(0, min(self.scroll_y, self.max_scroll))
                    return True
                elif event.key == pygame.K_DOWN:
                    self.scroll_y += 20
                    self.scroll_y = max(0, min(self.scroll_y, self.max_scroll))
                    return True
                elif event.key == pygame.K_PAGEUP:
                    self.scroll_y -= self.view_rect.height
                    self.scroll_y = max(0, min(self.scroll_y, self.max_scroll))
                    return True
                elif event.key == pygame.K_PAGEDOWN:
                    self.scroll_y += self.view_rect.height
                    self.scroll_y = max(0, min(self.scroll_y, self.max_scroll))
                    return True
                elif event.key == pygame.K_HOME:
                    self.scroll_y = 0
                    return True
                elif event.key == pygame.K_END:
                    self.scroll_y = self.max_scroll
                    return True
        
        # Scrollbar dragging
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.scrollbar_rect.collidepoint(mx, my) and self.max_scroll > 0:
                self.dragging_scrollbar = True
                self.drag_start_y = my
                self.drag_start_scroll = self.scroll_y
                return True
            # Click in scroll track (above or below bar)
            elif mx >= 250 and mx <= 255 and self.view_rect.top <= my <= self.view_rect.bottom:
                if self.max_scroll > 0:
                    # Calculate where in the track we clicked
                    relative_y = my - self.view_rect.top
                    total_h = self._calculate_total_height()
                    bar_h = self.view_rect.height * (self.view_rect.height / total_h)
                    
                    # Jump to that position
                    target_ratio = relative_y / self.view_rect.height
                    self.scroll_y = target_ratio * self.max_scroll
                    self.scroll_y = max(0, min(self.scroll_y, self.max_scroll))
                    return True
        
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.dragging_scrollbar:
                self.dragging_scrollbar = False
                return True
        
        if event.type == pygame.MOUSEMOTION:
            if self.dragging_scrollbar and self.max_scroll > 0:
                # Calculate scroll position based on drag distance
                dy = my - self.drag_start_y
                total_h = self._calculate_total_height()
                bar_h = self.view_rect.height * (self.view_rect.height / total_h)
                available_track = self.view_rect.height - bar_h
                
                if available_track > 0:
                    scroll_ratio = dy / available_track
                    self.scroll_y = self.drag_start_scroll + (scroll_ratio * self.max_scroll)
                    self.scroll_y = max(0, min(self.scroll_y, self.max_scroll))
                return True
        
        return False

    def _calculate_total_height(self):
        """Helper to calculate total content height."""
        lines = self.content.get_info_text()
        total_h = 0
        for line in lines:
            if line.startswith("---") or line.startswith("CAMPAIGN") or line.startswith("LOCATION") or line.startswith("MAP"):
                font = self.font_ui
            else:
                font = self.font_small
            surf = font.render(line, True, (255, 255, 255))
            total_h += surf.get_height() + 4
        return total_h

    def draw(self, screen):
        lines = self.content.get_info_text()
        
        # Calculate total height first
        total_h = 0
        rendered_lines = []
        
        for line in lines:
            if line.startswith("---") or line.startswith("CAMPAIGN") or line.startswith("LOCATION") or line.startswith("MAP"):
                font = self.font_ui
                color = (200, 200, 150)
            else:
                font = self.font_small
                color = (180, 180, 180)
            
            surf = font.render(line, True, color)
            rendered_lines.append(surf)
            total_h += surf.get_height() + 4
            
        self.max_scroll = max(0, total_h - self.view_rect.height)
        
        # CLIP AND DRAW
        screen.set_clip(self.view_rect)
        
        draw_y = self.view_rect.y - self.scroll_y
        
        for surf in rendered_lines:
            # Optimization: Only draw if visible
            if draw_y + surf.get_height() > self.view_rect.top and draw_y < self.view_rect.bottom:
                screen.blit(surf, (20, draw_y))
            draw_y += surf.get_height() + 4
            
        screen.set_clip(None)
        
        # Draw Scrollbar if needed
        if self.max_scroll > 0:
            bar_h = max(20, self.view_rect.height * (self.view_rect.height / total_h))
            bar_y = self.view_rect.y + (self.scroll_y / self.max_scroll) * (self.view_rect.height - bar_h)
            
            # Update scrollbar rect for collision detection
            self.scrollbar_rect = pygame.Rect(250, bar_y, 5, bar_h)
            
            # Draw scrollbar track
            pygame.draw.rect(screen, (50, 50, 50), (250, self.view_rect.top, 5, self.view_rect.height))
            
            # Draw scrollbar thumb
            bar_color = (150, 150, 150) if self.dragging_scrollbar else (100, 100, 100)
            pygame.draw.rect(screen, bar_color, self.scrollbar_rect)
            
            # Highlight on hover
            mx, my = pygame.mouse.get_pos()
            if self.scrollbar_rect.collidepoint(mx, my) and not self.dragging_scrollbar:
                pygame.draw.rect(screen, (120, 120, 120), self.scrollbar_rect)

    def _edit_current_node(self):
        map_marker_data = {
            'id': None, 
            'title': self.node['name'],
            'description': self.node['metadata'].get('overview', ''),
            'metadata': self.node['metadata'],
            'symbol': 'star' 
        }
        
        def on_save_node(mid, sym, title, desc, meta):
            meta['overview'] = desc
            self.db.update_node_data(self.node['id'], geometry=None, metadata=meta)
            return True

        NativeMarkerEditor(
            marker_data=map_marker_data,
            map_context="world_map", 
            on_save=on_save_node,
            on_ai_gen=self._handle_ai_gen_modal
        )
        return {"action": "reload_node"}

    def _handle_ai_gen_modal(self, mtype, title, context):
        return {}
