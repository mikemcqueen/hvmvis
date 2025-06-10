import pygame
from typing import List, Tuple

from claude_move2 import *

# Get the absolute path to the directory one level up (the root)
import os
import sys
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, root_dir)



from hvm import AppRef, Node, NodeTerm, MemOp, Term

# Initialize pygame font system
pygame.font.init()

# Constants for display
TITLE_FONT_SIZE = 14
FONT_SIZE = 14

BORDER_THICKNESS = 2
HEADER_BORDER_HEIGHT = 1

# Column character widths - now defines number of characters per column
COLUMN_CHARS = [4, 3, 3, 4]  # mem, tag, lab, loc (LAB is now 3 chars as requested)

# Colors
DIM_GREEN = (0, 160, 0)
DIM_YELLOW = (192, 192, 0)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GRAY = (128, 128, 128)
LIGHT_GRAY = (64, 64, 64)
# Better contrast colors
BRIGHT_GREEN = (0, 255, 0)      # Classic terminal green
LIGHT_CYAN = (224, 255, 255)    # Very light cyan
YELLOW = (255, 255, 0)          # Bright yellow
ORANGE = (255, 165, 0)          # Orange for headers

def get_font(size: int, bold: bool = True) -> pygame.font.Font:
    """Get a monospace font for consistent character spacing with better readability."""
    # Try multiple monospace fonts in order of preference
    font_names = [
        'consolas',        # Windows, excellent readability
        'menlo',           # macOS, very clean
        'monaco',          # macOS alternative
        'dejavu sans mono', # Linux
        'liberation mono', # Linux alternative
        'courier new',     # Cross-platform fallback
        'courier'          # Basic fallback
    ]
    
    for font_name in font_names:
        try:
            font_path = pygame.font.match_font(font_name, bold=bold)
            if font_path:
                return pygame.font.Font(font_path, size)
        except:
            continue
    
    # Final fallback to system default
    return pygame.font.Font(None, size)

def get_font_metrics(font: pygame.font.Font) -> dict:
    """Get useful font metrics for layout calculations."""
    char_width = font.size("X")[0]
    line_height = font.get_height()
    ascent = font.get_ascent()
    descent = font.get_descent()
    
    return {
        'char_width': char_width,
        'line_height': line_height,
        'ascent': ascent,
        'descent': descent,
        'half_char': char_width // 2,
        'quarter_line': line_height // 4,
        'half_line': line_height // 2
    }

def get_title_font() -> pygame.font.Font:
    return get_font(TITLE_FONT_SIZE, bold=True)

def get_content_font() -> pygame.font.Font:
    return get_font(FONT_SIZE, bold=True)

def get_table_metrics(font: pygame.font.Font = get_content_font(),
                      title_font: pygame.font.Font = get_title_font()) -> dict:
    metrics = get_font_metrics(font)
    title_metrics = get_font_metrics(title_font)

    col_spacing = {
        'margin': BORDER_THICKNESS + metrics['half_char'],     # Left/right margins
        'mem_term': metrics['char_width'],                 # Between MEM and Term
        'intra_term': metrics['half_char']                 # Intra-term spacing 
    }
    
    col_spacing_by_index = [
        col_spacing['margin'],                       # left margin
        col_spacing['mem_term'],                     # Between MEM and Term
        col_spacing['intra_term'],                   # Between TAG and LAB
        col_spacing['intra_term'],                   # Between LAB and LOC
        col_spacing['margin']                        # right margin
    ]

    row_spacing = {
        'title_to_header': metrics['quarter_line'],      # Between title and header
        'header_to_line':  metrics['quarter_line'],      # Between header and line
        'margin':          metrics['quarter_line'],      # Above & below row content
        'intra_row':       2                             # Between rows
    }
    
    # title / 2 + space + header + space + line
    table_header_height = (
        title_metrics['line_height'] // 2 + row_spacing['title_to_header'] +
        metrics['line_height'] + row_spacing['header_to_line'] + 
        HEADER_BORDER_HEIGHT
    )

    term_width = (
        sum(chars * metrics['char_width'] for chars in COLUMN_CHARS[1:]) +
        col_spacing['intra_term'] * 2
    )

    return {
        'col_spacing_by_index': col_spacing_by_index,

        'col_spacing': col_spacing,
        'row_spacing': row_spacing,
        
        # Column definitions
        'column_chars': COLUMN_CHARS,
        'column_widths': [chars * metrics['char_width'] for chars in COLUMN_CHARS],
        
        'table_header_height': table_header_height,
        'top_row_y': table_header_height + row_spacing['margin'],
        
        'term_width': term_width,
        
        # Derived totals for convenience
        'width': sum(chars * metrics['char_width'] for chars in COLUMN_CHARS) +
                     sum(col_spacing_by_index),
        
        # Include font metrics for reference
        'metrics': metrics,
        'title_metrics': title_metrics,
    }

