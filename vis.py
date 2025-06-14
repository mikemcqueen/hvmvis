import pygame
from dataclasses import dataclass
import time
from typing import List, Tuple, Generic, TypeVar

from fonts import fonts, get_font_metrics
from hvm import ExpandRef, Node, NodeTerm, MemOp, Term, Interaction
from refui import *
from itrui import ItrManager
from anim import AnimManager

# Column character widths
COLUMN_CHARS = [4, 3, 3, 4]  # mem, tag, lab, loc

def get_table_metrics() -> dict:
    metrics = get_font_metrics(fonts.content)
    title_metrics = get_font_metrics(fonts.title)

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

def draw_instructions(screen: pygame.Surface, table: dict):
    instructions = [
        "SPACE: Execute next operation",
        "Click: Toggle node selection",
        "D:     Toggle show dependencies"
    ]
    y = 10
    for i, instruction in enumerate(instructions):
        text = fonts.content.render(instruction, True, WHITE)
        screen.blit(text, (10, 10 + y))
        y += table['metrics']['line_height'] + table['row_spacing']['intra_row']

def event_handler(event, ref_mgr: RefManager, itr_mgr: ItrManager, anim_mgr: AnimManager):
    if event.type == pygame.QUIT:
        return False
    elif event.type == pygame.KEYDOWN:
        if event.key == pygame.K_SPACE:
            itr_mgr.next()
        elif event.key == pygame.K_d:
            ref_mgr.toggle_show_dependencies()

        # testing
        elif event.key == pygame.K_t:
            anim_mgr.swap(14, 38, ref_mgr.disp_rects)

        elif event.key == pygame.K_q:
            return False
    elif event.type == pygame.MOUSEBUTTONDOWN:
        rect = ref_mgr.get_rect_at_position(*event.pos)
        if rect:
            rect.selected = not rect.selected
    return True

def event_loop(itrs: list[Interaction]):
    pygame.display.init()

    screen = pygame.display.set_mode((1850, 1024))
    pygame.display.set_caption("HVM Vis")
    clock = pygame.time.Clock()
    
    table = get_table_metrics()
    
    ref_mgr = RefManager(screen, table)
    anim_mgr = AnimManager(screen, ref_mgr, table)
    itr_mgr = ItrManager(screen, itrs, ref_mgr, anim_mgr, table)
    
    if itrs:
        ref_mgr.add_ref(itrs[0], "dim terminal")
    
    pygame.key.set_repeat(500, 50)
    
    running = True
    while running:
        current_time = time.monotonic()
        
        for event in pygame.event.get():
            if not event_handler(event, ref_mgr, itr_mgr, anim_mgr):
                running = False
        
        screen.fill(BLACK)
        
        draw_instructions(screen, table)
        
        ref_mgr.draw_all()
        anim_mgr.update_all(current_time)
        anim_mgr.draw_all()
        itr_mgr.draw()
        
        pygame.display.flip()
        clock.tick(30)

    pygame.quit()
