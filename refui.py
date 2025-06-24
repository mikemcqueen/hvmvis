from dataclasses import dataclass
from typing import Tuple, Optional

import pygame

from commonui import Position
from fonts import fonts
from hvm import *
from text_cache import TextCache

TITLE_FONT_SIZE = 14
FONT_SIZE = 14

DIM_GREEN = (0, 160, 0)
DIM_YELLOW = (192, 192, 0)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GRAY = (128, 128, 128)
LIGHT_GRAY = (64, 64, 64)
BRIGHT_GREEN = (0, 255, 0)
YELLOW = (255, 255, 0)
BRIGHT_ORANGE = (255, 190, 30)
ORANGE = (255, 165, 0)

def ref_name(def_idx: int):
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
    if def_idx > DefIdx.MAT:
        def_idx -= DefIdx.MAT
        return f"matu32_{def_idx}"
    else:
        return d.get(def_idx, f"ref_{def_idx}")

@dataclass(eq=False)
class RefRect:
    ref: ExpandRef
    x: int
    y: int
    width: int
    height: int
    color_scheme: str = "dim terminal"
    selected: bool = False
    visible: bool = True

    def get_rect(self) -> pygame.Rect:
        return pygame.Rect(self.x, self.y, self.width, self.height)

    def get_node_term(self, loc: int) -> Optional[NodeTerm]:
        if not self.ref.contains(loc): return None
        for node in self.ref.nodes:
            for node_term in (node.pos, node.neg):
                if loc == node_term.mem_loc:
                    return node_term
        return None

    def draw_node_term(self, node_term: NodeTerm, surface: pygame.Surface, pos: Position, md: dict):
        term = node_term.term
        values = [
            f"{node_term.mem_loc:03d}",
            term.tag[:3],
            f"{term.lab:03d}",
            f"{term.loc:03d}"
        ]
        table = md['table']
        color = md['done_color'] if node_term.memops_done() else md['text_color']
        x_off = 0
        for i, value in enumerate(values):
            rndr_txt = md['text_cache'].get_rendered_text(value)
            if self.selected or (self.color_scheme == "brt terminal"):
                if not rndr_txt.brt.surface or rndr_txt.brt.color != color:
                    rndr_txt.brt.surface = md['font'].render(value, True, color)
                    rndr_txt.brt.color = color
                val_surf = rndr_txt.brt.surface
            else:
                if not rndr_txt.dim.surface or rndr_txt.dim.color != color:
                    rndr_txt.dim.surface = md['font'].render(value, True, color)
                    rndr_txt.dim.color = color
                val_surf = rndr_txt.dim.surface
                    
            surface.blit(val_surf, (pos.x + x_off, pos.y))
            if node_term.empty: # draw memory loc only for empty terms
                break
            x_off += table['column_widths'][i]
            if i < len(values) - 1:
                x_off += table['col_spacing_by_index'][i + 1]

    def draw_counts(self, node_term: NodeTerm, surface: pygame.Surface, y: int, md: dict):
        stor_idx = node_term.memop_idx
        stor_max = len(node_term.memops) - 1
        value = f"{stor_idx}/{stor_max}"
        color = md['done_color'] if node_term.memops_done() else md['text_color']
        val_surf = md['font'].render(value, True, color)
        table = md['table']
        x = self.x - (table['metrics']['char_width'] * 3 + table['metrics']['half_char'])
        surface.blit(val_surf, (x, y))

    # TODO probably move to hvm.py
    def get_redex(self, node_term: NodeTerm) -> Redex:
        ref = node_term.node.ref
        for redex in ref.redexes:
            for term in (redex.neg, redex.pos):
                if term.has_loc() and term.loc == node_term.mem_loc:
                    return term.tag
        return None

    # TODO probably move to hvm.py
    def get_kind(self, node_term: NodeTerm) -> str:
        #node = node_term.node
        itr = node_term.node.ref
        if itr.name() == AppRef.NAME:
            if node_term.mem_loc == itr.first_loc:
                return 'var'
            elif node_term.mem_loc == itr.first_loc + 1:
                return 'bod'
        #elif itr.name() == AppLam.NAME:

        """
        Term arg = take(port(1, a_loc));
        Loc ret = port(2, a_loc);

        Loc var = port(1, b_loc);
        Term bod = take(port(2, b_loc));

        move(tm, var, arg);
        move(tm, ret, bod);

        """
        redex = self.get_redex(node_term)
        if not redex: return None
        
        return None

    def draw_kind(self, node_term: NodeTerm, surface: pygame.Surface, y: int, md: dict):
        kind = self.get_kind(node_term)
        if not kind: return
        color = md['done_color'] if node_term.memops_done() else md['text_color']
        kind_surf = md['font'].render(kind, True, color)
        table = md['table']
        x = self.x + table['width'] + table['metrics']['char_width']
        surface.blit(kind_surf, (x, y))

    def draw_metadata(self, node_term: NodeTerm, surface: pygame.Surface, y: int, md: dict):
        if not md['show_md']: return
        self.draw_counts(node_term, surface, y, md)
        #self.draw_kind(node_term, surface, y, md)

    def draw(self, surface: pygame.Surface, md: dict):
        if not self.visible: return

        if self.ref.memops_done():
            text_color = ORANGE
            done_color = ORANGE
            header_color = DIM_YELLOW
            border_color = ORANGE
            line_color = ORANGE
        elif self.selected or (self.color_scheme == "bright terminal"):
            text_color = BRIGHT_GREEN
            done_color = BRIGHT_ORANGE
            header_color = YELLOW
            border_color = BRIGHT_GREEN
            line_color = BRIGHT_GREEN
        else: # not self.selected or self.color_scheme == "dim terminal":
            text_color = DIM_GREEN
            done_color = ORANGE
            header_color = DIM_YELLOW
            border_color = DIM_GREEN
            line_color = DIM_GREEN
  
        title_font = fonts.title
        font = fonts.content

        table = md['table']

        # Draw background
        pygame.draw.rect(surface, BLACK, (self.x, self.y, self.width, self.height))

        # Draw border
        border_rect = pygame.Rect(self.x, self.y, self.width, self.height)
        pygame.draw.rect(surface, border_color, border_rect, table['table_border_thickness'])

        # Draw title with background to clip the border
        title_surface = title_font.render(ref_name(self.ref.def_idx), True, header_color)
        title_width = title_surface.get_width()
        title_x = self.x + (self.width - title_width) // 2
        title_y = self.y - title_font.get_height() // 2

        title_bg_rect = pygame.Rect(title_x - 5, title_y, title_width + 10, title_font.get_height())
        pygame.draw.rect(surface, BLACK, title_bg_rect)
        surface.blit(title_surface, (title_x, title_y))

        # Column headers
        headers = ["MEM", "TAG", "LAB", "LOC"]
        title_bottom = title_y + table['title_metrics']['line_height']
        header_x = self.x + table['col_spacing']['margin']
        header_y = title_bottom + table['row_spacing']['title_to_header']

        for i, header in enumerate(headers):
            header_surface = font.render(header, True, header_color)
            surface.blit(header_surface, (header_x, header_y))
            header_x += table['column_widths'][i]
            if i < len(headers) - 1:
                header_x += table['col_spacing_by_index'][i + 1]

        # Draw horizontal line under headers
        line_y = header_y + table['metrics']['line_height'] + table['row_spacing']['header_to_line']
        line_left = self.x + table['col_spacing']['margin']
        line_right = self.x + self.width - table['col_spacing']['margin']
        pygame.draw.line(surface, line_color, (line_left, line_y), (line_right, line_y), 1)

        # Draw data rows
        md = {
            **md,
            'font': font,
            'text_color': text_color,
            'done_color': done_color,
        }
        x = self.x + table['col_spacing']['margin']
        y = line_y + 1 + table['row_spacing']['margin']
        for node in self.ref.nodes:
            for node_term in (node.neg, node.pos):
                self.draw_node_term(node_term, surface, Position(x, y), md)
                self.draw_metadata(node_term, surface, y, md)
                y += table['metrics']['line_height'] + table['row_spacing']['intra_row']

