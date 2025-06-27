import pygame

from anim import AnimManager
from fonts import fonts
from hvm import *
#from refui import RefManager
#from text_cache import TextCache

ORANGE = (255, 165, 0)
BRIGHT_ORANGE = (255, 190, 30)
YELLOW = (255, 255, 0)
DIM_YELLOW = (192, 192, 0)
DIM_GREEN = (0, 160, 0)

class FreeManager:
    def __init__(self, screen: pygame.Surface, table: dict):
        self.surface = screen
        self.table = table
        self.counts = [0] * 320
        self.rect = table['free']['rect']
        self.booted = False

    def draw(self):
        font = fonts.content
        x = self.rect.x + 5
        cnt_off_x = (self.table['metrics']['char_width'] * 4  # '000:'
                     #self.table['metrics']['half_char']
                     )
        top = self.rect.y  # + self.table['title_metrics']['line_height'] * 3
        y = top
        row_cnt = None
        line_height = self.table['metrics']['line_height'] + self.table['row_spacing']['intra_row']
        for i, count in enumerate(self.counts):
            loc = f"{i:>3}:"
            cnt = f"{count:<2}"
            clr = DIM_YELLOW
            loc_sfc = font.render(loc, True, clr)
            self.surface.blit(loc_sfc, (x, y))
            cnt_sfc = font.render(cnt, True, DIM_GREEN)
            self.surface.blit(cnt_sfc, (x + cnt_off_x, y))
            y += line_height
            if y + line_height > self.rect.bottom:
                if not row_cnt:
                    row_cnt = i - 1
                y = top
                x += self.table['free']['col_width'] + self.table['free']['col_spacing']
                if i + row_cnt < 99:
                    x -= self.table['metrics']['char_width']
                if x + self.table['free']['col_width'] > self.rect.right:
                    break

    def incr(self, loc: int):
        self.counts[loc] += 1
        
    def decr(self, loc: int):
        self.counts[loc] -= 1

    def term_incr(self, term: Term):
        if term.has_loc():
            self.incr(term.loc)

    def term_decr(self, term: Term):
        if term.has_loc():
            self.decr(term.loc)

    def redex_push(self, redex: Redex):
        self.term_incr(redex.neg.term)
        self.term_incr(redex.pos.term)

    def redex_pop(self, redex: Redex):
        self.term_decr(redex.neg.term)
        self.term_decr(redex.pos.term)

    def expand_ref(self, ref: ExpandRef):
        for node in ref.nodes:
            for nod_trm in (node.neg, node.pos):
                self.term_incr(nod_trm.term)

    def on_itr(self, itr: Interaction):
        loc = 16
        if itr.redex: # root itr has no redex
            self.redex_pop(itr.redex)
        if isinstance(itr, ExpandRef):
            self.expand_ref(itr)
        for redex in itr.redexes:
            self.redex_push(redex)

    def on_memop(self, memop: MemOp):
        if memop.put:
            self.term_incr(memop.put)
        if memop.got:
            self.term_decr(memop.got)

    def boot(self, term: Term):
        assert not self.booted
        self.term_incr(term)
        self.booted = True
