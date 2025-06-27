import pygame

from anim import AnimManager
from freeui import FreeManager
from fonts import fonts
from refui import RefManager
from hvm import *
from text_cache import TextCache

ORANGE = (255, 165, 0)
BRIGHT_ORANGE = (255, 190, 30)
BLACK = (0, 0, 0)
YELLOW = (255, 255, 0)
DIM_YELLOW = (192, 192, 0)

class ItrManager:
    def __init__(self, screen: pygame.Surface, itrs: list[Interaction],
                 ref_mgr: RefManager, anim_mgr: AnimManager, free_mgr: FreeManager,
                 table: dict, text_cache: TextCache):
        self.screen = screen
        self.table = table
        self.itrs = itrs
        self.ref_mgr = ref_mgr
        self.anim_mgr = anim_mgr
        self.free_mgr = free_mgr
        self.text_cache = text_cache
        self.itr_idx = 0
        self.op_idx = 0
        self.rect = self.init_rect(screen)

    def init_rect(self, screen: pygame.Surface) -> pygame.Rect:
        width = 240
        height = 320
        return pygame.Rect(
            screen.get_width() - width,
            screen.get_height() - height,
            width,
            height
        )

    def draw_header(self, surface: pygame.Surface, itr: Interaction):
        title_font = fonts.title
        header_color = ORANGE

        if itr.redex:
            text = f"{itr.name()}  {itr.redex.neg.term}"
            text2 = f"        {itr.redex.pos.term}"
        else:
            text = f"APPREF  Boot Ref"
            text2 = None

        x = self.rect.x + 5
        y = self.rect.y + 5
        surf = title_font.render(text, True, header_color)
        self.screen.blit(surf, (x, y))
        if text2:
            y += self.table['metrics']['line_height'] + self.table['row_spacing']['intra_row']
            surf = title_font.render(text2, True, header_color)
            self.screen.blit(surf, (x, y))

    def draw_memops(self, surface: pygame.Surface, memops: list[MemOp]):
        font = fonts.content
        x = self.rect.x + 5
        y = self.rect.y + 5 + self.table['title_metrics']['line_height'] * 3
        line_height = self.table['metrics']['line_height'] + self.table['row_spacing']['intra_row']
        for i, memop in enumerate(memops):
            text = f"{memop}"
            if i == self.op_idx:
                color = YELLOW if self.anim_mgr.ready else DIM_YELLOW
            else:
                color = ORANGE
            #color = sel_text_color if i == self.op_idx else text_color
            text_surface = font.render(text, True, color)
            surface.blit(text_surface, (x, y))
            y += line_height

    def done(self):
        return self.itr_idx >= len(self.itrs)

    def draw(self):
        if self.done(): return
        itr = self.itrs[self.itr_idx]
        self.draw_header(self.screen, itr)
        self.draw_memops(self.screen, itr.memops)

    def next(self):
        if self.done() or not self.anim_mgr.ready: return False
        itr = self.itrs[self.itr_idx]
        memop = itr.memops[self.op_idx] if self.op_idx < len(itr.memops) else None
        self.op_idx += 1
        if memop:
            self.anim_mgr.animate(memop)
            self.free_mgr.on_memop(memop)
            # execute must be called last
            self.execute(memop)
        else:
            rmvd = self.anim_mgr.remove_waiting()
            self.itr_idx += 1
            self.op_idx = 0
            if self.done(): return False
            itr = self.itrs[self.itr_idx]
            self.on_itr(itr)

        return True

    def on_itr(self, itr: Interaction):
        self.free_mgr.on_itr(itr)
        if isinstance(itr, ExpandRef) and itr.nodes:
            self.ref_mgr.add_ref(itr, "dim terminal")

    def execute(self, memop: MemOp):
        if memop.is_take():
            memop.node.take(memop.loc)
        elif memop.is_swap():
            memop.node.swap(memop.loc)
