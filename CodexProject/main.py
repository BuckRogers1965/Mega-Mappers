import sys
import warnings
import os

# Filter out the Pygame 'pkg_resources' deprecation warning.
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
from codex_engine.generators.local_gen import LocalGenerator
from codex_engine.generators.tactical_gen import TacticalGenerator

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
        if self.map_viewer: self.map_viewer.save_current_state()
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
                if self.map_viewer and self.map_viewer.current_node.get('parent_node_id'):
                    self.go_up_level()
                else:
                    if self.map_viewer: self.map_viewer.save_current_state()
                    print("Returning to Menu...")
                    self.state = "MENU"
                    self.current_campaign = None
                    self.menu_screen.refresh_list()
                return

        if self.map_viewer:
            result = self.map_viewer.handle_input(event)
            
            if result:
                if result.get("action") == "enter_marker":
                    self.enter_local_map(result['marker'])
                elif result.get("action") == "go_up_level":
                    self.go_up_level()
                elif result.get("action") == "reset_view":
                    self.reset_tactical_view()
                elif result.get("action") == "regenerate_tactical":
                    self.regenerate_tactical_map()
                elif result.get("action") == "click_zoom":
                    self.map_viewer.zoom = min(10.0, self.map_viewer.zoom * 2.0)


    def go_up_level(self):
        if not self.map_viewer or not self.map_viewer.current_node.get('parent_node_id'):
            return

        parent_id = self.map_viewer.current_node['parent_node_id']
        parent_node = self.db.get_node(parent_id)
        
        if parent_node:
            self.map_viewer.save_current_state()
            self.map_viewer.set_node(parent_node)
        else:
            print(f"CRITICAL ERROR: Parent Node {parent_id} not found.")

    def enter_local_map(self, marker):
        print(f"--- Transition Request: {marker['title']} ---")
        current_node = self.map_viewer.current_node
        target_x = int(marker['world_x'])
        target_y = int(marker['world_y'])

        # Case 1: World -> Local
        if current_node['type'] == 'world_map':
            existing_node = self.db.get_node_by_coords(self.current_campaign['id'], parent_id=current_node['id'], x=target_x, y=target_y)
            if existing_node:
                self.map_viewer.save_current_state()
                self.map_viewer.set_node(existing_node)
            else:
                self.display_loading_screen()
                gen = LocalGenerator(self.db)
                gen.generate_local_map(current_node, marker, self.current_campaign['id'])
                new_node = self.db.get_node_by_coords(self.current_campaign['id'], current_node['id'], target_x, target_y)
                self.map_viewer.save_current_state()
                self.map_viewer.set_node(new_node)

        # Case 2: Local -> Tactical
        elif current_node['type'] == 'local_map':
            existing_node = self.db.get_node_by_coords(self.current_campaign['id'], parent_id=current_node['id'], x=target_x, y=target_y)
            if existing_node:
                self.map_viewer.save_current_state()
                self.map_viewer.set_node(existing_node)
            else:
                self.display_loading_screen()
                gen = TacticalGenerator(self.db)
                new_id = gen.generate_tactical_map(current_node, marker, self.current_campaign['id'])
                new_node = self.db.get_node(new_id)
                self.map_viewer.save_current_state()
                self.map_viewer.set_node(new_node)
                
    def reset_tactical_view(self):
        if not self.map_viewer: return
        node = self.map_viewer.current_node
        geo = node.get('geometry_data', {})
        self.map_viewer.cam_x = geo.get('width', 30) / 2
        self.map_viewer.cam_y = geo.get('height', 30) / 2
        self.map_viewer.zoom = 1.0

    def regenerate_tactical_map(self):
        if not self.map_viewer or self.map_viewer.current_node['type'] not in ['dungeon_level', 'building_interior']:
            return
        
        # This is a destructive operation. We delete the current node and remake it.
        # 1. Get parent and marker info
        current_node = self.map_viewer.current_node
        parent_node = self.db.get_node(current_node['parent_node_id'])
        
        # Find the marker that created this node
        markers_on_parent = self.db.get_markers(parent_node['id'])
        source_marker = None
        for m in markers_on_parent:
            if int(m['world_x']) == current_node['grid_x'] and int(m['world_y']) == current_node['grid_y']:
                source_marker = m
                break
        
        if not source_marker:
            print("Error: Could not find source marker to regenerate from.")
            return

        # 2. Delete current node and its children (markers)
        self.db.delete_node_and_children(current_node['id'])

        # 3. Regenerate and transition
        self.enter_local_map(source_marker)

    def load_campaign(self, campaign_id, theme_id):
        print(f"--- Loading Campaign ID: {campaign_id} ---")
        self.current_campaign = self.db.get_campaign(campaign_id)
        self.theme_manager.load_theme(theme_id)
        
        if not self.map_viewer:
            self.map_viewer = MapViewer(self.screen, self.theme_manager)
        
        world_node = self.db.get_node_by_coords(campaign_id, parent_id=None, x=0, y=0)
        
        if not world_node:
            self.display_loading_screen()
            generator = WorldGenerator(self.theme_manager, self.db)
            generator.generate_world_node(campaign_id)
            world_node = self.db.get_node_by_coords(campaign_id, parent_id=None, x=0, y=0)

        if world_node:
            print(f"Loaded Node: {world_node.get('name')}")
            self.map_viewer.set_node(world_node)
            self.state = "GAME_WORLD"
        else:
            print("CRITICAL ERROR: Failed to load or generate world node.")
            self.state = "MENU"

    def display_loading_screen(self):
        self.screen.fill((20, 20, 30))
        font = pygame.font.Font(None, 48)
        text = font.render("Generating...", True, (200, 200, 200))
        rect = text.get_rect(center=(SCREEN_WIDTH//2, SCREEN_HEIGHT//2))
        self.screen.blit(text, rect)
        pygame.display.flip()

if __name__ == "__main__":
    app = CodexApp()
    app.run()
