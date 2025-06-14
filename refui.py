import pygame
from dataclasses import dataclass
from typing import Tuple

from fonts import fonts
from hvm import ExpandRef, DefIdx

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

@dataclass
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
        """Get pygame.Rect for collision detection and bounds checking."""
        return pygame.Rect(self.x, self.y, self.width, self.height)

    def draw(self, surface: pygame.Surface, table: dict):
        if not self.visible: return

        if self.selected or (self.color_scheme == "bright terminal"):
            text_color = BRIGHT_GREEN
            header_color = YELLOW
            border_color = BRIGHT_GREEN
            line_color = BRIGHT_GREEN
        elif self.color_scheme == "dim terminal":
            text_color = DIM_GREEN
            header_color = DIM_YELLOW
            border_color = DIM_GREEN
            line_color = DIM_GREEN
        else:  # soft
            text_color = LIGHT_CYAN
            header_color = WHITE
            border_color = LIGHT_CYAN
            line_color = LIGHT_CYAN
    
        title_font = fonts.title
        font = fonts.content
    
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
        header_y = title_bottom + table['row_spacing']['title_to_header']
        current_x = self.x + table['col_spacing']['margin']
    
        for i, header in enumerate(headers):
            header_surface = font.render(header, True, header_color)
            surface.blit(header_surface, (current_x, header_y))
            current_x += table['column_widths'][i]
            if i < len(headers) - 1:
                current_x += table['col_spacing_by_index'][i + 1]

        # Draw horizontal line under headers
        line_y = header_y + table['metrics']['line_height'] + table['row_spacing']['header_to_line']
        line_left = self.x + table['col_spacing']['margin']
        line_right = self.x + self.width - table['col_spacing']['margin']
        pygame.draw.line(surface, line_color, (line_left, line_y), (line_right, line_y), 1)
        
        # Draw data rows
        row_y = line_y + 1 + table['row_spacing']['margin'] 
        for node in self.ref.nodes:
            for term in (node.neg, node.pos):
                mem_loc = term.stores[0].loc
                current_x = self.x + table['col_spacing']['margin']
                values = [
                    f"{mem_loc:04d}",
                    term.tag[:3],
                    f"{term.lab:03d}",
                    f"{term.loc:04d}"
                ]
                for i, value in enumerate(values):
                    value_surface = font.render(value, True, text_color)
                    surface.blit(value_surface, (current_x, row_y))
                    if term.empty(): # memory loc only for empty terms
                        break
                    current_x += table['column_widths'][i]
                    if i < len(values) - 1:
                        current_x += table['col_spacing_by_index'][i + 1]
                row_y += table['metrics']['line_height'] + table['row_spacing']['intra_row']

class RefManager:
    def __init__(self, screen: pygame.Surface, table: dict):
        self.screen = screen
        self.table = table
        self.all_rects: list[RefRect] = []
        self.disp_rects: list[RefRect] = []
        self.ref_map = {}
        self.show_deps_only: bool = False
        
    def calculate_ref_dimensions(self, ref: ExpandRef) -> Tuple[int, int]:
        width = self.table['width']
        num_ops = len(ref.nodes) * 2
        height = (
            self.table['table_header_height'] + self.table['row_spacing']['margin'] * 2 + 
            num_ops * (self.table['metrics']['line_height'] + self.table['row_spacing']['intra_row']) -
            self.table['row_spacing']['intra_row'] + self.table['table_border_thickness']
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
        for rect in self.disp_rects:
            rect.draw(self.screen, self.table)

    def get_selected(self) -> list[RefRect]:
        return [rect for rect in self.disp_rects if rect.selected]

    def only_rects_visible(self, rects: list[RefRect]):
        map = {}
        for rect in rects:
            map[rect.ref.id] = rect

        # hide all non-selected that aren't in supplied rects
        for rect in self.all_rects:
            if not rect.selected:
                rect.visible = rect.ref.id in map
            else:
                assert rect.visible

    def all_rects_visible(self):
        for rect in self.all_rects:
            rect.visible = True

    def rect_from_loc(self, loc: int) -> RefRect:
        for rect in self.all_rects:
            if rect.ref.contains(loc):
                return rect
        return None

    def get_dep_rects(self, rect: RefRect) -> list[RefRect]:
        dep_rects = []
        while rect and rect.ref.redex:
            # ref.redex is the redex as it originally occurred from within an
            # ExpandRef. The neg term of that redex likely originated somewhere
            # else (neg.stores[0]), and may have been stored and reloaded from
            # other intermediate location(s) (neg.loads[]) since then.
            #
            # For <make_leaf> -> <leaf> we want to know the loc (and ref) from
            # which the neg term  was *last* loaded.
            #
            neg = rect.ref.redex.neg
            # TOOD: neg.tag constraint
            last_load = neg.loads and neg.loads[-1]
            if last_load and last_load.is_matnum_itr():
                loc = last_load.loc
                print(f"redex.neg last_load {last_load} loc {loc}")

            # For <make> -> <matu32_NN> we want...
            #
            # better approach
            # elif last_load.is_applam_itr():
            #     find the APPREF for this APPLAM. that's at the LAM's loc.
            #     loc = last_load.itr.redex.pos.loc
            elif neg.tag == 'MAT':
                loc = neg.loc
                print(f"redex.neg MAT loc {neg.term} loc {loc}")
            else:
                # fall back to the loc of the origin ref
                loc = neg.node.ref.first_loc()
                print(f"fall back redex.neg.node.ref {neg.node.ref.def_idx} first_loc {loc}")

            rect = self.rect_from_loc(loc)
            print(f"rect from loc {loc} is {ref_name(rect.ref.def_idx) if rect else None}")
            if rect:
                dep_rects.append(rect)
        return dep_rects

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
