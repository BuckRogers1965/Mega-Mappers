import sys
import warnings
import os

# Filter out the Pygame 'pkg_resources' deprecation warning.
# This is an internal Pygame issue, but we suppress it to keep our console clean.
warnings.filterwarnings("ignore", category=UserWarning, message=".*pkg_resources.*")
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
import pygame

# Configuration
from codex_engine.config import SCREEN_WIDTH, SCREEN_HEIGHT

# Core Systems
from codex_engine.core.db_manager import DBManager
from codex_engine.core.theme_manager import ThemeManager

# UI & Rendering
from codex_engine.ui.campaign_menu import CampaignMenu
from codex_engine.ui.map_viewer import MapViewer

# Generators
from codex_engine.generators.world_gen import WorldGenerator

class CodexApp:
    def __init__(self):
        # 1. Low-Level Initialization
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("The Codex Engine - Alpha")
        self.clock = pygame.time.Clock()
        
        # 2. Data Subsystems
        self.db = DBManager()
        self.theme_manager = ThemeManager()
        
        # 3. Application State
        self.state = "MENU" # States: MENU, GAME_WORLD, LOADING
        self.current_campaign = None
        
        # 4. View Controllers
        self.menu_screen = CampaignMenu(self.screen, self.db)
        self.map_viewer = None # Initialized only when a campaign is loaded

    def run(self):
        """The Main Application Loop"""
        running = True
        
        while running:
            # --- EVENT HANDLING ---
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                
                # Route events based on current state
                if self.state == "MENU":
                    self._handle_menu_input(event)
                elif self.state == "GAME_WORLD":
                    self._handle_game_input(event)

            # --- RENDERING ---
            if self.state == "MENU":
                self.menu_screen.draw()
            
            elif self.state == "GAME_WORLD":
                if self.map_viewer:
                    self.map_viewer.draw()
                
            # Update Display
            pygame.display.flip()
            self.clock.tick(60)

        # Cleanup
        pygame.quit()
        sys.exit()

    def _handle_menu_input(self, event):
        """Delegates input to the Menu Controller"""
        result = self.menu_screen.handle_input(event)
        
        # Did the menu ask us to do something?
        if result and result.get("action") == "load_campaign":
            self.load_campaign(result["id"], result["theme"])

    def _handle_game_input(self, event):
        """Delegates input to the Map Viewer"""
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                print("Returning to Menu...")
                self.state = "MENU"
                self.current_campaign = None
                self.menu_screen.refresh_list() # Refresh in case save data changed
                return

        # Pass event to the universal map viewer (Handling Panning/Zooming/Clicking)
        if self.map_viewer:
            self.map_viewer.handle_input(event)

    def load_campaign(self, campaign_id, theme_id):
        """
        The Logic Core:
        1. Loads Campaign Data
        2. Sets the Theme
        3. Checks for existing World Map (Persistence)
        4. If missing, triggers procedural generation (AI + Math)
        5. Switches View
        """
        print(f"--- Loading Campaign ID: {campaign_id} ---")
        
        # 1. Setup Data
        self.current_campaign = self.db.get_campaign(campaign_id)
        self.theme_manager.load_theme(theme_id)
        
        # 2. Initialize the Universal Map Viewer
        # We create a new instance so it picks up the correct Theme colors
        self.map_viewer = MapViewer(self.screen, self.theme_manager)
        
        # 3. 'Schrödinger's Map' Logic
        # Try to find the root node (World Map) at coordinates 0,0 with no parent
        world_node = self.db.get_node_by_coords(campaign_id, parent_id=None, x=0, y=0)
        
        if not world_node:
            self.display_loading_screen()
            
            # GENERATION STEP
            print("No world map found. Initializing World Generator...")
            generator = WorldGenerator(self.theme_manager, self.db)
            
            # This function runs Noise + AI and saves to DB
            generator.generate_world_node(campaign_id)
            
            # Fetch the newly created node
            world_node = self.db.get_node_by_coords(campaign_id, parent_id=None, x=0, y=0)

        # 4. Inject Data into Viewer
        if world_node:
            print(f"Loaded Node: {world_node.get('name')}")
            self.map_viewer.set_node(world_node)
            self.state = "GAME_WORLD"
        else:
            print("CRITICAL ERROR: Failed to load or generate world node.")
            self.state = "MENU"

    def display_loading_screen(self):
        """Forces a render pass to show loading text before the heavy generation blocks the thread."""
        self.screen.fill((20, 20, 30))
        
        font = pygame.font.Font(None, 48)
        text = font.render("Constructing World...", True, (200, 200, 200))
        subtext = pygame.font.Font(None, 24).render("Consulting AI Oracle & Calculating Terrain...", True, (150, 150, 150))
        
        rect = text.get_rect(center=(SCREEN_WIDTH//2, SCREEN_HEIGHT//2 - 20))
        sub_rect = subtext.get_rect(center=(SCREEN_WIDTH//2, SCREEN_HEIGHT//2 + 30))
        
        self.screen.blit(text, rect)
        self.screen.blit(subtext, sub_rect)
        pygame.display.flip()

if __name__ == "__main__":
    app = CodexApp()
    app.run()