def get_char_width(font: pygame.font.Font) -> int:
    return font.size("X")[0]

def calculate_column_widths(font: pygame.font.Font) -> List[int]:
    char_width = get_char_width(font)
    return [char_count * char_width for char_count in COLUMN_CHARS]

def draw_text_with_outline(surface: pygame.Surface, text: str, font: pygame.font.Font, 
                          x: int, y: int, text_color: tuple, outline_color: tuple = BLACK, outline_width: int = 1):
    # Draw outline by rendering text at offset positions
    for dx in range(-outline_width, outline_width + 1):
        for dy in range(-outline_width, outline_width + 1):
            if dx != 0 or dy != 0:  # Skip the center position
                outline_surface = font.render(text, True, outline_color)
                surface.blit(outline_surface, (x + dx, y + dy))
    
    # Draw the main text on top
    text_surface = font.render(text, True, text_color)
    surface.blit(text_surface, (x, y))
    return text_surface.get_rect(topleft=(x, y))

def format_hex_value(value: int, width: int = 4) -> str:
    """Format an integer as a zero-padded hexadecimal string."""
    return f"{value:0{width}X}"

def collect_memory_operations(app_ref: AppRef) -> List[Tuple[int, str, int, int]]:
    """
    Collect all memory operations from an AppRef's nodes.
    Returns list of tuples: (mem_loc, tag, lab, term_loc)
    """
    operations = []
    
    for node in app_ref.nodes:
        # Collect from negative term
        for load_op in node.neg.loads:
            if load_op.got:
                lab_val = load_op.got.lab if load_op.got.lab is not None else 0
                operations.append((load_op.loc, load_op.got.tag, lab_val, load_op.got.loc))
        
        for store_op in node.neg.stores:
            if store_op.put:
                lab_val = store_op.put.lab if store_op.put.lab is not None else 0
                operations.append((store_op.loc, store_op.put.tag, lab_val, store_op.put.loc))
        
        # Collect from positive term
        for load_op in node.pos.loads:
            if load_op.got:
                lab_val = load_op.got.lab if load_op.got.lab is not None else 0
                operations.append((load_op.loc, load_op.got.tag, lab_val, load_op.got.loc))
        
        for store_op in node.pos.stores:
            if store_op.put:
                lab_val = store_op.put.lab if store_op.put.lab is not None else 0
                operations.append((store_op.loc, store_op.put.tag, lab_val, store_op.put.loc))
    
    # Remove duplicates and sort by memory location
    #   unique_ops = list(set(operations))
    #    unique_ops.sort(key=lambda x: x[0])
    
    return operations

def calculate_appref_dimensions(app_ref: AppRef) -> Tuple[int, int]:
    """Calculate the required dimensions for displaying an AppRef."""
    operations = collect_memory_operations(app_ref)
    
    # Get table metrics for layout calculations
    table = get_table_metrics()
    
    # Width: all content + all spacing (already calculated in total_content_width)
    width = table['width']
    
    height = (
        table['table_header_height'] + table['row_spacing']['margin'] * 2 + 
        len(operations) * (table['metrics']['line_height'] + table['row_spacing']['intra_row']) -
        table['row_spacing']['intra_row'] + BORDER_THICKNESS
    )
    
    return width, height

