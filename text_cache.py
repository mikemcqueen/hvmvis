from dataclasses import dataclass, field
from typing import Optional, Tuple
import pygame

Color = Tuple[int, int, int]

@dataclass(eq=False)
class RenderedSurface:
    surface: Optional[pygame.Surface] = None
    color: Optional[Color] = None

@dataclass(eq=False)
class RenderedText:
    text: str
    dim: RenderedSurface = field(default_factory=RenderedSurface)
    bright: RenderedSurface = field(default_factory=RenderedSurface)

class TextCache:
    def __init__(self):
        self._cache: dict[str, RenderedText] = {}
    
    def get_rendered_text(self, text: str) -> RenderedText:
        if text not in self._cache:
            self._cache[text] = RenderedText(text)
        return self._cache[text]
    
    def clear(self):
        self._cache.clear()
    
    def size(self) -> int:
        return len(self._cache)