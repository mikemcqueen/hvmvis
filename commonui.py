from dataclasses import dataclass
from typing import NamedTuple, Optional, Tuple

TITLE_FONT_SIZE = 14
FONT_SIZE = 14

DIM_GREEN = (0, 160, 0)
DIM_YELLOW = (192, 192, 0)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GRAY = (128, 128, 128)
LIGHT_GRAY = (64, 64, 64)
BRIGHT_GREEN = (0, 255, 0)
YELLOW = (255, 255, 0)
BRIGHT_ORANGE = (255, 190, 30)
ORANGE = (255, 165, 0)

Color = Tuple[int, int, int]

class Position(NamedTuple):
    x: int
    y: int

@dataclass
class ScrollMgr:
    width: int = 0
    end_offset: int = 0
    offset: int = 0
    
    def scrolling(self) -> bool:
        return self.width != 0

    def scroll(self, cols: int, table: dict, anim = True):
        if self.scrolling(): return # or (self.offset == 0 and cols > 0): return
        width = -cols * table['layout']['scroll_width']
        if anim:
            self.width = width
            self.end_offset = self.offset + self.width
        else:
            self.offset += width

    def update(self, table: dict):
        if not self.scrolling(): return
        offset = self.width // 10
        self.offset += offset
        if abs(self.offset) >= abs(self.end_offset):
            self.offset = self.end_offset
            self.width = 0

class UI:
    def __init__(self):
        self.scroll_mgr = ScrollMgr()

ui = UI()
    
