from abc import ABC, abstractmethod

class MapRenderStrategy(ABC):
    @abstractmethod
    def draw(self, surface, cam_x, cam_y, zoom, screen_w, screen_h): pass
    @abstractmethod
    def get_object_at(self, world_x, world_y, zoom): pass
