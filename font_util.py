import pygame

# CJK Unicode ranges for character detection
CJK_RANGES = [
    (0x4E00, 0x9FFF),   # CJK Unified Ideographs
    (0x3400, 0x4DBF),   # CJK Unified Ideographs Extension A
    (0xFF00, 0xFFEF),   # Halfwidth and Fullwidth Forms
]

def is_cjk(char):
    """Check if a character is in the CJK ranges."""
    char_ord = ord(char)
    for start, end in CJK_RANGES:
        if start <= char_ord <= end:
            return True
    return False

class CompositeFont:
    """
    A wrapper for pygame.font.Font that uses a fallback font for CJK characters.
    It mimics the interface of pygame.font.Font for methods like render() and size().
    """
    def __init__(self, primary_path, primary_size, fallback_path, fallback_size=None):
        if fallback_size is None:
            fallback_size = primary_size
        self.primary_font = pygame.font.Font(primary_path, primary_size)
        self.fallback_font = pygame.font.Font(fallback_path, fallback_size)
        self.size_cache = {}

    def render(self, text, antialias, color, background=None):
        if background:
            raise NotImplementedError("CompositeFont does not support background color in render.")

        # If no CJK characters, use the primary font for performance
        if not any(is_cjk(char) for char in text):
            return self.primary_font.render(text, antialias, color)

        surfaces = []
        total_width = 0
        max_height = 0
        
        i = 0
        while i < len(text):
            use_fallback = is_cjk(text[i])
            
            j = i
            while j < len(text) and (is_cjk(text[j]) == use_fallback):
                j += 1
                
            segment = text[i:j]
            font_to_use = self.fallback_font if use_fallback else self.primary_font
            
            rendered_segment = font_to_use.render(segment, antialias, color)
            surfaces.append(rendered_segment)
            total_width += rendered_segment.get_width()
            max_height = max(max_height, rendered_segment.get_height())
            i = j

        final_surface = pygame.Surface((total_width, max_height), pygame.SRCALPHA)
        x = 0
        for surf in surfaces:
            # Align to bottom to handle different font metrics
            y = max_height - surf.get_height()
            final_surface.blit(surf, (x, y))
            x += surf.get_width()
            
        return final_surface

    def size(self, text):
        if text in self.size_cache:
            return self.size_cache[text]

        # If no CJK characters, use the primary font for performance
        if not any(is_cjk(char) for char in text):
            return self.primary_font.size(text)

        total_width = 0
        max_height = 0
        
        i = 0
        while i < len(text):
            use_fallback = is_cjk(text[i])
            
            j = i
            while j < len(text) and (is_cjk(text[j]) == use_fallback):
                j += 1
                
            segment = text[i:j]
            font_to_use = self.fallback_font if use_fallback else self.primary_font
            
            size_w, size_h = font_to_use.size(segment)
            total_width += size_w
            max_height = max(max_height, size_h)
            i = j
        
        result = (total_width, max_height)
        self.size_cache[text] = result
        return result
