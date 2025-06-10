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
FONT_SIZE = 14
HEADER_FONT_SIZE = 14
BORDER_WIDTH = 2
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

def get_font(size: int = FONT_SIZE, bold: bool = True) -> pygame.font.Font:
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

def get_table_metrics(font: pygame.font.Font) -> dict:
    """Get comprehensive table layout metrics based on font characteristics."""
    metrics = get_font_metrics(font)
    header_font = get_font(HEADER_FONT_SIZE, bold=True)
    header_metrics = get_font_metrics(header_font)
    
    # Column spacing - includes ALL horizontal spacing from inner edge of border to inner edge of border
    # Using font metrics for semantic spacing choices, accounting for border width
    col_spacing = [
        BORDER_WIDTH + metrics['half_char'],     # [0] Left border inner edge to MEM (border + spacing)
        metrics['char_width'],                   # [1] MEM to TAG (standard inter-column)
        metrics['half_char'],                   # [2] TAG to LAB (standard inter-column)
        metrics['half_char'],                   # [3] LAB to LOC (standard inter-column)  
        metrics['half_char'] + BORDER_WIDTH      # [4] LOC to right border inner edge (spacing + border)
    ]
    
    # Row spacing - vertical spacing with mixed reference points
    # Note: [0] is not used since header positioning is title-relative, not border-relative
    row_spacing = [
        metrics['quarter_line'],                 # [0] unused - header positioned relative to title
        metrics['line_height'],                  # [1] header_height: full line for header text
        metrics['quarter_line'],                 # [2] header_to_line: subtle separator spacing
        metrics['quarter_line'],                 # [3] line_to_data: subtle separator spacing
        metrics['line_height'],                  # [4] between_rows: full line between data rows
        metrics['quarter_line'] + BORDER_WIDTH   # [5] bottom_margin + bottom border
    ]
    
    # Title-relative positioning metrics
    title_to_header_spacing = metrics['quarter_line'] + metrics['descent']
    title_height = header_metrics['line_height']
    title_extends_above = title_height // 2
    
    return {
        # Spacing arrays using semantic font metrics
        'col_spacing': col_spacing,
        'row_spacing': row_spacing,
        
        # Column definitions
        'column_chars': COLUMN_CHARS,
        'column_widths': [chars * metrics['char_width'] for chars in COLUMN_CHARS],
        
        # Title positioning metrics
        'title_to_header_spacing': title_to_header_spacing,
        'title_height': title_height,
        'title_extends_above': title_extends_above,
        
        # Derived totals for convenience
        'total_content_width': sum(chars * metrics['char_width'] for chars in COLUMN_CHARS) + 
                              sum(col_spacing),
        
        # Include font metrics for reference
        'font_metrics': metrics,
        'header_font_metrics': header_metrics,
    }

def get_char_width(font: pygame.font.Font) -> int:
    """Get the width of a single character in the monospace font."""
    return font.size("X")[0]

def calculate_column_widths(font: pygame.font.Font) -> List[int]:
    """Calculate pixel widths for each column based on character count."""
    char_width = get_char_width(font)
    return [char_count * char_width for char_count in COLUMN_CHARS]

def draw_text_with_outline(surface: pygame.Surface, text: str, font: pygame.font.Font, 
                          x: int, y: int, text_color: tuple, outline_color: tuple = BLACK, outline_width: int = 1):
    """Draw text with an outline for better readability."""
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
    font = get_font(FONT_SIZE)
    table = get_table_metrics(font)
    
    # Width: all content + all spacing (already calculated in total_content_width)
    width = table['total_content_width']
    
    # Height: calculated from title positioning + header + data rows using table metrics
    height = (
        table['title_extends_above'] +  # title extends above border
        table['title_to_header_spacing'] +  # title to header spacing
        table['row_spacing'][1] +  # header_height
        table['row_spacing'][2] +  # header_to_line
        table['row_spacing'][3] +  # line_to_data
        len(operations) * table['row_spacing'][4] +  # data rows
        table['row_spacing'][5]    # bottom_margin
    )
    
    # Ensure minimum width for title
    title_font = get_font(HEADER_FONT_SIZE)
    
    return width, height

