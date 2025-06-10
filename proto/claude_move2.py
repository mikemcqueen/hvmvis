import pygame
import time
from typing import List, Tuple, Optional
from dataclasses import dataclass
from claude_appref9 import *

# Get the absolute path to the directory one level up (the root)
import os
import sys
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, root_dir)

from hvm import AppRef, Node, NodeTerm, MemOp, Term

# Animation constants
ANIMATION_DURATION = 1.5  # Total animation time in seconds
FADE_DURATION = 0.3      # Time to fade to bright green
SLIDE_OUT_DURATION = 0.4  # Time to slide right
SLIDE_VERTICAL_DURATION = 0.5  # Time to slide up/down
SLIDE_IN_DURATION = 0.3   # Time to slide left into position

@dataclass
class AnimationState:
    """Tracks the state of a moving term animation"""
    from_mem_loc: int
    to_mem_loc: int
    term_data: Tuple[str, str, str]  # (tag, lab, loc)
    
    # Animation timing
    start_time: float
    phase: str  # 'fade', 'slide_out', 'slide_vertical', 'slide_in', 'complete'
    
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

def get_row_position(app_ref: AppRef, mem_loc: int, table_metrics: dict, start_y: int) -> Optional[float]:
    """
    Calculate the Y position of a specific memory location row within an AppRef.
    
    Args:
        app_ref: The AppRef to search in
        mem_loc: The memory location to find
        table_metrics: Table layout metrics from get_table_metrics()
        start_y: The Y position where the AppRef starts drawing
    
    Returns:
        Y coordinate of the row, or None if memory location not found
    """
    operations = collect_memory_operations(app_ref)
    
    # Find the row index for this memory location
    for i, (op_mem_loc, _, _, _) in enumerate(operations):
        if op_mem_loc == mem_loc:
            # Calculate Y position using the same logic as draw_appref
            # Position relative to the AppRef's start position
            title_bottom = start_y + table_metrics['title_height'] + table_metrics['title_to_header_spacing']
            header_bottom = title_bottom + table_metrics['row_spacing'][1]  # header_height
            line_y = header_bottom + table_metrics['row_spacing'][2]  # header_to_line
            row_y = line_y + table_metrics['row_spacing'][3] + (i * table_metrics['row_spacing'][4])
            return row_y
    
    return None

def find_appref_and_position(app_refs_with_positions: List[Tuple], mem_loc: int, table_metrics: dict) -> Optional[Tuple]:
    """
    Find which AppRef contains a memory location and return its position info.
    app_refs_with_positions: List of (app_ref, start_x, start_y, title) tuples
    Returns: (app_ref, start_x, start_y, row_y) or None if not found
    """
    for app_ref, start_x, start_y, title in app_refs_with_positions:
        row_y = get_row_position(app_ref, mem_loc, table_metrics, start_y)
        if row_y is not None:
            return (app_ref, start_x, start_y, row_y)
    
    return None

