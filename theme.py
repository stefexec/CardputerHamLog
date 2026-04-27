import pygame

def _parse_color(color_str, default_color=(255, 0, 255)):
    """Safely parses a color string 'r,g,b' into a tuple."""
    if isinstance(color_str, tuple):
        return color_str
    try:
        return tuple(map(int, color_str.split(',')))
    except (ValueError, AttributeError):
        return default_color

class Theme:
    def __init__(self, user_config):
        self.bg_color = _parse_color(user_config.get("theme_bg", "20,20,30"))
        self.text_color = _parse_color(user_config.get("theme_text", "200,200,200"))
        self.box_color = _parse_color(user_config.get("theme_box", "100,100,120"))
        self.highlight_color = _parse_color(user_config.get("theme_highlight", "100,255,100"))
        # We need a dedicated typing color (was previously named dupe_color in the old code)
        self.typing_color = _parse_color(user_config.get("theme_typing", "255,165,0"))
        # And a dedicated dupe color (was previously tied to highlight_color in the old code)
        self.dupe_color = _parse_color(user_config.get("theme_dupe", "100,255,100"))

        self.popup_bg_color = _parse_color(user_config.get("theme_popup_bg", "40,40,60"))
        self.popup_border_color = _parse_color(user_config.get("theme_popup_border", "150,150,170"))
        self.separator_color = _parse_color(user_config.get("theme_separator", "60,60,70"))
        self.detail_bg_color = _parse_color(user_config.get("theme_detail_bg", "30,30,40"))
        self.scrollbar_track_color = _parse_color(user_config.get("theme_scrollbar_track", "40,40,60"))
        self.scrollbar_handle_color = _parse_color(user_config.get("theme_scrollbar_handle", "80,80,100"))
        self.log_header_color = _parse_color(user_config.get("theme_log_header", "180,180,180"))
