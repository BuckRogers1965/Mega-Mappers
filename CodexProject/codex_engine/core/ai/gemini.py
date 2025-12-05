import os
import json
import google.generativeai as genai
from .base import AIProvider

class GeminiProvider(AIProvider):
    def __init__(self, api_key_env_var="GEMINI_API_KEY"):
        self.api_key = os.getenv(api_key_env_var)
        self.model = None
        if self.api_key:
            genai.configure(api_key=self.api_key)
            self.model_name = "gemini-1.5-flash" 

    def is_available(self) -> bool:
        return self.api_key is not None

    def _get_model(self):
        if not self.model:
            self.model = genai.GenerativeModel(self.model_name)
        return self.model

    def generate_text(self, prompt: str, context: str = "") -> str:
        if not self.is_available():
            return "AI Unavailable: Key missing."
        
        full_prompt = f"Context: {context}\n\nTask: {prompt}"
        try:
            response = self._get_model().generate_content(full_prompt)
            return response.text
        except Exception as e:
            return f"AI Error: {str(e)}"

    def generate_json(self, prompt: str, schema_hint: str = "") -> dict:
        if not self.is_available():
            return {}

        sys_instruction = "You are a data API. Output ONLY valid JSON. No markdown formatting."
        full_prompt = f"{sys_instruction}\nSchema expected: {schema_hint}\nRequest: {prompt}"
        
        try:
            response = self._get_model().generate_content(full_prompt)
            clean_text = response.text.replace("```json", "").replace("```", "").strip()
            return json.loads(clean_text)
        except Exception as e:
            print(f"JSON Generation failed: {e}")
            return {}