def draw_appref(surface: pygame.Surface, app_ref: AppRef, x: int, y: int, title: str = "AppRef",
                color_scheme: str = "terminal"):
    """
    Draw an AppRef on the given surface at the specified position.
    
    Args:
        surface: Pygame surface to draw on
        app_ref: AppRef object to display
        x, y: Top-left position to draw at
        title: Title text to display in the border
        color_scheme: "terminal", "high_contrast", or "soft"
    """
    # Choose color scheme
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
    
    # Fonts - use bold for headers
    font = get_font(FONT_SIZE)
    header_font = get_font(HEADER_FONT_SIZE, bold=True)
    bold_font = get_font(FONT_SIZE, bold=True)
    
    # Get unified table metrics
    table = get_table_metrics(font)
    
    # Draw background
    pygame.draw.rect(surface, BLACK, (x, y, width, height))
    
    # Draw border (will be clipped by title)
    border_rect = pygame.Rect(x, y, width, height)
    pygame.draw.rect(surface, border_color, border_rect, BORDER_WIDTH)
    
    # Draw title with background to clip the border
    title_surface = header_font.render(title, True, header_color)
    title_width = title_surface.get_width()
    title_x = x + (width - title_width) // 2
    title_y = y - header_font.get_height() // 2
    
    # Draw black background behind title to "clip" the border
    title_bg_rect = pygame.Rect(title_x - 5, title_y, title_width + 10, header_font.get_height())
    pygame.draw.rect(surface, BLACK, title_bg_rect)
    
    # Draw the title text
    surface.blit(title_surface, (title_x, title_y))
    
    # Column headers with bold font positioned relative to title using table metrics
    headers = ["MEM", "TAG", "LAB", "LOC"]
    # Position header text relative to title using centralized spacing values
    title_bottom = title_y + table['title_height']
    header_y = title_bottom + table['title_to_header_spacing']
    current_x = x + table['col_spacing'][0]  # left border spacing
    
    for i, header in enumerate(headers):
        header_surface = bold_font.render(header, True, header_color)
        surface.blit(header_surface, (current_x, header_y))
        current_x += table['column_widths'][i]
        if i < len(headers) - 1:  # Add inter-column spacing if not the last column
            current_x += table['col_spacing'][i + 1]
    
    # Draw horizontal line under headers
    line_y = header_y + table['row_spacing'][1] + table['row_spacing'][2]  # header_height + header_to_line
    line_left = x + BORDER_WIDTH + table['font_metrics']['half_char']  # same as left content spacing
    line_right = x + width - BORDER_WIDTH - table['font_metrics']['half_char']  # same as right content spacing
    pygame.draw.line(surface, line_color, (line_left, line_y), (line_right, line_y), 1)
    
    # Draw data rows with dynamic positioning
    row_y = line_y + table['row_spacing'][3]  # line_to_data spacing
    for mem_loc, tag, lab, term_loc in operations:
        current_x = x + table['col_spacing'][0]  # left border spacing
        
        # Format values - adjust LAB to 3 characters as requested
        values = [
            f"{mem_loc:04d}", #format_hex_value(mem_loc, 4),  # MEM: 4 chars
            tag[:3],                       # TAG: truncate to 3 chars if needed
            f"{lab:03d}",                  # LAB: 3 chars zero-padded
            f"{term_loc:04d}"              # LOC: 4 chars zero-padded
        ]
        
        # Draw each column
        for i, value in enumerate(values):
            value_surface = font.render(value, True, text_color)
            surface.blit(value_surface, (current_x, row_y))
            current_x += table['column_widths'][i]
            if i < len(values) - 1:  # Add inter-column spacing if not the last column
                current_x += table['col_spacing'][i + 1]
        
        row_y += table['row_spacing'][4]  # between_rows spacing

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
    """
    # Create some example data (you would replace this with your actual AppRef data)
    example_term1 = Term("VAR", 0x1000, 0)
    example_term2 = Term("APP", 0x2000, 1)
    
    example_memop1 = MemOp(1, 0, "main", "LOAD", 0, None, example_term1, 0x1000)
    example_memop2 = MemOp(2, 0, "main", "STOR", 0, example_term2, None, 0x2000)
    
    example_node_term1 = NodeTerm(example_term1, loads=[example_memop1])
    example_node_term2 = NodeTerm(example_term2, stores=[example_memop2])
    
    example_app_ref = AppRef(1)
    example_node = Node(0x1000, example_app_ref, example_node_term1, example_node_term2)
    example_app_ref.nodes = [example_node]
    """

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
