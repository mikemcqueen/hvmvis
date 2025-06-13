import pygame

# Constants for display
TITLE_FONT_SIZE = 14
FONT_SIZE = 14

def get_font(size: int, bold: bool = True) -> pygame.font.Font:
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

class Fonts:
    def __init__(self):
        pygame.font.init()
        self.title = get_title_font()
        self.content = get_content_font()

fonts = Fonts()
