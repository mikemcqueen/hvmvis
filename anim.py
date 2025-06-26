from dataclasses import dataclass, field
import time
from typing import List, Tuple, Optional, NamedTuple

import pygame

from commonui import *
from hvm import MemOp, Term, Interaction
from refui import * #RefManager, RefRect
from fonts import fonts
from text_cache import TextCache

# Animation constants
durations: dict[str, float] = {
    'fade_in':      0.2,
    'slide_out':    0.3,
    'slide_to_top': 0.3,
    'slide_over':   0.4, # _on_top
    'slide_to_loc': 0.5,
    'slide_in':     0.3,
    'fade_out':     0.2,
    'wait':         0.0
}

class Phase(NamedTuple):
    name: str
    duration: float
    total: float

    @classmethod
    def make_list(cls, *names: str) -> list['Phase']:
        phases: list['Phase'] = []
        return cls.append(phases, *names)
        """
        total = 0.0
        for name in names:
            duration = durations[name]
            total += duration
            phases.append(cls(name, duration, total))
        return phases
        """

    @classmethod
    def append(cls, phases: list['Phase'], *names: str) -> list['Phase']:
        total = 0.0 if not phases else phases[-1].total
        for name in names:
            duration = durations[name]
            total += duration
            phases.append(cls(name, duration, total))
        return phases

# TODO: add to table metrics
# or, you know, just add char width to table.x + table.width and
# subtract from starting pos
def slide_right_distance(table: dict) -> int:
    return (
        table['term_width'] +
        table['col_spacing']['margin'] +
        #table['table_border_thickness'] +
        table['metrics']['char_width']
    )

def term_x_pos(rect: RefRect, table: dict) -> int:
    # table['term_offset_x']
    return (
        rect.x +
        #table['table_border_thickness'] +
        table['col_spacing']['margin'] +
        table['column_widths'][0]  +        # Add MEM column width
        table['col_spacing']['mem_term']    # Add MEM to Term spacing
    )

def term_y_pos(rect: RefRect, loc: int, table: dict) -> Optional[int]:
    for i, node in enumerate(rect.ref.nodes):
        for j, nod_trm in enumerate((node.neg, node.pos)):
            if loc == nod_trm.mem_loc:
                return (rect.y + table['top_row_y'] + (i * 2 + j) *
                    (table['metrics']['line_height'] +
                     table['row_spacing']['intra_row'])
                )
    return None

@dataclass
class AnimState:
    nod_trm: NodeTerm
    itr: Interaction
    beg_pos: Position
    phases: list[Phase]

    to_rect: Optional[RefRect] = None
    to_loc: int = 0
    from_rect: Optional[RefRect] = None
    phase: int = 0
    cur_pos: Optional[Position] = None
    end_pos: Optional[Position] = None
    alpha: float = 255
    color: Optional[Color] = None
    start_time: float = field(default_factory=time.monotonic)
    #subs: list['AnimState'] = field(default_factory=list)
    #in_flight: bool = False

    def phase_name(self):
        return self.phases[self.phase].name

    def waiting(self):
        return self.phase_name() == 'wait'

    def reset_phases(self):
        self.start_time = time.monotonic()
        self.phases = []
        self.phase = 0

    def has_last_wait_phase(self) -> bool:
        return self.phases and self.phases[-1].name == 'wait'

    def on_last_phase(self) -> bool:
        return self.phase == len(self.phases) - 1

    def remove_last_wait_phase(self):
        if self.has_last_wait_phase():
            if self.on_last_phase():
                self.reset_phases()
            else:
                self.phases = self.phases[:-1]

    def fractional_x(self, fraction: float) -> float:
        return self.beg_pos.x + (self.end_pos.x - self.beg_pos.x) * fraction

    def slide_over_end_pos(self, rect: RefRect, table: dict) -> Position:
        # TODO: support slide-in-from-left, maybe
        slide_distance = slide_right_distance(table)
        return Position(term_x_pos(rect, table) + slide_distance, table['top'])

    def slide_out_end_pos(self, table: dict) -> Position:
        # TODO: support slide-out-to-left, maybe
        if self.cur_pos.x > self.from_rect.x:
            dist = slide_right_distance(table)
        else:
            # TODO: fix
            assert False
        return Position(self.beg_pos.x + dist, self.beg_pos.y)

    """
    def subscribe(self, anim: 'AnimState'):
        assert self != anim
        if not self.in_flight:
            phases = Phase.make_list('wait')
            phases.extend(self.phases)
            self.phases = phases
        anim.add_subscriber(self)

    def add_subscriber(self, anim: 'AnimState') -> bool:
        print(f"term {anim.term}:{anim.itr.idx} waiting on {self.term}:{self.itr.idx}")
        self.subs.append(anim)
        return True

    def notify(self) -> Optional['AnimState']:
        if not self.subs: return None
        anim = self.subs[0]
        other = self.subs[1:]
        self.subs = []
        if anim.phase + 1 >= len(anim.phases) or not anim.waiting():
            print(f"ERROR term {anim.term}:{anim.itr.idx} was waiting on {self.term}:{self.itr.idx}")
            print(f"      now on phase {anim.phase} of {len(anim.phases)}")
            phase = anim.phases[anim.phase] if anim.phase < len(anim.phases) else 'complete'
            print(f"      phase0: {anim.phases[0]} phase: {phase}")
            assert anim.phase + 1 < len(anim.phases) and anim.waiting()
        total = anim.phases[anim.phase].total
        anim.phase += 1
        anim.start_time = time.monotonic() + total
        print(f"term {self.term}:{self.itr.idx} notifying {anim.term}:{anim.itr.idx}")
        if other:
            print(f"  adding {len(other)} subs to {anim.term}:{anim.itr.idx}")
            anim.subs.extend(other)
        return anim
    """

