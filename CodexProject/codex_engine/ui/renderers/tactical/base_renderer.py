import pygame
import random

# Common aesthetic constants
COLOR_PARCHMENT = (245, 235, 215)
COLOR_INK = (40, 30, 20)
COLOR_GRID = (220, 210, 190)

class BaseTacticalRenderer:
    def __init__(self, node_data, cell_size):
        self.node = node_data
        properties = node_data.get('properties', {})
        self.geometry = properties['geometry']
        self.grid_data = self.geometry['grid']
        self.width = self.geometry['width']
        self.height = self.geometry['height']
        self.cell_size = cell_size

    def render(self):
        """Creates and returns a pygame.Surface for the static map."""
        sc = self.cell_size
        map_w, map_h = self.width * sc, self.height * sc
        
        # 1. Common Setup (Parchment background)
        surface = pygame.Surface((map_w, map_h))
        surface.fill(COLOR_PARCHMENT)

        # 2. Add texture noise
        for _ in range(int(map_w * map_h * 0.001)): 
            x, y = random.randint(0, map_w-1), random.randint(0, map_h-1)
            c = random.randint(10, 20)
            base = surface.get_at((x,y))
            new_color = (max(0, base[0]-c), max(0, base[1]-c), max(0, base[2]-c))
            surface.set_at((x, y), new_color)
        
        return surface
