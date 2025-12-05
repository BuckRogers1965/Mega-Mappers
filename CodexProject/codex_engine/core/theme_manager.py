import json
import logging
from typing import Dict, Any, Tuple
from codex_engine.config import THEMES_DIR, DEFAULT_THEME

logger = logging.getLogger("ThemeManager")

class ThemeManager:
    def __init__(self):
        self.current_theme_data = {}
        self.loaded_theme_name = ""
        self.fallback_theme = {
            "colors": {
                "background": [245, 235, 215],
                "ink": [40, 30, 20],
                "accent": [200, 50, 50]
            },
            "vocabulary": {
                "settlement": "Village",
                "currency": "Gold Pieces"
            }
        }

    def load_theme(self, theme_name: str):
        path = THEMES_DIR / f"{theme_name}.json"
        
        if not path.exists():
            logger.warning(f"Theme {theme_name} not found at {path}. Using fallback.")
            self.current_theme_data = self.fallback_theme
            self.loaded_theme_name = "fallback"
            return

        try:
            with open(path, 'r', encoding='utf-8') as f:
                self.current_theme_data = json.load(f)
            self.loaded_theme_name = theme_name
            logger.info(f"Loaded theme: {theme_name}")
        except Exception as e:
            logger.error(f"Failed to parse theme {theme_name}: {e}")
            self.current_theme_data = self.fallback_theme

    def get_color(self, key: str) -> Tuple[int, int, int]:
        c = self.current_theme_data.get("colors", {}).get(key)
        if not c:
            c = self.fallback_theme["colors"].get(key, [255, 0, 255])
        return tuple(c)

    def get_vocab(self, key: str) -> str:
        v = self.current_theme_data.get("vocabulary", {}).get(key)
        return v if v else key.capitalize()

    def get_generator_settings(self, gen_type: str) -> Dict[str, Any]:
        return self.current_theme_data.get("generation_rules", {}).get(gen_type, {})
