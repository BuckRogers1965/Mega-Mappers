import random
import math

class SimpleNoise:
    """A standalone 2D noise generator for terrain heightmaps."""
    def __init__(self, seed=None):
        if seed: random.seed(seed)
        self.perm = list(range(256))
        random.shuffle(self.perm)
        self.perm += self.perm

    def noise(self, x, y):
        X, Y = int(x) & 255, int(y) & 255
        x, y = x - int(x), y - int(y)
        u, v = self.fade(x), self.fade(y)
        A = self.perm[X] + Y
        B = self.perm[X + 1] + Y
        return self.lerp(v, self.lerp(u, self.grad(self.perm[A], x, y), 
                                         self.grad(self.perm[B], x - 1, y)),
                            self.lerp(u, self.grad(self.perm[A + 1], x, y - 1), 
                                         self.grad(self.perm[B + 1], x - 1, y - 1)))

    def fade(self, t): return t * t * t * (t * (t * 6 - 15) + 10)
    def lerp(self, t, a, b): return a + t * (b - a)
    def grad(self, hash, x, y):
        h = hash & 15
        grad = 1 + (h & 7)
        if h & 8: grad = -grad
        return (grad * x) if (h & 1) == 0 else (grad * y)
    
    def get_octave_noise(self, x, y, octaves=4, persistence=0.5, scale=0.1):
        total = 0
        frequency = scale
        amplitude = 1
        max_value = 0
        for _ in range(octaves):
            total += self.noise(x * frequency, y * frequency) * amplitude
            max_value += amplitude
            amplitude *= persistence
            frequency *= 2
        return total / max_value
