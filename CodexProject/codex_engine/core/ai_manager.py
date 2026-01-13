import os
import json
import requests
from typing import Dict, Any, List

# Import the providers. 
# We remove 'import google.generativeai' completely from this file.
from .ai.gemini import GeminiProvider

# VERBOSITY LEVELS
LOG_NONE  = 0
LOG_INFO  = 1 # Function Enter/Exit
LOG_DEBUG = 2 # Data/Credential/Response Inspection

class AIManager:
    def __init__(self, db_manager, verbosity=LOG_NONE):
        self.db = db_manager
        self.verbosity = verbosity
        self._log(LOG_INFO, "AIManager Initialized")

    def _log(self, level, message):
        if self.verbosity >= level:
            prefix = "[AI INFO]" if level == LOG_INFO else "[AI DEBUG]"
            print(f"{prefix} {message}")

    def _resolve_credentials(self, provider_node_id):
        self._log(LOG_INFO, f"ENTER: _resolve_credentials (ID: {provider_node_id})")
        node = self.db.get_node(provider_node_id)
        if not node: 
            self._log(LOG_DEBUG, "Discovery failed: Node not found.")
            return None, None, None
        
        p = node['properties']
        env_var_name = p.get('api_key_var') or p.get('api_key')
        api_key = os.getenv(env_var_name) if env_var_name else None
        
        self._log(LOG_DEBUG, f"Resolved: VarName='{env_var_name}', KeyFound={api_key is not None}, URL='{p.get('url')}'")
        self._log(LOG_INFO, "EXIT: _resolve_credentials")
        return api_key, p.get('url'), p.get('model')

    def get_available_models_for_service(self, provider_node_id):
        self._log(LOG_INFO, f"ENTER: get_available_models_for_service (ID: {provider_node_id})")
        key, url, _ = self._resolve_credentials(provider_node_id)
        node = self.db.get_node(provider_node_id)
        driver = node['properties'].get('driver')

        try:
            if driver == 'gemini':
                self._log(LOG_DEBUG, "Driver: Gemini. Delegating to GeminiProvider...")
                provider = GeminiProvider()
                provider.configure(api_key=key if key else "", base_url=url)
                models = provider.list_models()
                self._log(LOG_DEBUG, f"Success: Found {len(models)} Gemini models.")
                self._log(LOG_INFO, "EXIT: get_available_models_for_service")
                return models
            
            elif driver == 'openai_compatible':
                # Note: Ideally this should also be moved to an OpenAIProvider class
                target_url = url.rstrip('/') + "/models" if url else "http://localhost:11434/v1/models"
                self._log(LOG_DEBUG, f"Driver: OpenAI Compatible. Hitting: {target_url}")
                headers = {"Authorization": f"Bearer {key if key else ''}"}
                resp = requests.get(target_url, headers=headers, timeout=5)
                
                if resp.status_code == 200:
                    models = [m['id'] for m in resp.json().get('data', [])]
                    self._log(LOG_DEBUG, f"Success: Found {len(models)} models.")
                    return models
                
                self._log(LOG_DEBUG, f"Service Error: {resp.status_code}")
                return [f"Service Error: {resp.status_code}"]
        except Exception as e:
            self._log(LOG_DEBUG, f"Exception during fetch: {e}")
            return [f"Connection Failed: {str(e)}"]
        
        return []

    def generate_text(self, provider_node_id, prompt, context=""):
        self._log(LOG_INFO, f"ENTER: generate_text (Provider: {provider_node_id})")
        key, url, model = self._resolve_credentials(provider_node_id)
        node = self.db.get_node(provider_node_id)
        driver = node['properties'].get('driver')

        try:
            if driver == 'gemini':
                self._log(LOG_DEBUG, "Driver: Gemini. Delegating to GeminiProvider...")
                provider = GeminiProvider()
                provider.configure(api_key=key if key else "", base_url=url)
                
                # Pass the resolved model name, defaulting if necessary
                model_name = model or "gemini-1.5-flash"
                self._log(LOG_DEBUG, f"Sending request via provider (Model: {model_name})")
                
                result = provider.generate_text(model=model_name, prompt=prompt, context=context)
                self._log(LOG_DEBUG, "Response received successfully.")
                return result
            
            elif driver == 'openai_compatible':
                # Note: Ideally this should also be moved to an OpenAIProvider class
                target_url = url.rstrip('/') + "/chat/completions" if url else "http://localhost:11434/v1/chat/completions"
                self._log(LOG_DEBUG, f"Sending OpenAI request to {target_url}")
                headers = {"Authorization": f"Bearer {key if key else ''}", "Content-Type": "application/json"}
                payload = {
                    "model": model,
                    "messages": [{"role": "system", "content": context}, {"role": "user", "content": prompt}],
                    "temperature": 0.7
                }
                resp = requests.post(target_url, headers=headers, json=payload)
                if resp.status_code == 200:
                    return resp.json()['choices'][0]['message']['content']
                return f"AI Error: {resp.status_code}"
                
        except Exception as e:
            self._log(LOG_DEBUG, f"Exception: {e}")
            return f"Request Failed: {e}"

    def generate_json(self, provider_node_id, prompt, schema_hint=""):
        self._log(LOG_INFO, f"ENTER: generate_json (Provider: {provider_node_id})")
        key, url, model = self._resolve_credentials(provider_node_id)
        node = self.db.get_node(provider_node_id)
        driver = node['properties'].get('driver')

        # Note: System instruction construction is now handled by the Provider, 
        # but we construct it here for OpenAI compatibility for now.
        system_instruction = f"Output ONLY valid JSON. Schema: {schema_hint}"

        try:
            if driver == 'gemini':
                self._log(LOG_DEBUG, "Driver: Gemini. Delegating to GeminiProvider...")
                provider = GeminiProvider()
                provider.configure(api_key=key if key else "", base_url=url)
                
                model_name = model or "gemini-1.5-flash"
                self._log(LOG_DEBUG, f"Sending JSON request via provider (Model: {model_name})")
                
                result = provider.generate_json(model=model_name, prompt=prompt, schema_hint=schema_hint)
                
                # Provider returns a Dict already, but let's ensure logging matches
                self._log(LOG_DEBUG, f"Raw JSON Response: {result}")
                return result
            
            elif driver == 'openai_compatible':
                # Note: Ideally this should also be moved to an OpenAIProvider class
                target_url = url.rstrip('/') + "/chat/completions" if url else "http://localhost:11434/v1/chat/completions"
                self._log(LOG_DEBUG, f"Sending OpenAI JSON request to {target_url}")
                headers = {"Authorization": f"Bearer {key if key else ''}", "Content-Type": "application/json"}
                payload = {
                    "model": model,
                    "messages": [{"role": "system", "content": system_instruction}, {"role": "user", "content": prompt}],
                    "response_format": {"type": "json_object"},
                    "temperature": 0.2
                }
                resp = requests.post(target_url, headers=headers, json=payload)
                if resp.status_code == 200:
                    content = resp.json()['choices'][0]['message']['content']
                    self._log(LOG_DEBUG, f"Raw JSON Response: {content}")
                    return json.loads(content)
                return {"error": f"Status {resp.status_code}"}

        except Exception as e:
            self._log(LOG_DEBUG, f"JSON Exception: {e}")
            return {"error": str(e)}
