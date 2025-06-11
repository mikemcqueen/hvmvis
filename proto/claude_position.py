import pygame
from dataclasses import dataclass
from typing import List, Tuple, Generic, TypeVar

from claude_appref9 import *
#from claude_move2 import *

# Get the absolute path to the directory one level up (the root)
import os
import sys
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, root_dir)

from hvm import AppRef, Node, NodeTerm, MemOp, Term
from apprefui import *

# Initialize pygame font system
pygame.font.init()


# Column character widths
COLUMN_CHARS = [4, 3, 3, 4]  # mem, tag, lab, loc

"""
# Colors
DIM_GREEN = (0, 160, 0)
DIM_YELLOW = (192, 192, 0)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GRAY = (128, 128, 128)
LIGHT_GRAY = (64, 64, 64)
LIGHT_CYAN = (173, 216, 230)
# Better contrast colors
BRIGHT_GREEN = (0, 255, 0)      # Classic terminal green
YELLOW = (255, 255, 0)          # Bright yellow
ORANGE = (255, 165, 0)          # Orange for headers
"""

def get_font(size: int, bold: bool = True) -> pygame.font.Font:
    """Get a monospace font for consistent character spacing with better readability."""
    font_names = [
        'consolas', 'menlo', 'monaco', 'dejavu sans mono', 
        'liberation mono', 'courier new', 'courier'
    ]
    
    for font_name in font_names:
        try:
            font_path = pygame.font.match_font(font_name, bold=bold)
            if font_path:
                return pygame.font.Font(font_path, size)
        except:
            continue
    
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

    border_thickness = 2

    col_spacing = {
        'margin': border_thickness + metrics['half_char'],
        'mem_term': metrics['char_width'],
        'intra_term': metrics['half_char']
    }
    
    col_spacing_by_index = [
        col_spacing['margin'],
        col_spacing['mem_term'],
        col_spacing['intra_term'],
        col_spacing['intra_term'],
        col_spacing['margin']
    ]

    row_spacing = {
        'title_to_header': metrics['quarter_line'],
        'header_to_line': metrics['quarter_line'],
        'margin': metrics['quarter_line'],
        'intra_row': 2
    }
    
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
        'top_margin':  85,
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

# Rest of the original functions remain the same...

def make_example_apprefs():
    """Create example AppRefs for testing."""
    app_refs = []

    # 3 @ 14
    terms = [
        Term("MAT", 0, 16), Term("VAR", 0, 16), Term("SUB", 0, 0), Term("SUB", 0, 18),
        Term("REF", 0, 4), Term("SUB", 0, 20), Term("REF", 0, 5), Term("SUB", 0, 0)
    ]
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

    return app_refs

def add_new_app_ref(manager, loc: int) -> int:
    new_ref = AppRef(len(manager.app_ref_rects) + 10)
    # Add some dummy nodes for demonstration
    term1 = Term("APP", 0, 100)
    term2 = Term("LAM", 0, 101)
    op1 = MemOp(0, 0, "APPREF", "STOR", 0, term1, None, loc)
    op2 = MemOp(1, 0, "APPREF", "STOR", 0, term2, None, loc + 1)
    neg = NodeTerm(term1, stores=[op1])
    pos = NodeTerm(term2, stores=[op2])
    node = Node(100, new_ref, neg, pos)
    new_ref.nodes.append(node)
    manager.add_appref(new_ref, "dim terminal")
    return loc + 2

def create_dynamic_example():
    pygame.init()
    screen = pygame.display.set_mode((1280, 950))
    pygame.display.set_caption("HVM Vis")
    clock = pygame.time.Clock()
    
    # Create the manager
    manager = AppRefManager(screen, get_table_metrics())
    
    loc = 100
    # Add initial AppRefs
    app_refs = make_example_apprefs()
    for app_ref in app_refs:
        manager.add_appref(app_ref, "dim terminal")
    
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:
                    loc = add_new_app_ref(manager, loc)
                elif event.key == pygame.K_r:
                    # Reposition all AppRefs
                    manager.reposition_all()
            elif event.type == pygame.MOUSEBUTTONDOWN:
                # Click to remove an AppRef
                clicked_rect = manager.get_appref_at_position(*event.pos)
                if clicked_rect:
                    manager.remove_appref(clicked_rect.app_ref)
        
        screen.fill(BLACK)
        manager.draw_all(screen)
        
        # Draw instructions
        font = get_content_font()
        instructions = [
            "SPACE: Add new AppRef",
            "R: Reposition all",
            "Click: Remove AppRef"
        ]
        for i, instruction in enumerate(instructions):
            text = font.render(instruction, True, WHITE)
            screen.blit(text, (10, 10 + i * 20))
        
        pygame.display.flip()
        clock.tick(60)
    
    pygame.quit()

if __name__ == "__main__":
    create_dynamic_example()
