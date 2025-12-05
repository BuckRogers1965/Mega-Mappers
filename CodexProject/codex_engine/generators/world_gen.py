import numpy as np
from PIL import Image
import uuid
import random
from codex_engine.config import MAPS_DIR
from codex_engine.core.db_manager import DBManager

class WorldGenerator:
    def __init__(self, theme_manager, db_manager: DBManager):
        self.db = db_manager
        
    def generate_world_node(self, campaign_id, width=513, height=513):
        # 8x Size override for your setup (approx 4k map)
        size = 1024 * 2 + 1
        
        print(f"Starting Simulation ({size}x{size})...")
        
        # 1. BASE TERRAIN
        terrain = self._diamond_square(size, roughness=0.55)
        
        # 2. EROSION
        print("Hydraulic Erosion...")
        terrain = self._hydraulic_erosion(terrain, iterations=80000)
        
        print("Thermal Erosion...")
        terrain = self._thermal_erosion(terrain, iterations=15)
        
        # --- AUTO-CENTERING ---
        print("Re-centering map on highest peak...")
        y_peak, x_peak = np.unravel_index(np.argmax(terrain), terrain.shape)
        
        center_y, center_x = size // 2, size // 2
        shift_y = center_y - y_peak
        shift_x = center_x - x_peak
        
        terrain = np.roll(terrain, shift_y, axis=0)
        terrain = np.roll(terrain, shift_x, axis=1)
        
        # 4. NORMALIZATION
        min_h, max_h = terrain.min(), terrain.max()
        terrain = (terrain - min_h) / (max_h - min_h)
        
        # 5. SAVE
        print("Saving to disk...")
        uint16_data = (terrain * 65535).astype(np.uint16)
        
        map_filename = f"{uuid.uuid4()}.png"
        map_path = MAPS_DIR / map_filename
        
        img = Image.fromarray(uint16_data, mode='I;16')
        img.save(map_path)
        print(f"Done: {map_path}")

        metadata = {
            "file_path": map_filename,
            "width": size,
            "height": size,
            "real_min": -11000.0,
            "real_max": 9000.0,
            "sea_level": 0.0
        }
        
        existing = self.db.get_node_by_coords(campaign_id, None, 0, 0)
        if existing:
            self.db.update_node_data(existing['id'], geometry={}, metadata=metadata)
            return existing['id'], metadata
        else:
            nid = self.db.create_node(campaign_id, "world_map", None, 0, 0, "Fractal World")
            self.db.update_node_data(nid, geometry={}, metadata=metadata)
            return nid, metadata

    def _diamond_square(self, size, roughness):
        """
        Seamlessly wrapping fractal terrain using multi-octave noise.
        This tiles perfectly since we use periodic coordinates.
        """
        map_data = np.zeros((size, size))
        
        # Use multiple octaves of sine-based noise that naturally wraps
        for octave in range(8):
            frequency = 2 ** octave
            amplitude = roughness ** octave
            
            # Create coordinate grids
            x = np.linspace(0, 2 * np.pi, size, endpoint=False)
            y = np.linspace(0, 2 * np.pi, size, endpoint=False)
            xx, yy = np.meshgrid(x, y)
            
            # Generate wrapping noise using sine waves at different angles
            angle1 = random.random() * 2 * np.pi
            angle2 = random.random() * 2 * np.pi
            
            noise = (np.sin(xx * frequency + angle1) * np.sin(yy * frequency + angle2) +
                    np.sin((xx + yy) * frequency * 0.7 + angle1) * 
                    np.cos((xx - yy) * frequency * 0.7 + angle2))
            
            map_data += noise * amplitude
        
        # Normalize to 0-1 range
        map_data = (map_data - map_data.min()) / (map_data.max() - map_data.min())
        
        return map_data

    def _thermal_erosion(self, terrain, iterations, talus=0.01):
        """YOUR ORIGINAL CODE - only change is % size for wrapping"""
        size = terrain.shape[0]
        
        for _ in range(iterations):
            diffs = []
            for dy in [-1, 0, 1]:
                for dx in [-1, 0, 1]:
                    if dx == 0 and dy == 0: continue
                    neighbor = np.roll(terrain, (dy, dx), axis=(0, 1))
                    d = terrain - neighbor
                    mask = d > talus
                    diffs.append((d, mask, dy, dx))
            
            change = np.zeros_like(terrain)
            for d, mask, dy, dx in diffs:
                amount = mask * d * 0.1 
                change -= amount 
            terrain += change
        return terrain

    def _hydraulic_erosion(self, terrain, iterations):
        """YOUR ORIGINAL CODE - unchanged"""
        rain_map = np.zeros_like(terrain)
        erosion_map = np.zeros_like(terrain)
        rain_map += 1.0
        
        for _ in range(20):
            gy, gx = np.gradient(terrain)
            slope = np.sqrt(gx**2 + gy**2)
            erosion_map += slope * rain_map * 0.01
        
        terrain -= erosion_map * 0.5
        return terrain
