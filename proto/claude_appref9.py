import pygame

from dataclasses import dataclass
from typing import List, Tuple, Generic, TypeVar
#from claude_move2 import *

# Get the absolute path to the directory one level up (the root)
import os
import sys
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, root_dir)

from hvm import ExpandRef, Node, NodeTerm, MemOp, Term

# Constants for display
TITLE_FONT_SIZE = 14
FONT_SIZE = 14

# Column character widths
COLUMN_CHARS = [4, 3, 3, 4]  # mem, tag, lab, loc

# Colors
DIM_GREEN = (0, 160, 0)
DIM_YELLOW = (192, 192, 0)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GRAY = (128, 128, 128)
LIGHT_GRAY = (64, 64, 64)
# Better contrast colors
BRIGHT_GREEN = (0, 255, 0)      # Classic terminal green
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

"""
def get_table_metrics(font: pygame.font.Font = get_content_font(),
                      title_font: pygame.font.Font = get_title_font()) -> dict:
    metrics = get_font_metrics(font)
    title_metrics = get_font_metrics(title_font)

    border_thickness = 2

    col_spacing = {
        'margin': border_thickness + metrics['half_char'],     # Left/right margins
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
        metrics['line_height'] + row_spacing['header_to_line'] + 1
    )

    term_width = (
        sum(chars * metrics['char_width'] for chars in COLUMN_CHARS[1:]) +
        col_spacing['intra_term'] * 2
    )

    layout = {
        'left_margin': 20,
        'top_margin':  50,
        'vert_spacing': 20,
        'horz_spacing': term_width + metrics['char_width'] * 2
    }

    return {
        'col_spacing_by_index': col_spacing_by_index,
        'col_spacing': col_spacing,
        'row_spacing': row_spacing,
        
        'column_chars': COLUMN_CHARS,
        'column_widths': [chars * metrics['char_width'] for chars in COLUMN_CHARS],
        
        'table_header_height': table_header_height,
        'table_border_thickness': border_thickness,

        'top_row_y': table_header_height + row_spacing['margin'],
        
        'term_width': term_width,
        
        'layout': layout,

        'width': sum(chars * metrics['char_width'] for chars in COLUMN_CHARS) +
                     sum(col_spacing_by_index),

        'metrics': metrics,
        'title_metrics': title_metrics,
    }
"""

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

def collect_memory_operations(ref: ExpandRef) -> List[Tuple[int, str, int, int]]:
    """
    Collect all memory operations from an ExpandRef's nodes.
    Returns list of tuples: (mem_loc, tag, lab, term_loc)
    """
    operations = []
    
    for node in ref.nodes:
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
    
    return operations

"""
def draw_appref(surface: pygame.Surface, ref: ExpandRef, x: int, y: int,
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
    
    operations = collect_memory_operations(ref)
    width, height = calculate_appref_dimensions(ref)
    
    title_font = get_title_font()
    font = get_content_font()
    
    # Get unified table metrics
    table = get_table_metrics()
    
    # Draw background
    pygame.draw.rect(surface, BLACK, (x, y, width, height))
    
    # Draw border (will be clipped by title)
    border_rect = pygame.Rect(x, y, width, height)
    pygame.draw.rect(surface, border_color, border_rect, table['table_border_thickness'])
    
    # Draw title with background to clip the border
    title_surface = title_font.render(ref_name(ref.ref), True, header_color)
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
    row_y = line_y + 1 + table['row_spacing']['margin'] 
    #row_y = table['top_row_y']
    for mem_loc, tag, lab, term_loc in operations:
        current_x = x + table['col_spacing']['margin'] 
        values = [
            f"{mem_loc:04d}",
            tag[:3],
            f"{lab:03d}",
            f"{term_loc:04d}"
        ]
        # Draw each column
        for i, value in enumerate(values):
            value_surface = font.render(value, True, text_color)
            surface.blit(value_surface, (current_x, row_y))
            current_x += table['column_widths'][i]
            if i < len(values) - 1:  # Add inter-column spacing if not the last column
                current_x += table['col_spacing_by_index'][i + 1]
        
        row_y += table['metrics']['line_height'] + table['row_spacing']['intra_row'] 
"""

def make_example_apprefs():
    refs = []

    # 3 @ 14
    terms = [
        Term("MAT", 0, 16),
        Term("VAR", 0, 16),
        Term("SUB", 0, 0),
        Term("SUB", 0, 18),
        Term("REF", 0, 4),
        Term("SUB", 0, 20),
        Term("REF", 0, 5),
        Term("SUB", 0, 0)
    ]

    ref = ExpandRef(3)
    for i in range(0, len(terms), 2):
        loc = 14+i
        op1 = MemOp(i, 0, "APPREF", "STOR", 0, terms[i], None, loc)
        op2 = MemOp(i+1, 0, "APPREF", "STOR", 0, terms[i+1], None, loc+1)
        neg = NodeTerm(terms[i], stores=[op1])
        pos = NodeTerm(terms[i+1], stores=[op2])
        nod = Node(ref, neg, pos)
        ref.nodes.append(nod)
    refs.append(ref)

    # 5 @ 24
    terms = [
        Term("DUP", 0, 26),
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
        Term("SUB", 0, 0)
    ]

    ref = ExpandRef(5)
    for i in range(0, len(terms), 2):
        loc = 24+i
        op1 = MemOp(i, 0, "APPREF", "STOR", 0, terms[i], None, loc)
        op2 = MemOp(i+1, 0, "APPREF", "STOR", 0, terms[i+1], None, loc+1)
        neg = NodeTerm(terms[i], stores=[op1])
        pos = NodeTerm(terms[i+1], stores=[op2])
        nod = Node(ref, neg, pos)
        ref.nodes.append(nod)
    refs.append(ref)

    # 6 @ 50
    terms = [
        Term("SUB", 0, 0),
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
        Term("VAR", 0, 59)
    ]
    
    ref = ExpandRef(6)
    for i in range(0, len(terms), 2):
        loc = 50+i
        op1 = MemOp(i, 0, "APPREF", "STOR", 0, terms[i], None, loc)
        op2 = MemOp(i+1, 0, "APPREF", "STOR", 0, terms[i+1], None, loc+1)
        neg = NodeTerm(terms[i], stores=[op1])
        pos = NodeTerm(terms[i+1], stores=[op2])
        nod = Node(ref, neg, pos)
        ref.nodes.append(nod)
    refs.append(ref)

    return refs

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
    pygame.init()
    screen = pygame.display.set_mode((1280, 950), 0)
    pygame.display.set_caption("HVM Vis")

    refs = make_example_apprefs()

    create_animated_example(screen, refs)

    """
    # Create display
    screen = pygame.display.set_mode((1280, 1024))
    pygame.display.set_caption("ExpandRef Display Example")
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
        for a in refs:
            # Try different color schemes - change this to test different options
            draw_appref(screen, a, 50, y, ref_name(a.ref), "dim terminal")
            y += calculate_appref_dimensions(a)[1] + 20
            
        pygame.display.flip()
        clock.tick(60)
    
    pygame.quit()
    """

if __name__ == "__main__":
    create_example_display()
