import os
import json
import google.genai as genai
from typing import Dict, Any, List
from .base import AIProvider

class GeminiProvider(AIProvider):
    def __init__(self):
        self.api_key = None
        self.client = None
        self.model_name = None

    def configure(self, api_key: str, base_url: str = None):
        self.api_key = api_key
        # The new library uses a Client instance rather than global configuration
        if self.api_key and self.api_key != "missing":
            # Initialize the client. 
            # Note: base_url is accepted but usually not needed for standard Google endpoints,
            # but kept for signature compatibility.
            self.client = genai.Client(api_key=self.api_key)

    def list_models(self) -> List[str]:
        if not self.client:
            return ["Error: Client not initialized (Missing API Key)"]
        try:
            # New SDK: Use client.models.list()
            models_response = self.client.models.list()
            
            model_names = []
            # Iterate through the response
            for m in models_response:
                # Filter for non-tuning/embedding models if necessary, 
                # though filtering by 'supported_generation_methods' might be deprecated 
                # or handled differently in the new proto definitions.
                # We return all model names here for safety.
                if m.name.startswith("models/"):
                    model_names.append(m.name.replace("models/", ""))
            
            return model_names
        except Exception as e:
            return [f"Error: {str(e)}"]

    def _get_model_instance(self, model_name: str):
        # In the new SDK, we don't explicitly instantiate a GenerativeModel object 
        # to store. Instead, we pass the model name to the client's methods.
        # This method is kept if other parts of the code expect it, 
        # but it effectively just validates the name.
        return model_name or "gemini-1.5-flash"

    def generate_text(self, model: str, prompt: str, context: str = "") -> str:
        if not self.client:
            return "AI Unavailable: Client not initialized (Missing API Key)."
        
        # Use the specific model provided, or default
        target_model = self._get_model_instance(model)
        full_prompt = f"Context: {context}\n\nTask: {prompt}"
        
        try:
            # New SDK: Call generate_content via the client
            response = self.client.models.generate_content(
                model=target_model,
                contents=full_prompt
            )
            return response.text
        except Exception as e:
            return f"AI Error: {str(e)}"

    def generate_json(self, model: str, prompt: str, schema_hint: str = "") -> Dict[str, Any]:
        if not self.client:
            return {}

        target_model = self._get_model_instance(model)
        
        # Constructing the prompt with the system instruction
        # Note: The new SDK has specific support for system instructions via Config,
        # but we append it to the prompt here to maintain strict backward compatibility 
        # with your existing prompt engineering logic.
        sys_instruction = "You are a data API. Output ONLY valid JSON. No markdown formatting."
        full_prompt = f"{sys_instruction}\nSchema expected: {schema_hint}\nRequest: {prompt}"
        
        try:
            # New SDK: Call generate_content via the client
            response = self.client.models.generate_content(
                model=target_model,
                contents=full_prompt
            )
            
            # Clean up markdown code blocks if the model still adds them
            clean_text = response.text.replace("```json", "").replace("```", "").strip()
            return json.loads(clean_text)
        except Exception as e:
            print(f"JSON Generation failed: {e}")
            return {}
