from dataclasses import dataclass
from enum import IntEnum
from typing import Tuple, Optional

import pygame

from commonui import *
from fonts import fonts
from hvm import *
from text_cache import TextCache

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

class Metadata(IntEnum):
    NONE = 0,
    CNT  = 1,
    CTX  = 2,
    ALL  = 3

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

    def get_node_term(self, loc: int) -> Optional[InPlaceNodeTerm]:
        if not self.ref.contains(loc): return None
        for node in self.ref.nodes:
            for nod_trm in (node.pos, node.neg):
                if loc == nod_trm.mem_loc:
                    return nod_trm
        return None

    def draw_node_term(self, nod_trm: InPlaceNodeTerm, surface: pygame.Surface, pos: Position, md: dict):
        term = nod_trm.term
        values = [
            f"{nod_trm.mem_loc:03d}",
            term.tag[:3],
            f"{term.lab:03d}",
            f"{term.loc:03d}"
        ]
        table = md['table']
        color = md['done_color'] if nod_trm.memops_done() else md['text_color']
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
            if nod_trm.empty: # draw memory loc only for empty terms
                break
            x_off += table['column_widths'][i]
            if i < len(values) - 1:
                x_off += table['col_spacing_by_index'][i + 1]

    def draw_counts(self, nod_trm: InPlaceNodeTerm, surface: pygame.Surface, y: int, md: dict):
        stor_idx = nod_trm.memop_idx
        stor_max = len(nod_trm.memops) - 1
        value = f"{stor_idx}/{stor_max}"
        color = md['done_color'] if nod_trm.memops_done() else md['text_color']
        val_surf = md['font'].render(value, True, color)
        table = md['table']
        x = self.x - (table['metrics']['char_width'] * 3 + table['metrics']['half_char']) + md['offset']
        surface.blit(val_surf, (x, y))

    """
    # TODO probably move to hvm.py
    def get_redex(self, nod_trm: NodeTerm) -> Redex:
        ref = nod_trm.node.ref
        for redex in ref.redexes:
            for term in (redex.neg, redex.pos):
                if term.has_loc() and term.loc == nod_trm.mem_loc:
                    return term.tag
        return None
    """

    def get_context(self, nod_trm: InPlaceNodeTerm) -> str:
        ctx = nod_trm.node.get_context(nod_trm)
        origin = nod_trm.origin
        if origin and origin.node:
            org_ctx = origin.node.get_context(origin)
            if org_ctx: 
                ctx = f"{ctx}<{org_ctx}"
        return ctx
    
        """
        #node = nod_trm.node
        itr = nod_trm.node.ref
        if itr.name() == AppRef.NAME:
            if nod_trm.mem_loc == itr.first_loc:
                return 'var'
            elif nod_trm.mem_loc == itr.first_loc + 1:
                return 'bod'
        #elif itr.name() == AppLam.NAME:

        Term arg = take(port(1, a_loc));
        Loc ret = port(2, a_loc);

        Loc var = port(1, b_loc);
        Term bod = take(port(2, b_loc));

        move(tm, var, arg);
        move(tm, ret, bod);

        redex = self.get_redex(nod_trm)
        if not redex: return None
        
        return None
        """

    def draw_context(self, nod_trm: InPlaceNodeTerm, surface: pygame.Surface, y: int, md: dict):
        ctx = self.get_context(nod_trm)
        if not ctx: return
        color = md['done_color'] if nod_trm.memops_done() else md['text_color']
        ctx_surf = md['font'].render(ctx, True, color)
        table = md['table']
        x = self.x + table['ref_width'] + table['metrics']['char_width'] + md['offset']
        surface.blit(ctx_surf, (x, y))

    def draw_metadata(self, nod_trm: InPlaceNodeTerm, surface: pygame.Surface, y: int, md: dict):
        show_md = md['show_md']
        if show_md in (Metadata.CNT, Metadata.ALL):
            self.draw_counts(nod_trm, surface, y, md)
        if show_md in (Metadata.CTX, Metadata.ALL):
            self.draw_context(nod_trm, surface, y, md)

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
        #pygame.draw.rect(surface, BLACK, (self.x, self.y, self.width, self.height))

        # Draw border
        rect = pygame.Rect(self.x + md['offset'], self.y, self.width, self.height)
        """
        if (rect.right + table['layout']['horz_spacing'] > table['layout']['section_width'] or
            rect.left < table['layout']['left_margin']):
            return
        """
        pygame.draw.rect(surface, border_color, rect, table['border_thickness'])

        # Draw title with background to clip the border
        title_surface = title_font.render(ref_name(self.ref.def_idx), True, header_color)
        title_width = title_surface.get_width()
        title_x = self.x + (self.width - title_width) // 2 + md['offset']
        title_y = self.y - title_font.get_height() // 2

        title_bg_rect = pygame.Rect(title_x - 5, title_y, title_width + 10, title_font.get_height())
        pygame.draw.rect(surface, BLACK, title_bg_rect)
        surface.blit(title_surface, (title_x, title_y))

        # Column headers
        headers = ["MEM", "TAG", "LAB", "LOC"]
        title_bottom = title_y + table['title_metrics']['line_height']
        header_x = self.x + table['col_spacing']['margin'] + md['offset']
        header_y = title_bottom + table['row_spacing']['title_to_header']

        for i, header in enumerate(headers):
            header_surface = font.render(header, True, header_color)
            surface.blit(header_surface, (header_x, header_y))
            header_x += table['column_widths'][i]
            if i < len(headers) - 1:
                header_x += table['col_spacing_by_index'][i + 1]

        # Draw horizontal line under headers
        line_y = header_y + table['metrics']['line_height'] + table['row_spacing']['header_to_line']
        line_left = self.x + table['col_spacing']['margin'] + md['offset']
        line_right = self.x + self.width - table['col_spacing']['margin'] + md['offset']
        pygame.draw.line(surface, line_color, (line_left, line_y), (line_right, line_y), 1)

        # Draw data rows
        md = {
            **md,
            'font': font,
            'text_color': text_color,
            'done_color': done_color,
        }
        x = self.x + table['col_spacing']['margin'] + md['offset']
        y = line_y + 1 + table['row_spacing']['margin']
        for node in self.ref.nodes:
            for nod_trm in (node.neg, node.pos):
                self.draw_node_term(nod_trm, surface, Position(x, y), md)
                self.draw_metadata(nod_trm, surface, y, md)
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
        self.show_md: Metadata = Metadata.NONE

    def get_ref_extents(self, ref: ExpandRef) -> Tuple[int, int]:
        width = self.table['ref_width']
        num_ops = len(ref.nodes) * 2
        height = (
            self.table['header_height'] + self.table['row_spacing']['margin'] * 2 +
            self.table['metrics']['line_height'] * num_ops +
            self.table['row_spacing']['intra_row'] * (num_ops - 1) +
            self.table['border_thickness']
        )
        return width, height

    def _add_rect(self, rect: RefRect):
        self.all_rects.append(rect)
        self.disp_rects.append(rect)
        self.ref_map[rect.ref.id] = rect

    def add_ref(self, ref: ExpandRef, color_scheme: str = "dim terminal") -> RefRect:
        width, height = self.get_ref_extents(ref)
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
        next_y = last_rect.y + last_rect.height + self.table['layout']['vert_spacing']

        # Check if it fits vertically
        if next_y + height <= self.screen.get_height():
            return last_rect.x, next_y

        # No room in last column, try to create a new column
        next_x = last_rect.x + last_rect.width + self.table['layout']['horz_spacing']

        # Check if new column fits horizontally
        next_wid = (
            (width + self.table['layout']['horz_spacing']) - 
            self.table['metrics']['char_width']
        )
        if next_x + next_wid > self.table['layout']['section_width']:
            # Doesn't fit horizontally; scroll
            ui.scroll_mgr.scroll(1, self.table)

        return next_x, self.table['layout']['top_margin']

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
            'show_md': self.show_md,
            'offset': ui.scroll_mgr.offset
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
        self.show_md += 1
        if self.show_md > Metadata.ALL:
            self.show_md = Metadata.NONE

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

    """
    def toggle_show_dependencies(self):
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
