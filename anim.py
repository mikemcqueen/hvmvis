import pygame
import time
from typing import List, Tuple, Optional, TypeVar, Generic, NamedTuple
from dataclasses import dataclass

#from claude_appref9 import *
from hvm import AppRef, Node, NodeTerm, MemOp, Term
from refui import * #RefManager, RefRect
from fonts import fonts

"""
T = TypeVar('T')

@dataclass
class Rect(Generic[T]):
    left: int
    top: int
    width: int
    height: int
    obj: T

AppRefRect = Rect[AppRef]
TermRect = Rect[Term]
"""

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

TOP = 20

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

@dataclass
class AnimState:
    #from_mem_loc: int
    node_term: NodeTerm
    #term_data: Tuple[str, str, str]  # (tag, lab, loc)
    
    start_time: float
    phases: list[Phase]
    
    from_rect: RefRect
    to_loc: int
    
    beg_pos: Position

    to_rect: Optional[RefRect] = None
    phase: int = 0
    cur_pos: Optional[Position] = None
    end_pos: Optional[Position] = None
    alpha: float = 255
    color: Optional[Color] = None

    def reset_phases(self):
        self.phases = []
        self.phase = 0

    def fractional_x(self, fraction: float) -> float:
        return self.beg_pos.x + (self.end_pos.x - self.beg_pos.x) * fraction

    def slide_in_end_pos(self, table: dict) -> Position:
        # TODO: fix
        if self.cur_pos.x > self.to_rect.x:
            dist = -slide_right_distance(table)
        else:
            # TODO: fix
            assert False
        return Position(self.beg_pos.x + dist, self.beg_pos.y)

    def slide_out_end_pos(self, table: dict) -> Position:
        # TODO: fix
        if self.cur_pos.x > self.from_rect.x:
            dist = slide_right_distance(table)
        else:
            # TODO: fix
            assert False
        return Position(self.beg_pos.x + dist, self.beg_pos.y)

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

    def term_x_pos(self, rect: RefRect) -> int:
        # table['term_offset_x']
        return (
            rect.x +
            self.table['table_border_thickness'] +
            self.table['col_spacing']['margin'] +
            self.table['column_widths'][0]  +        # Add MEM column width
            self.table['col_spacing']['mem_term']    # Add MEM to Term spacing
        )

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

    """
    def find_appref_and_position(self, rects: list[RefRect], loc: int) -> Optional[Tuple]:
        for rect in rects:
            if rect.ref.contains(loc):
                row_y = self.term_y_pos(rect, loc)
                if row_y is not None:
                    return (rect, row_y)
        return None

    def get_node_term_at_loc(self, rects: list[RefRect], loc: int) -> Optional[NodeTerm]:
        for rect in rects:
            if not rect.ref.contains(loc): continue
            for i, node in enumerate(rect.ref.nodes):
                for j, node_term in enumerate((node.pos, node.neg)):
                    if loc == node_term.stores[0].loc:
                        return node_term
        return None
    """

    def update_state(self, anim: AnimState, current_time: float) -> bool:
        log = False #self.log_update

        # quick, hack manifested anim i think
        if not anim.phases: return

        #print(f"anim for {anim.node_term.term} phase {anim.phase} of {len(anim.phases)}")
        phase = anim.phases[anim.phase]
        if phase.name == 'wait':
            if log: print(f"anim for {anim.node_term.term} is waiting, phase {anim.phase} of {len(anim.phases)}")
            return False        

        elapsed = current_time - anim.start_time

        phase_start = phase.total - phase.duration
        phase_elapsed = elapsed - phase_start

        if not anim.cur_pos:
            anim.cur_pos = anim.beg_pos
            
        # Check if we need to advance to next phase
        if phase_elapsed >= phase.duration:
            # could happen.
            assert anim.end_pos
            anim.beg_pos = anim.end_pos
            anim.cur_pos = anim.end_pos
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
                return True

        t = phase_elapsed / phase.duration
    
        slide_distance = slide_right_distance(self.table)
    
        # Apply phase-specific transformations
        phase_name = phase.name
    
        if log: print(f"phase {phase_name} for {anim.node_term.term}")

        if phase_name == 'fade_in':
            if not anim.end_pos:
                anim.end_pos = anim.beg_pos
            anim.color = interpolate_color(anim.color, BRIGHT_GREEN, t)
        
        elif phase_name == 'slide_in':
            if not anim.end_pos:
                anim.end_pos = anim.slide_in_end_pos(self.table)
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
            anim.cur_pos = Position(anim.cur_pos.x, from_y + (to_y - from_y) * t_eased)
            anim.color = BRIGHT_GREEN

        elif phase_name == 'slide_over':
            slide_distance = slide_right_distance(self.table)
            if not anim.end_pos:
                anim.end_pos = Position(self.term_x_pos(anim.to_rect) + slide_distance, TOP)
            t_eased = ease_in_out_cubic(t)
            anim.cur_pos = Position(anim.fractional_x(t_eased), anim.cur_pos.y)
            anim.color = BRIGHT_GREEN

        elif phase_name == 'slide_to_loc':
            if not anim.end_pos:
                anim.end_pos = Position(anim.beg_pos.x, self.term_y_pos(anim.to_rect, anim.to_loc))
            t_eased = ease_in_out_cubic(t)
            from_y = anim.beg_pos.y
            to_y = anim.end_pos.y
            anim.cur_pos = Position(anim.cur_pos.x, from_y + (to_y - from_y) * t_eased)
            anim.color = BRIGHT_GREEN
        
        elif phase_name == 'fade_out':
            if not anim.end_pos:
                anim.end_pos = anim.beg_pos
            anim.color = interpolate_color(BRIGHT_GREEN, DIM_GREEN, t)
            if anim.to_rect:
                node_term = anim.to_rect.get_node_term(anim.to_loc)
                node_term.node.replace_term(anim.to_loc, anim.node_term.term)
            
        elif phase_name == 'wait':
            if not anim.end_pos:
                anim.end_pos = anim.beg_pos
            pass
    
        # Animation continues
        return False

    """
    def update_state(self, anim: AnimState, current_time: float) -> bool:
        elapsed = current_time - anim.start_time
    
        slide_distance = SLIDE_RIGHT_DISTANCE
    
        # Phase transitions
        if elapsed < durations['fade_in']:
            anim.phase = 'fade'
            t = elapsed / durations['fade_in']
            # Fade from original color to bright green
            original_color = DIM_GREEN if 'dim' in str(anim.color) else BRIGHT_GREEN
            anim.color = interpolate_color(original_color, BRIGHT_GREEN, t)
        
        elif elapsed < durations['fade_in'] + durations['slide_out']:
            anim.phase = 'slide_out'
            t = (elapsed - durations['fade_in']) / durations['slide_out']
            t_eased = ease_in_out_cubic(t)
        
            # Slide out just beyond table boundary
            anim.current_x = anim.target_x + (slide_distance * t_eased)
            anim.color = BRIGHT_GREEN
            
            ##
            ## TODO: PAUSE
            ##
        
        elif elapsed < durations['fade_in'] + durations['slide_out'] + durations['slide_over']:
            anim.phase = 'slide_over'
            t = (
                (elapsed - durations['fade_in'] - durations['slide_out'])
                / durations['slide_over']
            )
            t_eased = ease_in_out_cubic(t)
        
            # Calculate vertical movement using the proper function and AppRef positions
            from_rect, _ = anim.from_appref_pos
            to_rect, _ = anim.to_appref_pos
            
            from_y = self.get_y_position(from_rect, anim.from_mem_loc) #, from_start_y)
            to_y = self.get_y_position(to_rect, anim.to_mem_loc) #, to_start_y)
            
            if from_y is not None and to_y is not None:
                anim.current_y = from_y + (to_y - from_y) * t_eased
        
            # Keep X position at slide distance during vertical movement
            anim.current_x = anim.target_x + slide_distance
            anim.color = BRIGHT_GREEN
        
        elif elapsed < ANIM_DURATION:
            anim.phase = 'slide_in'
            t = (
                (elapsed - durations['fade_in'] - durations['slide_out'] - durations['slide_over'])
                / durations['slide_in']
            )
            t_eased = ease_in_out_cubic(t)
        
            # Slide back in from the table boundary
            anim.current_x = (anim.target_x + slide_distance) + (-slide_distance * t_eased)
        
            # Also fade back to original color
            anim.color = interpolate_color(BRIGHT_GREEN, DIM_GREEN, t)
        
        else:
            anim.phase = 'complete'
            return True
    
        return False
    """

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

    """
    def move_term_animated(self, rects: list[RefRect], from_loc: int, to_loc: int,
                           color_scheme: str = "dim terminal") -> AnimState:

        # Find source and target positions
        from_info = self.find_appref_and_position(rects, from_loc)
        to_info = self.find_appref_and_position(rects, to_loc)
        
        if from_info is None:
            print(f"Source memory location {from_loc} not found")
            return None
        if to_info is None:
            print(f"Target memory location {to_loc} not found")
            return None
        
        # Get term data at the source location
        node_term = self.get_node_term_at_loc(rects, from_loc)
        if node_term is None:
            print(f"No term found at memory location {from_loc}")
            return None
    
        # Create animation state
        anim = AnimState(
            #from_mem_loc=from_loc,
            to_loc=to_loc,
            node_term=node_term,
            #term_data=term_data,
            start_time=time.monotonic(),
            phases=Phase.make_list('fade_in', 'slide_out', 'wait'),
            phase=0,
            from_rect=from_info[0],
            to_rect=to_info[0],
            beg_pos=Position(from_info[0].x + self.table['col_spacing']['mem_term'], from_info[1]),
            color=DIM_GREEN if 'dim' in color_scheme else BRIGHT_GREEN
        )
        return anim
    """

    def slide_out(self, node_term: NodeTerm, rect: RefRect, loc: int):
        if not rect: return None

        # table.term_offset_x
        x = self.term_x_pos(rect)
        y = self.term_y_pos(rect, loc)
        if y is None:
            #print(f"slide_out: row position for {loc} not found")
            return None

        anim = AnimState(
            #from_mem_loc=0, #loc,
            to_loc=0,
            node_term=node_term,
            start_time=time.monotonic(),
            phases=Phase.make_list('fade_in', 'slide_out', 'wait'),
            phase=0,
            from_rect=rect,
            to_rect=None,
            beg_pos=Position(x, y),
            color=DIM_GREEN # TODO, if not rect.selected else BRIGHT_GREEN
        )
        self.anims.append(anim)
        return anim

    def take(self, memop: MemOp):
        rect = self.ref_mgr.get_rect(memop.node.ref)
        node_term = memop.node.term_at(memop.loc)
        self.slide_out(node_term, rect, memop.loc)

    """
    # early prototype
    def swap_test(self, from_loc: int, to_loc: int, rects: list[RefRect]):
        anim = self.move_term_animated(rects, from_loc, to_loc)
        if anim:
            self.anims.append(anim)
    """

    # NOTE this is unpredictable if two terms exist with same fields
    def find(self, term: Term) -> AnimState:
        for anim in self.anims:
            if term == anim.node_term.term:
                #print(f"found anim for term {term}")
                return anim
        print(f"no anim for term {term}")        
        return None

    # a term either was emergent in code, or was taken from a non-visible ref,
    # so we must make it "appear out of nowhere"
    def manifest(self, node_term: NodeTerm) -> AnimState:
        x = (self.screen.get_width() - self.table['term_width']) / 2
        y = TOP
        anim = AnimState(
            #from_mem_loc=0,
            node_term=node_term,
            start_time=time.monotonic(),
            phases=Phase.make_list('fade_in'),
            phase=0,
            from_rect=None,
            to_rect=None,
            to_loc=0,
            beg_pos=Position(x, y),
            color=DIM_GREEN # TODO, if not rect.selected else BRIGHT_GREEN
        )
        self.anims.append(anim)
        return anim
        
    def move(self, anim: AnimState, rect: RefRect, loc: int) -> AnimState:
        # TODO move offscreen or fade out or something
        
        if not rect or not anim: return None

        final_x = self.term_x_pos(rect)
        final_y = self.term_y_pos(rect, loc)

        #print(f"moving anim for {anim.node_term.term}")
        self.log_update = True

        slide_x = final_x + slide_right_distance(self.table)
        # there might be some epsilon here to consider
        if anim.beg_pos.x != slide_x:
            if anim.beg_pos.y != TOP:
                #print(f"  adding slide_to_top")
                Phase.append(anim.phases, 'slide_to_top')
            #print(f"  adding slide_over")
            Phase.append(anim.phases, 'slide_over')
        if anim.beg_pos.y != final_y:
            #print(f"  adding slide_to_loc")
            Phase.append(anim.phases, 'slide_to_loc')
        #print(f"  adding slide_in/fade_out")
        Phase.append(anim.phases, 'slide_in')
        Phase.append(anim.phases, 'fade_out')
        anim.to_rect = rect
        anim.to_loc = loc
        anim.start_time = time.monotonic()

    def swap(self, memop: MemOp):
        rect = self.ref_mgr.get_rect(memop.node.ref)
        node_term = memop.node.term_at(memop.loc)
        if not node_term:
            # don't bother manifesting 'emergent' terms that slide to nowhere
            if not dst: return
            src_anim = self.manifest(NodeTerm(memop.put, node_term.node, stores=[memop]))
            print(f"manifested anim for {memop.put}")
        else:
            src_anim = self.find(memop.put)
            if src_anim:
                src_anim.reset_phases()
        dst_anim = self.slide_out(node_term, rect, memop.loc)
        self.move(src_anim, rect, memop.loc)

    def animate(self, memop: MemOp):
        if memop.is_take():
            self.take(memop)
        elif memop.is_swap():
            self.swap(memop)

    def update_all(self, time):
        self.anims = [anim for anim in self.anims if not self.update_state(anim, time)]
        self.log_update = False

    def draw_all(self):
        for anim in self.anims:
            #if anim.phase != 'complete':
            self.draw_animated_term(self.screen, anim, fonts.content)

# Simple event loop integration example
def create_animated_example(screen, app_refs):
    clock = pygame.time.Clock()
    
    # Track active animations - you need this list in your main loop
    active_animations = []
    
    # Setup AppRef positions for the animation system
    rects = []
    y_pos = 50
    for app_ref in app_refs:
        (width, height) = calculate_appref_dimensions(app_ref)
        rects.append(RefRect(20, y_pos, width, height, app_ref))
        y_pos += height + 20
    
    running = True
    while running:
        current_time = time.monotonic()
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE and app_refs:
                    try:
                        anim = move(14, 50, rects)
                        active_animations.append(anim)
                    except ValueError as e:
                        print(f"Animation error: {e}")
        
        screen.fill(BLACK)
        
        active_animations = [anim for anim in active_animations 
                           if not update_state(anim, current_time)]
        
        # Draw AppRefs with animations
        for rect in rects:
            draw_appref_with_animation(screen, rect, "dim terminal", active_animations)
        
        pygame.display.flip()
        clock.tick(30)
    pygame.quit()

