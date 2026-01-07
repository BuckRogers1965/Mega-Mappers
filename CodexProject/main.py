import warnings
import os

# --- INSTRUMENTATION CONFIG ---
LOG_NONE  = 0
LOG_INFO  = 1 # Function Enter/Exit
LOG_DEBUG = 2 # Data Inspection
APP_VERBOSITY = LOG_DEBUG 

# 1. Quiet environment warnings immediately
warnings.filterwarnings("ignore", category=UserWarning, message=".*pkg_resources.*")
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

def log(level, message):
    if APP_VERBOSITY >= level:
        prefix = ""
        if level == LOG_INFO: prefix = "[APP INFO]"
        if level == LOG_DEBUG: prefix = "[APP DEBUG]"
        print(f"{prefix} {message}")

import sys
import json
import socket
import multiprocessing
import pygame
import qrcode

from codex_engine.core.db_manager import DBManager
from codex_engine.core.theme_manager import ThemeManager
from codex_engine.core.config_manager import ConfigManager
from codex_engine.core.ai_manager import AIManager
from codex_engine.ui.campaign_menu import CampaignMenu
from codex_engine.ui.map_viewer import MapViewer
from codex_engine.generators.world_gen import WorldGenerator
from codex_engine.generators.local_gen import LocalGenerator
from codex_engine.generators.tactical_gen import TacticalGenerator

# --- HARDWARE SUB-PROCESSES ---

def server_process(port, host):
    log(LOG_INFO, f"ENTER: server_process (Port: {port})")
    import uvicorn
    # Force path for imports
    current_dir = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, current_dir)
    
    try:
        from codex_server.main import app
        uvicorn.run(app, host=host, port=port, log_level="warning")
    except Exception as e:
        log(LOG_DEBUG, f"SERVER ERROR: {e}")
    log(LOG_INFO, "EXIT: server_process")

def player_window_process(image_queue):
    """Separate process for the player display window."""
    import pygame
    
    pygame.init()
    try:
        if pygame.display.get_num_displays() > 1:
            screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN | pygame.NOFRAME, display=1)
        else:
            raise pygame.error("Only one display detected.")
    except pygame.error as e:
        print(f"Player Window: Falling back to windowed mode. Reason: {e}")
        screen = pygame.display.set_mode((1280, 720), pygame.RESIZABLE)

    pygame.display.set_caption("Player View")
    screen.fill((0, 0, 0))
    pygame.display.flip()
    
    clock = pygame.time.Clock()
    running = True
    
    initial_image = None
    current_image_surface = None

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.VIDEORESIZE:
                screen = pygame.display.set_mode(event.size, pygame.RESIZABLE)
                if current_image_surface:
                    scaled_image = pygame.transform.smoothscale(current_image_surface, screen.get_size())
                    screen.blit(scaled_image, (0, 0))
                    pygame.display.flip()

        if not image_queue.empty():
            data = image_queue.get()
            
            if data == "QUIT":
                running = False
            elif data == "REVERT":
                if initial_image:
                    current_image_surface = initial_image
                    scaled_image = pygame.transform.smoothscale(initial_image, screen.get_size())
                    screen.blit(scaled_image, (0, 0))
                    pygame.display.flip()
            elif isinstance(data, tuple):
                image_string, size = data
                try:
                    new_image = pygame.image.fromstring(image_string, size, 'RGB')
                    if not initial_image:
                        initial_image = new_image
                    
                    current_image_surface = new_image
                    scaled_image = pygame.transform.smoothscale(new_image, screen.get_size())
                    screen.blit(scaled_image, (0, 0))
                    pygame.display.flip()
                except Exception as e:
                    print(f"Player Window Error: Failed to display surface: {e}")
        
        clock.tick(30)
    
    pygame.quit()
# --- MAIN APP ---

