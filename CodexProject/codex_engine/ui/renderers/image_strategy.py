import pygame
import numpy as np
from PIL import Image
from codex_engine.config import MAPS_DIR
from codex_engine.utils.spline import calculate_catmull_rom

COLOR_RIVER = (80, 120, 255)
COLOR_ROAD = (160, 82, 45)

class ImageMapStrategy:
    def __init__(self, metadata, theme_manager):
        self.theme = theme_manager
        self.metadata = metadata

        print (f" *** {self.metadata}")
        
        map_path = MAPS_DIR / metadata['file_path']
        print (f" *** {map_path}")
        img = Image.open(map_path)
        self.heightmap = np.array(img, dtype=np.float32) / 65535.0
        
        self.height = self.heightmap.shape[0]
        self.width = self.heightmap.shape[1]
        
        self.real_min = metadata.get('real_min', -11000.0)
        self.real_max = metadata.get('real_max', 9000.0)
        
        self.light_azimuth = 315.0
        self.light_altitude = 45.0
        self.light_intensity = 1.5 
        
    def _get_visible_region(self, cam_x, cam_y, zoom, screen_width, screen_height):

        #print (f" *** _get_visible_region {cam_x} {cam_y} {zoom} {screen_width} {screen_height}")
        visible_map_width = screen_width / zoom
        visible_map_height = screen_height / zoom
        
        x_start = int(max(0, cam_x - visible_map_width / 2))
        x_end = int(min(self.width, cam_x + visible_map_width / 2))
        y_start = int(max(0, cam_y - visible_map_height / 2))
        y_end = int(min(self.height, cam_y + visible_map_height / 2))
        
        buffer = 2
        x_start = max(0, x_start - buffer)
        x_end = min(self.width, x_end + buffer)
        y_start = max(0, y_start - buffer)
        y_end = min(self.height, y_end + buffer)
        
        return x_start, x_end, y_start, y_end
    
    def _calculate_hillshade_region(self, heightmap_region):
        z_factor = 100.0 
        gy, gx = np.gradient(heightmap_region)
        slope = np.arctan(np.sqrt(gx**2 + gy**2) * z_factor)
        aspect = np.arctan2(gy, -gx)
        zenith_rad = np.deg2rad(90 - self.light_altitude)
        azimuth_rad = np.deg2rad(self.light_azimuth)
        shaded = ((np.cos(zenith_rad) * np.cos(slope)) + 
                  (np.sin(zenith_rad) * np.sin(slope) * np.cos(azimuth_rad - aspect)))
        shaded = np.clip(shaded, 0, 1)
        ambient = 0.2
        shaded = ambient + (shaded * (1.0 - ambient))
        shaded = np.clip(shaded * self.light_intensity, 0, 1.2)
        return shaded
    
    def _render_region(self, heightmap_region, sea_level_norm, contour_interval=0):
        h, w = heightmap_region.shape
        hillshade = self._calculate_hillshade_region(heightmap_region)
        rgb_array = np.zeros((h, w, 3), dtype=np.float32)
        
        land_mask = heightmap_region >= sea_level_norm
        water_mask = ~land_mask
        
        mask_green = (heightmap_region >= sea_level_norm) & (heightmap_region < 0.6)
        rgb_array[mask_green] = [100, 160, 100] 
        mask_dark = (heightmap_region >= 0.6) & (heightmap_region < 0.85)
        rgb_array[mask_dark] = [50, 100, 50]
        mask_grey = (heightmap_region >= 0.85) & (heightmap_region < 0.95)
        rgb_array[mask_grey] = [120, 120, 120]
        mask_white = (heightmap_region >= 0.95)
        rgb_array[mask_white] = [255, 255, 255]
        
        if np.any(land_mask):
            rgb_array[land_mask] *= hillshade[land_mask, np.newaxis]
        
        if np.any(water_mask):
            depth = sea_level_norm - heightmap_region
            mask_shore = (depth < 0.02) & water_mask
            rgb_array[mask_shore] = [120, 210, 220] 
            mask_shelf = (depth >= 0.02) & (depth < 0.1) & water_mask
            rgb_array[mask_shelf] = [70, 150, 200]
            mask_ocean = (depth >= 0.1) & (depth < 0.3) & water_mask
            rgb_array[mask_ocean] = [40, 90, 170]
            mask_deep = (depth >= 0.3) & water_mask
            rgb_array[mask_deep] = [20, 40, 100]
            
            water_light = 0.85 + (hillshade[water_mask] * 0.15)
            rgb_array[water_mask] *= water_light[:, np.newaxis]

        if contour_interval > 0:
            height_m = self.real_min + heightmap_region * (self.real_max - self.real_min)
            levels = np.floor(height_m / contour_interval)
            edges = np.zeros_like(levels, dtype=bool)
            edges[:-1, :] |= (levels[:-1, :] != levels[1:, :])
            edges[:, :-1] |= (levels[:, :-1] != levels[:, 1:])
            rgb_array[edges] = [40, 40, 40]
        
        return np.clip(rgb_array, 0, 255).astype(np.uint8)
    
    def draw(self, screen, cam_x, cam_y, zoom, screen_width, screen_height, sea_level_meters=0.0, vectors=None, active_vector=None, selected_point_idx=None, contour_interval=0):
        sea_level_norm = (sea_level_meters - self.real_min) / (self.real_max - self.real_min)

        #print (f" **** **** **** draw {cam_x} {cam_y} {zoom} {screen_width} {screen_height} ")
        
        x_start, x_end, y_start, y_end = self._get_visible_region(cam_x, cam_y, zoom, screen_width, screen_height)
        
        visible_heightmap = self.heightmap[y_start:y_end, x_start:x_end]
        if visible_heightmap.size == 0: return
        
        rgb_array = self._render_region(visible_heightmap, sea_level_norm, contour_interval)
        surface = pygame.surfarray.make_surface(np.transpose(rgb_array, (1, 0, 2)))
        
        region_width = x_end - x_start
        region_height = y_end - y_start
        scaled_width = int(region_width * zoom)
        scaled_height = int(region_height * zoom)
        
        center_x = screen_width // 2
        center_y = screen_height // 2
        
        if scaled_width > 0 and scaled_height > 0:
            scaled_surface = pygame.transform.smoothscale(surface, (scaled_width, scaled_height))
            draw_x = center_x - int(cam_x * zoom) + int(x_start * zoom)
            draw_y = center_y - int(cam_y * zoom) + int(y_start * zoom)
            screen.blit(scaled_surface, (draw_x, draw_y))

        all_vectors = []
        if vectors: all_vectors.extend(vectors)
        if active_vector: all_vectors.append(active_vector)

        for vec in all_vectors:
            # Handle Node structure vs Flat Dict
            props = vec.get('properties', vec)
            
            points = props.get('points', [])
            if not points: continue
            
            v_type = props.get('type', 'road')
            width_val = props.get('width', 4)
            
            color = COLOR_RIVER if v_type == 'river' else COLOR_ROAD
            
            # Highlight active vector
            if active_vector and vec is active_vector:
                color = (255, 255, 0)

            width = max(2, int(width_val * zoom))
            
            screen_pts = []
            for px, py in points:
                sx = center_x - (cam_x * zoom) + (px * zoom)
                sy = center_y - (cam_y * zoom) + (py * zoom)
                screen_pts.append((sx, sy))
            
            if len(screen_pts) > 1:
                curve_pts = calculate_catmull_rom(screen_pts)
                pygame.draw.lines(screen, color, False, curve_pts, width)
            
            if active_vector and vec is active_vector:
                for idx, (sx, sy) in enumerate(screen_pts):
                    pt_color = (255, 0, 0) if idx == selected_point_idx else (255, 255, 255)
                    pygame.draw.circle(screen, pt_color, (sx, sy), 5)
                    pygame.draw.circle(screen, (0,0,0), (sx, sy), 5, 1)

    def set_light_direction(self, azimuth, altitude):
        self.light_azimuth = azimuth; self.light_altitude = altitude
    
    def set_light_intensity(self, intensity):
        self.light_intensity = intensity
    
    def get_object_at(self, world_x, world_y, zoom):
        px = int(world_x); py = int(world_y)
        if 0 <= px < self.width and 0 <= py < self.height:
            raw = self.heightmap[py, px]
            meters = self.real_min + (raw * (self.real_max - self.real_min))
            return {"h_meters": meters}
        return None
