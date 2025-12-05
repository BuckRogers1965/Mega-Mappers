import pygame
import numpy as np
from PIL import Image
from codex_engine.config import MAPS_DIR

class ImageMapStrategy:
    def __init__(self, metadata, theme_manager):
        self.theme = theme_manager
        self.metadata = metadata
        
        # Load map
        map_path = MAPS_DIR / metadata['file_path']
        img = Image.open(map_path)
        self.heightmap = np.array(img, dtype=np.float32) / 65535.0
        
        self.height = self.heightmap.shape[0]
        self.width = self.heightmap.shape[1]
        
        self.real_min = metadata.get('real_min', -11000.0)
        self.real_max = metadata.get('real_max', 9000.0)
        
        # Lighting defaults
        self.light_azimuth = 315.0
        self.light_altitude = 45.0
        self.light_intensity = 1.5 # Boosted default intensity
        
    def _get_visible_region(self, cam_x, cam_y, zoom, screen_width, screen_height):
        visible_map_width = screen_width / zoom
        visible_map_height = screen_height / zoom
        
        x_start = int(max(0, cam_x - visible_map_width / 2))
        x_end = int(min(self.width, cam_x + visible_map_width / 2))
        y_start = int(max(0, cam_y - visible_map_height / 2))
        y_end = int(min(self.height, cam_y + visible_map_height / 2))
        
        # Buffer for lighting calculations
        buffer = 2
        x_start = max(0, x_start - buffer)
        x_end = min(self.width, x_end + buffer)
        y_start = max(0, y_start - buffer)
        y_end = min(self.height, y_end + buffer)
        
        return x_start, x_end, y_start, y_end
    
    def _calculate_hillshade_region(self, heightmap_region):
        """
        Standard GIS Hillshade Algorithm.
        """
        # 1. Calculate Slope and Aspect
        # Exaggerate Z to make shadows visible on flat terrain
        z_factor = 100.0 
        
        # Gradients
        gy, gx = np.gradient(heightmap_region)
        
        slope = np.arctan(np.sqrt(gx**2 + gy**2) * z_factor)
        aspect = np.arctan2(gy, -gx)
        
        # 2. Lighting Angles
        zenith_rad = np.deg2rad(90 - self.light_altitude)
        azimuth_rad = np.deg2rad(self.light_azimuth)
        
        # 3. Lambertian Reflectance Formula
        # (Cos(Zenith) * Cos(Slope)) + (Sin(Zenith) * Sin(Slope) * Cos(Azimuth - Aspect))
        shaded = ((np.cos(zenith_rad) * np.cos(slope)) + 
                  (np.sin(zenith_rad) * np.sin(slope) * np.cos(azimuth_rad - aspect)))
        
        # 4. Normalize and Contrast Stretch
        shaded = np.clip(shaded, 0, 1)
        
        # Apply intensity curve to make shadows darker
        # Ambient light floor = 0.2 (Deep shadow)
        ambient = 0.2
        shaded = ambient + (shaded * (1.0 - ambient))
        
        # Intensity boost
        shaded = np.clip(shaded * self.light_intensity, 0, 1.2) # Allow slight overexposure
        
        return shaded
    
    def _render_region(self, heightmap_region, sea_level_norm):
        h, w = heightmap_region.shape
        
        # 1. Compute Shadows
        hillshade = self._calculate_hillshade_region(heightmap_region)
        
        # 2. Define RGB Canvas
        rgb_array = np.zeros((h, w, 3), dtype=np.float32)
        
        # 3. Create Masks
        land_mask = heightmap_region >= sea_level_norm
        water_mask = ~land_mask
        
        # 4. Apply Relief Map Color Scheme
        # Thresholds relative to Land (0.0 to 1.0 above sea level)
        # We need relative height for consistent banding
        # But for global consistency, we use absolute heightmap values
        
        # Green (Lowlands)
        mask_green = (heightmap_region >= sea_level_norm) & (heightmap_region < 0.6)
        rgb_array[mask_green] = [100, 160, 100] 
        
        # Dark Green (Midlands / Forest)
        mask_dark = (heightmap_region >= 0.6) & (heightmap_region < 0.85)
        rgb_array[mask_dark] = [50, 100, 50]
        
        # Grey (Mountains)
        mask_grey = (heightmap_region >= 0.85) & (heightmap_region < 0.95)
        rgb_array[mask_grey] = [120, 120, 120]
        
        # White (Peaks)
        mask_white = (heightmap_region >= 0.95)
        rgb_array[mask_white] = [255, 255, 255]
        
        # 5. Apply Lighting to Land
        if np.any(land_mask):
            # Multiply color by shadow map
            rgb_array[land_mask] *= hillshade[land_mask, np.newaxis]
        
        # 6. Water Rendering (Blue Gradient)
        if np.any(water_mask):
            depth = sea_level_norm - heightmap_region
            
            # Zone 1: Shore / Shallows (Turquoise) - Depth 0% to 2%
            mask_shore = (depth < 0.02) & water_mask
            rgb_array[mask_shore] = [120, 210, 220] 

            # Zone 2: Continental Shelf (Light Blue) - Depth 2% to 10%
            mask_shelf = (depth >= 0.02) & (depth < 0.1) & water_mask
            rgb_array[mask_shelf] = [70, 150, 200]

            # Zone 3: Open Ocean (Medium Blue) - Depth 10% to 30%
            mask_ocean = (depth >= 0.1) & (depth < 0.3) & water_mask
            rgb_array[mask_ocean] = [40, 90, 170]

            # Zone 4: Deep Ocean (Navy) - Depth 30% to 60%
            mask_deep = (depth >= 0.3) & (depth < 0.6) & water_mask
            rgb_array[mask_deep] = [20, 40, 100]

            # Zone 5: The Abyss (Dark Indigo/Black) - Depth 60%+
            mask_abyss = (depth >= 0.6) & water_mask
            rgb_array[mask_abyss] = [10, 10, 40]
            
            # Apply Water Lighting (Subtle Gloss)
            # Water is flatter, so we mix less shadow in (0.2 impact vs 1.0 on land)
            water_light = 0.85 + (hillshade[water_mask] * 0.15)
            rgb_array[water_mask] *= water_light[:, np.newaxis]
        
        return np.clip(rgb_array, 0, 255).astype(np.uint8)
    
    def draw(self, screen, cam_x, cam_y, zoom, screen_width, screen_height, sea_level_meters=0.0):
        # Normalize sea level
        sea_level_norm = (sea_level_meters - self.real_min) / (self.real_max - self.real_min)
        
        x_start, x_end, y_start, y_end = self._get_visible_region(
            cam_x, cam_y, zoom, screen_width, screen_height
        )
        
        visible_heightmap = self.heightmap[y_start:y_end, x_start:x_end]
        if visible_heightmap.size == 0: return
        
        rgb_array = self._render_region(visible_heightmap, sea_level_norm)
        surface = pygame.surfarray.make_surface(np.transpose(rgb_array, (1, 0, 2)))
        
        region_width = x_end - x_start
        region_height = y_end - y_start
        scaled_width = int(region_width * zoom)
        scaled_height = int(region_height * zoom)
        
        if scaled_width > 0 and scaled_height > 0:
            scaled_surface = pygame.transform.smoothscale(surface, (scaled_width, scaled_height))
            
            center_x = screen_width // 2
            center_y = screen_height // 2
            
            draw_x = center_x - int(cam_x * zoom) + int(x_start * zoom)
            draw_y = center_y - int(cam_y * zoom) + int(y_start * zoom)
            
            screen.blit(scaled_surface, (draw_x, draw_y))
    
    def set_light_direction(self, azimuth, altitude):
        self.light_azimuth = azimuth
        self.light_altitude = altitude
    
    def set_light_intensity(self, intensity):
        self.light_intensity = intensity
    
    def get_object_at(self, world_x, world_y, zoom):
        px = int(world_x)
        py = int(world_y)
        if 0 <= px < self.width and 0 <= py < self.height:
            raw = self.heightmap[py, px] # Already normalized 0-1
            meters = self.real_min + (raw * (self.real_max - self.real_min))
            return {"h_meters": meters}
        return None
