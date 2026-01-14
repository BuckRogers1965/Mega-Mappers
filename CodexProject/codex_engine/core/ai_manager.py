import os
import uuid
import threading
import queue
from typing import Dict, Any, List

# Updated imports pointing to the 'ai' subfolder
from .ai.gemini import GeminiProvider
from .ai.openai_compatible import OpenAICompatibleProvider

# VERBOSITY LEVELS (Restored for logging)
LOG_NONE  = 0
LOG_INFO  = 1
LOG_DEBUG = 2

class AIManager:
    def __init__(self, db_manager, verbosity=LOG_NONE):
        # Match the arguments passed from main.py
        self.config = db_manager
        self.verbosity = verbosity

        self.drivers = {
            "gemini": GeminiProvider(),
            "openai_compatible": OpenAICompatibleProvider()
        }
        
        # Queues and Worker Thread
        self.request_queue = queue.Queue()
        self.callback_queue = queue.Queue()
        
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()

        self._job_count = 0
        self._lock = threading.Lock()
        
        self._log(LOG_INFO, "AIManager Initialized with Queue")

    def _log(self, level, message):
        if self.verbosity >= level:
            prefix = "[AI INFO]" if level == LOG_INFO else "[AI DEBUG]"
            print(f"{prefix} {message}")

    def get_active_job_count(self):
        """Public method to get the number of jobs submitted but not yet completed."""
        with self._lock:
            return self._job_count

    def _worker_loop(self):
        """The background thread's main function. Runs forever."""
        while True:
            job = self.request_queue.get()
            
            # Extract job details
            callback_fn = job.get('callback')
            prompt = job.get('prompt')
            schema = job.get('schema_hint')
            context_chain = job.get('context_chain')
            svc_override = job.get('service_override')
            model_override = job.get('model_override')

            try:
                # Execute the AI generation synchronously within the worker thread
                result = self.generate_json(
                    prompt,
                    schema_hint=schema,
                    context_chain=context_chain,
                    service_override=svc_override,
                    model_override=model_override
                )
                
                if callback_fn:
                    # Post result back to the main thread via callback queue
                    self.callback_queue.put((callback_fn, result))
            except Exception as e:
                print(f"[AI WORKER ERROR] {e}")
                if callback_fn:
                    self.callback_queue.put((callback_fn, None))

            finally:
                # Decrement counter only AFTER the job is fully done
                with self._lock:
                    self._job_count -= 1

    def submit_json_request(self, prompt, schema_hint, context_chain, callback, service_override=None, model_override=None):
        """Non-blocking method to add a job to the queue."""
        job = {
            'prompt': prompt,
            'schema_hint': schema_hint,
            'context_chain': context_chain,
            'callback': callback,
            'service_override': service_override,
            'model_override': model_override
        }
        with self._lock:
            self._job_count += 1
            
        self.request_queue.put(job)
        print(f"[AI Manager] Job submitted. Total active jobs: {self.get_active_job_count()}")

    def get_completed_callbacks(self):
        """Called by main thread to get finished jobs."""
        completed = []
        while not self.callback_queue.empty():
            try:
                completed.append(self.callback_queue.get_nowait())
            except queue.Empty:
                break
        return completed

    def get_service_registry(self):
        reg = self.config.get("global_ai_registry") 
        if not reg: return []
        return reg

    def add_service(self, name, driver_type):
        registry = self.get_service_registry()
        new_id = str(uuid.uuid4())[:8]
        registry.append({"id": new_id, "name": name, "driver": driver_type})
        self.config.set("global_ai_registry", registry, "global")
        return new_id

    def delete_service(self, service_id):
        registry = self.get_service_registry()
        registry = [s for s in registry if s['id'] != service_id]
        self.config.set("global_ai_registry", registry, "global")

    def _get_active_provider_and_model(self, context_chain=None, service_override=None, model_override=None):
        registry = self.get_service_registry()
        if not registry: return None, None

        active_id = service_override if service_override else self.config.get("active_service_id", context_chain)
        if not active_id: active_id = registry[0]['id']

        model = model_override
        if not model: model = self.config.get(f"service_{active_id}_model", context_chain)

        if not active_id: return None, None
        
        service_def = next((s for s in registry if s['id'] == active_id), None)
        if not service_def: return None, None
        
        env_key_var = self.config.get(f"service_{active_id}_key_var")
        base_url = self.config.get(f"service_{active_id}_url")
        api_key = os.getenv(env_key_var) if env_key_var else None

        driver = self.drivers.get(service_def['driver'])
        if driver: driver.configure(api_key, base_url)
        return driver, model

    def is_available(self, context_chain=None, service_override=None):
        provider, model = self._get_active_provider_and_model(context_chain, service_override=service_override)
        return provider is not None

    def generate_json(self, prompt, schema_hint="", context_chain=None, service_override=None, model_override=None):
        provider, model = self._get_active_provider_and_model(
            context_chain, 
            service_override=service_override, 
            model_override=model_override
        )
        if not provider: return {}
        return provider.generate_json(model, prompt, schema_hint)
    
    def get_available_models_for_service(self, service_id, context_chain=None):
        registry = self.get_service_registry()
        service_def = next((s for s in registry if s['id'] == service_id), None)
        if not service_def: return ["Error: Service not found"]

        driver = self.drivers.get(service_def['driver'])
        
        env_key_var = self.config.get(f"service_{service_id}_key_var", context_chain)
        base_url = self.config.get(f"service_{service_id}_url", context_chain)
        api_key = os.getenv(env_key_var) if env_key_var else None
        
        try:
            driver.configure(api_key, base_url)
            return driver.list_models()
        except Exception as e:
            return [f"Error: {e}"]
