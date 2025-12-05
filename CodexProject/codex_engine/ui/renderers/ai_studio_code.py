import pygame
import numpy as np
from PIL import Image
from codex_engine.config import MAPS_DIR
from .base import MapRenderStrategy

class ImageMapStrategy(MapRenderStrategy):
    def __init__(self, metadata, theme):
        self.metadata = metadata
        self.theme = theme
        
        # Load the 16-bit PNG
        self.map_path = MAPS_DIR / metadata['file_path']
        self.width = metadata['width']
        self.height = metadata['height']
        self.real_min = metadata['real_min']
        self.real_max = metadata['real_max']
        self.h_range = self.real_max - self.real_min
        
        print(f"Loading map: {self.map_path}")
        pil_img = Image.open(self.map_path)
        
        # Convert to numpy array for fast processing
        self.raw_data = np.array(pil_img) # uint16
        
        # Pre-calculate a Surface cache? 
        # For a 1024x1024 map, we can keep a base surface in memory.
        self.base_surface = pygame.Surface((self.width, self.height))
        self._generate_base_terrain()

    def _generate_base_terrain(self):
        """Generates the static Greyscale terrain layer."""
        # Normalize uint16 (0-65535) to uint8 (0-255) for display
        display_data = (self.raw_data / 256).astype(np.uint8)
        
        # Create RGB array (Grey)
        rgb_data = np.stack((display_data, display_data, display_data), axis=-1)
        
        # Blit to surface
        pygame.surfarray.blit_array(self.base_surface, np.transpose(rgb_data, (1, 0, 2)))

    def draw(self, surface, cam_x, cam_y, zoom, screen_w, screen_h, sea_level_meters=0.0):
        # 1. DRAW TERRAIN (Scaled & Panned)
        # We handle zoom/pan by manipulating the rect
        
        # Calculate source rect (visible part of the map)
        # Inverse zoom logic: if zoom is 2.0, we see half the map
        # Let's simplify: Zoom 1.0 = 1 pixel per map pixel
        
        # Dest Rect: Where on screen
        center_x, center_y = screen_w // 2, screen_h // 2
        dest_x = center_x - (cam_x * zoom)
        dest_y = center_y - (cam_y * zoom)
        
        scaled_w = int(self.width * zoom)
        scaled_h = int(self.height * zoom)
        
        # Use Pygame's transform to scale the base terrain
        # Optimization: Only scale the visible chunk? For now, scale whole (simple).
        # Note: Scaling 1024x1024 every frame is slow. 
        # In production, we would scale only when zoom changes.
        
        scaled_surf = pygame.transform.scale(self.base_surface, (scaled_w, scaled_h))
        surface.blit(scaled_surf, (dest_x, dest_y))
        
        # 2. DRAW WATER OVERLAY (The Transparent Blue Layer)
        # We calculate a water mask based on the real meters slider
        
        # Convert slider meters to uint16 threshold
        # Threshold = (Meters - Min) / Range * 65535
        if self.h_range == 0: self.h_range = 1
        threshold_ratio = (sea_level_meters - self.real_min) / self.h_range
        threshold_uint16 = int(threshold_ratio * 65535)
        
        # Mask: Where raw_data <= threshold
        water_mask = self.raw_data <= threshold_uint16
        
        if np.any(water_mask):
            # Create a Blue Surface
            water_surf = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
            
            # Create RGBA array
            # R=0, G=0, B=150, A=100 (Transparent Blue)
            # We want to set alpha only where mask is True
            
            # Fast numpy construction
            rgba = np.zeros((self.width, self.height, 4), dtype=np.uint8)
            
            # Transpose mask to match Pygame (x, y) vs Numpy (row, col)
            mask_t = water_mask.T 
            
            # Set Blue and Alpha
            rgba[mask_t, 2] = 150 # Blue
            rgba[mask_t, 3] = 100 # Alpha
            
            # Blit array to surface
            pygame.surfarray.blit_array(water_surf, rgba)
            
            # Scale and Blit
            scaled_water = pygame.transform.scale(water_surf, (scaled_w, scaled_h))
            surface.blit(scaled_water, (dest_x, dest_y))

    def get_object_at(self, world_x, world_y, zoom):
        # Convert screen world coords to map pixel coords
        # pixel_x = world_x
        # pixel_y = world_y
        
        px = int(world_x)
        py = int(world_y)
        
        if 0 <= px < self.width and 0 <= py < self.height:
            raw = self.raw_data[py, px]
            # Convert to meters
            ratio = raw / 65535.0
            meters = self.real_min + (ratio * self.h_range)
            return {"h_meters": meters}
        return None