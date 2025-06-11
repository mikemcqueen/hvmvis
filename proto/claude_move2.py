import pygame
import time
from typing import List, Tuple, Optional
from dataclasses import dataclass

from claude_appref9 import *
#from claude_position import *

# Get the absolute path to the directory one level up (the root)
import os
import sys
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, root_dir)

from hvm import AppRef, Node, NodeTerm, MemOp, Term

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

# Animation constants
durations: dict[str, float] = {
    'fade_in':    0.2,
    'slide_out':  0.3,
    'pause_out' : 0.0,
    'slide_over': 0.5,
    'pause_in' :  0.0,
    'slide_in':   0.3,
    'fade_out':   0.0
}

ANIM_DURATION = (
    durations['fade_in'] + durations['slide_out'] + durations['pause_out'] +
    durations['slide_over'] + durations['pause_in'] +
    durations['slide_in'] + durations['fade_out']
)

@dataclass
class AnimationState:
    """Tracks the state of a moving term animation"""
    from_mem_loc: int
    to_mem_loc: int
    term_data: Tuple[str, str, str]  # (tag, lab, loc)
    
    # Animation timing
    start_time: float
    phase: str  # 'fade_in', 'slide_out', 'slide_over', 'slide_in', 'fade_out', 'complete'
    
    # Position tracking (includes cross-AppRef movement)
    from_appref_pos: Tuple  # (app_ref, start_x, start_y, row_y)
    to_appref_pos: Tuple    # (app_ref, start_x, start_y, row_y)
    
    current_x: float
    current_y: float
    target_x: float
    target_y: float
    
    # Visual state
    alpha: float = 255
    color: Tuple[int, int, int] = None

# TODODODODODODDO dumb so much dumb here in these methods
def get_row_position(app_ref: AppRef, mem_loc: int, table: dict, start_y: int) -> Optional[int]:
    operations = collect_memory_operations(app_ref)
    # Find the row index for this memory location
    for i, (op_mem_loc, _, _, _) in enumerate(operations):
        if op_mem_loc == mem_loc:
            row_y = (
                start_y + table['top_row_y'] +
                (i * (table['metrics']['line_height'] + table['row_spacing']['intra_row']))
            )
            return row_y
    
    return None

def find_appref_and_position(app_ref_rects: list[AppRefRect], mem_loc: int,
                             table: dict = get_table_metrics()) -> Optional[Tuple]:
    # wut
    for app_ref_rect in app_ref_rects:
        row_y = get_row_position(app_ref_rect.obj, mem_loc, table, app_ref_rect.top)
        if row_y is not None:
            return (app_ref_rect.obj, app_ref_rect.left, app_ref_rect.top, row_y)
    
    return None

def get_term_data_at_location(app_ref_rects: list[AppRefRect], mem_loc: int) -> Optional[Tuple[str, str, str]]:
    """Get the term data (tag, lab, loc) at a specific memory location across all AppRefs"""
    for app_ref_rect in app_ref_rects:
        operations = collect_memory_operations(app_ref_rect.obj)
        
        for op_mem_loc, tag, lab, loc in operations:
            if op_mem_loc == mem_loc:
                return (tag[:3], f"{lab:03d}", f"{loc:04d}")
    
    return None

def ease_in_out_cubic(t: float) -> float:
    """Smooth easing function for animations"""
    if t < 0.5:
        return 4 * t * t * t
    else:
        return 1 - pow(-2 * t + 2, 3) / 2

def interpolate_color(color1: Tuple[int, int, int], color2: Tuple[int, int, int], t: float) -> Tuple[int, int, int]:
    """Interpolate between two colors"""
    return (
        int(color1[0] + (color2[0] - color1[0]) * t),
        int(color1[1] + (color2[1] - color1[1]) * t),
        int(color1[2] + (color2[2] - color1[2]) * t)
    )

def update_animation_state(anim: AnimationState, current_time: float, 
                           table: dict = get_table_metrics()) -> bool:

    elapsed = current_time - anim.start_time
    
    # Calculate slide distance - just outside table boundary (2-3 character widths)
    slide_distance = (
        table['term_width'] + table['col_spacing']['margin'] +
        table['metrics']['char_width'] 
    )
    
    # Phase transitions
    if elapsed < durations['fade_in']:
        anim.phase = 'fade'
        t = elapsed / durations['fade_in']
        # Fade from original color to bright green
        original_color = DIM_GREEN if 'DIM' in str(anim.color) else BRIGHT_GREEN
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
        from_app_ref, from_start_x, from_start_y, _ = anim.from_appref_pos
        to_app_ref, to_start_x, to_start_y, _ = anim.to_appref_pos
        
        from_y = get_row_position(from_app_ref, anim.from_mem_loc, table, from_start_y)
        to_y = get_row_position(to_app_ref, anim.to_mem_loc, table, to_start_y)
        
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

