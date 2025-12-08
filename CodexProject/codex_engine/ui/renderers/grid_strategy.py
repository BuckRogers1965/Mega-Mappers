import pygame
import math
from .base import MapRenderStrategy

# TILE PALETTE (Value -> Color)
TILES = {
    0: (20, 20, 30),    # VOID / BACKGROUND
    1: (150, 140, 130), # FLOOR (Stone)
    2: (100, 80, 60),   # WALL (Wood/Stone mix)
    3: (80, 120, 200),  # WATER
    4: (160, 82, 45)    # DOOR
}

class GridMapStrategy(MapRenderStrategy):
    def __init__(self, node_data, theme):
        self.node = node_data
        self.theme = theme
        
        # Geometry Data holds the grid
        geo = node_data.get('geometry_data', {})
        self.grid = geo.get('grid', []) 
        self.width = geo.get('width', 20)
        self.height = geo.get('height', 20)
        self.cell_size = 32 # Base pixels per tile

    def draw(self, surface, cam_x, cam_y, zoom, screen_w, screen_h, active_brush=None, **kwargs):
        center_x, center_y = screen_w // 2, screen_h // 2
        
        # Calculate scaled cell size
        sc = self.cell_size * zoom
        
        # Cull visible range
        start_col = int(max(0, (cam_x - (screen_w/2)/zoom)))
        end_col = int(min(self.width, (cam_x + (screen_w/2)/zoom) + 1))
        start_row = int(max(0, (cam_y - (screen_h/2)/zoom)))
        end_row = int(min(self.height, (cam_y + (screen_h/2)/zoom) + 1))

        # 1. Draw Grid
        for r in range(start_row, end_row):
            for c in range(start_col, end_col):
                # Calculate Screen Coords
                # (c, r) is world space. 
                screen_x = center_x + (c - cam_x) * sc
                screen_y = center_y + (r - cam_y) * sc
                
                # Get Tile Value
                try:
                    val = self.grid[r][c]
                except IndexError:
                    val = 0
                
                color = TILES.get(val, (255, 0, 255))
                
                # Draw Tile
                rect = pygame.Rect(screen_x, screen_y, sc + 1, sc + 1) # +1 to prevent gaps
                pygame.draw.rect(surface, color, rect)
                
                # Draw Grid Lines (optional, makes it look "Tactical")
                pygame.draw.rect(surface, (50, 50, 60), rect, 1)

    def get_object_at(self, world_x, world_y, zoom):
        # Convert world float coords to grid integer coords
        c = int(world_x)
        r = int(world_y)
        if 0 <= c < self.width and 0 <= r < self.height:
            return {"grid_pos": (c, r), "tile_val": self.grid[r][c]}
        return None
