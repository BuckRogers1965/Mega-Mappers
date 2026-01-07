import pygame
import os
from codex_engine.ui.widgets import Button, InputBox, SimpleDropdown, ContextMenu
from codex_engine.ui.settings_editor import UnifiedSettingsEditor
from codex_engine.config import THEMES_DIR, SCREEN_HEIGHT

# --- SHARED CONSTANTS ---
LOG_NONE  = 0
LOG_INFO  = 1
LOG_DEBUG = 2

class CampaignMenu:
    def __init__(self, screen, db, config_mgr, ai_mgr, verbosity=LOG_NONE):
        self.verbosity = verbosity
        self.log(LOG_INFO, "ENTER: CampaignMenu.__init__")
        
        self.screen = screen
        self.db = db
        self.config = config_mgr
        self.ai = ai_mgr
        
        self.font_title = pygame.font.Font(None, 60)
        self.font_ui = pygame.font.Font(None, 32)
        
        # 1. State
        self.mode = "SELECT" 
        self.selected_campaign_id = None
        self.campaign_list = []
        self.campaign_registry_id = None
        
        # 2. Load Themes from Disk
        self.themes = self._load_themes()
        
        # 3. SELECT MODE WIDGETS
        self.btn_new = Button(50, 740, 200, 50, "New Campaign", self.font_ui, 
                             (100, 200, 100), (150, 250, 150), (0,0,0), self.switch_to_create)
        
        self.btn_settings = Button(1150, 20, 120, 40, "Settings", self.font_ui, 
                                  (60, 60, 70), (80, 80, 90), (255, 255, 255), self.open_global_settings)

        # 4. CREATE MODE WIDGETS
        self.input_name = InputBox(800, 200, 300, 40, self.font_ui)
        self.dd_themes = SimpleDropdown(800, 300, 300, 40, self.font_ui, self.themes)
        
        self.btn_do_create = Button(800, 400, 200, 50, "Create World", self.font_ui, 
                                   (100, 200, 100), (150, 250, 150), (0,0,0), self.do_create_campaign)
        
        self.btn_cancel = Button(1020, 400, 150, 50, "Cancel", self.font_ui, 
                                (200, 100, 100), (250, 150, 150), (0,0,0), self.switch_to_select)

        # Discovery
        self.refresh_list()
        self.log(LOG_INFO, "EXIT: CampaignMenu.__init__")

    def log(self, level, message):
        if self.verbosity >= level:
            prefix = "[MENU INFO]" if level == LOG_INFO else "[MENU DEBUG]"
            print(f"{prefix} {message}")

    def _load_themes(self):
        """Scans the themes directory for available .json files."""
        self.log(LOG_DEBUG, f"Scanning for themes in {THEMES_DIR}")
        if not THEMES_DIR.exists(): return ["fantasy"] 
        theme_files = [f.stem for f in THEMES_DIR.glob("*.json")]
        theme_files.sort()
        return theme_files if theme_files else ["fantasy"]

    def refresh_list(self):
        """Finds the registry and updates the local campaign list."""
        self.log(LOG_INFO, "ENTER: CampaignMenu.refresh_list")
        node = self.db.find_node('campaign_registry')
        if node:
            self.campaign_registry_id = node['id']
            self.campaign_list = self.db.get_children(self.campaign_registry_id)
            self.log(LOG_DEBUG, f"Loaded {len(self.campaign_list)} campaigns.")
        self.log(LOG_INFO, "EXIT: CampaignMenu.refresh_list")

    def switch_to_create(self):
        self.log(LOG_INFO, "ENTER: CampaignMenu.switch_to_create")
        self.mode = "CREATE"
        self.input_name.text = ""
        self.dd_themes.selected_idx = -1 # Reset selection
        self.log(LOG_INFO, "EXIT: CampaignMenu.switch_to_create")

    def switch_to_select(self):
        self.mode = "SELECT"

    def do_create_campaign(self):
        name = self.input_name.text.strip()
        theme = self.dd_themes.get_selected_id()
        
        # Validation: Require Name and Theme
        if not name or not theme:
            self.log(LOG_DEBUG, "Validation Failed: Name and Theme required.")
            return
        
        self.log(LOG_INFO, f"ENTER: do_create_campaign (Name: {name}, Theme: {theme})")
        self.db.create_node(
            type='campaign',
            name=name,
            parent_id=self.campaign_registry_id,
            properties={"theme": theme}
        )
        self.refresh_list()
        self.mode = "SELECT"
        self.log(LOG_INFO, "EXIT: do_create_campaign")

    def open_global_settings(self):
        # 1. Find the parent node of the settings you want to edit
        settings_root = self.db.find_node('settings')
        
        # 2. Launch the generic editor
        editor = UnifiedSettingsEditor(self.screen, self.db, settings_root['id'], self.ai, self.verbosity)
        
        # 3. Modal loop
        while editor.running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT: pygame.quit(); exit()
                editor.handle_input(event)
            
            self.draw() # Draw menu underneath
            editor.draw()
            pygame.display.flip()

    def handle_input(self, event):
        if self.mode == "SELECT":
            # Handle button clicks (New, Settings)
            self.btn_new.handle_event(event)
            self.btn_settings.handle_event(event)
            
            # Handle campaign selection
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mx, my = event.pos
                for i, camp in enumerate(self.campaign_list):
                    rect = pygame.Rect(50, 150 + (i * 60), 600, 50)
                    if rect.collidepoint(mx, my):
                        self.selected_campaign_id = camp['id']
                        theme = camp['properties'].get('theme', 'fantasy')
                        
                        # --- THE FIX: Return the action to the main loop ---
                        self.log(LOG_DEBUG, f"Triggering load for Campaign: {camp['name']}")
                        return {
                            "action": "load_campaign", 
                            "id": camp['id'], 
                            "theme": theme
                        }
        
        elif self.mode == "CREATE":
            if self.dd_themes.handle_event(event): return
            self.input_name.handle_event(event)
            self.btn_do_create.handle_event(event)
            self.btn_cancel.handle_event(event)
            
        return None

    def draw(self):
        C_BG = (40, 30, 20)
        C_PANEL = (245, 235, 215)
        C_TEXT = (40, 30, 20)

        self.screen.fill(C_BG)
        
        # Draw Campaign List Panel
        pygame.draw.rect(self.screen, C_PANEL, (30, 30, 640, 780), border_radius=10)
        title = self.font_title.render("Campaign Chronicles", True, C_TEXT)
        self.screen.blit(title, (50, 50))
        
        for i, camp in enumerate(self.campaign_list):
            y = 150 + (i * 60)
            color = (180, 220, 180) if camp['id'] == self.selected_campaign_id else (200, 190, 170)
            rect = pygame.Rect(50, y, 600, 50)
            pygame.draw.rect(self.screen, color, rect, border_radius=5)
            pygame.draw.rect(self.screen, C_TEXT, rect, 2, border_radius=5)
            
            name_txt = self.font_ui.render(camp['name'], True, C_TEXT)
            theme_txt = self.font_ui.render(f"Theme: {camp['properties'].get('theme','?').title()}", True, (100, 100, 100))
            self.screen.blit(name_txt, (70, y + 15))
            self.screen.blit(theme_txt, (450, y + 15))

        if self.mode == "SELECT":
            self.btn_new.draw(self.screen)
            self.btn_settings.draw(self.screen)
                
        elif self.mode == "CREATE":
            # Creation Panel (Right Side)
            pygame.draw.rect(self.screen, C_PANEL, (750, 100, 420, 400), border_radius=10)
            pygame.draw.rect(self.screen, (200, 50, 50), (750, 100, 420, 400), 3, border_radius=10)
            
            head = self.font_title.render("New World", True, C_TEXT)
            self.screen.blit(head, (780, 120))
            
            self.screen.blit(self.font_ui.render("Campaign Name:", True, C_TEXT), (800, 170))
            self.input_name.draw(self.screen)
            
            self.screen.blit(self.font_ui.render("Select Theme:", True, C_TEXT), (800, 270))
            
            # Validation Visual feedback
            is_valid = self.input_name.text.strip() != "" and self.dd_themes.selected_idx != -1
            self.btn_do_create.base_color = (100, 200, 100) if is_valid else (100, 100, 100)
            
            self.btn_do_create.draw(self.screen)
            self.btn_cancel.draw(self.screen)
            self.dd_themes.draw(self.screen)