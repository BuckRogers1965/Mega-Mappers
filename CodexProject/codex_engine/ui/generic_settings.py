import pygame
from codex_engine.ui.widgets import Button, InputBox, Dropdown, UIScrollPanel
from codex_engine.config import SCREEN_WIDTH, SCREEN_HEIGHT

OPENAI_TEMPLATES = {
    # Local / self-hosted
    "ollama": {
        "name": "Ollama (Local)",
        "key_var": "",
        "url": "http://localhost:11434/v1",
    },
    "openai": {
        "name": "OpenAI",
        "key_var": "OPENAI_API_KEY",
        "url": "https://api.openai.com/v1",
    },
    "groq": {
        "name": "Groq",
        "key_var": "GROQ_API_KEY",
        "url": "https://api.groq.com/openai/v1",
    },
    "lmstudio": {
        "name": "LM Studio (Local)",
        "key_var": "",
        "url": "http://localhost:1234/v1",
    },
    "vllm": {
        "name": "vLLM (Local)",
        "key_var": "",
        "url": "http://localhost:8000/v1",
    },

    # First-party

    "azure_openai": {
        "name": "Azure OpenAI",
        "key_var": "AZURE_OPENAI_API_KEY",
        "url": "https://{RESOURCE_NAME}.openai.azure.com/openai/deployments/{DEPLOYMENT_NAME}",
    },

    # Major aggregators
    "openrouter": {
        "name": "OpenRouter",
        "key_var": "OPENROUTER_API_KEY",
        "url": "https://openrouter.ai/api/v1",
    },
    "together": {
        "name": "Together.ai",
        "key_var": "TOGETHER_API_KEY",
        "url": "https://api.together.xyz/v1",
    },
    "anyscale": {
        "name": "Anyscale",
        "key_var": "ANYSCALE_API_KEY",
        "url": "https://api.endpoints.anyscale.com/v1",
    },
    "fireworks": {
        "name": "Fireworks.ai",
        "key_var": "FIREWORKS_API_KEY",
        "url": "https://api.fireworks.ai/inference/v1",
    },
    "deepinfra": {
        "name": "DeepInfra",
        "key_var": "DEEPINFRA_API_KEY",
        "url": "https://api.deepinfra.com/v1/openai",
    },

    # High-performance inference providers
 
    "cerebras": {
        "name": "Cerebras",
        "key_var": "CEREBRAS_API_KEY",
        "url": "https://api.cerebras.ai/v1",
    },
    "sambanova": {
        "name": "SambaNova",
        "key_var": "SAMBANOVA_API_KEY",
        "url": "https://api.sambanova.ai/v1",
    },
    "nvidia_nim": {
        "name": "NVIDIA NIM",
        "key_var": "NVIDIA_API_KEY",
        "url": "https://integrate.api.nvidia.com/v1",
    },

    # Model vendors with OpenAI-compatible endpoints
    "mistral": {
        "name": "Mistral",
        "key_var": "MISTRAL_API_KEY",
        "url": "https://api.mistral.ai/v1",
    },
    "perplexity": {
        "name": "Perplexity",
        "key_var": "PERPLEXITY_API_KEY",
        "url": "https://api.perplexity.ai/v1",
    },
}

