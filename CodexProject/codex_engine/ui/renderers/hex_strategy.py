import math
import pygame
from .base import MapRenderStrategy

class HexMapStrategy(MapRenderStrategy):
    def __init__(self, hex_data, metadata, theme):
        self.hex_data = hex_data
        self.metadata = metadata
        self.theme = theme

    def _axial_to_pixel(self, q, r, size):
        x = size * (3/2 * q)
        y = size * (math.sqrt(3)/2 * q + math.sqrt(3) * r)
        return x, y

    def _pixel_to_axial(self, x, y, size):
        q = (2./3 * x) / size
        r = (-1./3 * x + math.sqrt(3)/3 * y) / size
        return self._axial_round(q, r)

    def _axial_round(self, q, r):
        x, y, z = q, r, -q-r
        rx, ry, rz = round(x), round(y), round(z)
        x_diff, y_diff, z_diff = abs(rx - x), abs(ry - y), abs(rz - z)
        if x_diff > y_diff and x_diff > z_diff: rx = -ry - rz
        elif y_diff > z_diff: ry = -rx - rz
        return int(rx), int(ry)

    def draw(self, surface, cam_x, cam_y, zoom, screen_w, screen_h, sea_level=0.0):
        center_x, center_y = screen_w // 2, screen_h // 2
        
        for key, h in self.hex_data.items():
            height = h.get('h', 0.0)
            
            # --- FIXED LOGIC ---
            # Use <= so that if slider is 1.0 and height is 1.0, it is underwater.
            if height <= sea_level:
                # WATER
                # Visual depth: Deeper water is darker
                # Avoid negative colors if sea_level is very low
                dist = max(0.0, sea_level - height)
                
                # Simple blue gradient
                blue = int(255 - (dist * 200))
                blue = max(50, min(255, blue))
                color = (0, 0, blue)
            else:
                # LAND
                grey = int(height * 255)
                color = (grey, grey, grey)

            # Projection
            px, py = self._axial_to_pixel(h['q'], h['r'], zoom)
            draw_x = px - cam_x + center_x
            draw_y = py - cam_y + center_y
            
            if draw_x < -zoom or draw_x > screen_w + zoom: continue
            if draw_y < -zoom or draw_y > screen_h + zoom: continue
            
            points = []
            for i in range(6):
                angle = math.pi / 3 * i
                points.append((
                    draw_x + zoom * math.cos(angle),
                    draw_y + zoom * math.sin(angle)
                ))
            
            pygame.draw.polygon(surface, color, points)

    def get_object_at(self, world_x, world_y, zoom):
        q, r = self._pixel_to_axial(world_x, world_y, zoom)
        key = f"{q},{r}"
        return self.hex_data.get(key)
