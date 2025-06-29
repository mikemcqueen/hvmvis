import time

import pygame

from commonui import *
from fonts import fonts, get_font_metrics
from freeui import FreeManager
from hvm import Interaction, Term
from refui import RefManager
from itrui import ItrManager
from anim import AnimManager
from text_cache import TextCache

def get_table_metrics() -> dict:
    metrics = get_font_metrics(fonts.content)
    title_metrics = get_font_metrics(fonts.title)

    column_chars = [3, 3, 3, 3]  # mem, tag, lab, loc
    border_thickness = 2

    col_spacing = {
        'margin': border_thickness + metrics['half_char'],
        'mem_term': metrics['half_char'],
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
        'title_to_header': 2,
        'header_to_line': 2,
        'margin': 2,
        'intra_row': 2
    }
    header_height = (
        title_metrics['line_height'] // 2 + row_spacing['title_to_header'] +
        metrics['line_height'] + row_spacing['header_to_line'] + 1
    )
    term_width = (
        sum(chars * metrics['char_width'] for chars in column_chars[1:]) +
        col_spacing['intra_term'] * (len(column_chars[1:]) - 1)
    )
    screen_width = 1850
    screen_height = 925
    itr_section_width = 240
    itr_section_height = 320

    free_section_top = 20
    free_section_width = metrics['char_width'] * 8 * 5 # 8 chars * 5 columns
    free_section_height = screen_height - itr_section_height - free_section_top

    free_layout = {
        'rect': pygame.Rect(screen_width - free_section_width, free_section_top,
                            free_section_width, free_section_height),
        'col_width': metrics['char_width'] * 7, # '000:0 0'
        'col_spacing': metrics['char_width']
    }

    ref_left_margin = metrics['char_width'] * 4
    ref_horz_spacing = term_width + metrics['char_width'] * 2
    ref_width = (
        sum(chars * metrics['char_width'] for chars in column_chars) +
        sum(col_spacing_by_index)
    )
    ref_section_width = screen_width - max(itr_section_width, free_section_width)
    #FUDGE = 35
    #ref_section_width = (ref_left_margin + ref_width * 2 + ref_horz_spacing * 2 + FUDGE)
    ref_scroll = ref_width + ref_horz_spacing

    layout = {
        'left_margin': ref_left_margin,
        'top_margin':  85,
        'vert_spacing': 10,
        'horz_spacing': ref_horz_spacing,
        'section_width': ref_section_width,
        #'columns': ref_columns,
        'scroll_width': ref_scroll,
        'scroll_offset': 0,
        'first_column': 0
    }
    return {
        'width': screen_width,
        'height':  screen_height,
        'top': layout['top_margin'] - metrics['line_height'] - metrics['line_height'] // 2,
        'col_spacing_by_index': col_spacing_by_index,
        'col_spacing': col_spacing,
        'row_spacing': row_spacing,
        'column_chars': column_chars,
        'column_widths': [chars * metrics['char_width'] for chars in column_chars],
        'header_height': header_height,
        'border_thickness': border_thickness,
        'top_row_y': header_height + row_spacing['margin'],
        'term_width': term_width,
        'layout': layout,
        'ref_width': ref_width,
        'metrics': metrics,
        'title_metrics': title_metrics,
        'free': free_layout,
    }

def draw_instructions(screen: pygame.Surface, table: dict):
    if not 'speed' in table: table['speed'] = 1
    instructions = [
        "SPACE: Execute next        ←/→: Scroll",
        f"Click: Toggle select       +/-: Speed({table['speed']})",
        #"D:     Toggle dependencies",
        "M:     Toggle metadata"
        #,f"+/-:   Speed({table['speed']})"
    ]
    y = 0
    color = WHITE
    line_height = table['metrics']['line_height'] + table['row_spacing']['intra_row']
    for i, instruction in enumerate(instructions):
        text = fonts.content.render(instruction, True, color)
        screen.blit(text, (10, 10 + y))
        y += line_height

def add_speed(amt: int, table: dict):
    speed = table['speed'] + amt
    table['speed'] = max(1, min(6, speed))

def event_handler(event, ref_mgr: RefManager, itr_mgr: ItrManager, anim_mgr: AnimManager, table: dict):
    if event.type == pygame.QUIT:
        return False
    elif event.type == pygame.KEYDOWN:
        if event.key == pygame.K_SPACE:
            itr_mgr.next()
        #elif event.key == pygame.K_d:
        #    ref_mgr.toggle_show_dependencies()
        elif event.key == pygame.K_m:
            ref_mgr.toggle_show_metadata()
        elif event.key == pygame.K_MINUS:
            add_speed(-1, table)
        elif event.key == pygame.K_EQUALS and event.mod & pygame.KMOD_SHIFT:
            add_speed(1, table)
        elif event.key == pygame.K_LEFT:
            ui.scroll_mgr.scroll(-1, table, False)
        elif event.key == pygame.K_RIGHT:
            ui.scroll_mgr.scroll(1, table, False)
        elif event.key == pygame.K_q:
            return False
    elif event.type == pygame.MOUSEBUTTONDOWN:
        rect = ref_mgr.rect_at_position(*event.pos)
        if rect:
            rect.selected = not rect.selected
    return True

def event_loop(root: Term, itrs: list[Interaction]):
    pygame.display.init()

    table = get_table_metrics()
    screen = pygame.display.set_mode((table['width'], table['height']))
    pygame.display.set_caption("HVM3 Node Visualizer")
    clock = pygame.time.Clock()

    text_cache = TextCache()

    ref_mgr = RefManager(screen, table, text_cache)
    anim_mgr = AnimManager(screen, ref_mgr, table, text_cache)
    free_mgr = FreeManager(screen, ref_mgr, table)
    itr_mgr = ItrManager(screen, itrs, ref_mgr, anim_mgr, free_mgr, table, text_cache)

    free_mgr.boot(root)
    itr_mgr.on_itr(itrs[0])

    pygame.key.set_repeat(500, 50)

    running = True
    while running:
        current_time = time.monotonic()

        for event in pygame.event.get():
            if not event_handler(event, ref_mgr, itr_mgr, anim_mgr, table):
                running = False

        screen.fill(BLACK)

        draw_instructions(screen, table)

        ui.scroll_mgr.update(table)
        ref_mgr.draw_all()
        anim_mgr.update_all(current_time)
        anim_mgr.draw_all()
        free_mgr.draw()
        itr_mgr.draw()

        pygame.display.flip()

        clock.tick(30)

    pygame.quit()
