import pygame
from codex_engine.core.db_manager import DBManager
from codex_engine.ui.widgets import Button, InputBox

class CampaignMenu:
    def __init__(self, screen, db_manager: DBManager):
        self.screen = screen
        self.db = db_manager
        self.font_title = pygame.font.Font(None, 60)
        self.font_ui = pygame.font.Font(None, 32)
        self.c_bg = (40, 30, 20)
        self.c_panel = (245, 235, 215)
        self.c_text = (40, 30, 20)
        
        self.mode = "SELECT" 
        self.selected_campaign_id = None
        self.campaign_list = []
        self.refresh_list()
        
        self.input_name = InputBox(800, 200, 300, 40, self.font_ui)
        self.btn_new = Button(50, 800, 200, 50, "New Campaign", self.font_ui, (100, 200, 100), (150, 250, 150), (0,0,0), self.switch_to_create)
        self.btn_create = Button(800, 400, 200, 50, "Create World", self.font_ui, (100, 200, 100), (150, 250, 150), (0,0,0), self.do_create)
        self.btn_cancel = Button(1020, 400, 150, 50, "Cancel", self.font_ui, (200, 100, 100), (250, 150, 150), (0,0,0), self.switch_to_select)
        
        self.themes = ["fantasy", "scifi"]
        self.selected_theme_idx = 0
        
    def refresh_list(self): self.campaign_list = self.db.get_all_campaigns()
    def switch_to_create(self): self.mode = "CREATE"; self.input_name.text = ""; self.input_name.txt_surface = self.input_name.font.render("", True, (0,0,0))
    def switch_to_select(self): self.mode = "SELECT"
    def do_create(self):
        name = self.input_name.text.strip()
        if not name: return
        theme = self.themes[self.selected_theme_idx]
        new_id = self.db.create_campaign(name, theme)
        self.refresh_list()
        self.mode = "SELECT"
        
    def handle_input(self, event):
        if self.mode == "SELECT":
            if event.type == pygame.MOUSEBUTTONDOWN:
                mx, my = event.pos
                start_y = 150
                for camp in self.campaign_list:
                    rect = pygame.Rect(50, start_y, 600, 50)
                    if rect.collidepoint(mx, my):
                        self.selected_campaign_id = camp['id']
                        return {"action": "load_campaign", "id": camp['id'], "theme": camp['theme_id']}
                    start_y += 60
            self.btn_new.handle_event(event)
        elif self.mode == "CREATE":
            self.input_name.handle_event(event)
            self.btn_create.handle_event(event)
            self.btn_cancel.handle_event(event)
            if event.type == pygame.MOUSEBUTTONDOWN:
                if pygame.Rect(800, 300, 300, 40).collidepoint(event.pos): self.selected_theme_idx = (self.selected_theme_idx + 1) % len(self.themes)

    def draw(self):
        self.screen.fill(self.c_bg)
        pygame.draw.rect(self.screen, self.c_panel, (30, 30, 640, 840), border_radius=10)
        title = self.font_title.render("Campaign Chronicles", True, self.c_text)
        self.screen.blit(title, (50, 50))
        
        start_y = 150
        for camp in self.campaign_list:
            color = (200, 190, 170) if camp['id'] != self.selected_campaign_id else (180, 220, 180)
            pygame.draw.rect(self.screen, color, (50, start_y, 600, 50), border_radius=5)
            pygame.draw.rect(self.screen, self.c_text, (50, start_y, 600, 50), 2, border_radius=5)
            name_txt = self.font_ui.render(camp['name'], True, self.c_text)
            date_txt = self.font_ui.render(f"Theme: {camp['theme_id'].title()}", True, (100, 100, 100))
            self.screen.blit(name_txt, (70, start_y + 15))
            self.screen.blit(date_txt, (450, start_y + 15))
            start_y += 60
            
        if self.mode == "SELECT":
            self.btn_new.draw(self.screen)
            if self.selected_campaign_id:
                instr = self.font_ui.render("Click Selected to Launch", True, (200, 200, 200))
                self.screen.blit(instr, (400, 815))
                
        elif self.mode == "CREATE":
            pygame.draw.rect(self.screen, self.c_panel, (750, 100, 420, 400), border_radius=10)
            pygame.draw.rect(self.screen, (200, 50, 50), (750, 100, 420, 400), 3, border_radius=10)
            head = self.font_title.render("New World", True, self.c_text)
            self.screen.blit(head, (780, 120))
            lbl_name = self.font_ui.render("Campaign Name:", True, self.c_text)
            self.screen.blit(lbl_name, (800, 170))
            self.input_name.draw(self.screen)
            lbl_theme = self.font_ui.render("Select Theme:", True, self.c_text)
            self.screen.blit(lbl_theme, (800, 270))
            pygame.draw.rect(self.screen, (255, 255, 255), (800, 300, 300, 40))
            pygame.draw.rect(self.screen, (0,0,0), (800, 300, 300, 40), 2)
            theme_txt = self.font_ui.render(self.themes[self.selected_theme_idx].title(), True, (0,0,0))
            self.screen.blit(theme_txt, (810, 310))
            self.btn_create.draw(self.screen)
            self.btn_cancel.draw(self.screen)