def get_term_data_at_location(app_refs_with_positions: List[Tuple], mem_loc: int) -> Optional[Tuple[str, str, str]]:
    """Get the term data (tag, lab, loc) at a specific memory location across all AppRefs"""
    for app_ref, _, _, _ in app_refs_with_positions:
        operations = collect_memory_operations(app_ref)
        
        for op_mem_loc, tag, lab, term_loc in operations:
            if op_mem_loc == mem_loc:
                return (tag[:3], f"{lab:03d}", f"{term_loc:04d}")
    
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
                          table_metrics: dict) -> bool:
    """
    Update animation state based on current time.
    Returns True if animation is complete, False otherwise.
    """
    elapsed = current_time - anim.start_time
    
    # Calculate slide distance - just outside table boundary (2-3 character widths)
    char_width = table_metrics['font_metrics']['char_width']
    slide_distance = char_width * 2.5  # 2.5 character widths to the right
    
    # Phase transitions
    if elapsed < FADE_DURATION:
        anim.phase = 'fade'
        t = elapsed / FADE_DURATION
        # Fade from original color to bright green
        original_color = DIM_GREEN if 'dim' in str(anim.color) else BRIGHT_GREEN
        anim.color = interpolate_color(original_color, BRIGHT_GREEN, t)
        
    elif elapsed < FADE_DURATION + SLIDE_OUT_DURATION:
        anim.phase = 'slide_out'
        t = (elapsed - FADE_DURATION) / SLIDE_OUT_DURATION
        t_eased = ease_in_out_cubic(t)
        
        # Slide out just beyond table boundary
        anim.current_x = anim.target_x + (slide_distance * t_eased)
        anim.color = BRIGHT_GREEN
        
    elif elapsed < FADE_DURATION + SLIDE_OUT_DURATION + SLIDE_VERTICAL_DURATION:
        anim.phase = 'slide_vertical'
        t = (elapsed - FADE_DURATION - SLIDE_OUT_DURATION) / SLIDE_VERTICAL_DURATION
        t_eased = ease_in_out_cubic(t)
        
        # Calculate vertical movement using the proper function and AppRef positions
        from_app_ref, from_start_x, from_start_y, _ = anim.from_appref_pos
        to_app_ref, to_start_x, to_start_y, _ = anim.to_appref_pos
        
        from_y = get_row_position(from_app_ref, anim.from_mem_loc, table_metrics, from_start_y)
        to_y = get_row_position(to_app_ref, anim.to_mem_loc, table_metrics, to_start_y)
        
        if from_y is not None and to_y is not None:
            anim.current_y = from_y + (to_y - from_y) * t_eased
        
        # Keep X position at slide distance during vertical movement
        anim.current_x = anim.target_x + slide_distance
        anim.color = BRIGHT_GREEN
        
    elif elapsed < ANIMATION_DURATION:
        anim.phase = 'slide_in'
        t = (elapsed - FADE_DURATION - SLIDE_OUT_DURATION - SLIDE_VERTICAL_DURATION) / SLIDE_IN_DURATION
        t_eased = ease_in_out_cubic(t)
        
        # Slide back in from the table boundary
        anim.current_x = (anim.target_x + slide_distance) + (-slide_distance * t_eased)
        
        # Also fade back to original color
        anim.color = interpolate_color(BRIGHT_GREEN, DIM_GREEN, t)
        
    else:
        anim.phase = 'complete'
        return True
    
    return False

def draw_animated_term(surface: pygame.Surface, anim: AnimationState, font: pygame.font.Font,
                      table_metrics: dict, start_x: int):
    """Draw a term that's currently being animated"""
    if anim.phase == 'complete':
        return
    
    # Calculate column positions for TAG, LAB, LOC (skip MEM column)
    col_positions = []
    current_x = start_x + table_metrics['col_spacing'][0]  # Start at left border spacing
    
    # Skip MEM column (index 0) and calculate positions for TAG, LAB, LOC
    current_x += table_metrics['column_widths'][0]  # Add MEM column width
    current_x += table_metrics['col_spacing'][1]    # Add MEM to TAG spacing
    
    for i in range(1, 4):  # TAG (1), LAB (2), LOC (3) columns
        col_positions.append(current_x)
        if i < 3:  # Don't add spacing after the last column
            current_x += table_metrics['column_widths'][i]
            current_x += table_metrics['col_spacing'][i + 1]
    
    # Draw each field of the term (TAG, LAB, LOC)
    for i, (value, col_x) in enumerate(zip(anim.term_data, col_positions)):
        text_surface = font.render(value, True, anim.color)
        
        # Apply animation offset
        draw_x = col_x + (anim.current_x - anim.target_x) if hasattr(anim, 'current_x') else col_x
        draw_y = anim.current_y if hasattr(anim, 'current_y') else 0
        
        surface.blit(text_surface, (draw_x, draw_y))

def move_term_animated(app_refs_with_positions: List[Tuple], from_loc: int, to_loc: int,
                      color_scheme: str = "dim terminal") -> AnimationState:
    """
    Start an animated move of a term from one memory location to another.
    Can move within the same AppRef or between different AppRefs.
    
    Args:
        app_refs_with_positions: List of (app_ref, start_x, start_y, title) tuples
        from_loc: Source memory location
        to_loc: Target memory location
        color_scheme: Visual style
    
    Returns:
        AnimationState object that should be updated each frame.
    """
    # Get table metrics
    font = get_font(FONT_SIZE)
    table_metrics = get_table_metrics(font)
    
    # Find source and target positions
    from_info = find_appref_and_position(app_refs_with_positions, from_loc, table_metrics)
    to_info = find_appref_and_position(app_refs_with_positions, to_loc, table_metrics)
    
    if from_info is None:
        raise ValueError(f"No term found at memory location {from_loc}")
    if to_info is None:
        raise ValueError(f"Target memory location {to_loc} not found")
    
    # Get term data at the source location
    term_data = get_term_data_at_location(app_refs_with_positions, from_loc)
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
        current_x=from_info[1] + table_metrics['col_spacing'][0],  # Start at TAG column
        current_y=from_info[3],  # Start row Y
        target_x=from_info[1] + table_metrics['col_spacing'][0],   # Will be updated during animation
        target_y=to_info[3],     # Target row Y
        color=DIM_GREEN if "dim" in color_scheme else BRIGHT_GREEN
    )
    
    return anim