class RefManager:
    def __init__(self, screen: pygame.Surface, table: dict, text_cache: TextCache):
        self.screen = screen
        self.table = table
        self.text_cache = text_cache
        self.all_rects: list[RefRect] = []
        self.disp_rects: list[RefRect] = []
        self.ref_map = {}
        self.show_deps_only: bool = False
        self.show_md: bool = False

    def calculate_ref_dimensions(self, ref: ExpandRef) -> Tuple[int, int]:
        width = self.table['width']
        num_ops = len(ref.nodes) * 2
        height = (
            self.table['table_header_height'] + self.table['row_spacing']['margin'] * 2 +
            self.table['metrics']['line_height'] * num_ops +
            self.table['row_spacing']['intra_row'] * (num_ops - 1) +
            self.table['table_border_thickness']
        )
        return width, height

    def _add_rect(self, rect: RefRect):
        self.all_rects.append(rect)
        self.disp_rects.append(rect)
        self.ref_map[rect.ref.id] = rect

    def add_ref(self, ref: ExpandRef, color_scheme: str = "dim terminal") -> RefRect:
        width, height = self.calculate_ref_dimensions(ref)
        x, y = self._find_next_position(width, height)

        rect = RefRect(ref, x, y, width, height, color_scheme)
        self._add_rect(rect)
        return rect

    def get_rect(self, ref: ExpandRef) -> RefRect:
        return self.ref_map[ref.id] if ref.id in self.ref_map else None

    def _find_next_position(self, width: int, height: int) -> Tuple[int, int]:
        if not self.all_rects:
            return self.table['layout']['left_margin'], self.table['layout']['top_margin']

        # Try to place under last ref
        last_rect = self.all_rects[-1]
        potential_y = last_rect.y + last_rect.height + self.table['layout']['vert_spacing']

        # Check if it fits vertically and doesn't exceed screen bounds
        if potential_y + height <= self.screen.get_height():
            return last_rect.x, potential_y

        # No room in last column, create a new column
        new_column_x = last_rect.x + last_rect.width + self.table['layout']['horz_spacing']

        # Check if new column fits horizontally
        if new_column_x + width <= self.screen.get_width():
            return new_column_x, self.table['layout']['top_margin']

        # If we can't fit horizontally, wrap to a new "row" of columns
        # This is a fallback - you might want to handle this differently
        # TODO
        raise RuntimeError("ran out of screen space")

    """
    def remove_appref(self, app_ref: AppRef) -> bool:
        for i, rect in enumerate(self.app_ref_rects):
            if rect.app_ref is app_ref:
                del self.app_ref_rects[i]
                return True
        return False
    """

    def get_rect_at_position(self, x: int, y: int) -> RefRect:
        for rect in self.disp_rects:
            if rect.get_rect().collidepoint(x, y):
                return rect
        return None

    """
    def reposition_all(self):
        if not self.disp_app_refs:
            return
            
        self.disp_app_refs.clear()
        for app_ref, color_scheme in app_refs_data:
            self.add_appref(app_ref, color_scheme)
    """

    def draw_all(self):
        md = {
            'table' : self.table,
            'text_cache': self.text_cache,
            'show_md': self.show_md
        }
        for rect in self.disp_rects:
            rect.draw(self.screen, md)

    def get_selected(self) -> list[RefRect]:
        return [rect for rect in self.disp_rects if rect.selected]

    def only_rects_visible(self, rects: list[RefRect]):
        d = {}
        for rect in rects:
            d[rect.ref.id] = rect

        # hide all non-selected that aren't in supplied rects
        for rect in self.all_rects:
            if not rect.selected:
                rect.visible = rect.ref.id in d
            else:
                assert rect.visible

    def all_rects_visible(self):
        for rect in self.all_rects:
            rect.visible = True

    def rect_from_loc(self, loc: int) -> RefRect:
        #return rect for rect in self.all_rects if rect.ref.contains(loc) else None
        for rect in self.all_rects:
            if rect.ref.contains(loc):
                return rect
        return None

    def toggle_show_metadata(self):
        self.show_md = not self.show_md

    """
    def get_dep_rects(self, rect: RefRect) -> list[RefRect]:
        dep_rects = []
        while rect and rect.ref.redex:
            # ref.redex is the redex as it originally occurred from within an
            # ExpandRef. The neg term of that redex likely originated somewhere
            # else, and may have been stored and reloaded from other location(s)
            # since then.
            #
            # For <make_leaf> -> <leaf> we want to know the loc (and ref) from
            # which the neg term was *last* loaded.
            #
            neg = rect.ref.redex.neg
            # TODO: neg.tag constraint
            last_load = neg.loads and neg.loads[-1]
            if last_load and last_load.is_matnum_itr():
                loc = last_load.loc
                #print(f"redex.neg last_load {last_load} loc {loc}")

            # For <make> -> <matu32_NN> we want...
            #
            # better approach
            # elif last_load.is_applam_itr():
            #     find the APPREF for this APPLAM. that's at the LAM's loc.
            #     loc = last_load.itr.redex.pos.loc
            elif neg.tag == 'MAT':
                loc = neg.loc
                #print(f"redex.neg MAT loc {neg.term} loc {loc}")
            else:
                # fall back to the loc of the origin ref
                loc = neg.node.ref.first_loc
                #print(f"fall back redex.neg.node.ref {neg.node.ref.def_idx} first_loc {loc}")

            rect = self.rect_from_loc(loc)
            #print(f"rect from loc {loc} is {ref_name(rect.ref.def_idx) if rect else None}")
            if rect:
                dep_rects.append(rect)
        return dep_rects
    """

    def toggle_show_dependencies(self):
        """
        if self.show_deps_only:
            self.all_rects_visible()
            self.show_deps_only = False
            return

        sel_rects = self.get_selected()
        if not sel_rects:
            return

        sel_rect = sel_rects[0]
        dep_rects = self.get_dep_rects(sel_rect)

        self.only_rects_visible(dep_rects)
        self.show_deps_only = True
        """
