from dataclasses import dataclass
from typing import NamedTuple, Optional

import pygame

from anim import AnimManager
from fonts import fonts
from hvm import *
from refui import RefManager
#from text_cache import TextCache

ORANGE = (255, 165, 0)
BRIGHT_ORANGE = (255, 190, 30)
YELLOW = (255, 255, 0)
DIM_YELLOW = (192, 192, 0)
DIM_GREEN = (0, 160, 0)

@dataclass(eq=False)
class RefCount:
    cnt: int
    free: bool

    @property
    def zero(self) -> bool: return self.cnt == 0

class FreeManager:
    def __init__(self, screen: pygame.Surface, ref_mgr: RefManager, table: dict):
        self.surface = screen
        self.ref_mgr = ref_mgr
        self.table = table
        self.rect = table['free']['rect']
        self.refcnts: list[RefCount] = [RefCount(0, False) for _ in range(320)]
        self.booted = False
        self.end_loc = 0
        self.itr_locs: dict[int, Optional[int]] = {}
        self.logging = False

    def log(self, msg: str):
        if self.logging:
            print(msg)

    def draw(self):
        if self.end_loc < 3: return
        font = fonts.content
        loc_x = self.rect.x + 5
        cnt_off_x = self.table['metrics']['char_width'] * 4
        top = self.rect.y
        y = top
        row_cnt = None
        line_height = self.table['metrics']['line_height'] + self.table['row_spacing']['intra_row']
        for i in range(2, self.end_loc, 2):
            neg_refcnt = self.refcnts[i]
            pos_refcnt = self.refcnts[i + 1]
            free = neg_refcnt.free and pos_refcnt.free
            loc = f"{i:>3}:"
            cnt = f"{neg_refcnt.cnt} {pos_refcnt.cnt}"

            clr = ORANGE if free else DIM_YELLOW
            loc_sfc = font.render(loc, True, clr)
            self.surface.blit(loc_sfc, (loc_x, y))

            clr = ORANGE if free else DIM_GREEN
            cnt_sfc = font.render(cnt, True, clr)
            self.surface.blit(cnt_sfc, (loc_x + cnt_off_x, y))

            y += line_height
            if y + line_height > self.rect.bottom:
                if not row_cnt:
                    row_cnt = i - 1
                y = top
                loc_x += self.table['free']['col_width'] + self.table['free']['col_spacing']
                if i + row_cnt < 99:
                    loc_x -= self.table['metrics']['char_width']
                if loc_x + self.table['free']['col_width'] > self.rect.right:
                    break

    def add_itr_loc(self, nod_loc: int, trm_loc: Optional[int] = None):
        self.log(f"adding itr_loc[{nod_loc}] = {trm_loc}")
        self.itr_locs[nod_loc] = trm_loc

    def is_neg_loc(self, loc: int) -> bool:
        return (loc & 1) == 0 

    def neg_loc(self, loc: int) -> int:
        return loc if self.is_neg_loc(loc) else loc - 1

    def process_itr_locs(self):
        neg_locs: set[int] = set()
        for nod_loc, trm_loc in self.itr_locs.items():
            nod_refcnt = self.refcnts[nod_loc]
            if not nod_refcnt.zero:
                continue
            neg_locs.add(self.neg_loc(nod_loc))
            if trm_loc and self.is_neg_loc(nod_loc):
                neg_locs.add(self.neg_loc(trm_loc))

        while neg_locs:
            neg_loc = neg_locs.pop()
            neg_refcnt = self.refcnts[neg_loc]
            pos_refcnt = self.refcnts[neg_loc + 1]
            total_cnt = neg_refcnt.cnt + pos_refcnt.cnt
            if total_cnt != 0:
                continue
            
            self.log(f"freeing node @ {neg_loc} total {total_cnt} {neg_refcnt} {pos_refcnt}")
            assert not (neg_refcnt.free or pos_refcnt.free)
            neg_refcnt.free = True
            pos_refcnt.free = True

            node = self.ref_mgr.ref_at(neg_loc).node_at(neg_loc)
            for loc in (neg_loc, neg_loc + 1):
                term = node.term_at(loc)
                trm_loc = term.loc if term and term.has_loc() else None
                if trm_loc and self.loc_decr(trm_loc, "process term"):
                    neg_locs.add(self.neg_loc(trm_loc))

    def loc_incr(self, loc: int, src: str):
        refcnt = self.refcnts[loc]
        refcnt.cnt += 1
        self.log(f"loc_incr loc {loc} to {refcnt} from {src}")
        
    def loc_decr(self, loc: int, src: str) -> bool:
        refcnt = self.refcnts[loc]
        assert refcnt.cnt > 0, f"loc_decr loc {loc} {refcnt}"
        refcnt.cnt -= 1
        self.log(f"loc_decr loc {loc} to {refcnt} from {src}")
        return refcnt.zero

    def term_incr(self, term: Term, src: str):
        if term.has_loc():
            self.loc_incr(term.loc, src)

    def term_decr(self, term: Term, src: str):
        if term.has_loc():
            self.loc_decr(term.loc, src)

    def redex_push(self, redex: Redex):
        self.term_incr(redex.neg.term, "redex push")
        self.term_incr(redex.pos.term, "redex push")

    def redex_pop(self, redex: Redex):
        self.term_decr(redex.neg.term, "redex pop")
        self.term_decr(redex.pos.term, "redex pop")

    def expand_ref(self, ref: ExpandRef):
        for node in ref.nodes:
            for nod_trm in (node.neg, node.pos):
                self.term_incr(nod_trm.term, "expand ref")
        if ref.nodes:
            self.end_loc = ref.last_loc + 1

    def on_itr(self, itr: Interaction):
        self.process_itr_locs()
        self.itr_locs = {}

        if itr.memops: self.log("---on_itr---")

        if itr.redex:
            self.redex_pop(itr.redex)
        if isinstance(itr, ExpandRef):
            self.expand_ref(itr)
        for redex in itr.redexes:
            self.redex_push(redex)

    def on_memop(self, memop: MemOp):
        if memop.put:
            self.term_incr(memop.put, f"put {memop.put} to {memop.loc}")
            nod_refcnt = self.refcnts[memop.loc]
            if nod_refcnt.zero:
                self.add_itr_loc(memop.loc,
                                 memop.put.loc if memop.put.has_loc() else None)
        if memop.got:
            self.term_decr(memop.got, f"got {memop.got} from {memop.loc}")

    def boot(self, term: Term):
        assert not self.booted
        self.term_incr(term, "boot")
        self.booted = True
