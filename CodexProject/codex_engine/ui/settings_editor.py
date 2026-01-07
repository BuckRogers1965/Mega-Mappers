import pygame
from codex_engine.ui.widgets import Button, InputBox, Dropdown

# --- INSTRUMENTATION CONSTANTS ---
LOG_NONE  = 0
LOG_INFO  = 1
LOG_DEBUG = 2

OPENAI_TEMPLATES = {
    "ollama": {"name": "Ollama (Local)", "key_var": "", "url": "http://localhost:11434/v1"},
    "openai": {"name": "OpenAI", "key_var": "OPENAI_API_KEY", "url": "https://api.openai.com/v1"},
    "groq": {"name": "Groq", "key_var": "GROQ_API_KEY", "url": "https://api.groq.com/openai/v1"},
    "openrouter": {"name": "OpenRouter", "key_var": "OPENROUTER_API_KEY", "url": "https://openrouter.ai/api/v1"},
    "mistral": {"name": "Mistral", "key_var": "MISTRAL_API_KEY", "url": "https://api.mistral.ai/v1"},
}

class UnifiedSettingsEditor:
    def __init__(self, screen, db, root_node_id, ai_manager, verbosity=LOG_NONE):
        self.verbosity = verbosity
        self._log(LOG_INFO, "ENTER: UnifiedSettingsEditor.__init__")
        
        self.screen = screen
        self.db = db
        self.ai = ai_manager
        
        # 1. Tab Discovery: Each child of the settings root is a tab
        self.tabs = self.db.get_children(root_node_id)
        self.active_tab_idx = 0
        self.running = True
        
        # 2. UI Layout
        self.rect = pygame.Rect(150, 60, 1100, 720)
        self.font = pygame.font.Font(None, 24)
        self.font_bold = pygame.font.Font(None, 28)

        # 3. Persistent UI Widgets
        self.new_svc_name = InputBox(0, 0, 200, 30, self.font)
        self.new_svc_driver = Dropdown(0, 0, 200, 30, self.font, [
            {'id': 'openai_compatible', 'name': 'OpenAI Compatible'},
            {'id': 'gemini', 'name': 'Google Gemini'}
        ])
        self.btn_add_ai = Button(0, 0, 80, 30, "Add", self.font, (60, 60, 80), (80, 80, 100), (255,255,255), self._add_ai_provider)
        
        # ADDED: Done Button to save and exit
        self.btn_done = Button(self.rect.right - 120, self.rect.bottom - 50, 100, 40, "Done", self.font, 
                              (50, 150, 50), (80, 180, 80), (255, 255, 255), self._close_editor)

        # 4. Storage for active row widgets (cached to prevent focus loss)
        self.ai_row_widgets = {} # node_id -> dict of widgets
        self.generic_inputs = {} # key -> InputBox
        
        self._refresh_tab_data()
        self._log(LOG_INFO, "EXIT: UnifiedSettingsEditor.__init__")

    def _log(self, level, message):
        if self.verbosity >= level:
            prefix = "[SETTINGS INFO]" if level == LOG_INFO else "[SETTINGS DEBUG]"
            print(f"{prefix} {message}")

    def _refresh_tab_data(self):
        self._log(LOG_INFO, "ENTER: _refresh_tab_data")
        active_node = self.tabs[self.active_tab_idx]
        if active_node['type'] == 'ai_registry':
            self._rebuild_ai_widgets(active_node)
        else:
            self.generic_inputs = {k: InputBox(0, 0, 400, 30, self.font, str(v)) for k, v in active_node['properties'].items()}
        self._log(LOG_INFO, "EXIT: _refresh_tab_data")

    def _rebuild_ai_widgets(self, registry_node):
        self._log(LOG_DEBUG, "Rebuilding AI provider widgets...")
        self.ai_row_widgets = {}
        providers = self.db.get_children(registry_node['id'], type_filter='ai_provider')
        t_opts = [{'id': k, 'name': v['name']} for k, v in OPENAI_TEMPLATES.items()]

        for p in providers:
            pid, props = p['id'], p['properties']
            current_key = props.get('api_key_var') or props.get('api_key', '')
            
            self.ai_row_widgets[pid] = {
                'api_key_inp': InputBox(0, 0, 240, 30, self.font, current_key),
                'url_inp': InputBox(0, 0, 240, 30, self.font, props.get('url', '')),
                'template_dd': Dropdown(0, 0, 180, 30, self.font, t_opts),
                'model_dd': Dropdown(0, 0, 200, 30, self.font, [{'id': props.get('model'), 'name': props.get('model')}] if props.get('model') else [], initial_id=props.get('model')),
                'fetch_btn': Button(0, 0, 60, 30, "Fetch", self.font, (60,60,80), (80,80,100), (255,255,255), lambda n=pid: self._fetch_models(n)),
                'del_btn': Button(0, 0, 60, 25, "Delete", self.font, (100,0,0), (150,0,0), (255,255,255), lambda n=pid: self._delete_ai_provider(n))
            }

    def _add_ai_provider(self):
        name, drv = self.new_svc_name.text.strip(), self.new_svc_driver.get_selected_id()
        if name and drv:
            props = {'driver': drv}
            if drv == 'gemini': props.update({'model': 'gemini-1.5-flash', 'api_key': 'GEMINI_API_KEY'})
            self.db.create_node('ai_provider', name, parent_id=self.tabs[self.active_tab_idx]['id'], properties=props)
            self.new_svc_name.text = ""; self._rebuild_ai_widgets(self.tabs[self.active_tab_idx])

    def _delete_ai_provider(self, node_id):
        self.db.delete_node(node_id)
        self._rebuild_ai_widgets(self.tabs[self.active_tab_idx])

    def _fetch_models(self, node_id):
        self._log(LOG_INFO, f"ENTER: _fetch_models (Node: {node_id})")
        w = self.ai_row_widgets[node_id]
        node = self.db.get_node(node_id)
        key_field = 'api_key' if node['properties'].get('driver') == 'gemini' else 'api_key_var'
        self.db.update_node(node_id, properties={key_field: w['api_key_inp'].text, 'url': w['url_inp'].text})
        
        models = self.ai.get_available_models_for_service(node_id)
        w['model_dd'].options = [{'id': m, 'name': m} for m in models]
        if models and "Error" not in models[0]: w['model_dd'].selected_idx = 0
        self._log(LOG_INFO, "EXIT: _fetch_models")

    def _close_editor(self):
        self._log(LOG_INFO, "Closing settings editor...")
        self._save_active_tab()
        self.running = False

    def handle_input(self, event):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE: self._close_editor()
        
        # Handle the Done Button
        self.btn_done.handle_event(event)

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for i in range(len(self.tabs)):
                if pygame.Rect(self.rect.x + (i * 145), self.rect.y - 35, 140, 35).collidepoint(event.pos):
                    self._save_active_tab(); self.active_tab_idx = i; self._refresh_tab_data(); return

        active_node = self.tabs[self.active_tab_idx]
        if active_node['type'] == 'ai_registry':
            self.new_svc_name.handle_event(event); self.new_svc_driver.handle_event(event); self.btn_add_ai.handle_event(event)
            for nid, w in self.ai_row_widgets.items():
                w['api_key_inp'].handle_event(event); w['url_inp'].handle_event(event); w['model_dd'].handle_event(event); w['fetch_btn'].handle_event(event); w['del_btn'].handle_event(event)
                if w['template_dd'].handle_event(event):
                    t_key = w['template_dd'].get_selected_id()
                    if t_key:
                        tpl = OPENAI_TEMPLATES[t_key]
                        self.db.update_node(nid, properties={'api_key_var': tpl['key_var'], 'url': tpl['url']})
                        self._rebuild_ai_widgets(active_node)
        else:
            for inp in self.generic_inputs.values(): inp.handle_event(event)

    def _save_active_tab(self):
        self._log(LOG_INFO, "ENTER: _save_active_tab")
        if not self.tabs: return
        active_node = self.tabs[self.active_tab_idx]
        if active_node['type'] == 'ai_registry':
            for nid, w in self.ai_row_widgets.items():
                node = self.db.get_node(nid)
                kf = 'api_key' if node['properties'].get('driver') == 'gemini' else 'api_key_var'
                self.db.update_node(nid, properties={kf: w['api_key_inp'].text, 'url': w['url_inp'].text, 'model': w['model_dd'].get_selected_id()})
        else:
            self.db.update_node(active_node['id'], properties={k: inp.text for k, inp in self.generic_inputs.items()})
        self._log(LOG_INFO, "EXIT: _save_active_tab")

    def draw(self):
        overlay = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 200)); self.screen.blit(overlay, (0,0))
        pygame.draw.rect(self.screen, (35, 35, 45), self.rect, border_radius=10)
        pygame.draw.rect(self.screen, (100, 100, 130), self.rect, 2, border_radius=10)

        for i, node in enumerate(self.tabs):
            active = (i == self.active_tab_idx)
            tab_r = pygame.Rect(self.rect.x + (i * 145), self.rect.y - 35, 140, 35)
            pygame.draw.rect(self.screen, (55, 55, 85) if active else (25, 25, 35), tab_r, border_top_left_radius=5, border_top_right_radius=5)
            self.screen.blit(self.font.render(node['name'], True, (255,255,255) if active else (150,150,150)), (tab_r.x + 10, tab_r.y + 8))

        if self.tabs[self.active_tab_idx]['type'] == 'ai_registry': self._draw_ai_manager()
        else: self._draw_generic_form()
        
        self.btn_done.draw(self.screen)

    def _draw_generic_form(self):
        y = self.rect.y + 50
        for key, inp in self.generic_inputs.items():
            self.screen.blit(self.font.render(f"{key.replace('_', ' ').title()}:", True, (200, 200, 200)), (self.rect.x + 40, y + 5))
            inp.rect.topleft = (self.rect.x + 200, y); inp.draw(self.screen); y += 45

    def _draw_ai_manager(self):
        y = self.rect.y + 20
        self.screen.blit(self.font_bold.render("Add AI Service:", True, (200,200,200)), (self.rect.x + 30, y))
        self.new_svc_name.rect.topleft, self.new_svc_driver.rect.topleft, self.btn_add_ai.rect.topleft = (self.rect.x + 180, y-5), (self.rect.x + 400, y-5), (self.rect.x + 620, y-5)
        self.new_svc_name.draw(self.screen); self.btn_add_ai.draw(self.screen); y += 60
        
        # Pass 1: Draw everything EXCEPT the dropdowns
        dropdowns_to_draw = []
        
        # Always draw the "Add Service" dropdown first
        self.new_svc_driver.draw(self.screen)
        if self.new_svc_driver.is_open:
            dropdowns_to_draw.append(self.new_svc_driver)

        for nid, w in self.ai_row_widgets.items():
            node = self.db.get_node(nid); row = pygame.Rect(self.rect.x + 20, y, self.rect.width - 40, 140)
            pygame.draw.rect(self.screen, (45, 45, 55), row, border_radius=5)
            self.screen.blit(self.font_bold.render(f"{node['name']} ({node['properties'].get('driver')})", True, (255,200,100)), (row.x+20, row.y+15))
            self.screen.blit(self.font.render("Env Key:", True, (150,150,150)), (row.x+20, row.y+55))
            w['api_key_inp'].rect.topleft = (row.x+90, row.y+50); w['api_key_inp'].draw(self.screen)
            
            if node['properties'].get('driver') == 'openai_compatible':
                self.screen.blit(self.font.render("URL:", True, (150,150,150)), (row.x+350, row.y+55))
                w['url_inp'].rect.topleft = (row.x+400, row.y+50)
                w['url_inp'].draw(self.screen)
                self.screen.blit(self.font.render("Template:", True, (150,150,150)), (row.x+660, row.y+55))
                w['template_dd'].rect.topleft = (row.x+740, row.y+50)
                w['template_dd'].draw(self.screen) # Draw the box
                if w['template_dd'].is_open: dropdowns_to_draw.append(w['template_dd'])

            self.screen.blit(self.font.render("Model:", True, (150,150,150)), (row.x+20, row.y+95))
            w['fetch_btn'].rect.topleft, w['model_dd'].rect.topleft = (row.x+90, row.y+90), (row.x+160, row.y+90)
            w['fetch_btn'].draw(self.screen)
            w['model_dd'].draw(self.screen) # Draw the box
            if w['model_dd'].is_open: dropdowns_to_draw.append(w['model_dd'])

            w['del_btn'].rect.topright = (row.right-10, row.top+10); w['del_btn'].draw(self.screen); 
            y += 150
            
        # Pass 2: Draw all OPEN dropdowns on top of everything else
        for dd in dropdowns_to_draw:
            dd.draw(self.screen)

        y = self.rect.y + 20
        self.screen.blit(self.font_bold.render("Add AI Service:", True, (200,200,200)), (self.rect.x + 30, y))
        self.new_svc_name.rect.topleft, self.new_svc_driver.rect.topleft, self.btn_add_ai.rect.topleft = (self.rect.x + 180, y-5), (self.rect.x + 400, y-5), (self.rect.x + 620, y-5)
        self.new_svc_name.draw(self.screen); self.new_svc_driver.draw(self.screen); self.btn_add_ai.draw(self.screen); y += 60
        
        for nid, w in self.ai_row_widgets.items():
            node = self.db.get_node(nid); row = pygame.Rect(self.rect.x + 20, y, self.rect.width - 40, 140)
            pygame.draw.rect(self.screen, (45, 45, 55), row, border_radius=5)
            self.screen.blit(self.font_bold.render(f"{node['name']} ({node['properties'].get('driver')})", True, (255,200,100)), (row.x+20, row.y+15))
            self.screen.blit(self.font.render("Env Key:", True, (150,150,150)), (row.x+20, row.y+55))
            w['api_key_inp'].rect.topleft = (row.x+90, row.y+50); w['api_key_inp'].draw(self.screen)
            if node['properties'].get('driver') == 'openai_compatible':
                self.screen.blit(self.font.render("URL:", True, (150,150,150)), (row.x+350, row.y+55))
                w['url_inp'].rect.topleft, w['template_dd'].rect.topleft = (row.x+400, row.y+50), (row.x+740, row.y+50)
                w['url_inp'].draw(self.screen); self.screen.blit(self.font.render("Template:", True, (150,150,150)), (row.x+660, row.y+55)); w['template_dd'].draw(self.screen)
            self.screen.blit(self.font.render("Model:", True, (150,150,150)), (row.x+20, row.y+95))
            w['fetch_btn'].rect.topleft, w['model_dd'].rect.topleft = (row.x+90, row.y+90), (row.x+160, row.y+90)
            w['fetch_btn'].draw(self.screen); w['model_dd'].draw(self.screen); w['del_btn'].rect.topright = (row.right-10, row.top+10); w['del_btn'].draw(self.screen); y += 150
            