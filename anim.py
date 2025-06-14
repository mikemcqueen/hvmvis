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
    'fade_in':    0.2,
    'slide_out':  0.3,
    'pause_out' : 0.0,
    'slide_over': 0.5,
    'pause_in' :  0.0,
    'slide_in':   0.3,
    'fade_out':   0.2,
    'wait':       0.0
}

ANIM_DURATION = (
    durations['fade_in'] +
    durations['slide_out'] +
    durations['pause_out'] +
    durations['slide_over'] +
    durations['pause_in'] +
    durations['slide_in'] +
    durations['fade_out']
)

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

@dataclass
class AnimationState:
    from_mem_loc: int
    to_mem_loc: int
    term: NodeTerm
    #term_data: Tuple[str, str, str]  # (tag, lab, loc)
    
    # Animation timing
    start_time: float
    phases: Tuple[Phase]
    phase: int
    
    # Position tracking (includes cross-AppRef movement)
    from_appref_pos: Tuple  # (RefRect, row_y)
    to_appref_pos: Tuple    # (RefRect, row_y)
    
    current_x: float
    current_y: float
    target_x: float
    target_y: float
    
    # Visual state
    alpha: float = 255
    color: Color = None

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
        self.anims: List[AnimationState] = []

    def slide_right_distance(self) -> int:
        return (
            self.table['term_width'] +
            self.table['col_spacing']['margin'] +
            self.table['table_border_thickness'] +
            self.table['metrics']['char_width']
        )

    def get_row_position(self, rect: RefRect, loc: int) -> Optional[int]:
        for i, node in enumerate(rect.ref.nodes):
            for j, term in enumerate((node.neg, node.pos)):
                term_loc = term.stores[0].loc
                if loc == term_loc:
                    return (
                        rect.y + self.table['top_row_y'] +
                        (i * 2 + j) * (self.table['metrics']['line_height'] + self.table['row_spacing']['intra_row'])
                    )
        return None

    def find_appref_and_position(self, rects: list[RefRect], loc: int) -> Optional[Tuple]:
        for rect in rects:
            if rect.ref.contains(loc):
                row_y = self.get_row_position(rect, loc)
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


    def update_state(self, anim: AnimationState, current_time: float) -> bool:
        phase = anim.phases[anim.phase]
        if phase.name == 'wait':
            return False        

        elapsed = current_time - anim.start_time

        phase_start = phase.total - phase.duration
        phase_elapsed = elapsed - phase_start
        
        # Check if we need to advance to next phase
        if phase_elapsed >= phase.duration:
            # Move to next phase if available
            if anim.phase + 1 < len(anim.phases):
                anim.phase += 1
                phase = anim.phases[anim.phase]
                if phase.name == 'wait':
                    return False              
                phase_start = phase.total - phase.duration
                phase_elapsed = elapsed - phase_start
            else:
                anim.phase = len(anim.phases)
                return True

        t = phase_elapsed / phase.duration
    
        slide_distance = self.slide_right_distance()
    
        # Apply phase-specific transformations
        phase_name = phase.name
    
        if phase_name == 'fade_in':
            anim.color = interpolate_color(anim.color, BRIGHT_GREEN, t)
        
        elif phase_name == 'slide_out':
            t_eased = ease_in_out_cubic(t)
            # Slide out beyond table boundary
            anim.current_x = anim.target_x + (slide_distance * t_eased)
            anim.color = BRIGHT_GREEN
        
        elif phase_name == 'slide_over':
            t_eased = ease_in_out_cubic(t)
            # Calculate vertical movement between AppRef positions
            from_rect, _ = anim.from_appref_pos
            to_rect, _ = anim.to_appref_pos
            
            from_y = self.get_row_position(from_rect, anim.from_mem_loc)
            to_y = self.get_row_position(to_rect, anim.to_mem_loc)
            
            if from_y is not None and to_y is not None:
                anim.current_y = from_y + (to_y - from_y) * t_eased
        
                # Keep X position at slide distance during vertical movement
                anim.current_x = anim.target_x + slide_distance
                anim.color = BRIGHT_GREEN
        
        elif phase_name == 'pause_in':
            # Hold position during pause
            anim.current_x = anim.target_x + slide_distance
            anim.color = BRIGHT_GREEN
        
        elif phase_name == 'slide_in':
            t_eased = ease_in_out_cubic(t)
            # Slide back in from the table boundary
            anim.current_x = (anim.target_x + slide_distance) + (-slide_distance * t_eased)
        
        elif phase_name == 'fade_out':
            # Fade to final color or transparency
            anim.color = interpolate_color(BRIGHT_GREEN, DIM_GREEN, t)
            
        elif phase_name == 'wait':
            # Hold current state indefinitely
            pass
    
        # Animation continues
        return False


    """
    def update_state(self, anim: AnimationState, current_time: float) -> bool:
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
            
            from_y = self.get_row_position(from_rect, anim.from_mem_loc) #, from_start_y)
            to_y = self.get_row_position(to_rect, anim.to_mem_loc) #, to_start_y)
            
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

    def draw_animated_term(self, surface: pygame.Surface, anim: AnimationState, 
                           font: pygame.font.Font):
        if anim.phase == len(anim.phases):
            return
    
        # Calculate column positions for TAG, LAB, LOC (skip MEM column)
        col_positions = []
        current_x = anim.from_appref_pos[0].x + self.table['col_spacing']['margin']
        
        # Skip MEM column (index 0) and calculate positions for TAG, LAB, LOC
        current_x += self.table['column_widths'][0]  # Add MEM column width
        current_x += self.table['col_spacing']['mem_term']    # Add MEM to Term spacing
    
        for i in range(1, 4):  # TAG (1), LAB (2), LOC (3) columns
            col_positions.append(current_x)
            if i < 3:  # Don't add spacing after the last column
                current_x += self.table['column_widths'][i]
                current_x += self.table['col_spacing_by_index'][i + 1]
    
        # Draw each field of the term (TAG, LAB, LOC)
        term_data = (anim.term.tag[:3], f"{anim.term.lab:03d}", f"{anim.term.loc:04d}")
        for i, (value, col_x) in enumerate(zip(term_data, col_positions)):
            text_surface = font.render(value, True, anim.color)
        
            # Apply animation offset
            draw_x = col_x + (anim.current_x - anim.target_x) if hasattr(anim, 'current_x') else col_x
            draw_y = anim.current_y if hasattr(anim, 'current_y') else 0
            
            surface.blit(text_surface, (draw_x, draw_y))

    def move_term_animated(self, rects: list[RefRect], from_loc: int, to_loc: int,
                           color_scheme: str = "dim terminal") -> AnimationState:

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
        term = self.get_node_term_at_loc(rects, from_loc)
        if term is None:
            print(f"No term found at memory location {from_loc}")
            return None
    
        # Create animation state
        anim = AnimationState(
            from_mem_loc=from_loc,
            to_mem_loc=to_loc,
            term=term,
            #term_data=term_data,
            start_time=time.monotonic(),
            phases=Phase.make_list('fade_in', 'slide_out', 'wait'),
            phase=0,
            from_appref_pos=from_info,
            to_appref_pos=to_info,
            current_x=from_info[0].x + self.table['col_spacing']['mem_term'],  # Start at TAG column
            current_y=from_info[1],  # Start row Y
            target_x=to_info[0].x + self.table['col_spacing']['mem_term'],   # Will be updated during animation
            target_y=to_info[1],     # Target row Y
            color=DIM_GREEN if 'dim' in color_scheme else BRIGHT_GREEN
        )
        return anim

    def slide_out(self, term: NodeTerm, rect: RefRect, loc: int):
        start_y = self.get_row_position(rect, loc)
        if start_y is None:
            print(f"slide_out: row position for {loc} not found")
            return None

        start_x = rect.x + self.table['col_spacing']['mem_term']

        # Create animation state
        anim = AnimationState(
            from_mem_loc=loc,
            to_mem_loc=0,
            term=term,
            start_time=time.monotonic(),
            phases=Phase.make_list('fade_in', 'slide_out', 'wait'),
            phase=0,
            from_appref_pos=(rect, 0),
            to_appref_pos=(None, 0),
            current_x=start_x,
            current_y=start_y,
            target_x=start_x,   # Will be updated during animation
            target_y=start_y,
            color=DIM_GREEN # TODO, if not rect.selected else BRIGHT_GREEN
        )
        return anim

    def update_all(self, time):
        self.anims = [anim for anim in self.anims if not self.update_state(anim, time)]

    def draw_all(self):
        for anim in self.anims:
            if anim.phase != 'complete':
                self.draw_animated_term(self.screen, anim, fonts.content)

    def swap(self, from_loc: int, to_loc: int, rects: list[RefRect]):
        anim = self.move_term_animated(rects, from_loc, to_loc)
        if anim:
            self.anims.append(anim)

    def take(self, memop: MemOp):
        rect = self.ref_mgr.get_rect(memop.node.ref)
        # this check is necessary as long as i allow 'executing' memops that refer
        # refs that were not provided to ref_mgr (such as @sum)
        if rect:
            term = memop.node.term_at(memop.loc)
            anim = self.slide_out(term, rect, memop.loc)
            if anim:
                self.anims.append(anim)

    def animate(self, memop: MemOp):
        if memop.is_take():
            self.take(memop)

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

