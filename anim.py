import pygame
import time
from typing import List, Tuple, Optional, TypeVar, Generic, NamedTuple
from dataclasses import dataclass, field

from hvm import AppRef, Node, NodeTerm, MemOp, Term, Interaction
from refui import * #RefManager, RefRect
from fonts import fonts

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

TOP = 30.0

Color = Tuple[int, int, int]

class Phase(NamedTuple):
    name: str
    duration: float
    total: float

    @classmethod
    def make_list(cls, *names: str) -> list['Phase']:
        result = []
        total = 0.0
        for name in names:
            duration = durations[name]
            total += duration
            result.append(cls(name, duration, total))
        return result

    @classmethod
    def append(cls, phases: list['Phase'], name: str) -> list['Phase']:
        total = 0.0 if not phases else phases[-1].total
        duration = durations[name]
        total += duration
        phases.append(cls(name, duration, total))
        return phases

class Position(NamedTuple):
    x: int
    y: int


# TODO: add to table metrics
# or, you know, just add char width to table.x + table.width and
# subtract from starting pos
def slide_right_distance(table: dict) -> int:
    return (
        table['term_width'] +
        table['col_spacing']['margin'] +
        table['table_border_thickness'] +
        table['metrics']['char_width']
    )

def term_x_pos(rect: RefRect, table: dict) -> int:
    # table['term_offset_x']
    return (
        rect.x +
        table['table_border_thickness'] +
        table['col_spacing']['margin'] +
        table['column_widths'][0]  +        # Add MEM column width
        table['col_spacing']['mem_term']    # Add MEM to Term spacing
    )

@dataclass
class AnimState:
    #term: Term
    #itr: Interaction
    node_term: NodeTerm
    start_time: float
    phases: list[Phase]
    beg_pos: Position

    to_rect: Optional[RefRect] = None
    to_loc: int = 0
    from_rect: Optional[RefRect] = None
    phase: int = 0
    cur_pos: Optional[Position] = None
    end_pos: Optional[Position] = None
    alpha: float = 255
    color: Optional[Color] = None
    subs: list['AnimState'] = field(default_factory=list)

    def reset_phases(self):
        self.phases = []
        self.phase = 0

    def fractional_x(self, fraction: float) -> float:
        return self.beg_pos.x + (self.end_pos.x - self.beg_pos.x) * fraction

    def slide_over_end_pos(self, rect: RefRect, table: dict) -> Position:
        # TODO: support slide-in-from-left, maybe
        slide_distance = slide_right_distance(table)
        return Position(term_x_pos(rect, table) + slide_distance, TOP)

    def slide_out_end_pos(self, table: dict) -> Position:
        # TODO: support slide-out-to-left, maybe
        if self.cur_pos.x > self.from_rect.x:
            dist = slide_right_distance(table)
        else:
            # TODO: fix
            assert False
        return Position(self.beg_pos.x + dist, self.beg_pos.y)

    def add_subscriber(self, anim: 'AnimState') -> bool:
        assert self.to_rect
        print(f"term {anim.node_term.term} @ {anim.node_term.store_loc} waiting on {self.node_term.term} @ {self.node_term.store_loc}")
        self.subs.append(anim)
        return True

    def notify(self) -> Optional['AnimState']:
        subs = self.subs
        self.subs = []
        for i, anim in enumerate(subs):
            assert (anim.phase + 1 < len(anim.phases) and
                    anim.phases[anim.phase].name == 'wait')
            total = anim.phases[anim.phase].total
            anim.phase += 1
            anim.start_time = time.monotonic() + total
            print(f"term {self.node_term.term} @ {self.node_term.store_loc} notifying {anim.node_term.term} @ {anim.node_term.store_loc}")
            if anim.to_rect:
                print(f"  adding {len(subs[i + 1:])} subs to {anim.node_term.term} @ {anim.node_term.store_loc}")
                anim.subs.extend(subs[i + 1:])
                return anim
        return None

def ease_in_out_cubic(t: float) -> float:
    if t < 0.5:
        return 4 * t * t * t
    else:
        return 1 - pow(-2 * t + 2, 3) / 2

def interpolate_color(color1: Color, color2: Color, t: float) -> Color:
    return (
        int(color1[0] + (color2[0] - color1[0]) * t),
        int(color1[1] + (color2[1] - color1[1]) * t),
        int(color1[2] + (color2[2] - color1[2]) * t)
    )

