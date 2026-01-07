import numpy as np
from scipy.signal import convolve2d
from PIL import Image
import uuid
import random
from codex_engine.config import MAPS_DIR
from codex_engine.core.db_manager import DBManager

class WorldGenerator:
    def __init__(self, theme_manager, db_manager: DBManager):
        self.db = db_manager
        
    def generate_world_node(self, campaign_id, width=513, height=513):
        # 2:1 aspect ratio for spherical world
        height = 1024 * 1 + 1
        width = 1024 * 2 + 1
        
        print(f"Starting Simulation ({width}x{height})...")
        
        # 1. BASE TERRAIN
        terrain = self._diamond_square(width, height, roughness=0.45)
        terrain = self._brute_force_smooth_and_dither(terrain, iterations=32, size=3)
        terrain = self._brute_force_smooth_and_dither(terrain, iterations=8, size=7)

        # --- AUTO-CENTERING ---
        print("Re-centering map on highest peak...")
        y_peak, x_peak = np.unravel_index(np.argmax(terrain), terrain.shape)
        
        center_y, center_x = height // 2, width // 2
        shift_y = center_y - y_peak
        shift_x = center_x - x_peak
        
        terrain = np.roll(terrain, shift_y, axis=0)
        terrain = np.roll(terrain, shift_x, axis=1)

        terrain = terrain + self._diamond_square(width, height, roughness=0.35)/2
        terrain = self._brute_force_smooth_and_dither(terrain, iterations=6, size=5)

        
        dither_step = 1.0 / 65535.0
        smooth_range = 15
        for i in range(smooth_range):
            print(f"Erosion {i} of {smooth_range}")
            terrain = self._hydraulic_erosion(terrain, iterations=1000)
            terrain = self._thermal_erosion(terrain, iterations=1)

            terrain = np.roll(terrain, 2, axis=0)
            terrain = np.roll(terrain, -1, axis=1)
            
            #terrain = terrain + self._diamond_square(width, height, roughness=0.15)
            #terrain = self._brute_force_smooth_and_dither(terrain, iterations=2, size=3)

            dither_noise = (np.random.randint(0, 10, size=terrain.shape)-5) * dither_step
            terrain += dither_noise

        # --- AUTO-CENTERING ---
        #print("Re-centering map on highest peak...")
        #y_peak, x_peak = np.unravel_index(np.argmax(terrain), terrain.shape)
        
        #center_y, center_x = height // 2, width // 2
        #shift_y = center_y - y_peak
        #shift_x = center_x - x_peak
        
        #terrain = np.roll(terrain, shift_y, axis=0)
        #terrain = np.roll(terrain, shift_x, axis=1)
        
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
            "width": width,
            "height": height,
            "real_min": -11000.0,
            "real_max": 9000.0,
            "sea_level": 0.0
        }
        
        nid = None
        existing = self.db.get_node_by_coords(campaign_id, None, 0, 0)
        if existing:
            self.db.update_node(existing['id'], properties=metadata)
            nid = existing['id']
        else:
            #nid = self.db.create_node(campaign_id, "world_map", None, 0, 0, "Fractal World")
            nid = self.db.create_node("world_map", "Fractal World", campaign_id, {"grid_x": 0, "grid_y": 0})
            self.db.update_node(nid, properties=metadata)
        
        # NO AUTOMATIC ROADS/RIVERS ADDED HERE
        return nid, metadata

    def _brute_force_smooth_and_dither(self, terrain, iterations=1, size=3):
        """
        Applies a size x size averaging blur with wrap-around on both horizontal and
        vertical axes by transposing the array for the second pass. Also dithers.
        """
        if not convolve2d:
            print("WARNING: 'scipy' is not installed. Smoothing step will be skipped. Run: pip install scipy")
            return terrain

        kernel = np.ones((size, size)) / size**2
        dither_step = 1.0 / 65535.0
        smoothed_terrain = terrain.copy()
        
        for i in range(iterations):
            print(f"Smoothing & Dithering Pass {i+1}/{iterations}...")
            
            # 1. Smooth horizontally
            smoothed_terrain = convolve2d(smoothed_terrain, kernel, mode='same', boundary='wrap')
            
            # 2. Rotate, smooth again (now vertically), and rotate back
            smoothed_terrain = convolve2d(smoothed_terrain.T, kernel, mode='same', boundary='wrap').T
            
            # 3. Add dither noise after both smoothing passes
            dither_noise = (np.random.randint(0, 10, size=smoothed_terrain.shape)-5) * dither_step
            smoothed_terrain += dither_noise
            
        return smoothed_terrain

    def _diamond_square(self, width, height, roughness):
        map_data = np.zeros((height, width))
        for octave in range(8):
            frequency = 2 ** octave
            amplitude = roughness ** octave
            x = np.linspace(0, 2 * np.pi, width, endpoint=False)
            y = np.linspace(0, 2 * np.pi, height, endpoint=False)
            xx, yy = np.meshgrid(x, y)
            angle1 = random.random() * 2 * np.pi
            angle2 = random.random() * 2 * np.pi
            noise = (np.sin(xx * frequency + angle1) * np.sin(yy * frequency + angle2) +
                    np.sin((xx + yy) * frequency * 0.7 + angle1) * 
                    np.cos((xx - yy) * frequency * 0.7 + angle2))
            map_data += noise * amplitude
        map_data = (map_data - map_data.min()) / (map_data.max() - map_data.min())
        return map_data

    def _thermal_erosion(self, terrain, iterations, talus=0.01):
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
                amount = mask * d * 0.01 
                change -= amount 
            terrain += change
        return terrain

    def _hydraulic_erosion(self, terrain, iterations):
        rain_map = np.zeros_like(terrain)
        erosion_map = np.zeros_like(terrain)
        rain_map += 1.0
        for _ in range(20):
            gy, gx = np.gradient(terrain)
            slope = np.sqrt(gx**2 + gy**2)
            erosion_map += slope * rain_map * 0.01
        terrain -= erosion_map * 0.4
        return terrain
