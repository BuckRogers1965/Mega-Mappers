from abc import ABC, abstractmethod

class BaseController(ABC):
    def __init__(self, db_manager, node_data, theme_manager):
        self.db = db_manager
        self.node = node_data
        self.theme = theme_manager
        self.widgets = [] # Buttons, Sliders, etc.

    @abstractmethod
    def handle_input(self, event, cam_x, cam_y, zoom):
        """
        Process input. 
        Returns a dict if an action needs to bubble up (e.g. 'enter_marker'), 
        or None if handled internally.
        """
        pass

    @abstractmethod
    def update(self):
        """Frame-by-frame updates."""
        pass

    @abstractmethod
    def draw_map(self, screen, cam_x, cam_y, zoom, screen_w, screen_h):
        """Draws the specific map content (Image, Grid, etc)."""
        pass

    @abstractmethod
    def draw_overlays(self, screen, cam_x, cam_y, zoom):
        """Draws things on top of the map (Markers, Vectors, Fog)."""
        pass

    @abstractmethod
    def get_metadata_updates(self):
        """Returns a dictionary of metadata to save to the DB."""
        return {}

    @abstractmethod
    def cleanup(self):
        """Called when switching away from this controller."""
        pass