class GenericSettingsEditor:
    def __init__(self, screen, config_manager, ai_manager, context_chain=None):
        self.screen = screen
        self.config = config_manager
        self.ai = ai_manager
        self.context_chain = context_chain or [] 
        self.is_global = (len(self.context_chain) == 0)
        
        if self.is_global:
            self.save_scope, self.save_id = "global", None
        else:
            self.save_scope, self.save_id = self.context_chain[0]

        self.font = pygame.font.Font(None, 24)
        self.font_bold = pygame.font.Font(None, 28)
        self.title_font = pygame.font.Font(None, 36)
        
        # Main Window Rect
        self.w, self.h = 900, 700
        self.rect = pygame.Rect(0, 0, self.w, self.h)
        self.rect.center = (SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)
        
        # State
        self.running = True
        self.widgets = [] # List of widget instances for event handling
        self.scroll_panel = None
        
        # Temp storage for "New Service" inputs
        self.new_svc_name = InputBox(0, 0, 200, 30, self.font, text="")
        #self.new_svc_name = InputBox(0,0,200,30, self.font, "New Service Name")
        self.new_svc_driver = Dropdown(0,0,180,90, self.font, [
            {'id': 'openai_compatible', 'name': 'OpenAI / Groq / Ollama'},
            {'id': 'gemini', 'name': 'Google Gemini'},
            {'test': 'other', 'name': ''}
        ])

        template_opts = [{'id': k, 'name': v['name']} for k, v in OPENAI_TEMPLATES.items()]
        self.dd_template = Dropdown(0, 0, 180, 30, self.font, template_opts)
        
        self._rebuild_ui()
        self.run()

    def _apply_template_to_service(self, service_id, template_key):
        """Finds a template and updates the config for the given service ID."""
        template = OPENAI_TEMPLATES.get(template_key)
        if not template: return

        print(f"Applying template '{template_key}' to service '{service_id}'")
        
        # Update the config keys for this specific service
        self.config.set(f"service_{service_id}_key_var", template.get("key_var", ""), "global")
        self.config.set(f"service_{service_id}_url", template.get("url", ""), "global")

    def _rebuild_ui(self):
        self.widgets = []
        
        if self.is_global:
            self._build_global_ui()
        else:
            self._build_local_ui()
            
        # Add common Close/Save buttons (outside scroll area)
        self.btn_save = Button(self.rect.right - 120, self.rect.bottom - 50, 100, 40, "Done", self.font, (50,150,50), (80,180,80), (255,255,255), self._save_and_close)
        self.widgets.append(self.btn_save)

    def _build_global_ui(self):
        registry = self.ai.get_service_registry()
        
        # Calculate height needed: Header + (Rows * Height) + Footer
        row_h = 160
        total_h = 100 + (len(registry) * row_h) + 100 
        
        # Create Scroll Panel inside the main rect (padding for title/buttons)
        panel_rect = pygame.Rect(self.rect.x + 20, self.rect.y + 70, self.rect.width - 40, self.rect.height - 130)
        self.scroll_panel = UIScrollPanel(panel_rect.x, panel_rect.y, panel_rect.width, panel_rect.height, total_h)
        
        # --- DRAW ONTO SCROLL SURFACE ---
        surf = self.scroll_panel.surface
        
        # Storage for labels to redraw each frame
        self.labels = []
        
        # 1. "Add Service" Section at top
        y = 10
        
        self.labels.append(("Add New AI Service:", (10, y + 5), (200, 200, 200)))
        self.labels.append(("Name:", (200, y + 8), (180, 180, 180)))
        
        self.new_svc_name.rect.topleft = (260, y)
        self.new_svc_driver.rect.topleft = (470, y)
        
        btn_add = Button(700, y, 80, 30, "Add", self.font, (60, 60, 80), (80, 80, 100), (255,255,255), self._add_service_action)
        
        self.widgets.extend([self.new_svc_name, self.new_svc_driver, btn_add])
        
        y += 60
        
        # 2. Render Existing Services
        for svc in registry:
            if not svc or not isinstance(svc, dict) or 'id' not in svc:
                continue

            sid = svc['id']
            
            # Box Background - store for redraw
            self.labels.append(("BOX", (10, y, self.scroll_panel.rect.width - 40, 140), (30, 30, 35)))
            
            # Header: Name & Type
            self.labels.append((f"{svc['name']} ({svc['driver']})", (25, y+15), (255, 200, 100)))
            
            # Delete Button
            btn_del = Button(self.scroll_panel.rect.width - 100, y+10, 60, 25, "Delete", self.font, (100,0,0), (150,0,0), (255,255,255), lambda s=sid: self._del_service_action(s))
            btn_del.rect.y = y + 10 
            self.widgets.append(btn_del)
            
            # Config Fields
            field_y = y + 50
            
            # Key Var
            self.labels.append(("Env Key:", (25, field_y+8), (150,150,150)))
            val_k = self.config.get(f"service_{sid}_key_var")
            inp_k = InputBox(100, field_y, 250, 30, self.font, str(val_k or ""))
            inp_k.config_key = f"service_{sid}_key_var"
            self.widgets.append(inp_k)
            
            # Base URL (only if supported)
            if svc['driver'] == 'openai_compatible':
                self.labels.append(("URL:", (370, field_y+8), (150,150,150)))
                val_u = self.config.get(f"service_{sid}_url")
                inp_u = InputBox(420, field_y, 250, 30, self.font, str(val_u or ""))
                inp_u.config_key = f"service_{sid}_url"
                self.widgets.append(inp_u)
            
            if svc['driver'] == 'openai_compatible':
                template_y = y + 100 # Position at the bottom of the card
                self.labels.append(("Apply Template:", (460, template_y+4), (180, 180, 180)))
                
                template_opts = [{'id': k, 'name': v['name']} for k, v in OPENAI_TEMPLATES.items()]
                dd_t = Dropdown(600, template_y, 200, 30, self.font, template_opts)
                # Tag it so we know which service it belongs to
                dd_t.service_id_tag = sid 
                dd_t.is_template_selector = True # Custom flag for event handling
                self.widgets.append(dd_t)
            
            # Default Model
            model_y = field_y + 40
            self.labels.append(("Def. Model:", (25, model_y+8), (150,150,150)))
            
            # Fetch Button
            btn_fetch = Button(110, model_y, 60, 30, "Fetch", self.font, (60,60,80), (80,80,100), (255,255,255), lambda s=sid: self._fetch_models_action(s))
            btn_fetch.rect.y = model_y
            self.widgets.append(btn_fetch)
            
            # Model Dropdown
            val_m = self.config.get(f"service_{sid}_model")
            dd_m = Dropdown(180, model_y, 250, 30, self.font, [{'id': val_m, 'name': str(val_m)}], initial_id=val_m)
            dd_m.config_key = f"service_{sid}_model"
            dd_m.service_id_tag = sid 
            self.widgets.append(dd_m)

            y += row_h

    def _build_local_ui(self):
        self.labels = []
        
        # Override Mode: Simple Dropdown
        y = self.rect.y + 100
        
        # 1. Select Active Service
        reg = self.ai.get_service_registry()
        opts = [{'id': 'inherit', 'name': 'Inherit (Default)'}] + \
            [{'id': s['id'], 'name': s['name']} for s in reg]
        
        curr = self.config.get("active_service_id", self.context_chain) or 'inherit'
        
        self.labels.append(("Active Service Override:", (self.rect.x + 50, y), (200,200,200)))
        
        dd_svc = Dropdown(self.rect.x + 250, y-5, 300, 30, self.font, opts, initial_id=curr)
        dd_svc.config_key = "active_service_id"
        self.widgets.append(dd_svc)
        # 2. Select Model Override (Dynamic based on selected service)
        # ... (Similar logic to previous implementation, fetch based on selected service ID)

    def _add_service_action(self):
        name = self.new_svc_name.text
        drv = self.new_svc_driver.get_selected_id()
        
        if name and name.strip() and drv:
            service_id = self.ai.add_service(name, drv)
            
            # --- SIMPLIFIED: Just set Gemini key if needed ---
            if drv == 'gemini':
                self.config.set(f"service_{service_id}_key_var", "GEMINI_API_KEY", "global")
            
            self.new_svc_name.text = "" 
            self._rebuild_ui()
        else:
            print("[UI] Add Failed: Name cannot be empty.")

    def _del_service_action(self, sid):
        print(f"[DEBUG] DELETE called for service ID: {sid}")
        self.ai.delete_service(sid)
        print(f"[DEBUG] DELETE completed, rebuilding UI...")
        self._rebuild_ui()

    def _fetch_models_action(self, sid):
        # 1. Save current inputs for this service to DB so AI manager can read them
        for w in self.widgets:
            if hasattr(w, 'config_key') and w.config_key.startswith(f"service_{sid}"):
                val = w.text if isinstance(w, InputBox) else w.get_selected_id()
                self.config.set(w.config_key, val, "global") # Always global in this view
        
        # 2. Fetch
        models = self.ai.get_available_models_for_service(sid)
        
        # 3. Update the specific dropdown
        for w in self.widgets:
            if isinstance(w, Dropdown) and getattr(w, 'service_id_tag', None) == sid:
                w.options = [{'id': m, 'name': m} for m in models]
                if w.options: w.selected_idx = 0

    def _save_and_close(self):
        # Save all widgets with config_key
        for w in self.widgets:
            if hasattr(w, 'config_key'):
                val = w.text if isinstance(w, InputBox) else w.get_selected_id()
                if val == 'inherit': val = None
                self.config.set(w.config_key, val, self.save_scope, self.save_id)
        self.running = False

    def _autofill_from_template(self, event):
        """Called when the 'Add New Service' driver dropdown changes."""
        driver = self.new_svc_driver.get_selected_id()
 
    def run(self):
        clock = pygame.time.Clock()
        while self.running:
            events = pygame.event.get()
            for e in events:
                if e.type == pygame.QUIT: 
                    self.running = False
                
                # Handle Scroll Panel
                if self.scroll_panel and self.scroll_panel.handle_event(e):
                    continue
                
                # Handle Widgets - ONLY EVENT HANDLING, NO DRAWING
                # Handle Widgets - ONLY EVENT HANDLING, NO DRAWING
                if self.scroll_panel:
                    if e.type in [pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP, pygame.MOUSEMOTION]:
                        if self.scroll_panel.rect.collidepoint(e.pos):
                            adj_pos = (e.pos[0] - self.scroll_panel.rect.x, 
                                    e.pos[1] - self.scroll_panel.rect.y + self.scroll_panel.scroll_y)
                            e.pos = adj_pos
                            
                            # Check for template dropdown changes FIRST
                            template_changed = False
                            for w in self.widgets:
                                if isinstance(w, Dropdown) and getattr(w, 'is_template_selector', False):
                                    old_selection = w.get_selected_id()
                                    if w.handle_event(e):
                                        new_selection = w.get_selected_id()
                                        if old_selection != new_selection and new_selection != 'none':
                                            service_id = w.service_id_tag
                                            self._apply_template_to_service(service_id, new_selection)
                                            self._rebuild_ui()
                                            template_changed = True
                                            break
                            
                            if not template_changed:
                                # Handle all other widgets
                                for w in self.widgets:
                                    if w not in [self.btn_save]: 
                                        if not (isinstance(w, Dropdown) and getattr(w, 'is_template_selector', False)):
                                            w.handle_event(e)
                            
                            e.pos = (e.pos[0] + self.scroll_panel.rect.x, 
                                    e.pos[1] + self.scroll_panel.rect.y - self.scroll_panel.scroll_y)
                        else:
                            self.btn_save.handle_event(e)
                    elif e.type == pygame.KEYDOWN:
                        for w in self.widgets:
                            if w not in [self.btn_save]:
                                w.handle_event(e)
                else:
                    for w in self.widgets:
                        w.handle_event(e)

            # Draw - HAPPENS ONCE PER FRAME AFTER ALL EVENTS
            self.screen.fill((0,0,0))
            overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            overlay.fill((0,0,0,180))
            self.screen.blit(overlay, (0,0))
            
            # Main Box
            pygame.draw.rect(self.screen, (40, 40, 50), self.rect, border_radius=10)
            pygame.draw.rect(self.screen, (100, 100, 120), self.rect, 2, border_radius=10)
            
            ts = self.title_font.render("AI Settings Manager", True, (255,255,255))
            self.screen.blit(ts, (self.rect.x + 20, self.rect.y + 20))

            if self.scroll_panel:
                self.scroll_panel.draw_background()
                surf = self.scroll_panel.surface
                
                # Draw all stored labels
                for label_data in self.labels:
                    if label_data[0] == "BOX":
                        _, (x, y, w, h), color = label_data
                        pygame.draw.rect(surf, color, (x, y, w, h), border_radius=5)
                        pygame.draw.rect(surf, (60, 60, 70), (x, y, w, h), 1, border_radius=5)
                    else:
                        text, pos, color = label_data
                        lbl = self.font.render(text, True, color)
                        surf.blit(lbl, pos)
                
                # Draw widgets
                for w in self.widgets:
                    if w not in [self.btn_save]:
                        w.draw(surf)
                
                self.scroll_panel.draw_to_screen(self.screen)
            else:
                # Draw labels for local mode
                for label_data in self.labels:
                    text, pos, color = label_data
                    lbl = self.font.render(text, True, color)
                    self.screen.blit(lbl, pos)
                
                for w in self.widgets: 
                    w.draw(self.screen)
            
            self.btn_save.draw(self.screen)
            
            pygame.display.flip()
            clock.tick(30)