def draw_appref(surface: pygame.Surface, app_ref: AppRef, x: int, y: int, title: str = "AppRef",
                color_scheme: str = "terminal"):
    if color_scheme == "bright terminal":
        text_color = BRIGHT_GREEN
        header_color = YELLOW
        border_color = BRIGHT_GREEN
        line_color = BRIGHT_GREEN
    elif color_scheme == "dim terminal":
        text_color = DIM_GREEN
        header_color = DIM_YELLOW
        border_color = DIM_GREEN
        line_color = DIM_GREEN
    else:  # soft
        text_color = LIGHT_CYAN
        header_color = WHITE
        border_color = LIGHT_CYAN
        line_color = LIGHT_CYAN
    
    operations = collect_memory_operations(app_ref)
    width, height = calculate_appref_dimensions(app_ref)
    
    title_font = get_title_font()
    font = get_content_font()
    
    # Get unified table metrics
    table = get_table_metrics()
    
    # Draw background
    pygame.draw.rect(surface, BLACK, (x, y, width, height))
    
    # Draw border (will be clipped by title)
    border_rect = pygame.Rect(x, y, width, height)
    pygame.draw.rect(surface, border_color, border_rect, BORDER_THICKNESS)
    
    # Draw title with background to clip the border
    title_surface = title_font.render(title, True, header_color)
    title_width = title_surface.get_width()
    title_x = x + (width - title_width) // 2
    title_y = y - title_font.get_height() // 2
    
    # Draw black background behind title to "clip" the border
    title_bg_rect = pygame.Rect(title_x - 5, title_y, title_width + 10, title_font.get_height())
    pygame.draw.rect(surface, BLACK, title_bg_rect)
    
    # Draw the title text
    surface.blit(title_surface, (title_x, title_y))
    
    # Column headers with bold font positioned relative to title using table metrics
    headers = ["MEM", "TAG", "LAB", "LOC"]
    # Position header text relative to title using centralized spacing values
    title_bottom = title_y + table['title_metrics']['line_height']
    header_y = title_bottom + table['row_spacing']['title_to_header']
    current_x = x + table['col_spacing']['margin']  # left border spacing
    
    for i, header in enumerate(headers):
        header_surface = font.render(header, True, header_color)
        surface.blit(header_surface, (current_x, header_y))
        current_x += table['column_widths'][i]
        if i < len(headers) - 1:  # Add inter-column spacing if not the last column
            current_x += table['col_spacing_by_index'][i + 1]
    
    # Draw horizontal line under headers
    line_y = header_y + table['metrics']['line_height'] + table['row_spacing']['header_to_line']
    line_left = x + table['col_spacing']['margin']
    line_right = x + width - table['col_spacing']['margin']
    pygame.draw.line(surface, line_color, (line_left, line_y), (line_right, line_y), 1)
    
    # Draw data rows with dynamic positioning
    row_y = line_y + HEADER_BORDER_HEIGHT + table['row_spacing']['margin'] 
    #row_y = table['top_row_y']
    for mem_loc, tag, lab, term_loc in operations:
        current_x = x + table['col_spacing']['margin'] 
        
        values = [
            f"{mem_loc:04d}",              # MEM: 4 chars
            tag[:3],                       # TAG: 3 chars
            f"{lab:03d}",                  # LAB: 3 chars zero-padded
            f"{term_loc:04d}"              # LOC: 4 chars zero-padded
        ]
        
        # Draw each column
        for i, value in enumerate(values):
            value_surface = font.render(value, True, text_color)
            surface.blit(value_surface, (current_x, row_y))
            current_x += table['column_widths'][i]
            if i < len(values) - 1:  # Add inter-column spacing if not the last column
                current_x += table['col_spacing_by_index'][i + 1]
        
        row_y += table['metrics']['line_height'] + table['row_spacing']['intra_row'] 

def draw_multiple_apprefs(surface: pygame.Surface, app_refs: List[Tuple[AppRef, str]], 
                         start_x: int = 10, start_y: int = 10, spacing: int = 20,
                         color_scheme: str = "terminal"):
    """
    Draw multiple AppRefs on the surface with automatic positioning.
    
    Args:
        surface: Pygame surface to draw on
        app_refs: List of (AppRef, title) tuples
        start_x, start_y: Starting position
        spacing: Vertical spacing between AppRefs
        color_scheme: "terminal", "high_contrast", or "soft"
    """
    current_y = start_y
    
    for app_ref, title in app_refs:
        draw_appref(surface, app_ref, start_x, current_y, title, color_scheme)
        _, height = calculate_appref_dimensions(app_ref)
        current_y += height + spacing

