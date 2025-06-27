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

"""
class ItrLoc(NamedTuple):
    trm_loc: int
    neg_loc: Optional[int]
"""
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

    def add_itr_loc(self, nod_loc: int, trm_loc: Optional[int] = None,
                    force: Optional[bool] = True):
        # TODO no longer use force
        if force or nod_loc not in self.itr_locs:
            print(f"adding itr_loc[{nod_loc}] = {trm_loc}")
            self.itr_locs[nod_loc] = trm_loc

    def is_neg_loc(self, loc: int) -> bool:
        return (loc & 1) == 0 

    def neg_loc(self, loc: int) -> int:
        return loc if self.is_neg_loc(loc) else loc - 1

    def process_itr_locs(self):
        neg_locs: set[int] = set()
        for nod_loc, trm_loc in self.itr_locs.items():
            nod_refcnt = self.refcnts[nod_loc]
            if nod_refcnt.zero:
                #if self.is_neg_loc(nod_loc):
                neg_locs.add(self.neg_loc(nod_loc))
                if trm_loc == None: continue
                if self.is_neg_loc(nod_loc):
                    # Rule #1
                    """
                    print(f"dec trm_loc {trm_loc} @ neg nod_loc {nod_loc} because nod {nod_refcnt}")
                    if self.loc_decr(trm_loc, "process neg"):
                    """
                    neg_locs.add(self.neg_loc(trm_loc))
                else:
                    # Rule #2
                    neg_loc = nod_loc - 1
                    neg_refcnt = self.refcnts[neg_loc]
                    if neg_refcnt.zero:
                        neg_locs.add(neg_loc)
                        """
                        print(f"dec trm_loc {trm_loc} @ pos nod_loc {nod_loc} because nod,neg is {nod_refcnt},{neg_refcnt}")
                        if self.loc_decr(trm_loc, "process pos"):
                            neg_locs.add(self.neg_loc(trm_loc))
                        """

        while neg_locs:
            neg_loc = neg_locs.pop()
            neg_refcnt = self.refcnts[neg_loc]
            pos_refcnt = self.refcnts[neg_loc + 1]
            total_cnt = neg_refcnt.cnt + pos_refcnt.cnt
            if total_cnt == 0:
                print(f"setting node @ {neg_loc} free because total refcounts are {total_cnt}: {neg_refcnt},{pos_refcnt}")
                assert not neg_refcnt.free
                assert not pos_refcnt.free
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
        print(f"loc_incr loc {loc} to {refcnt} from {src}")
        
    def loc_decr(self, loc: int, src: str) -> bool:
        refcnt = self.refcnts[loc]
        if refcnt.cnt <= 0:
            print(f"loc_decr loc {loc} {refcnt}")
            assert refcnt.cnt > 0
        refcnt.cnt -= 1
        print(f"loc_decr loc {loc} to {refcnt} from {src}")
        return refcnt.zero
        # any time a node loc is decremented to zero, add it to the set of locs
        # to check-if-free at the end of the interaction
        #if refcnt.zero:
        #    self.add_itr_loc(loc, None, False)

    def term_incr(self, term: Term, src: str) -> bool:
        if term.has_loc():
            self.loc_incr(term.loc, src)
            return True
        return False

    def term_decr(self, term: Term, src: str) -> bool:
        if term.has_loc():
            return self.loc_decr(term.loc, src)
        return False

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

        if itr.memops: print("---on_itr---")

        if itr.redex:
            self.redex_pop(itr.redex)
        if isinstance(itr, ExpandRef):
            self.expand_ref(itr)
        for redex in itr.redexes:
            self.redex_push(redex)

    def on_memop(self, memop: MemOp):
        if memop.put:
            nod_refcnt = self.refcnts[memop.loc]
            if memop.is_exch() and not memop.put.has_loc() and nod_refcnt.zero:
                self.add_itr_loc(memop.loc)
            elif self.term_incr(memop.put, f"put {memop.put} to {memop.loc}"):
                if nod_refcnt.zero:
                    self.add_itr_loc(memop.loc, memop.put.loc)
        if memop.got:
            if self.term_decr(memop.got, f"got {memop.got} from {memop.loc}"):
                pass
            """
                got_refcnt = self.refcnts[memop.got.loc]
                if nod_refcnt.zero:
                    self.add_itr_loc(memop.got.loc)
            """

    def boot(self, term: Term):
        assert not self.booted
        self.term_incr(term, "boot")
        self.booted = True
