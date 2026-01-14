import os
import threading
import queue
import json
from typing import Dict, Any, List

# --- FIX: Removed library-specific imports ---
# import requests  <- REMOVED
# import google.generativeai as genai <- REMOVED

from .ai.gemini import GeminiProvider
from .ai.openai_compatible import OpenAICompatibleProvider

LOG_NONE  = 0
LOG_INFO  = 1
LOG_DEBUG = 2

class AIManager:
    def __init__(self, db_manager, verbosity=LOG_NONE):
        self.db = db_manager
        self.verbosity = verbosity
        
        self.drivers = {
            "gemini": GeminiProvider(),
            "openai_compatible": OpenAICompatibleProvider()
        }
        
        self.request_queue = queue.Queue()
        self.callback_queue = queue.Queue()
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()
        self._job_count = 0
        self._lock = threading.Lock()
        
        self._log(LOG_INFO, "AIManager Initialized with Queue and DBManager")

    def _log(self, level, message):
        if self.verbosity >= level:
            prefix = "[AI INFO]" if level == LOG_INFO else "[AI DEBUG]"
            print(f"{prefix} {message}")

    def _worker_loop(self):
        while True:
            job = self.request_queue.get()
            self._log(LOG_INFO, "Worker thread picked up a new job.")
            
            callback_fn = job.get('callback')
            try:
                result = self.generate_json(
                    job['provider_node_id'], 
                    job['prompt'], 
                    job['schema_hint']
                )
                if callback_fn:
                    self.callback_queue.put((callback_fn, result))
            except Exception as e:
                print(f"[AI WORKER ERROR] {e}")
                if callback_fn:
                    self.callback_queue.put((callback_fn, None))
            finally:
                with self._lock:
                    self._job_count -= 1
    
    def submit_json_request(self, provider_node_id, prompt, schema_hint, callback):
        job = {
            'provider_node_id': provider_node_id, 
            'prompt': prompt, 
            'schema_hint': schema_hint, 
            'callback': callback
        }
        with self._lock:
            self._job_count += 1
        self.request_queue.put(job)
        self._log(LOG_INFO, f"Job submitted. Total active jobs: {self._job_count}")

    def get_completed_callbacks(self):
        completed = []
        while not self.callback_queue.empty():
            try:
                completed.append(self.callback_queue.get_nowait())
            except queue.Empty:
                break
        return completed

    def _resolve_credentials(self, provider_node_id):
        node = self.db.get_node(provider_node_id)
        if not node: return None, None, None, None
        
        p = node['properties']
        driver_name = p.get('driver')
        env_var_name = p.get('api_key_var') or p.get('api_key')
        api_key = os.getenv(env_var_name) if env_var_name else None
        
        self._log(LOG_DEBUG, f"Resolved Provider ID {provider_node_id}: driver='{driver_name}', key_var='{env_var_name}', url='{p.get('url')}'")
        return driver_name, api_key, p.get('url'), p.get('model')

    def get_available_models_for_service(self, provider_node_id):
        self._log(LOG_INFO, f"Fetching models for provider ID: {provider_node_id}")
        driver_name, key, url, _ = self._resolve_credentials(provider_node_id)
        
        driver = self.drivers.get(driver_name)
        if not driver:
            return [f"Error: Unknown driver '{driver_name}'"]
        
        try:
            driver.configure(key, url)
            return driver.list_models()
        except Exception as e:
            return [f"Error: {e}"]

    def generate_json(self, provider_node_id, prompt, schema_hint=""):
        self._log(LOG_INFO, f"Generating JSON for provider ID: {provider_node_id}")
        driver_name, key, url, model = self._resolve_credentials(provider_node_id)

        driver = self.drivers.get(driver_name)
        if not driver:
            self._log(LOG_DEBUG, f"Generate failed: Driver '{driver_name}' not found.")
            return {"error": f"Driver '{driver_name}' not found"}
        
        driver.configure(key, url)
        return driver.generate_json(model, prompt, schema_hint)