def draw_appref_with_animation(surface: pygame.Surface, app_ref: AppRef, x: int, y: int, 
                              title: str = "AppRef", color_scheme: str = "dim terminal",
                              animations: List[AnimationState] = None):
    """
    Enhanced version of draw_appref that can handle animated terms.
    """
    if animations is None:
        animations = []
    
    # First draw the normal AppRef
    draw_appref(surface, app_ref, x, y, title, color_scheme)
    
    # Then draw any animated terms on top
    font = get_font(FONT_SIZE)
    table_metrics = get_table_metrics(font)
    
    for anim in animations:
        if anim.phase != 'complete':
            draw_animated_term(surface, anim, font, table_metrics, x)

# Simple event loop integration example
def create_animated_example(app_refs):
    """
    Example showing how to integrate the animation system with your existing display.
    """
    pygame.init()
    
    screen = pygame.display.set_mode((1280, 1024))
    pygame.display.set_caption("AppRef Display with Animation")
    clock = pygame.time.Clock()
    
    # Track active animations - you need this list in your main loop
    active_animations = []
    
    # Setup AppRef positions for the animation system
    app_refs_info = []
    y_pos = 50
    for app_ref in app_refs:
        app_refs_info.append((app_ref, 50, y_pos, ref_name(app_ref.ref)))
        y_pos += calculate_appref_dimensions(app_ref)[1] + 20
    
    running = True
    while running:
        current_time = time.time()
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE and app_refs:
                    # YES! You can call move() directly like this:
                    # Move from location 14 to location 50 (could be different AppRefs!)
                    try:
                        anim = move(14, 50, app_refs_info)
                        active_animations.append(anim)
                    except ValueError as e:
                        print(f"Animation error: {e}")
        
        screen.fill(BLACK)
        
        # Update animations each frame (required!)
        font = get_font(FONT_SIZE)
        table_metrics = get_table_metrics(font)
        active_animations = [anim for anim in active_animations 
                           if not update_animation_state(anim, current_time, table_metrics)]
        
        # Draw AppRefs with animations
        for i, (app_ref, x, y, title) in enumerate(app_refs_info):
            draw_appref_with_animation(screen, app_ref, x, y, title, "dim terminal", active_animations)
        
        pygame.display.flip()
        clock.tick(30)
    
    pygame.quit()

# Minimal integration pattern for your existing code:
"""
# In your existing pygame loop, add these things:

# 1. Before the loop - create animation list and AppRef position info
active_animations = []
app_refs_info = [
    (app_ref1, x1, y1, "Title1"),
    (app_ref2, x2, y2, "Title2"),
    # ... etc for all your AppRefs with their display positions
]

# 2. In event handling - call move() directly with just the locations
if some_condition:
    anim = move(from_loc, to_loc, app_refs_info)  # That's it!
    active_animations.append(anim)

# 3. Each frame - update and draw with animations
table_metrics = get_table_metrics(get_font(FONT_SIZE))
active_animations = [a for a in active_animations 
                   if not update_animation_state(a, time.time(), table_metrics)]

# Use draw_appref_with_animation() instead of draw_appref()
for app_ref, x, y, title in app_refs_info:
    draw_appref_with_animation(screen, app_ref, x, y, title, color_scheme, active_animations)
"""

# Simple function interface as requested
def move(from_loc: int, to_loc: int, app_refs_with_positions: List[Tuple]) -> AnimationState:
    """
    Simple interface function to start a move animation.
    
    Args:
        from_loc: Source memory location
        to_loc: Target memory location  
        app_refs_with_positions: List of (app_ref, start_x, start_y, title) tuples
    
    Returns:
        Animation state that needs to be updated each frame.
        
    Example usage:
        # Setup your AppRefs with their display positions
        app_refs_info = [
            (app_ref1, 50, 50, "AppRef1"),
            (app_ref2, 50, 200, "AppRef2")
        ]
        
        # Move from location 14 in any AppRef to location 18 in any AppRef
        anim = move(14, 18, app_refs_info)
        active_animations.append(anim)
    """
    return move_term_animated(app_refs_with_positions, from_loc, to_loc)