def make_example_apprefs():
    app_refs = []

    # 3 @ 14
    terms = [Term("MAT", 0, 16),
             Term("VAR", 0, 16),
             Term("SUB", 0, 0),
             Term("SUB", 0, 18),
             Term("REF", 0, 4),
             Term("SUB", 0, 20),
             Term("REF", 0, 5),
             Term("SUB", 0, 0)]

    ref = AppRef(3)
    for i in range(0, len(terms), 2):
        loc = 14+i
        op1 = MemOp(i, 0, "APPREF", "STOR", 0, terms[i], None, loc)
        op2 = MemOp(i+1, 0, "APPREF", "STOR", 0, terms[i+1], None, loc+1)
        neg = NodeTerm(terms[i], stores=[op1])
        pos = NodeTerm(terms[i+1], stores=[op2])
        nod = Node(loc, ref, neg, pos)
        ref.nodes.append(nod)
    app_refs.append(ref)

    # 5 @ 24
    terms = [Term("DUP", 0, 26),
             Term("LAM", 0, 28),
             Term("SUB", 0, 0),
             Term("SUB", 0, 0),
             Term("DUP", 0, 30),
             Term("VAR", 0, 49),
             Term("SUB", 0, 0),
             Term("SUB", 0, 0),
             Term("VAR", 0, 31),
             Term("SUB", 0, 0),
             Term("VAR", 0, 33),
             Term("SUB", 0, 0),
             Term("VAR", 0, 27),
             Term("APP", 0, 38),
             Term("VAR", 0, 35),
             Term("SUB", 0, 0),
             Term("VAR", 0, 30),
             Term("SUB", 0, 0),
             Term("VAR", 0, 26),
             Term("APP", 0, 44),
             Term("VAR", 0, 41),
             Term("SUB", 0, 0),
             Term("VAR", 0, 45),
             Term("APP", 0, 48),
             Term("VAR", 0, 39),
             Term("SUB", 0, 0)]


    ref = AppRef(5)
    for i in range(0, len(terms), 2):
        loc = 24+i
        op1 = MemOp(i, 0, "APPREF", "STOR", 0, terms[i], None, loc)
        op2 = MemOp(i+1, 0, "APPREF", "STOR", 0, terms[i+1], None, loc+1)
        neg = NodeTerm(terms[i], stores=[op1])
        pos = NodeTerm(terms[i+1], stores=[op2])
        nod = Node(loc, ref, neg, pos)
        ref.nodes.append(nod)
    app_refs.append(ref)

    # 6 @ 50
    terms = [Term("SUB", 0, 0),
             Term("LAM", 0, 52),
             Term("SUB", 0, 0),
             Term("LAM", 0, 54),
             Term("APP", 0, 56),
             Term("LAM", 0, 60),
             Term("VAR", 0, 50),
             Term("APP", 0, 58),
             Term("VAR", 0, 52),
             Term("SUB", 0, 0),
             Term("ERA", 0, 0),
             Term("VAR", 0, 59)]
    
    ref = AppRef(6)
    for i in range(0, len(terms), 2):
        loc = 50+i
        op1 = MemOp(i, 0, "APPREF", "STOR", 0, terms[i], None, loc)
        op2 = MemOp(i+1, 0, "APPREF", "STOR", 0, terms[i+1], None, loc+1)
        neg = NodeTerm(terms[i], stores=[op1])
        pos = NodeTerm(terms[i+1], stores=[op2])
        nod = Node(loc, ref, neg, pos)
        ref.nodes.append(nod)
    app_refs.append(ref)

    return app_refs

def ref_name(ref: int):
    d = {
        0: "height",
        1: "leaf",
        2: "main",
        3: "make",
        4: "make_leaf",
        5: "make_node",
        6: "node",
        7: "sum",
        8: "sum_leaf",
        9: "sum_node"
    }
    return d[ref]

# Example usage function
def create_example_display():
    """
    Create an example pygame window displaying AppRefs.
    This is a demonstration of how to use the display functions.
    """
    pygame.init()
    
    app_refs = make_example_apprefs()

    create_animated_example(app_refs)

    """
    # Create display
    screen = pygame.display.set_mode((1280, 1024))
    pygame.display.set_caption("AppRef Display Example")
    clock = pygame.time.Clock()
    
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
                move(14, 34)
                
        screen.fill(BLACK)
        
        y = 50
        for a in app_refs:
            # Try different color schemes - change this to test different options
            draw_appref(screen, a, 50, y, ref_name(a.ref), "dim terminal")
            y += calculate_appref_dimensions(a)[1] + 20
            
        pygame.display.flip()
        clock.tick(60)
    
    pygame.quit()
    """

if __name__ == "__main__":
    create_example_display()