class CodexApp:
    def __init__(self):
        log(LOG_INFO, "ENTER: CodexApp.__init__")
        
        # 1. Connect to Rugged Registry
        log(LOG_DEBUG, "Initialising DBManager with Unified Node Registry...")
        self.db = DBManager("data/codex.db", verbosity=APP_VERBOSITY)
        
        # 2. BOOTSTRAP: Ensure tree is seeded from JSON if DB is new
        self._ensure_nodes_exist("config.json")

        # 3. DISCOVERY: Query the nodes for hardware configuration
        log(LOG_DEBUG, "Discovery phase: Fetching hardware config from registry...")
        srv = self.db.find_node('server_config')
        dsp = self.db.find_node('display_config')
        pvw = self.db.find_node('player_view_config')

        if not all([srv, dsp, pvw]):
            log(LOG_DEBUG, "FATAL: Discovery failed. One or more config nodes missing.")
            sys.exit(1)

        # 4. START HARDWARE PROCESSES
        s_p = srv['properties']
        log(LOG_DEBUG, f"Starting server process on {s_p['host']}:{s_p['port']}")
        self.server_proc = multiprocessing.Process(target=server_process, args=(s_p['port'], s_p['host']))
        self.server_proc.start()

        pygame.init()
        d_p = dsp['properties']
        log(LOG_DEBUG, f"Initializing Pygame window: {d_p['width']}x{d_p['height']}")
        self.screen = pygame.display.set_mode((d_p['width'], d_p['height']), pygame.RESIZABLE)
        pygame.display.set_caption(d_p.get('title', 'Codex'))
        self.clock = pygame.time.Clock()

        self.image_queue = multiprocessing.Queue()
        self.player_proc = multiprocessing.Process(target=player_window_process, args=(self.image_queue,))
        self.player_proc.start()

        # 5. INITIALIZE MANAGERS
        log(LOG_DEBUG, "Loading core engine managers...")
        self.config_mgr = ConfigManager(self.db)
        self.ai = AIManager(self.db, verbosity=APP_VERBOSITY)
        self.theme_mgr = ThemeManager()
        
        # 6. STATE & UI
        self.state = "MENU"
        self.current_campaign_id = None
        self.menu_screen = CampaignMenu(self.screen, self.db, self.config_mgr, self.ai, verbosity=APP_VERBOSITY)
        self.map_viewer = None

        # 7. GENERATE LOBBY
        log(LOG_DEBUG, "Calculating lobby screen with dynamic QR and IP...")
        pv_p = pvw['properties']
        lobby = self._generate_lobby_surface(
            pv_p['image'], 
            s_p['port'], 
            pv_p['qr_size'], 
            pv_p['margin']
        )
        self.update_player_image(lobby)
        
        log(LOG_INFO, "EXIT: CodexApp.__init__")

    def _ensure_nodes_exist(self, seed_file):
        log(LOG_INFO, f"ENTER: _ensure_nodes_exist (Seed: {seed_file})")
        if self.db.find_node('app_root'):
            log(LOG_DEBUG, "Discovery: app_root found. Seeding skipped.")
            log(LOG_INFO, "EXIT: _ensure_nodes_exist")
            return
        
        log(LOG_DEBUG, f"Discovery: app_root missing. Seeding hierarchy from {seed_file}...")
        try:
            with open(seed_file, 'r') as f:
                seed_data = json.load(f)
                self._build_node_recursive(seed_data['bootstrap'], None)
            log(LOG_DEBUG, "Bootstrap: Full recursive tree created.")
        except Exception as e:
            log(LOG_DEBUG, f"CRITICAL BOOTSTRAP FAILURE: {e}")
            sys.exit(1)
        log(LOG_INFO, "EXIT: _ensure_nodes_exist")

    def _build_node_recursive(self, node_data, parent_id):
        n_type = node_data.get('type')
        
        new_id = self.db.create_node(
            type=n_type,
            name=node_data.get('name', 'Unnamed Node'),
            parent_id=parent_id,
            properties=node_data.get('properties', {})
        )
        
        for child_blueprint in node_data.get('children', []):
            self._build_node_recursive(child_blueprint, new_id)

    def load_campaign(self, campaign_id, theme_id):
        log(LOG_INFO, f"ENTER: load_campaign (ID: {campaign_id}, Theme: {theme_id})")
        self.current_campaign_id = campaign_id
        self.theme_mgr.load_theme(theme_id)
        
        # Discovery: Locate world map node for this specific campaign
        log(LOG_DEBUG, f"Searching for world_map child of Campaign {campaign_id}...")
        maps = self.db.get_children(campaign_id, type_filter='world_map')
        
        if not maps:
            log(LOG_DEBUG, "Discovery: No map found. Triggering WorldGenerator...")
            self.display_loading_screen("Generating Fractal World...")
            gen = WorldGenerator(self.theme_mgr, self.db)
            world_node_id, _ = gen.generate_world_node(campaign_id)
            world_node = self.db.get_node(world_node_id)
        else:
            world_node = maps[0]
            log(LOG_DEBUG, f"Discovery: Found map ID {world_node['id']}")

        if not self.map_viewer:
            log(LOG_DEBUG, "Initialising MapViewer component...")
            self.map_viewer = MapViewer(self.screen, self.theme_mgr, self.ai, self.db)
        
        self.map_viewer.set_node(world_node)
        self.state = "GAME_WORLD"
        log(LOG_INFO, "EXIT: load_campaign (State -> GAME_WORLD)")

    def go_up_level(self):
        log(LOG_INFO, "ENTER: go_up_level")
        if not self.map_viewer or not self.map_viewer.current_node:
            self.state = "MENU"
            return

        current_node = self.map_viewer.current_node
        parent_id = current_node.get('parent_id')
        
        if not parent_id:
            log(LOG_DEBUG, "No parent ID found. Returning to Menu.")
            self.state = "MENU"
            return

        parent_node = self.db.get_node(parent_id)
        
        # --- FIX: Hierarchy Jump ---
        # If the parent is a POI (the marker), we skip it and go to the Map it sits on.
        # This prevents the UI from trying to "render" a marker node.
        if parent_node and parent_node['type'] == 'poi':
            log(LOG_DEBUG, f"Skipping POI node {parent_id} to reach the container Map.")
            parent_id = parent_node.get('parent_id')
            parent_node = self.db.get_node(parent_id)
        # ----------------------------

        # If the parent is a campaign level, we return to the main menu
        if not parent_node or parent_node['type'] in ['campaign', 'campaign_registry']:
            log(LOG_DEBUG, "Reached Registry level. Returning to Menu.")
            self.state = "MENU"
        else:
            # Check for source marker link to update portal (Back-linking)
            props = current_node.get('properties', {})
            meta = props.get('metadata', {})
            source_marker_id = meta.get('source_marker_id')
            
            if source_marker_id:
                marker_node = self.db.get_node(source_marker_id)
                if marker_node:
                    m_props = marker_node.get('properties', {})
                    m_meta = m_props.get('metadata', {})
                    if m_meta.get('portal_to') != current_node['id']:
                        log(LOG_DEBUG, "Updating back-link portal on source marker.")
                        m_meta['portal_to'] = current_node['id']
                        self.db.update_node(source_marker_id, properties={'metadata': m_meta})

            log(LOG_DEBUG, f"Navigating up to Parent Node ID {parent_id}")
            self.transition_to_node(parent_id)
            
        log(LOG_INFO, "EXIT: go_up_level")

    def transition_to_node(self, node_id):
        log(LOG_INFO, f"ENTER: transition_to_node ({node_id})")
        node = self.db.get_node(node_id)
        if node:
            if self.map_viewer: self.map_viewer.save_current_state()
            self.map_viewer.set_node(node)
        else:
            log(LOG_DEBUG, "Node not found.")
        log(LOG_INFO, "EXIT: transition_to_node")

    def _handle_game_input(self, event):

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.go_up_level()
                return

        if event.type == pygame.MOUSEWHEEL:
            if self.map_viewer:
                self.map_viewer.handle_zoom(event.y, pygame.mouse.get_pos())
            return 

        if self.map_viewer:
            result = self.map_viewer.handle_input(event)
            if result:
                if result.get("action") == "update_player_view":
                    self.render_and_update_player_view()
                    return

                if result.get("action") == "enter_marker":
                    marker = result['marker']
                    
                    '''
                    props = marker.get('properties', {})
                    if props.get('is_view_marker'):
                        print (f" *** *** props {props}")
                        new_state = not props.get('is_active', False)
                        log(LOG_INFO, f"App Logic: Toggling Party View -> {new_state}")
                        self.db.update_node(marker['id'], properties={'is_active': new_state})
                        
                        if new_state: self.render_and_update_player_view()
                        else:
                            print (f" *** *** Reverting") 
                            self.image_queue.put("REVERT")
                        return
                    '''

                    current_type = self.map_viewer.current_node['type']
                    if current_type == 'world_map':
                        self.enter_local_map(marker)
                    elif current_type == 'local_map':
                        self.enter_tactical_map(marker)
                    else: 
                        self.transition_tactical_map(marker)

                elif result.get("action") == "go_up_level":
                    self.go_up_level()
                elif result.get("action") == "reset_view":
                    self.reset_tactical_view()
                elif result.get("action") == "regenerate_tactical":
                    self.regenerate_tactical_map()
                elif result.get("action") == "transition_node":
                    self.transition_to_node(result['node_id'])

    def _handle_menu_input(self, event):
        res = self.menu_screen.handle_input(event)
        if res and res.get("action") == "load_campaign":
            log(LOG_DEBUG, f"Action: Loading campaign {res['id']}")
            self.load_campaign(res['id'], res['theme'])

    def enter_local_map(self, marker):
        current_node = self.map_viewer.current_node
        props = marker.get('properties', {})
        target_x = int(props.get('world_x', 0))
        target_y = int(props.get('world_y', 0))
        
        # Manual search for existing LOCAL MAP at coordinates (avoids picking up the marker itself)
        # World Map is parent of Local Map
        children = self.db.get_children(current_node['id'], type_filter='local_map')
        existing_node = None
        for child in children:
            cp = child.get('properties', {})
            if int(cp.get('world_x', -999)) == target_x and int(cp.get('world_y', -999)) == target_y:
                existing_node = child
                break
        
        if existing_node:
            # Self-heal: Link marker if missing
            meta = props.get('metadata', {})
            if 'portal_to' not in meta:
                meta['portal_to'] = existing_node['id']
                self.db.update_node(marker['id'], properties={'metadata': meta})
            
            self.transition_to_node(existing_node['id'])
        else:
            self.display_loading_screen()
            gen = LocalGenerator(self.db)
            campaign_id = current_node.get('parent_id')
            
            # Flatten for generator
            flat_marker = {'id': marker['id'], 'title': marker['name'], **props}
            new_id = gen.generate_local_map(current_node, flat_marker, campaign_id)
            
            if new_id: 
                # Link marker to new map
                meta = props.get('metadata', {})
                meta['portal_to'] = new_id
                self.db.update_node(marker['id'], properties={'metadata': meta})
                
                self.transition_to_node(new_id)

    def enter_tactical_map(self, marker):
        props = marker.get('properties', {})
        meta = props.get('metadata', {})
        portal_id = meta.get('portal_to')
        
        if portal_id:
            self.transition_to_node(portal_id)
            return

        self.display_loading_screen()
        gen = TacticalGenerator(self.db)
        
        # Traverse up: Local -> World -> Campaign
        world_node = self.db.get_node(self.map_viewer.current_node['parent_id'])
        campaign_id = world_node['parent_id'] if world_node else None
        
        flat_marker = {'id': marker['id'], 'title': marker['name'], **props}
        new_id = gen.generate_tactical_map(self.map_viewer.current_node, flat_marker, campaign_id)
        
        if new_id:
            meta['portal_to'] = new_id
            self.db.update_node(marker['id'], properties={'metadata': meta})
            self.transition_to_node(new_id)

    def transition_tactical_map(self, marker):
        log(LOG_INFO, f"ENTER: transition_tactical_map (Marker: {marker.get('name')})")
        props = marker.get('properties', {})
        
        # Portal link can be directly in properties or inside metadata for older markers
        portal_id = props.get('portal_to') or props.get('metadata', {}).get('portal_to')
        
        if portal_id:
            log(LOG_DEBUG, f"Found portal_to link: {portal_id}. Transitioning.")
            self.transition_to_node(portal_id)
        else:
            log(LOG_DEBUG, "No portal_to link found on marker. No transition.")

    def reset_tactical_view(self):
        if not self.map_viewer: return
        node = self.map_viewer.current_node
        geo = node.get('properties', {}).get('geometry_data', {})
        self.map_viewer.cam_x = geo.get('width', 30) / 2
        self.map_viewer.cam_y = geo.get('height', 30) / 2
        self.map_viewer.zoom = 1.0

    def regenerate_tactical_map(self):
        if not self.map_viewer: return
        current_node = self.map_viewer.current_node
        if current_node['type'] not in ['dungeon_level', 'building_interior', 'tactical_map']: return
        
        props = current_node.get('properties', {})
        meta = props.get('metadata', {})
        source_marker_id = meta.get('source_marker_id')
        parent_id = current_node['parent_id']
        
        if not source_marker_id:
            print("Cannot regenerate: Node is missing source marker link.")
            return
        
        # Delete current node (Cascade should handle children)
        self.db.delete_node(current_node['id'])
        
        # Unlink Source Marker
        source_marker = self.db.get_node(source_marker_id)
        if source_marker:
            m_props = source_marker.get('properties', {})
            m_meta = m_props.get('metadata', {})
            if 'portal_to' in m_meta:
                del m_meta['portal_to']
                self.db.update_node(source_marker['id'], properties={'metadata': m_meta})
            
            self.transition_to_node(parent_id)
        else:
            self.go_up_level()

    def _on_enter_marker(self, marker_node):
        """Logic for entering a marker: check for portal or generate new map."""
        log(LOG_INFO, "ENTER: _on_enter_marker")
        
        props = marker_node.get('properties', {})
        meta = props.get('metadata', {})
        
        # 1. Check existing link
        if 'portal_to' in meta:
            target_id = meta['portal_to']
            log(LOG_DEBUG, f"Marker has portal_to: {target_id}")
            target_node = self.db.get_node(target_id)
            if target_node:
                self.transition_to_node(target_id)
                return

        # 2. Prepare Flattened Marker for Generators
        flat_marker = {'id': marker_node['id'], 'name': marker_node['name'], 'title': marker_node['name']}
        flat_marker.update(props)

        current_node = self.map_viewer.current_node
        new_node_id = None
        
        # 3. Contextual Logic
        if current_node['type'] == 'world_map':
            # Check if local map exists at these coords (unlinked)
            existing = self.db.get_node_by_coords(current_node['parent_id'], current_node['id'], flat_marker.get('world_x'), flat_marker.get('world_y'))
            if existing:
                log(LOG_DEBUG, "Found existing local map by coords.")
                self.transition_to_node(existing['id'])
                return

            log(LOG_INFO, "Generating NEW Local Map...")
            self.display_loading_screen(f"Generating {flat_marker['title']}...")
            
            gen = LocalGenerator(self.db)
            campaign_id = current_node['parent_id']
            new_node_id = gen.generate_local_map(current_node, flat_marker, campaign_id)

        elif current_node['type'] == 'local_map':
            log(LOG_INFO, "Generating NEW Tactical Map...")
            self.display_loading_screen(f"Entering {flat_marker['title']}...")
            
            gen = TacticalGenerator(self.db)
            # Find Campaign ID: Local -> World -> Campaign
            world_node = self.db.get_parent(current_node['id'])
            campaign_id = world_node['parent_id'] if world_node else None
            
            if campaign_id:
                new_node_id = gen.generate_tactical_map(current_node, flat_marker, campaign_id)
                
                # Link it
                if new_node_id:
                    meta['portal_to'] = new_node_id
                    self.db.update_node(marker_node['id'], properties={'metadata': meta})
            else:
                log(LOG_DEBUG, "Error: Could not resolve Campaign ID.")

        # 4. Transition
        if new_node_id:
            self.transition_to_node(new_node_id)
        else:
            log(LOG_DEBUG, "No transition occurred (Generation skipped or failed).")
        
        log(LOG_INFO, "EXIT: _on_enter_marker")

    def render_and_update_player_view(self):
        log(LOG_INFO, "ENTER: render_and_update_player_view")
        if self.map_viewer and self.map_viewer.controller:
            # The controller returns None if no active view marker is found
            player_surface = self.map_viewer.controller.render_player_view_surface()
            
            if player_surface:
                log(LOG_DEBUG, "Shipping updated player view to display.")
                self.update_player_image(player_surface)
            else:
                # --- FIX: Explicitly revert if the view is disabled ---
                log(LOG_DEBUG, "No active view found. Reverting player display to standby.")
                self.image_queue.put("REVERT")

    def display_loading_screen(self, msg="Processing..."):
        log(LOG_INFO, f"ENTER: display_loading_screen (Msg: {msg})")
        self.screen.fill((20, 20, 30))
        txt = pygame.font.Font(None, 48).render(msg, True, (200, 200, 200))
        self.screen.blit(txt, txt.get_rect(center=self.screen.get_rect().center))
        pygame.display.flip()
        log(LOG_INFO, "EXIT: display_loading_screen")

    def _generate_lobby_surface(self, bg_path, port, qr_size, margin):
        log(LOG_INFO, "ENTER: _generate_lobby_surface")
        # 1. Resolve local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(('10.255.255.255', 1))
            ip = s.getsockname()[0]
        except: ip = '127.0.0.1'
        finally: s.close()
        url = f"http={ip}:{port}"
        log(LOG_DEBUG, f"Lobby URL: {url}")

        # 2. Load Artwork
        try: 
            surface = pygame.image.load(bg_path).convert()
            log(LOG_DEBUG, f"Loaded artwork from {bg_path}")
        except Exception as e:
            log(LOG_DEBUG, f"Artwork missing ({e}). Using safety background.")
            surface = pygame.Surface((1920, 1080))
            surface.fill((20, 20, 30))

        # 3. Compositing
        qr_pil = qrcode.make(url).convert('RGB').resize((qr_size, qr_size))
        qr_surf = pygame.image.frombytes(qr_pil.tobytes(), (qr_size, qr_size), 'RGB')
        surface.blit(qr_surf, (margin, margin))

        font = pygame.font.SysFont("arial", 48, bold=True)
        text = font.render(f"Join: {url}", True, (255, 255, 255))
        surface.blit(text, (surface.get_width()//2 - text.get_width()//2, 
                           surface.get_height() - text.get_height() - margin))
        
        log(LOG_INFO, "EXIT: _generate_lobby_surface")
        return surface

    def update_player_image(self, surface):
        if not self.player_proc.is_alive(): 
            return
        img_str = pygame.image.tobytes(surface, 'RGB')
        self.image_queue.put((img_str, surface.get_size()))

    def run(self):
        log(LOG_INFO, "ENTER: CodexApp.run (Starting Main Loop)")
        running = True
        while running:
            # Process AI callbacks if any (Future async support)
            if hasattr(self.ai, 'get_completed_callbacks'):
                for cb, res in self.ai.get_completed_callbacks():
                    if cb: cb(res)

            for event in pygame.event.get():
                if event.type == pygame.QUIT: running = False
                if event.type == pygame.VIDEORESIZE:
                    self.screen = pygame.display.set_mode(event.size, pygame.RESIZABLE)

                if self.state == "MENU": self._handle_menu_input(event)
                elif self.state == "GAME_WORLD": self._handle_game_input(event)

            if self.state == "MENU": self.menu_screen.draw()
            elif self.state == "GAME_WORLD" and self.map_viewer: self.map_viewer.draw()
            
            pygame.display.flip()
            self.clock.tick(60)

        # Cleanup Phase
        log(LOG_DEBUG, "App shutdown initiated. Saving state...")
        if self.map_viewer: self.map_viewer.save_current_state()
        self.image_queue.put("QUIT")
        self.player_proc.join(timeout=1)
        self.server_proc.terminate()
        pygame.quit()
        log(LOG_INFO, "EXIT: CodexApp.run (Application Terminated)")

if __name__ == "__main__":
    if sys.platform == 'darwin' or sys.platform == 'win32':
        multiprocessing.set_start_method('spawn', force=True)
    app = CodexApp()
    app.run()