def draw_animated_term(surface: pygame.Surface, anim: AnimationState, 
                       start_x: int, font: pygame.font.Font = get_content_font(),
                       table: dict = get_table_metrics()):

    if anim.phase == 'complete':
        return
    
    # Calculate column positions for TAG, LAB, LOC (skip MEM column)
    col_positions = []
    current_x = start_x + table['col_spacing']['margin']  # Start at left border spacing
    
    # Skip MEM column (index 0) and calculate positions for TAG, LAB, LOC
    current_x += table['column_widths'][0]  # Add MEM column width
    current_x += table['col_spacing']['mem_term']    # Add MEM to Term spacing
    
    for i in range(1, 4):  # TAG (1), LAB (2), LOC (3) columns
        col_positions.append(current_x)
        if i < 3:  # Don't add spacing after the last column
            current_x += table['column_widths'][i]
            current_x += table['col_spacing_by_index'][i + 1]
    
    # Draw each field of the term (TAG, LAB, LOC)
    for i, (value, col_x) in enumerate(zip(anim.term_data, col_positions)):
        text_surface = font.render(value, True, anim.color)
        
        # Apply animation offset
        draw_x = col_x + (anim.current_x - anim.target_x) if hasattr(anim, 'current_x') else col_x
        draw_y = anim.current_y if hasattr(anim, 'current_y') else 0
        
        surface.blit(text_surface, (draw_x, draw_y))

def move_term_animated(app_ref_rects: list[AppRefRect], from_loc: int, to_loc: int,
                       table: dict = get_table_metrics(),
                       color_scheme: str = "dim terminal") -> AnimationState:

    # Find source and target positions
    from_info = find_appref_and_position(app_ref_rects, from_loc)
    to_info = find_appref_and_position(app_ref_rects, to_loc)
    
    if from_info is None:
        raise ValueError(f"No term found at memory location {from_loc}")
    if to_info is None:
        raise ValueError(f"Target memory location {to_loc} not found")
    
    # Get term data at the source location
    term_data = get_term_data_at_location(app_ref_rects, from_loc)
    if term_data is None:
        raise ValueError(f"No term data found at memory location {from_loc}")
    
    # Create animation state
    anim = AnimationState(
        from_mem_loc=from_loc,
        to_mem_loc=to_loc,
        term_data=term_data,
        start_time=time.time(),
        phase='fade',
        from_appref_pos=from_info,
        to_appref_pos=to_info,
        current_x=from_info[1] + table['col_spacing']['mem_term'],  # Start at TAG column
        current_y=from_info[3],  # Start row Y
        target_x=from_info[1] + table['col_spacing']['mem_term'],   # Will be updated during animation
        target_y=to_info[3],     # Target row Y
        color=DIM_GREEN if "DIM" in color_scheme else BRIGHT_GREEN
    )
    
    return anim

def draw_appref_with_animation(surface: pygame.Surface, app_ref_rect: AppRefRect,
                              color_scheme: str = "dim terminal",
                              animations: List[AnimationState] = None):
    """
    Enhanced version of draw_appref that can handle animated terms.
    """
    if animations is None:
        animations = []
    
    # First draw the normal AppRef
    draw_appref(surface, app_ref_rect.obj, app_ref_rect.left, app_ref_rect.top, color_scheme)
    
    # Then draw any animated terms on top
    for anim in animations:
        if anim.phase != 'complete':
            draw_animated_term(surface, anim, app_ref_rect.left)

# Simple event loop integration example
def create_animated_example(screen, app_refs):
    """
    Example showing how to integrate the animation system with your existing display.
    """
    #pygame.init()
    
    clock = pygame.time.Clock()
    
    # Track active animations - you need this list in your main loop
    active_animations = []
    
    # Setup AppRef positions for the animation system
    app_ref_rects = []
    y_pos = 50
    for app_ref in app_refs:
        (width, height) = calculate_appref_dimensions(app_ref)
        app_ref_rects.append(AppRefRect(20, y_pos, width, height, app_ref))
        y_pos += height + 20
    
    running = True
    while running:
        current_time = time.time()
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE and app_refs:
                    try:
                        anim = move(14, 50, app_ref_rects)
                        active_animations.append(anim)
                    except ValueError as e:
                        print(f"Animation error: {e}")
        
        screen.fill(BLACK)
        
        active_animations = [anim for anim in active_animations 
                           if not update_animation_state(anim, current_time)]
        
        # Draw AppRefs with animations
        for app_ref_rect in app_ref_rects:
            draw_appref_with_animation(screen, app_ref_rect, "dim terminal", active_animations)
        
        pygame.display.flip()
        clock.tick(30)
    
    pygame.quit()

def move(from_loc: int, to_loc: int, app_ref_rects: list[AppRefRect]) -> AnimationState:
    return move_term_animated(app_ref_rects, from_loc, to_loc)
