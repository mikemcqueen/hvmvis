import pygame

from anim import AnimManager
from fonts import fonts
from refui import RefManager
from hvm import *

ORANGE = (255, 165, 0)
BRIGHT_ORANGE = (255, 190, 30)
BLACK = (0, 0, 0)
YELLOW = (255, 255, 0)
DIM_YELLOW = (192, 192, 0)

class ItrManager:
    def __init__(self, screen: pygame.Surface, itrs: list[Interaction],
                 ref_mgr: RefManager, anim_mgr: AnimManager, table: dict):
        self.screen = screen
        self.table = table
        self.itrs = itrs
        self.ref_mgr = ref_mgr
        self.anim_mgr = anim_mgr
        self.itr_idx = 0
        self.op_idx = 0
        self.rect = self.init_rect(screen)

    def init_rect(self, screen: pygame.Surface) -> pygame.Rect:
        width = 240
        height = 340
        return pygame.Rect(
            screen.get_width() - width,
            screen.get_height() - height,
            width,
            height
        )
        
    def draw_header(self, surface: pygame.Surface, itr: Interaction):
        # Draw background
        pygame.draw.rect(surface, BLACK, self.rect) # (self.x, self.y, self.width, self.height))
    
        # Draw border
        #border_rect = pygame.Rect(self.x, self.y, self.width, self.height)
        #pygame.draw.rect(surface, border_color, border_rect, table['table_border_thickness'])
    
        """
        # Draw title with background to clip the border
        title_surface = title_font.render(ref_name(self.ref.def_idx), True, header_color)
        title_width = title_surface.get_width()
        title_x = self.x + (self.width - title_width) // 2
        title_y = self.y - title_font.get_height() // 2
    
        title_bg_rect = pygame.Rect(title_x - 5, title_y, title_width + 10, title_font.get_height())
        pygame.draw.rect(surface, BLACK, title_bg_rect)
        surface.blit(title_surface, (title_x, title_y))
    
        # Column headers
        headers = ["MEM", "TAG", "LAB", "LOC"]
        title_bottom = title_y + table['title_metrics']['line_height']
        header_y = title_bottom + table['row_spacing']['title_to_header']
        current_x = self.x + table['col_spacing']['margin']
        """
    
        title_font = fonts.title

        header_color = ORANGE

        if itr.redex:
            text = f"{itr.name()}  {itr.redex.neg.term}"
            text2 = f"        {itr.redex.pos.term}"
        else:
            text = f"APPREF  Boot Redex"
            text2 = None

        x = self.rect.x + 5
        y = self.rect.y + 5
        surf = title_font.render(text, True, header_color)
        self.screen.blit(surf, (x, y))
        if text2:
            y += self.table['metrics']['line_height'] + self.table['row_spacing']['intra_row']
            surf = title_font.render(text2, True, header_color)
            self.screen.blit(surf, (x, y))
            

        # Draw horizontal line under headers
        #line_y = header_y + table['metrics']['line_height'] + table['row_spacing']['header_to_line']
        #line_left = self.x + table['col_spacing']['margin']
        #line_right = self.x + self.width - table['col_spacing']['margin']
        #pygame.draw.line(surface, line_color, (line_left, line_y), (line_right, line_y), 1)

    def draw_memops(self, surface: pygame.Surface, memops: list[MemOp]):
        font = fonts.content

        text_color = ORANGE
        sel_text_color = YELLOW

        x = self.rect.x + 5
        y = self.rect.y + 5 + self.table['title_metrics']['line_height'] * 3
        for i, memop in enumerate(memops):
            text = f"{memop}"
            color = sel_text_color if i == self.op_idx else text_color
            surf = font.render(text, True, color)
            self.screen.blit(surf, (x, y))
            y += self.table['metrics']['line_height'] + self.table['row_spacing']['intra_row']

    def done(self):
        return (
            self.itr_idx >= len(self.itrs)
            #or self.op_idx >= len(self.itrs[self.itr_idx].memops)
        )

    def draw(self):
        if self.done(): return
        itr = self.itrs[self.itr_idx]
        self.draw_header(self.screen, itr)
        self.draw_memops(self.screen, itr.memops)

    def next(self):
        if self.done(): return False
        itr = self.itrs[self.itr_idx];
        memop = itr.memops[self.op_idx] if self.op_idx < len(itr.memops) else None
        self.op_idx += 1
        if memop:
            self.anim_mgr.animate(memop)
            # must call execute *after* animate
            self.execute(memop)
        else:
            self.anim_mgr.remove_waiting()
            self.itr_idx += 1
            self.op_idx = 0
            if self.done(): return False
            itr = self.itrs[self.itr_idx]
            if isinstance(itr, ExpandRef) and itr.nodes:
                # hacky
                if itr.def_idx < 7 or itr.def_idx >= DefIdx.MAT:
                    self.ref_mgr.add_ref(itr, "dim terminal")

        return True

    def execute(self, memop: MemOp):
        if memop.is_take():
            memop.node.take(memop.loc)
        elif memop.is_swap():
            memop.node.swap(memop.loc)