def ease_in_out_cubic(t: float) -> float:
    if t < 0.5:
        return 4 * t * t * t
    else:
        return 1 - pow(-2 * t + 2, 3) / 2

def interpolate_color(color1: Color, color2: Color, t: float) -> Color:
    color = (
        int(color1[0] + (color2[0] - color1[0]) * t),
        int(color1[1] + (color2[1] - color1[1]) * t),
        int(color1[2] + (color2[2] - color1[2]) * t)
    )
    return tuple(max(0, min(255, x)) for x in color)

class AnimManager:
    def __init__(self, screen: pygame.Surface, ref_mgr: RefManager, table: dict, text_cache: TextCache):
        self.screen = screen
        self.ref_mgr = ref_mgr
        self.table = table
        self.text_cache = text_cache
        self.anims: List[AnimState] = []
        self.ready: bool = True
        #self.loc_map: dict[int, AnimState] = {}

    def add(self, anim: AnimState):
        if not anim.cur_pos:
            anim.cur_pos = anim.beg_pos
        self.anims.append(anim)

    def update_state(self, anim: AnimState, current_time: float) -> bool:
        phase = anim.phases[anim.phase]
        if phase.name == 'wait':
            return False

        #anim.in_flight = True

        elapsed = current_time - anim.start_time

        speed = max(0.1, (5 - (self.table['speed'] - 1)) * 0.2)

        phase_start = (phase.total - phase.duration) * speed
        phase_elapsed = elapsed - phase_start

        # Check if we need to advance to next phase
        if phase_elapsed >= phase.duration * speed:
            # could happen.
            assert anim.end_pos
            anim.beg_pos = anim.end_pos
            anim.cur_pos = anim.beg_pos
            anim.end_pos = None
            # Move to next phase if available
            if anim.phase + 1 < len(anim.phases):
                anim.phase += 1
                phase = anim.phases[anim.phase]
                if phase.name == 'wait':
                    return False
                phase_start = (phase.total - phase.duration) * speed
                phase_elapsed = elapsed - phase_start
            else:
                anim.phase = len(anim.phases)
                # Animation done
                return True

        t = float(phase_elapsed) / (phase.duration * speed)

        # Apply phase-specific transformations
        phase_name = phase.name
        if phase_name == 'fade_in':
            if not anim.end_pos:
                anim.end_pos = anim.beg_pos
            anim.color = interpolate_color(anim.color, BRIGHT_GREEN, t)

        elif phase_name == 'slide_in':
            if not anim.end_pos:
                anim.end_pos = Position(term_x_pos(anim.to_rect, self.table), anim.beg_pos.y)
            t_eased = ease_in_out_cubic(t)
            anim.cur_pos = Position(anim.fractional_x(t_eased), anim.cur_pos.y)
            anim.color = BRIGHT_GREEN

        elif phase_name == 'slide_out':
            if not anim.end_pos:
                anim.end_pos = anim.slide_out_end_pos(self.table)
            t_eased = ease_in_out_cubic(t)
            anim.cur_pos = Position(anim.fractional_x(t_eased), anim.cur_pos.y)
            anim.color = BRIGHT_GREEN

        elif phase_name == 'slide_to_top':
            if not anim.end_pos:
                anim.end_pos = Position(anim.beg_pos.x, self.table['top'])
            t_eased = ease_in_out_cubic(t)
            from_y = anim.beg_pos.y
            to_y = self.table['top']
            #vert_slide_pos
            anim.cur_pos = Position(anim.cur_pos.x, from_y + (to_y - from_y) * t_eased)
            anim.color = BRIGHT_GREEN

        elif phase_name == 'slide_over':
            if not anim.end_pos:
                if not anim.to_rect:
                    print(f"anim: {anim}")
                anim.end_pos = anim.slide_over_end_pos(anim.to_rect, self.table)
            t_eased = ease_in_out_cubic(t)
            #horz_slide_pos
            anim.cur_pos = Position(anim.fractional_x(t_eased), anim.cur_pos.y)
            anim.color = BRIGHT_GREEN

        elif phase_name == 'slide_to_loc':
            if not anim.end_pos:
                anim.end_pos = Position(anim.beg_pos.x, term_y_pos(anim.to_rect, anim.to_loc, self.table))
            t_eased = ease_in_out_cubic(t)
            from_y = anim.beg_pos.y
            to_y = anim.end_pos.y
            #vert_slide_pos
            anim.cur_pos = Position(anim.cur_pos.x, from_y + (to_y - from_y) * t_eased)
            anim.color = BRIGHT_GREEN

        elif phase_name == 'fade_out':
            if not anim.end_pos:
                anim.end_pos = anim.beg_pos
            anim.color = interpolate_color(BRIGHT_GREEN, DIM_GREEN, t)
            if anim.to_rect:
                to_nod = anim.to_rect.get_node_term(anim.to_loc).node
                to_nod.set(anim.to_loc, anim.nod_trm)
                anim.to_rect = None
                """
                next_anim = anim.notify()
                if next_anim:
                    self.loc_map[anim.to_loc] = next_anim
                else:
                    del self.loc_map[anim.to_loc] #.pop(anim.to_loc, None)
                """

        elif phase_name == 'wait':
            if not anim.end_pos:
                anim.end_pos = anim.beg_pos

        # Animation continues
        return False

    def draw(self, surface: pygame.Surface, anim: AnimState, font: pygame.font.Font):
        if anim.phase == len(anim.phases):
            return

        # TODO: dumb to calculate this every time, they don't change
        col_positions = []
        pos_x = 0
        for i in range(1, len(self.table['column_widths'])):
            col_positions.append(pos_x)
            if i < 3:  # Don't add spacing after the last column
                pos_x += (
                    self.table['column_widths'][i] +
                    self.table['col_spacing_by_index'][i + 1]
                )

        # Draw each field of the term (TAG, LAB, LOC)
        term = anim.nod_trm
        term_data = (
            term.tag[:3],
            f"{term.lab:03d}",
            f"{term.loc:03d}"
        )
        offset = ui.scroll_mgr.offset
        pos = Position(anim.cur_pos.x + offset, anim.cur_pos.y)
        for i, (value, col_x) in enumerate(zip(term_data, col_positions)):
            if anim.color in (DIM_GREEN, BRIGHT_GREEN, ORANGE, BRIGHT_ORANGE):
                # Use cache for standard colors
                rndr_txt = self.text_cache.get_rendered_text(value)

                if anim.color in (BRIGHT_GREEN, BRIGHT_ORANGE):
                    if not rndr_txt.brt.surface or rndr_txt.brt.color != anim.color:
                        rndr_txt.brt.surface = font.render(value, True, anim.color)
                        rndr_txt.brt.color = anim.color
                    txt_surf = rndr_txt.brt.surface
                else:
                    if not rndr_txt.dim.surface or rndr_txt.dim.color != anim.color:
                        rndr_txt.dim.surface = font.render(value, True, anim.color)
                        rndr_txt.dim.color = anim.color
                    txt_surf = rndr_txt.dim.surface
            else:
                # Render directly for interpolated colors
                txt_surf = font.render(value, True, anim.color)
            
            surface.blit(txt_surf, (pos.x + col_x, pos.y))

    def slide_out(self, term: Term, rect: RefRect, memop: MemOp) -> AnimState:
        nod_trm = memop.node.get(memop.loc)
        if term != nod_trm.term:
            print(f"{term} {nod_trm} memops {nod_trm.memops}")
        assert term == nod_trm.term

        if not rect: return None

        x = term_x_pos(rect, self.table)
        y = term_y_pos(rect, memop.loc, self.table)
        if y is None: return None

        last_phase = 'fade_out' if term.tag == 'SUB' else 'wait'
        phases = ['fade_in', 'slide_out', last_phase]
        anim = AnimState(nod_trm.copy(), memop.itr, Position(x, y),
                         Phase.make_list(*phases), from_rect = rect,
                         color = DIM_GREEN)
        """
        if loc in self.loc_map:
            active = self.loc_map[loc]
            anim.subscribe(active)
        """
        self.add(anim)
        return anim

    def take(self, memop: MemOp):
        rect = self.ref_mgr.get_rect(memop.node.ref)
        self.slide_out(memop.got, rect, memop)

    # NOTE this is unpredictable if two terms exist with same fields
    # TODO: can this be changed to use NodeTerm?
    def find_anim(self, term: Term, itr: Interaction) -> AnimState:
        found = None
        for anim in self.anims:
            if itr.idx == anim.itr.idx and term == anim.nod_trm.term:
                if found:
                    print(f"found 2 x {term}:{itr.idx} @ {itr.name()}")
                    assert not found
                found = anim
        return found

    # a term was either emergent in code, or was taken from a non-visible ref,
    # or was taken from the current redex. make it "appear out of nowhere"
    def manifest(self, term: Term, itr: Interaction) -> AnimState:
        # was term from redex?
        nod_trm = itr.redex.get_node_term(term)
        # TODO:
        #   was a "emergent" term (such as VAR in MATU32)
        #   came from hidden ref
        #assert nod_trm, f"no node term for {term}"
        if not nod_trm:
            nod_trm = NodeTerm(term)

        x = (self.screen.get_width() - self.table['term_width']) // 2
        y = self.table['top']
        anim = AnimState(nod_trm.copy(), itr, Position(x, y),
                         Phase.make_list('fade_in'), color = DIM_GREEN)
        self.add(anim)
        return anim

    def move(self, anim: AnimState, rect: RefRect, loc: int) -> AnimState:
        if not rect:
            Phase.append(anim.phases, 'slide_to_top', 'fade_out')
            return

        final_x = term_x_pos(rect, self.table)
        final_y = term_y_pos(rect, loc, self.table)

        slide_x = final_x + slide_right_distance(self.table)
        # there might be some epsilon here to consider
        y_change = False
        if anim.beg_pos.x != slide_x:
            if anim.beg_pos.y != self.table['top']:
                Phase.append(anim.phases, 'slide_to_top')
                y_change = True
            Phase.append(anim.phases, 'slide_over')
        if y_change or anim.beg_pos.y != final_y:
            Phase.append(anim.phases, 'slide_to_loc')
        Phase.append(anim.phases, 'slide_in', 'fade_out')
        anim.to_rect = rect
        anim.to_loc = loc
        """
        if loc in self.loc_map:
            active = self.loc_map[loc]
            anim.subscribe(active)
        else:
            self.loc_map[loc] = anim
        """

    def swap(self, memop: MemOp):
        rect = self.ref_mgr.get_rect(memop.node.ref)
        got_anim = self.slide_out(memop.got, rect, memop)
        put_anim = self.find_anim(memop.put, memop.itr)
        # update the dst node state now if the dst ref isn't visible
        # call NodeTerm.set() below *after* slide_out() above as set() updates state
        if not rect:
            dst_nod_trm = memop.node.get(memop.loc)
            dst_nod_trm.set(memop.put)
        if not put_anim:
            # don't bother manifesting 'emergent' terms that slide to nowhere
            if not got_anim:
                return
            put_anim = self.manifest(memop.put, memop.itr)
        else:
            put_anim.remove_last_wait_phase()
        self.move(put_anim, rect, memop.loc)

    def animate(self, memop: MemOp):
        if memop.is_take():
            self.take(memop)
        elif memop.is_swap():
            self.swap(memop)
        else:
            assert False, f"unknown memop {memop}"

    def remove_waiting(self):
        self.anims = [anim for anim in self.anims
                      if not anim.on_last_phase() or not anim.waiting()]

    def update_all(self, now: float):
        all_waiting = True
        anims: [AnimState] = []
        for anim in self.anims:
            if not self.update_state(anim, now):
                anims.append(anim)
                if not anim.waiting():
                    all_waiting = False
        self.anims = anims
        self.ready = all_waiting

    def draw_all(self):
        for anim in self.anims:
            self.draw(self.screen, anim, fonts.content)
