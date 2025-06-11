import pygame
from dataclasses import dataclass
from typing import Tuple
from hvm import AppRef

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
    return d.get(ref, f"ref_{ref}")

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

@dataclass
class AppRefRect:
    app_ref: AppRef
    x: int
    y: int
    width: int
    height: int
    color_scheme: str = "dim terminal"
    
    def get_rect(self) -> pygame.Rect:
        """Get pygame.Rect for collision detection and bounds checking."""
        return pygame.Rect(self.x, self.y, self.width, self.height)


    def draw(self, surface: pygame.Surface, table: dict):
        if self.color_scheme == "bright terminal":
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
    
        #operations = self.collect_memory_operations()
    
        title_font = get_title_font()
        font = get_content_font()
    
        # Draw background
        pygame.draw.rect(surface, BLACK, (self.x, self.y, self.width, self.height))
    
        # Draw border
        border_rect = pygame.Rect(self.x, self.y, self.width, self.height)
        pygame.draw.rect(surface, border_color, border_rect, table['table_border_thickness'])
    
        # Draw title with background to clip the border
        title_surface = title_font.render(ref_name(self.app_ref.ref), True, header_color)
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
        for node in self.app_ref.nodes:
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
                    current_x += table['column_widths'][i]
                    if i < len(values) - 1:
                        current_x += table['col_spacing_by_index'][i + 1]

                row_y += table['metrics']['line_height'] + table['row_spacing']['intra_row']

class AppRefManager:
    def __init__(self, screen: pygame.Surface, table: dict):
        self.screen = screen
        self.table = table
        self.app_ref_rects: list[AppRefRect] = []
        
    def calculate_appref_dimensions(self, app_ref: AppRef) -> Tuple[int, int]:
        width = self.table['width']
        num_ops = len(app_ref.nodes) * 2
        height = (
            self.table['table_header_height'] + self.table['row_spacing']['margin'] * 2 + 
            num_ops * (self.table['metrics']['line_height'] + self.table['row_spacing']['intra_row']) -
            self.table['row_spacing']['intra_row'] + self.table['table_border_thickness']
        )
        return width, height

    def add_appref(self, app_ref: AppRef, color_scheme: str = "dim terminal") -> AppRefRect:
        width, height = self.calculate_appref_dimensions(app_ref)
        x, y = self._find_next_position(width, height)
        
        app_ref_rect = AppRefRect(app_ref, x, y, width, height, color_scheme)
        self.app_ref_rects.append(app_ref_rect)
        return app_ref_rect
    
    def _find_next_position(self, width: int, height: int) -> Tuple[int, int]:
        if not self.app_ref_rects:
            return self.table['layout']['left_margin'], self.table['layout']['top_margin']
        
        # Try to place under last appref
        last_rect = self.app_ref_rects[-1]
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
    
    def remove_appref(self, app_ref: AppRef) -> bool:
        for i, rect in enumerate(self.app_ref_rects):
            if rect.app_ref is app_ref:
                del self.app_ref_rects[i]
                return True
        return False
    
    def get_appref_at_position(self, x: int, y: int) -> AppRefRect:
        for rect in self.app_ref_rects:
            if rect.get_rect().collidepoint(x, y):
                return rect
        return None
    
    def reposition_all(self):
        if not self.app_ref_rects:
            return
            
        # Store the AppRefs and their properties
        app_refs_data = [(rect.app_ref, rect.color_scheme) for rect in self.app_ref_rects]
        
        # Clear the list and re-add them
        self.app_ref_rects.clear()
        for app_ref, color_scheme in app_refs_data:
            self.add_appref(app_ref, color_scheme)
    
    def draw_all(self, surface: pygame.Surface):
        for arr in self.app_ref_rects:
            arr.draw(surface, self.table)