class AnimManager:
    def __init__(self, screen: pygame.Surface, ref_mgr: RefManager, table: dict):
        self.screen = screen
        self.ref_mgr = ref_mgr
        self.table = table
        self.anims: List[AnimState] = []
        self.log_update = False
        self.put_loc_map: dict[int, AnimState] = {}

    def term_y_pos(self, rect: RefRect, loc: int) -> Optional[int]:
        for i, node in enumerate(rect.ref.nodes):
            for j, node_term in enumerate((node.neg, node.pos)):
                term_loc = node_term.stores[0].loc
                if loc == term_loc:
                    return (
                        rect.y + self.table['top_row_y'] + (i * 2 + j) *
                        (self.table['metrics']['line_height'] +
                         self.table['row_spacing']['intra_row'])
                    )
        return None

    def add(self, anim: AnimState):
        if not anim.cur_pos:
            anim.cur_pos = anim.beg_pos
        self.anims.append(anim)

    def update_state(self, anim: AnimState, current_time: float) -> bool:
        log = False #self.log_update

        # quick, hack manifested anim i think
        if not anim.phases: return False

        #print(f"anim for {anim.node_term.term} phase {anim.phase} of {len(anim.phases)}")
        phase = anim.phases[anim.phase]
        if phase.name == 'wait':
            if log: print(f"anim for {anim.node_term.term} is waiting, phase {anim.phase} of {len(anim.phases)}")
            return False        

        elapsed = current_time - anim.start_time

        phase_start = phase.total - phase.duration
        phase_elapsed = elapsed - phase_start

        # Check if we need to advance to next phase
        if phase_elapsed >= phase.duration:
            # could happen.
            assert anim.end_pos
            anim.beg_pos = anim.end_pos
            anim.cur_pos = anim.beg_pos
            anim.end_pos = None
            # Move to next phase if available
            if anim.phase + 1 < len(anim.phases):
                anim.phase += 1
                phase = anim.phases[anim.phase]
                if log: print(f"next phase {phase.name} for {anim.node_term.term}")
                if phase.name == 'wait':
                    return False              
                phase_start = phase.total - phase.duration
                phase_elapsed = elapsed - phase_start
            else:
                anim.phase = len(anim.phases)
                if log: print(f"final phase {phase.name} for {anim.node_term.term}")
                # Animation done
                return True

        t = phase_elapsed / phase.duration
    
        # Apply phase-specific transformations
        phase_name = phase.name
    
        if log: print(f"phase {phase_name} for {anim.node_term.term}")

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
                anim.end_pos = Position(anim.beg_pos.x, TOP)
            t_eased = ease_in_out_cubic(t)
            from_y = anim.beg_pos.y
            to_y = TOP
            #vert_slide_pos
            anim.cur_pos = Position(anim.cur_pos.x, from_y + (to_y - from_y) * t_eased)
            anim.color = BRIGHT_GREEN

        elif phase_name == 'slide_over':
            if not anim.end_pos:
                anim.end_pos = anim.slide_over_end_pos(anim.to_rect, self.table)
            t_eased = ease_in_out_cubic(t)
            #horz_slide_pos
            anim.cur_pos = Position(anim.fractional_x(t_eased), anim.cur_pos.y)
            anim.color = BRIGHT_GREEN

        elif phase_name == 'slide_to_loc':
            if not anim.end_pos:
                anim.end_pos = Position(anim.beg_pos.x, self.term_y_pos(anim.to_rect, anim.to_loc))
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
                node_term = anim.to_rect.get_node_term(anim.to_loc)
                node_term.node.replace_term(anim.to_loc, anim.node_term.term)
                anim.to_rect = None
                next_anim = anim.notify()
                if next_anim:
                    self.put_loc_map[anim.to_loc] = next_anim
                else:
                    del self.put_loc_map[anim.to_loc] #.pop(anim.to_loc, None)
                
        elif phase_name == 'wait':
            if not anim.end_pos:
                anim.end_pos = anim.beg_pos
            pass
    
        # Animation continues
        return False

    def draw_animated_term(self, surface: pygame.Surface, anim: AnimState, 
                           font: pygame.font.Font):
        if anim.phase == len(anim.phases):
            return
    
        # TODO: dumb to calculate this every time, they don't change
        col_positions = []
        pos_x = 0
        for i in range(1, 4):  # TAG (1), LAB (2), LOC (3) columns
            col_positions.append(pos_x)
            if i < 3:  # Don't add spacing after the last column
                pos_x += (
                    self.table['column_widths'][i] +
                    self.table['col_spacing_by_index'][i + 1]
                )
    
        # Draw each field of the term (TAG, LAB, LOC)
        term = anim.node_term.term
        term_data = (term.tag[:3], f"{term.lab:03d}", f"{term.loc:04d}")
        for i, (value, col_x) in enumerate(zip(term_data, col_positions)):
            text_surface = font.render(value, True, anim.color)
        
            # Apply animation offset
            draw_x = anim.cur_pos.x + col_x
            draw_y = anim.cur_pos.y
            
            surface.blit(text_surface, (draw_x, draw_y))

    def slide_out(self, node_term: NodeTerm, rect: RefRect):
        if not rect: return None

        # table.term_offset_x
        x = term_x_pos(rect, self.table)
        y = self.term_y_pos(rect, node_term.store_loc)
        if y is None:
            #print(f"slide_out: row position for {loc} not found")
            return None

        last_phase = 'fade_out' if node_term.tag == 'SUB' else 'wait'
        phases = ['fade_in', 'slide_out', last_phase]
        anim = AnimState(
            node_term=node_term,
            start_time=time.monotonic(),
            phases=Phase.make_list(*phases),
            from_rect=rect,
            beg_pos=Position(x, y),
            color=DIM_GREEN # TODO, if not rect.selected else BRIGHT_GREEN
        )
        if node_term.store_loc in self.put_loc_map:
            other = self.put_loc_map[node_term.store_loc]
            other.add_subscriber(anim)
            # TODO: make_list('wait'), phases.extend(phases)
            anim.phases = Phase.make_list('wait', *phases)
        self.add(anim)
        return anim

    def take(self, memop: MemOp):
        rect = self.ref_mgr.get_rect(memop.node.ref)
        node_term = memop.node.term_at(memop.loc)
        self.slide_out(node_term, rect)

    # NOTE this is unpredictable if two terms exist with same fields
    def find_anim(self, term: Term) -> AnimState:
        for anim in self.anims:
            if term == anim.node_term.term:
                #print(f"found anim for term {term}")
                return anim
        #print(f"no anim for term {term}")
        return None

    # a term either was emergent in code, or was taken from a non-visible ref,
    # so we must make it "appear out of nowhere"
    def manifest(self, node_term: NodeTerm) -> AnimState:
        x = (self.screen.get_width() - self.table['term_width']) / 2
        y = TOP
        anim = AnimState(
            node_term=node_term,
            start_time=time.monotonic(),
            phases=Phase.make_list('fade_in'),
            to_loc=0,
            beg_pos=Position(x, y),
            color=DIM_GREEN # TODO, if not rect.selected else BRIGHT_GREEN
        )
        self.add(anim)
        return anim
        
    def move(self, anim: AnimState, rect: RefRect, loc: int) -> AnimState:
        anim.start_time = time.monotonic()
        if not rect:
            Phase.append(anim.phases, 'slide_to_top')
            Phase.append(anim.phases, 'fade_out')
            return

        final_x = term_x_pos(rect, self.table)
        final_y = self.term_y_pos(rect, loc)

        #print(f"moving anim for {anim.node_term.term}")
        self.log_update = True

        slide_x = final_x + slide_right_distance(self.table)
        # there might be some epsilon here to consider
        if anim.beg_pos.x != slide_x:
            if anim.beg_pos.y != TOP:
                Phase.append(anim.phases, 'slide_to_top')
            Phase.append(anim.phases, 'slide_over')
        if anim.beg_pos.y != final_y:
            Phase.append(anim.phases, 'slide_to_loc')
        Phase.append(anim.phases, 'slide_in')
        Phase.append(anim.phases, 'fade_out')
        anim.to_rect = rect
        anim.to_loc = loc
        if loc in self.put_loc_map:
            other = self.put_loc_map[loc]
            anim.add_subscriber(other)
            # TODO: make_list
            phases = Phase.append([], 'wait')
            phases.extend(anim.phases)
            anim.phases = phases
        else:
            self.put_loc_map[loc] = anim

    def swap(self, memop: MemOp):
        rect = self.ref_mgr.get_rect(memop.node.ref)
        node_term = memop.node.term_at(memop.loc)
        got_anim = self.slide_out(node_term, rect)
        put_anim = self.find_anim(memop.put)
        if not put_anim:
            # don't bother manifesting 'emergent' terms that slide to nowhere
            if not got_anim: return
            put_anim = self.manifest(NodeTerm(memop.put, node_term.node, stores=[memop]))
            #print(f"manifested anim for {memop.put}")
        else:
            put_anim.reset_phases()
        self.move(put_anim, rect, memop.loc)

    def animate(self, memop: MemOp):
        if memop.is_take():
            self.take(memop)
        elif memop.is_swap():
            self.swap(memop)

    def remove_waiting(self):
        anims = []
        for anim in self.anims:
            if anim.phase == len(anim.phases) - 1 and anim.phases[-1].name == 'wait':
                continue
            anims.append(anim)
        self.anims = anims
                      
    def update_all(self, time):
        self.anims = [anim for anim in self.anims if not self.update_state(anim, time)]
        self.log_update = False

    def draw_all(self):
        for anim in self.anims:
            #if anim.phase != 'complete':
            self.draw_animated_term(self.screen, anim, fonts.content)

