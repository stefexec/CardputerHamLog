import pygame
import os
from flag_utils import get_flag_surface
from language import get_string
from logger import get_band_from_freq
from datetime import datetime

def draw_callsign_and_flag(screen, font, callsign, color, center_x, y, flag_sprite_sheet):
    """Draws a callsign with its flag, centered horizontally."""
    if not callsign:
        return

    callsign_surf = font.render(callsign, True, color)
    
    flag_surf = None
    if flag_sprite_sheet:
        flag_surf = get_flag_surface(callsign, flag_sprite_sheet)

    total_width = callsign_surf.get_width()
    if flag_surf:
        total_width += flag_surf.get_width() + 5

    start_x = center_x - total_width // 2
    
    current_x = start_x
    if flag_surf:
        screen.blit(flag_surf, (current_x, y + (callsign_surf.get_height() - flag_surf.get_height()) // 2))
        current_x += flag_surf.get_width() + 5

    screen.blit(callsign_surf, (current_x, y))

class UIField:
    def __init__(self, rect, label, value=""):
        self.rect, self.label, self.value, self.active = rect, label, value, False

class MainScreen:
    def __init__(self, font, small_font, theme, user_config, lang, app_state, flag_sprite_sheet, on_lookup, on_log_qso, on_mode_select, on_menu_open, on_time_edit):
        self.font = font
        self.small_font = small_font
        self.theme = theme
        self.user_config = user_config
        self.lang = lang
        self.app_state = app_state
        self.flag_sprite_sheet = flag_sprite_sheet
        
        self.on_lookup = on_lookup
        self.on_log_qso = on_log_qso
        self.on_mode_select = on_mode_select
        self.on_menu_open = on_menu_open
        self.on_time_edit = on_time_edit

        self.fields = self.build_fields()
        self.bottom_nav = [pygame.Rect(10, 138, 240, 25), pygame.Rect(255, 138, 25, 25), pygame.Rect(285, 138, 25, 25)]
        self.bottom_focus = 0
        self.is_auto_time = True
        self.qso_datetime = None
        self.active_pos = [0, 0]
        self.main_grid_active = True
        self.fields[0][0].active = True
        self.clear_on_next_input = True
        self.cursor_timer = 0
        self.callsign_cache = set()

    def build_fields(self):
        sota_active = self.user_config.get("sota_mode", "0") == "1"
        pota_active = self.user_config.get("pota_mode", "0") == "1"
        contest_active = self.user_config.get("contest_mode", "0") == "1"
        base_fields = [
            [UIField(pygame.Rect(10, 23, 140, 25), get_string(self.lang, "callsign")), UIField(pygame.Rect(0, 0, 0, 0), "lookup", ""), UIField(pygame.Rect(170, 23, 140, 25), get_string(self.lang, "freq"), self.app_state["freq"])],
            [UIField(pygame.Rect(10,63,65,25), get_string(self.lang, "rst_s"), "59"), UIField(pygame.Rect(85,63,65,25), get_string(self.lang, "rst_r"), "59"), UIField(pygame.Rect(170,63,140,25), get_string(self.lang, "mode"), self.app_state["mode"])]
        ]
        if sota_active:
            base_fields.append([UIField(pygame.Rect(10,103,140,25), get_string(self.lang, "my_sota"), self.app_state.get("my_sota", "")), UIField(pygame.Rect(170,103,140,25), get_string(self.lang, "sota_ref"), self.app_state.get("sota_ref", ""))])
        elif pota_active:
            base_fields.append([UIField(pygame.Rect(10,103,140,25), get_string(self.lang, "my_pota"), self.app_state.get("my_pota", "")), UIField(pygame.Rect(170,103,140,25), get_string(self.lang, "pota_ref"), self.app_state.get("pota_ref", ""))])
        elif contest_active:
            base_fields.append([UIField(pygame.Rect(10,103,140,25), get_string(self.lang, "stx"), self.app_state.get("stx_string", "001")), UIField(pygame.Rect(170,103,140,25), get_string(self.lang, "srx"), self.app_state.get("srx_string", ""))])
        base_fields.append([None, None, None]) # Dummy row
        return base_fields

    def update_fields(self):
        old_extra_row = self.fields[2] if len(self.fields) > 3 else None
        self.fields = self.build_fields()
        if old_extra_row and len(self.fields) > 3:
            if self.fields[2][0].label == old_extra_row[0].label:
                self.fields[2][0].value = old_extra_row[0].value
                self.fields[2][1].value = old_extra_row[1].value
        
        if self.main_grid_active and self.active_pos[0] >= len(self.fields) - 1:
            self.active_pos[0] = len(self.fields) - 2
            self.active_pos[1] = 0
            for r in self.fields:
                for f in r:
                    if f: f.active = False
            self.fields[self.active_pos[0]][self.active_pos[1]].active = True

    def handle_event(self, event):
        active_field = None
        if self.main_grid_active:
            current_row = self.fields[self.active_pos[0]]
            if self.active_pos[1] < len(current_row):
                active_field = current_row[self.active_pos[1]]

        if event.key in (pygame.K_DOWN, pygame.K_UP, pygame.K_RIGHT, pygame.K_LEFT):
            if active_field: active_field.active = False
            self.clear_on_next_input = True
            if self.main_grid_active:
                max_row = len(self.fields) - 2
                if event.key == pygame.K_DOWN and self.active_pos[0] == max_row: self.main_grid_active = False
                else:
                    if event.key == pygame.K_DOWN: self.active_pos[0]=min(max_row, self.active_pos[0]+1)
                    elif event.key == pygame.K_UP: self.active_pos[0]=max(0, self.active_pos[0]-1)
                    elif event.key == pygame.K_RIGHT: self.active_pos[1]+=1
                    elif event.key == pygame.K_LEFT: self.active_pos[1]-=1
                    row_len = len([f for f in self.fields[self.active_pos[0]] if f is not None])
                    if row_len > 0:
                        self.active_pos[1] = (self.active_pos[1] + row_len) % row_len
                    else:
                        self.active_pos[1] = 0
            else:
                max_row = len(self.fields) - 2
                if event.key == pygame.K_UP: self.main_grid_active=True; self.active_pos=[max_row, min(self.bottom_focus, len([f for f in self.fields[max_row] if f is not None])-1)]
                elif event.key == pygame.K_RIGHT: self.bottom_focus=(self.bottom_focus+1)%3
                elif event.key == pygame.K_LEFT: self.bottom_focus=(self.bottom_focus-1+3)%3
            
            if self.main_grid_active:
                current_row = self.fields[self.active_pos[0]]
                if self.active_pos[1] < len(current_row) and current_row[self.active_pos[1]]:
                    current_row[self.active_pos[1]].active = True
            return "active"

        elif event.key == pygame.K_RETURN:
            if active_field and active_field.label == "lookup":
                callsign_to_lookup = self.fields[0][0].value
                if callsign_to_lookup:
                    self.on_lookup(callsign_to_lookup.upper(), False)
            elif active_field and active_field.label == get_string(self.lang, "callsign"):
                call,freq,mode = self.fields[0][0].value,self.fields[0][2].value,self.fields[1][2].value
                band = get_band_from_freq(freq)
                if call and band != "N/A":
                    my_sota, sota_ref, my_pota, pota_ref, stx_str, srx_str = "", "", "", "", "", ""
                    if len(self.fields) > 3:
                        if self.user_config.get("sota_mode", "0") == "1": my_sota, sota_ref = self.fields[2][0].value, self.fields[2][1].value
                        elif self.user_config.get("pota_mode", "0") == "1": my_pota, pota_ref = self.fields[2][0].value, self.fields[2][1].value
                        elif self.user_config.get("contest_mode", "0") == "1": stx_str, srx_str = self.fields[2][0].value, self.fields[2][1].value
                    
                    qso_data = {
                        "call": call, "rst_s": self.fields[1][0].value, "rst_r": self.fields[1][1].value, "band": band, "mode": mode, "freq": freq, 
                        "qso_datetime": self.qso_datetime, "my_sota": my_sota, "sota_ref": sota_ref, "my_pota": my_pota, "pota_ref": pota_ref, 
                        "stx_str": stx_str, "srx_str": srx_str
                    }
                    self.on_log_qso(qso_data)
                elif not call:
                    self.on_lookup("", True) # clear cache
            elif active_field and active_field.label == get_string(self.lang, "mode"): 
                self.on_mode_select()
            elif not self.main_grid_active:
                if self.bottom_focus == 0: self.on_time_edit()
                elif self.bottom_focus == 1: self.is_auto_time = not self.is_auto_time
                elif self.bottom_focus == 2: self.on_menu_open()
            return "active"
            
        elif event.key == pygame.K_BACKSPACE and active_field and active_field.label != "lookup": 
            self.clear_on_next_input=False
            active_field.value=active_field.value[:-1]
            return "active"
            
        elif active_field and active_field.label != "lookup" and event.unicode.isprintable():
            if self.clear_on_next_input: active_field.value, self.clear_on_next_input = "", False
            if active_field.label == get_string(self.lang, "callsign"):
                active_field.value += event.unicode.upper()
            elif active_field.label == get_string(self.lang, "freq"):
                val,char=active_field.value,event.unicode
                if char.isdigit():
                    if '.' in val and len(val.split('.')[1])>=6: pass
                    elif ',' in val and len(val.split(',')[1])>=6: pass
                    else: active_field.value+=char
                elif char in '.,' and '.' not in val and ',' not in val: active_field.value+=char
            elif active_field.label in [get_string(self.lang, "rst_s"), get_string(self.lang, "rst_r")]:
                if event.unicode.isdigit() and len(active_field.value)<2: active_field.value+=event.unicode
            else: active_field.value+=event.unicode.upper()
            return "active"

        return None

    def draw(self, screen):
        self.cursor_timer += 1
        screen.fill(self.theme.bg_color)
        lookup_icon_active = self.main_grid_active and self.active_pos == [0, 1]
        
        for r_idx, r in enumerate(self.fields):
            if r_idx == len(self.fields) - 1: continue
            for f_idx, f in enumerate(r):
                if f:
                    if f.label == "lookup": continue

                    # 1. Draw labels and decorations
                    if f.label == get_string(self.lang, "freq"):
                        band_val = get_band_from_freq(f.value)
                        display_label = f"{f.label} [{band_val}]" if band_val and band_val != "N/A" else f.label
                        l_surf = self.small_font.render(display_label, True, self.theme.text_color)
                        screen.blit(l_surf, (f.rect.x, f.rect.y-14))
                    elif f.label == get_string(self.lang, "callsign"):
                        l_surf = self.small_font.render(f.label, True, self.theme.text_color)
                        screen.blit(l_surf, (f.rect.x, f.rect.y-14))
                        
                        lookup_icon_rect = pygame.Rect(f.rect.x + l_surf.get_width() + 5, f.rect.y - 14, 20, 14)
                        icon_color = self.theme.highlight_color if lookup_icon_active else self.theme.text_color
                        lookup_surf = self.small_font.render("󰍉", True, icon_color)
                        screen.blit(lookup_surf, lookup_icon_rect)
                        if lookup_icon_active:
                            pygame.draw.rect(screen, self.theme.highlight_color, lookup_icon_rect.inflate(4,4), 1, border_radius=3)

                        current_flag_surf = get_flag_surface(f.value, self.flag_sprite_sheet)
                        if current_flag_surf:
                            screen.blit(current_flag_surf, (lookup_icon_rect.right + 5, f.rect.y - 14))
                    else:
                        l_surf = self.small_font.render(f.label, True, self.theme.text_color)
                        screen.blit(l_surf, (f.rect.x, f.rect.y-14))

                    # 2. Draw field boxes and values
                    b_color = self.theme.highlight_color if f.active else self.theme.box_color
                    pygame.draw.rect(screen, b_color, f.rect, 2, border_radius=3)
                    
                    final_color = self.theme.text_color
                    if f.label == get_string(self.lang, "callsign"):
                        if f.value and f.value.upper() in self.callsign_cache:
                            final_color = self.theme.dupe_color
                        elif f.value and f.active:
                            final_color = self.theme.typing_color
                    
                    v_surf = self.font.render(f.value, True, final_color)
                    
                    text_render_rect = f.rect.inflate(-10, 0)
                    text_y = f.rect.centery - v_surf.get_height() // 2

                    if v_surf.get_width() > text_render_rect.width:
                        x_offset = text_render_rect.width - v_surf.get_width()
                        screen.set_clip(text_render_rect)
                        screen.blit(v_surf, (text_render_rect.x + x_offset, text_y))
                        screen.set_clip(None)
                        cursor_x = text_render_rect.right
                    else:
                        screen.blit(v_surf, (text_render_rect.x, text_y))
                        cursor_x = text_render_rect.x + v_surf.get_width()

                    if f.active and self.cursor_timer % 60 < 30:
                        pygame.draw.line(screen, self.theme.text_color, (cursor_x, f.rect.y + 5), (cursor_x, f.rect.bottom - 5), 2)

        
        time_b_color = self.theme.highlight_color if not self.main_grid_active and self.bottom_focus==0 else self.theme.box_color
        auto_b_color = self.theme.highlight_color if not self.main_grid_active and self.bottom_focus==1 else self.theme.box_color
        menu_b_color = self.theme.highlight_color if not self.main_grid_active and self.bottom_focus==2 else self.theme.box_color
        pygame.draw.rect(screen, time_b_color, self.bottom_nav[0], 2, border_radius=3)
        pygame.draw.rect(screen, auto_b_color, self.bottom_nav[1], 2, border_radius=3)
        pygame.draw.rect(screen, menu_b_color, self.bottom_nav[2], 2, border_radius=3)
        time_str = self.qso_datetime.strftime("%Y-%m-%d %H:%M:%S UTC") if isinstance(self.qso_datetime, datetime) else "AUTO"
        time_surf = self.small_font.render(time_str, True, self.theme.text_color); screen.blit(time_surf, (self.bottom_nav[0].x+10, self.bottom_nav[0].centery - time_surf.get_height()//2))
        
        auto_icon_color = self.theme.highlight_color if self.is_auto_time else self.theme.text_color
        auto_surf = self.font.render("◷", True, auto_icon_color)
        screen.blit(auto_surf, (self.bottom_nav[1].centerx - auto_surf.get_width()//2, self.bottom_nav[1].centery - auto_surf.get_height()//2 - 2))
        
        menu_surf = self.font.render("≡", True, self.theme.text_color)
        screen.blit(menu_surf, (self.bottom_nav[2].centerx - menu_surf.get_width()//2, self.bottom_nav[2].centery - menu_surf.get_height()//2))

class DateSelector:
    def __init__(self, dt, font, small_font, theme):
        self.dt, self.font, self.small_font, self.theme = dt, font, small_font, theme
        self.parts = [dt.year, dt.month, dt.day]
        self.active_part = 0
        self.rect = pygame.Rect(40, 40, 240, 80)

    def handle_event(self, event):
        if event.key == pygame.K_RIGHT: self.active_part = (self.active_part + 1) % 3
        elif event.key == pygame.K_LEFT: self.active_part = (self.active_part - 1 + 3) % 3
        elif event.key == pygame.K_UP: self.parts[self.active_part] -= 1
        elif event.key == pygame.K_DOWN: self.parts[self.active_part] += 1
        self._update_dt()
        if event.key == pygame.K_RETURN: return self.dt
        if event.key == pygame.K_ESCAPE: return None
        return "active"

    def _update_dt(self):
        try: self.dt = self.dt.replace(year=self.parts[0], month=self.parts[1], day=self.parts[2])
        except ValueError: pass
        self.parts = [self.dt.year, self.dt.month, self.dt.day]

    def draw(self, screen):
        pygame.draw.rect(screen, self.theme.popup_bg_color, self.rect, border_radius=5)
        pygame.draw.rect(screen, self.theme.popup_border_color, self.rect, 2, border_radius=5)
        date_str = self.dt.strftime("%Y-%m-%d")
        date_surf = self.font.render(date_str, True, self.theme.text_color)
        screen.blit(date_surf, (self.rect.centerx - date_surf.get_width()//2, self.rect.centery - date_surf.get_height()//2))
        
        y_pos = self.rect.centerx - date_surf.get_width()//2 + self.font.size("20")[0]
        m_pos = self.rect.centerx - date_surf.get_width()//2 + self.font.size("2023-")[0] + self.font.size("0")[0]
        d_pos = self.rect.centerx - date_surf.get_width()//2 + self.font.size("2023-10-")[0] + self.font.size("0")[0]
        
        positions = [y_pos, m_pos, d_pos]
        x = positions[self.active_part]
        y = self.rect.centery - date_surf.get_height()//2
        
        up_arrow = self.small_font.render("▲", True, self.theme.highlight_color)
        down_arrow = self.small_font.render("▼", True, self.theme.highlight_color)
        
        screen.blit(up_arrow, (x - up_arrow.get_width()//2, y - 20))
        screen.blit(down_arrow, (x - down_arrow.get_width()//2, y + 25))

class TimeEditor:
    def __init__(self, dt, font, small_font, theme):
        self.dt, self.font, self.small_font, self.theme = dt, font, small_font, theme
        self.parts = [dt.hour, dt.minute, dt.year, dt.month, dt.day]
        self.active_part = 0
        self.rect = pygame.Rect(40, 30, 240, 110)
        
    def handle_event(self, event):
        if event.key == pygame.K_RIGHT: self.active_part = (self.active_part + 1) % 5
        elif event.key == pygame.K_LEFT: self.active_part = (self.active_part - 1 + 5) % 5
        elif event.key == pygame.K_UP: self.parts[self.active_part] -= 1
        elif event.key == pygame.K_DOWN: self.parts[self.active_part] += 1
        self._update_dt()
        if event.key == pygame.K_RETURN: return self.dt
        if event.key == pygame.K_ESCAPE: return None
        return "active"
        
    def _update_dt(self):
        try: self.dt = self.dt.replace(hour=self.parts[0], minute=self.parts[1], year=self.parts[2], month=self.parts[3], day=self.parts[4])
        except ValueError: pass
        self.parts = [self.dt.hour, self.dt.minute, self.dt.year, self.dt.month, self.dt.day]
        
    def draw(self, screen):
        pygame.draw.rect(screen, self.theme.popup_bg_color, self.rect, border_radius=5)
        pygame.draw.rect(screen, self.theme.popup_border_color, self.rect, 2, border_radius=5)
        time_str, date_str = self.dt.strftime("%H:%M"), self.dt.strftime("%Y-%m-%d")
        time_surf, date_surf = self.font.render(time_str, True, self.theme.text_color), self.font.render(date_str, True, self.theme.text_color)
        screen.blit(time_surf, (self.rect.centerx - time_surf.get_width()//2, self.rect.y + 15))
        screen.blit(date_surf, (self.rect.centerx - date_surf.get_width()//2, self.rect.y + 50))
        h, m = self.rect.centerx-time_surf.get_width()//2+self.font.size("0")[0], self.rect.centerx-time_surf.get_width()//2+self.font.size("00:")[0]+self.font.size("0")[0]
        y_pos, m_pos, d_pos = self.rect.centerx-date_surf.get_width()//2+self.font.size("20")[0], self.rect.centerx-date_surf.get_width()//2+self.font.size("2023-")[0]+self.font.size("0")[0], self.rect.centerx-date_surf.get_width()//2+self.font.size("2023-10-")[0]+self.font.size("0")[0]
        x, y = [h,m,y_pos,m_pos,d_pos][self.active_part], [self.rect.y+15]*2+[self.rect.y+50]*3
        up, down = self.small_font.render("▲", True, self.theme.highlight_color), self.small_font.render("▼", True, self.theme.highlight_color)
        screen.blit(up, (x-up.get_width()//2, y[self.active_part]-15)); screen.blit(down, (x-down.get_width()//2, y[self.active_part]+25))

class ModeSelector:
    MODES = {"PHONE":["FM","NFM","AM","NAM","SSB","LSB","USB"],"CW":["CW","CW-R"],"DIGITALVOICE":["DMR","DSTAR","C4FM","P25","FUSION"],"DIGITAL":["RTTY","PSK","PSK31","PSK63","FT8","FT4","JT65","JT9","JS8"],"IMAGE":["SSTV"]}
    def __init__(self, font, small_font, theme):
        self.font, self.small_font, self.theme = font, small_font, theme
        self.rect = pygame.Rect(30,10,260,150)
        self.items = [item for cat,modes in self.MODES.items() for item in [("category",f"-[ {cat} ]-")] + [("mode",mode) for mode in modes]]
        self.active_index, self.scroll_offset = 1, 0
        self.max_visible = (self.rect.height-20)//20
        
    def handle_event(self, event):
        if event.key == pygame.K_ESCAPE: return None
        if event.key == pygame.K_DOWN:
            self.active_index = min(len(self.items)-1, self.active_index+1)
            if self.items[self.active_index][0] == "category": self.active_index = min(len(self.items)-1, self.active_index+1)
        elif event.key == pygame.K_UP:
            self.active_index = max(0, self.active_index-1)
            if self.items[self.active_index][0] == "category": self.active_index = max(0, self.active_index-1)
        if self.active_index < self.scroll_offset: self.scroll_offset = self.active_index
        elif self.active_index >= self.scroll_offset+self.max_visible: self.scroll_offset = self.active_index-self.max_visible+1
        if event.key == pygame.K_RETURN and self.items[self.active_index][0] == "mode": return self.items[self.active_index][1]
        return "active"
        
    def draw(self, screen):
        pygame.draw.rect(screen, self.theme.popup_bg_color, self.rect, border_radius=5); pygame.draw.rect(screen, self.theme.popup_border_color, self.rect, 2, border_radius=5)
        y = self.rect.y + 10
        for i, (typ, name) in enumerate(self.items[self.scroll_offset:self.scroll_offset+self.max_visible]):
            idx = self.scroll_offset+i
            if typ == "category": surf = self.small_font.render(name, True, self.theme.popup_border_color); screen.blit(surf, (self.rect.centerx-surf.get_width()//2, y))
            else: color = self.theme.highlight_color if idx == self.active_index else self.theme.text_color; surf = self.font.render(name, True, color); screen.blit(surf, (self.rect.x+20, y))
            y += 20
        if len(self.items) > self.max_visible:
            track_h = self.rect.height-10; track = pygame.Rect(self.rect.right-12, self.rect.top+5, 7, track_h); pygame.draw.rect(screen, self.theme.scrollbar_track_color, track, border_radius=3)
            handle_h = max(10, track_h*(self.max_visible/len(self.items))); scroll_perc = self.scroll_offset/(len(self.items)-self.max_visible)
            handle_y = track.y+(track_h-handle_h)*scroll_perc; handle = pygame.Rect(track.x, handle_y, 7, handle_h); pygame.draw.rect(screen, self.theme.scrollbar_handle_color, handle, border_radius=3)

class MenuBase:
    def __init__(self, font, small_font, theme, lang, title, items, flag_sprite_sheet=None):
        self.font = font
        self.small_font = small_font
        self.theme = theme
        self.lang = lang
        self.title = title
        self.items = items
        self.flag_sprite_sheet = flag_sprite_sheet
        self.active_index = 0
        self.scroll_offset = 0
        self.max_visible = 3

    def handle_event(self, event):
        if event.key == pygame.K_ESCAPE:
            return "close"
        if event.key == pygame.K_DOWN:
            self.active_index = min(len(self.items) - 1, self.active_index + 1)
        elif event.key == pygame.K_UP:
            self.active_index = max(0, self.active_index - 1)

        if self.active_index < self.scroll_offset:
            self.scroll_offset = self.active_index
        elif self.active_index >= self.scroll_offset + self.max_visible:
            self.scroll_offset = self.active_index - self.max_visible + 1

        if event.key == pygame.K_RETURN:
            return self.items[self.active_index]["action"]
        return "active"

    def draw(self, screen):
        screen.fill(self.theme.bg_color)
        title_surf = self.font.render(self.title, True, self.theme.text_color)
        screen.blit(title_surf, (screen.get_width() // 2 - title_surf.get_width() // 2, 10))
        y = 40
        for i, item in enumerate(self.items[self.scroll_offset:self.scroll_offset + self.max_visible]):
            idx = self.scroll_offset + i
            color = self.theme.highlight_color if idx == self.active_index else self.theme.box_color
            box_rect = pygame.Rect(40, y, 240, 35)
            pygame.draw.rect(screen, color, box_rect, 2, border_radius=5)

            label_x = box_rect.x + 10
            if "icon" in item:
                icon_surf = self.font.render(item["icon"], True, color)
                screen.blit(icon_surf, (box_rect.x + 10, box_rect.centery - icon_surf.get_height() // 2))
                label_x = box_rect.x + 40
            
            if item.get("flag") and self.flag_sprite_sheet:
                pass

            label_surf = self.font.render(item["label"], True, self.theme.text_color)
            screen.blit(label_surf, (label_x, box_rect.centery - label_surf.get_height() // 2))
            y += 40

        if len(self.items) > self.max_visible:
            track_h = self.max_visible * 40 - 5
            track = pygame.Rect(290, 40, 7, track_h)
            pygame.draw.rect(screen, self.theme.scrollbar_track_color, track, border_radius=3)
            handle_h = max(10, track_h * (self.max_visible / len(self.items)))
            scroll_perc = self.scroll_offset / (len(self.items) - self.max_visible) if len(self.items) > self.max_visible else 0
            handle_y = track.y + (track_h - handle_h) * scroll_perc
            handle = pygame.Rect(track.x, handle_y, 7, handle_h)
            pygame.draw.rect(screen, self.theme.scrollbar_handle_color, handle, border_radius=3)


class SettingsMenu(MenuBase):
    def __init__(self, font, small_font, lang="en", flag_sprite_sheet=None, theme=None):
        items = [
            {"icon": "", "label": get_string(lang, "log_settings"), "action": "log_settings"},
            {"icon": "󰀖", "label": get_string(lang, "lookup"), "action": "lookup_settings"},
            {"icon": "󱓡", "label": get_string(lang, "modes"), "action": "mode_settings"},
            {"icon": "", "label": get_string(lang, "theme"), "action": "theme_settings"},
            {"icon": "", "label": get_string(lang, "language"), "action": "language_settings", "flag": True},
        ]
        title = get_string(lang, "settings_categories")
        super().__init__(font, small_font, theme, lang, title, items, flag_sprite_sheet)

class TextInputPopup:
    def __init__(self, font, small_font, theme, initial_text, title):
        self.font = font
        self.small_font = small_font
        self.theme = theme
        self.text = str(initial_text) if initial_text else ""
        self.title = title
        self.rect = pygame.Rect(10, 35, 300, 100)
        self.cursor_timer = 0
        
    def handle_event(self, event):
        if event.key == pygame.K_RETURN:
            return self.text
        if event.key == pygame.K_ESCAPE:
            return "cancel"
        if event.key == pygame.K_BACKSPACE:
            self.text = self.text[:-1]
        elif event.unicode.isprintable():
            self.text += event.unicode
        return None

    def draw(self, screen):
        self.cursor_timer += 1
        pygame.draw.rect(screen, self.theme.popup_bg_color, self.rect, border_radius=5)
        pygame.draw.rect(screen, self.theme.popup_border_color, self.rect, 2, border_radius=5)
        
        title_surf = self.small_font.render(self.title, True, self.theme.text_color)
        screen.blit(title_surf, (self.rect.centerx - title_surf.get_width()//2, self.rect.y + 10))
        
        text_rect = pygame.Rect(self.rect.x + 10, self.rect.y + 40, self.rect.width - 20, 30)
        pygame.draw.rect(screen, self.theme.box_color, text_rect, border_radius=3)
        pygame.draw.rect(screen, self.theme.highlight_color, text_rect, 2, border_radius=3)
        
        text_surf = self.small_font.render(self.text, True, self.theme.text_color)
        
        text_render_rect = text_rect.inflate(-10, 0)
        
        if text_surf.get_width() > text_render_rect.width:
            x_offset = text_render_rect.width - text_surf.get_width()
            screen.set_clip(text_render_rect)
            screen.blit(text_surf, (text_render_rect.x + x_offset, text_rect.y + (text_rect.height - text_surf.get_height()) // 2))
            screen.set_clip(None)
            cursor_x = text_render_rect.right
        else:
            screen.blit(text_surf, (text_render_rect.x, text_rect.y + (text_rect.height - text_surf.get_height()) // 2))
            cursor_x = text_render_rect.x + text_surf.get_width()
            
        if self.cursor_timer % 60 < 30:
            pygame.draw.line(screen, self.theme.text_color, (cursor_x, text_rect.y + 5), (cursor_x, text_rect.bottom - 5), 2)

class SettingsScreenBase:
    def __init__(self, user_config, font, small_font, title, settings, buttons=None, flag_sprite_sheet=None, theme=None):
        self.user_config = user_config
        self.font, self.small_font = font, small_font
        self.title = title
        self.settings = settings
        self.buttons = buttons if buttons else []
        self.flag_sprite_sheet = flag_sprite_sheet
        self.theme = theme
        
        self.active_setting = 0
        self.active_button = 0
        self.focus_on_buttons = False
        self.edit_mode = False
        self.scroll_offset = 0
        self.max_visible_items = 4
        self.rect = pygame.Rect(10, 10, 300, 150)
        self.popup = None
        self.cursor_timer = 0
        
    def handle_event(self, event):
        if getattr(self, 'popup', None) is not None:
            res = self.popup.handle_event(event)
            if res is not None:
                if res != "cancel":
                    self.settings[self.active_setting]["value"] = res
                self.popup = None
            return "active"

        if event.key == pygame.K_ESCAPE: 
            return {s["key"]: s["value"] for s in self.settings}
        
        if self.edit_mode:
            setting = self.settings[self.active_setting]
            if event.key == pygame.K_RETURN: self.edit_mode = False
            elif event.key == pygame.K_BACKSPACE and setting["type"] in ("text", "password"): 
                setting["value"] = setting["value"][:-1]
            elif event.unicode.isprintable() and setting["type"] in ("text", "password"): 
                setting["value"] += event.unicode
            return "active"

        if self.focus_on_buttons:
            if event.key == pygame.K_UP:
                self.focus_on_buttons = False
            elif event.key == pygame.K_RIGHT:
                self.active_button = (self.active_button + 1) % len(self.buttons)
            elif event.key == pygame.K_LEFT:
                self.active_button = (self.active_button - 1 + len(self.buttons)) % len(self.buttons)
            elif event.key == pygame.K_RETURN:
                return self.buttons[self.active_button]["action"]
        else:
            if event.key == pygame.K_DOWN:
                if self.active_setting == len(self.settings) - 1 and self.buttons:
                    self.focus_on_buttons = True
                else:
                    self.active_setting = (self.active_setting + 1) % len(self.settings)
            elif event.key == pygame.K_UP:
                self.active_setting = (self.active_setting - 1 + len(self.settings)) % len(self.settings)
            elif event.key == pygame.K_RETURN:
                setting = self.settings[self.active_setting]
                if setting["type"] == "checkbox":
                    current_val = setting["value"]
                    new_val = "1" if current_val == "0" else "0"
                    setting["value"] = new_val
                    if new_val == "1":
                        if setting["key"] == "sota_mode":
                            for s in self.settings:
                                if s["key"] in ("pota_mode", "contest_mode"): s["value"] = "0"
                        elif setting["key"] == "pota_mode":
                            for s in self.settings:
                                if s["key"] in ("sota_mode", "contest_mode"): s["value"] = "0"
                        elif setting["key"] == "contest_mode":
                            for s in self.settings:
                                if s["key"] in ("sota_mode", "pota_mode"): s["value"] = "0"

                        if setting["key"].startswith("lang_"):
                            for s in self.settings:
                                if s["key"].startswith("lang_") and s["key"] != setting["key"]:
                                    s["value"] = "0"
                elif setting["type"] == "options":
                    current_index = setting["options"].index(setting["value"])
                    next_index = (current_index + 1) % len(setting["options"])
                    setting["value"] = setting["options"][next_index]
                elif setting["type"] == "path":
                    self.popup = TextInputPopup(self.font, self.small_font, self.theme, setting["value"], setting["label"])
                else:
                    self.edit_mode = True
            
            if self.active_setting < self.scroll_offset:
                self.scroll_offset = self.active_setting
            elif self.active_setting >= self.scroll_offset + self.max_visible_items:
                self.scroll_offset = self.active_setting - self.max_visible_items + 1

        return "active"
        
    def draw(self, screen):
        self.cursor_timer += 1
        screen.fill(self.theme.bg_color)
        title_surf = self.font.render(self.title, True, self.theme.text_color)
        screen.blit(title_surf, (self.rect.centerx - title_surf.get_width()//2, self.rect.y + 5))
        
        y = self.rect.y + 35
        for i, setting in enumerate(self.settings[self.scroll_offset:self.scroll_offset+self.max_visible_items]):
            actual_index = self.scroll_offset + i
            color = self.theme.highlight_color if actual_index == self.active_setting and not self.focus_on_buttons else self.theme.box_color
            
            label_x = self.rect.x + 10
            
            if setting.get("flag_call") and self.flag_sprite_sheet:
                flag_surf = get_flag_surface(setting["flag_call"], self.flag_sprite_sheet)
                if flag_surf:
                    screen.blit(flag_surf, (label_x, y + (24 - flag_surf.get_height()) // 2))
                    label_x += flag_surf.get_width() + 5

            label_surf = self.small_font.render(setting["label"], True, color)
            label_y = y + (24 - label_surf.get_height()) // 2
            screen.blit(label_surf, (label_x, label_y))
            
            value_x_pos = self.rect.x + 105
            value_width = self.rect.width - 125
            if len(self.settings) > self.max_visible_items:
                value_width = self.rect.width - 135

            if setting["type"] == "checkbox":
                cb_surf = self.font.render("☑" if setting["value"] == "1" else "☐", True, self.theme.text_color)
                screen.blit(cb_surf, (self.rect.centerx - cb_surf.get_width()//2, y))
            elif setting["type"] == "options":
                value_rect = pygame.Rect(value_x_pos, y, value_width, 24)
                border_color = self.theme.highlight_color if actual_index == self.active_setting else color
                pygame.draw.rect(screen, border_color, value_rect, 2, border_radius=3)
                
                value_surf = self.small_font.render(str(setting["value"]), True, self.theme.text_color)
                text_y = value_rect.y + (value_rect.height - value_surf.get_height()) // 2
                screen.blit(value_surf, (value_rect.x + 5, text_y))
            else:
                value_rect = pygame.Rect(value_x_pos, y, value_width, 24)
                is_active_setting = actual_index == self.active_setting and not self.focus_on_buttons
                is_editing = is_active_setting and self.edit_mode

                border_color = self.theme.highlight_color if is_active_setting else self.theme.box_color
                pygame.draw.rect(screen, border_color, value_rect, 2, border_radius=3)
                
                display_value = str(setting["value"])
                if setting["type"] == "password" and not is_editing:
                    display_value = "*" * len(display_value)
                elif setting["type"] == "path":
                    filename = os.path.basename(display_value) if display_value else ""
                    if not filename and display_value:
                        filename = os.path.basename(display_value.rstrip('/\\'))
                    if not filename:
                        filename = display_value
                    
                    if display_value and display_value != filename:
                        display_value = ".../" + filename
                    else:
                        display_value = filename

                value_surf = self.small_font.render(display_value, True, self.theme.text_color)
                text_y = value_rect.y + (value_rect.height - value_surf.get_height()) // 2
                
                text_render_rect = value_rect.inflate(-10, 0)

                if value_surf.get_width() > text_render_rect.width:
                    x_offset = text_render_rect.width - value_surf.get_width()
                    screen.set_clip(text_render_rect)
                    screen.blit(value_surf, (text_render_rect.x + x_offset, text_y))
                    screen.set_clip(None)
                    cursor_x = text_render_rect.right
                else:
                    screen.blit(value_surf, (text_render_rect.x, text_y))
                    cursor_x = text_render_rect.x + value_surf.get_width()

                if is_editing and self.cursor_timer % 60 < 30:
                    pygame.draw.line(screen, self.theme.text_color, (cursor_x, value_rect.y + 5), (cursor_x, value_rect.bottom - 5), 2)
            
            y += 28 
            
        if self.buttons:
            button_y = self.rect.bottom - 40
            button_width = (self.rect.width - (len(self.buttons) + 1) * 10) / len(self.buttons)
            for i, button in enumerate(self.buttons):
                button_rect = pygame.Rect(self.rect.x + 10 + i * (button_width + 10), button_y, button_width, 30)
                color = self.theme.highlight_color if i == self.active_button and self.focus_on_buttons else self.theme.box_color
                pygame.draw.rect(screen, color, button_rect, 2, border_radius=5)
                label_surf = self.small_font.render(button["label"], True, color)
                screen.blit(label_surf, (button_rect.centerx - label_surf.get_width()//2, button_rect.centery - label_surf.get_height()//2))

        if len(self.settings) > self.max_visible_items:
            track_h = self.rect.height-30
            track = pygame.Rect(self.rect.right-12, self.rect.top+25, 7, track_h)
            pygame.draw.rect(screen, self.theme.scrollbar_track_color, track, border_radius=3)
            handle_h = max(10, track_h*(self.max_visible_items/len(self.settings)))
            scroll_perc = self.scroll_offset/(len(self.settings)-self.max_visible_items) if len(self.settings) > self.max_visible_items else 0
            handle_y = track.y+(track_h-handle_h)*scroll_perc
            handle = pygame.Rect(track.x, handle_y, 7, handle_h)
            pygame.draw.rect(screen, self.theme.scrollbar_handle_color, handle, border_radius=3)
            
        if getattr(self, 'popup', None) is not None:
            self.popup.draw(screen)

class LogSettingsScreen(SettingsScreenBase):
    def __init__(self, user_config, font, small_font, theme):
        lang = user_config.get("language", "en")
        settings = [
            {"key": "station_callsign", "label": get_string(lang, "callsign"), "value": user_config.get("station_callsign", ""), "type": "text"},
            {"key": "my_gridsquare", "label": get_string(lang, "my_grid"), "value": user_config.get("my_gridsquare", ""), "type": "text"},
            {"key": "tx_pwr", "label": get_string(lang, "tx_pwr"), "value": user_config.get("tx_pwr", ""), "type": "text"},
            {"key": "cq_zone", "label": get_string(lang, "cq_zone"), "value": user_config.get("cq_zone", ""), "type": "text"},
            {"key": "itu_zone", "label": get_string(lang, "itu_zone"), "value": user_config.get("itu_zone", ""), "type": "text"},
        ]
        super().__init__(user_config, font, small_font, get_string(lang, "log_settings_title"), settings, theme=theme)

class LookupSettingsScreen(SettingsScreenBase):
    def __init__(self, user_config, font, small_font, theme):
        lang = user_config.get("language", "en")
        settings = [
            {"key": "lookup_auto", "label": get_string(lang, "lookup_auto"), "value": user_config.get("lookup_auto", "0"), "type": "checkbox"},
            {"key": "lookup_provider", "label": get_string(lang, "provider"), "value": user_config.get("lookup_provider", "hamdb"), "type": "options", "options": ["hamdb", "qrz"]},
            {"key": "qrz_username", "label": get_string(lang, "qrz_username"), "value": user_config.get("qrz_username", ""), "type": "text"},
            {"key": "qrz_password", "label": get_string(lang, "qrz_password"), "value": user_config.get("qrz_password", ""), "type": "password"},
        ]
        super().__init__(user_config, font, small_font, get_string(lang, "lookup_settings"), settings, theme=theme)

class ModeSettingsScreen(SettingsScreenBase):
    def __init__(self, user_config, font, small_font, theme):
        lang = user_config.get("language", "en")
        settings = [
            {"key": "sota_mode", "label": get_string(lang, "sota_mode"), "value": user_config.get("sota_mode", "0"), "type": "checkbox"},
            {"key": "pota_mode", "label": get_string(lang, "pota_mode"), "value": user_config.get("pota_mode", "0"), "type": "checkbox"},
            {"key": "contest_mode", "label": get_string(lang, "contest_mode"), "value": user_config.get("contest_mode", "0"), "type": "checkbox"},
        ]
        super().__init__(user_config, font, small_font, get_string(lang, "mode_settings_title"), settings, theme=theme)

class ThemeSettingsScreen(SettingsScreenBase):
    def __init__(self, user_config, font, small_font, theme):
        lang = user_config.get("language", "en")
        settings = [
            {"key": "theme_bg", "label": get_string(lang, "theme_bg_color"), "value": user_config.get("theme_bg", "20,20,30"), "type": "text"},
            {"key": "theme_text", "label": get_string(lang, "theme_text_color"), "value": user_config.get("theme_text", "200,200,200"), "type": "text"},
            {"key": "theme_box", "label": get_string(lang, "theme_box_color"), "value": user_config.get("theme_box", "100,100,120"), "type": "text"},
            {"key": "theme_highlight", "label": get_string(lang, "theme_highlight_color"), "value": user_config.get("theme_highlight", "100,255,100"), "type": "text"},
            {"key": "theme_typing", "label": get_string(lang, "theme_typing_color"), "value": user_config.get("theme_typing", "255,165,0"), "type": "text"},
            {"key": "theme_dupe", "label": get_string(lang, "theme_dupe_color"), "value": user_config.get("theme_dupe", "100,255,100"), "type": "text"},
            {"key": "theme_popup_bg", "label": get_string(lang, "theme_popup_bg"), "value": user_config.get("theme_popup_bg", "40,40,60"), "type": "text"},
            {"key": "theme_popup_border", "label": get_string(lang, "theme_popup_border"), "value": user_config.get("theme_popup_border", "150,150,170"), "type": "text"},
            {"key": "theme_separator", "label": get_string(lang, "theme_separator"), "value": user_config.get("theme_separator", "60,60,70"), "type": "text"},
            {"key": "theme_detail_bg", "label": get_string(lang, "theme_detail_bg"), "value": user_config.get("theme_detail_bg", "30,30,40"), "type": "text"},
            {"key": "theme_scrollbar_track", "label": get_string(lang, "theme_scrollbar_track"), "value": user_config.get("theme_scrollbar_track", "40,40,60"), "type": "text"},
            {"key": "theme_scrollbar_handle", "label": get_string(lang, "theme_scrollbar_handle"), "value": user_config.get("theme_scrollbar_handle", "80,80,100"), "type": "text"},
            {"key": "theme_log_header", "label": get_string(lang, "theme_log_header"), "value": user_config.get("theme_log_header", "180,180,180"), "type": "text"},
        ]
        super().__init__(user_config, font, small_font, get_string(lang, "theme"), settings, theme=theme)

class LanguageSettingsScreen(SettingsScreenBase):
    def __init__(self, user_config, font, small_font, flag_sprite_sheet, theme):
        lang = user_config.get("language", "en")
        
        is_en = "1" if lang == "en" else "0"
        is_de = "1" if lang == "de" else "0"
        is_zh = "1" if lang == "zh-hans" else "0"
        is_nl = "1" if lang == "nl" else "0"
        is_es = "1" if lang == "es" else "0"
        is_pt = "1" if lang == "pt" else "0"
        is_it = "1" if lang == "it" else "0"

        settings = [
            {"key": "lang_en", "label": get_string(lang, "lang_en"), "value": is_en, "type": "checkbox", "flag_call": "M1ABC"},
            {"key": "lang_de", "label": get_string(lang, "lang_de"), "value": is_de, "type": "checkbox", "flag_call": "DL1ABC"},
            {"key": "lang_zh-hans", "label": get_string(lang, "lang_zh-hans"), "value": is_zh, "type": "checkbox", "flag_call": "B1ABC"},
            {"key": "lang_nl", "label": get_string(lang, "lang_nl"), "value": is_nl, "type": "checkbox", "flag_call": "PA1ABC"},
            {"key": "lang_es", "label": get_string(lang, "lang_es"), "value": is_es, "type": "checkbox", "flag_call": "EA1ABC"},
            {"key": "lang_pt", "label": get_string(lang, "lang_pt"), "value": is_pt, "type": "checkbox", "flag_call": "CT1ABC"},
            {"key": "lang_it", "label": get_string(lang, "lang_it"), "value": is_it, "type": "checkbox", "flag_call": "I1ABC"},
        ]
        super().__init__(user_config, font, small_font, get_string(lang, "language"), settings, flag_sprite_sheet=flag_sprite_sheet, theme=theme)

    def handle_event(self, event):
        res = super().handle_event(event)
        if isinstance(res, dict):
            # Convert checkboxes back to language code
            for key, value in res.items():
                if key.startswith("lang_") and value == "1":
                    return {"language": key.replace("lang_", "")}
            
            # If no language is selected, default to English
            return {"language": "en"}
        return res

class ExportSettingsScreen(SettingsScreenBase):
    def __init__(self, user_config, font, small_font, theme):
        lang = user_config.get("language", "en")
        settings = [
            {"key": "logfile", "label": get_string(lang, "log_file"), "value": user_config.get("logfile", ""), "type": "path"},
        ]
        buttons = [
            {"label": get_string(lang, "export_today"), "action": "export_today"},
            {"label": get_string(lang, "export_by_date"), "action": "export_by_date"},
        ]
        super().__init__(user_config, font, small_font, get_string(lang, "export"), settings, buttons, theme=theme)


class AdditionalInfoScreen:
    def __init__(self, font, small_font, theme, lang="en"):
        self.font, self.small_font, self.lang, self.theme = font, small_font, lang, theme
        self.rect = pygame.Rect(10, 10, 300, 150)
        
    def handle_event(self, event):
        if event.key == pygame.K_ESCAPE: return "close"
        return "active"
        
    def draw(self, screen):
        screen.fill(self.theme.bg_color)
        pygame.draw.rect(screen, self.theme.popup_border_color, self.rect, 2, border_radius=5)
        title_surf = self.font.render(get_string(self.lang, "about"), True, self.theme.text_color); screen.blit(title_surf, (self.rect.centerx - title_surf.get_width()//2, self.rect.y + 5))
        
        info = [
            "Cardputer HamLog v0.1",
            "A minimalist logger for",
            "SOTA/POTA and portable ops.",
            "",
            "Created with ❤ by DN9GRK"
        ]
        
        y = self.rect.y + 40
        for line in info:
            surf = self.small_font.render(line, True, self.theme.text_color)
            screen.blit(surf, (self.rect.centerx - surf.get_width()//2, y))
            y += 20

class MainMenu(MenuBase):
    def __init__(self, font, small_font, theme, lang="en"):
        items = [
            {"icon": "", "label": get_string(lang, "view_log"), "action": "view_log"},
            {"icon": "", "label": get_string(lang, "settings"), "action": "settings"},
            {"icon": "󱘬", "label": get_string(lang, "export"), "action": "export_settings"},
            {"icon": "", "label": get_string(lang, "statistics"), "action": "statistics"},
            {"icon": "", "label": get_string(lang, "about"), "action": "about"},
        ]
        title = get_string(lang, "menu_title") if get_string(lang, "menu_title") else "Main Menu"
        super().__init__(font, small_font, theme, lang, title, items)

class StatisticsMenu(MenuBase):
    def __init__(self, font, small_font, theme, lang="en"):
        items = [
            {"icon": "", "label": get_string(lang, "band_distribution"), "action": "band_distribution"},
        ]
        title = get_string(lang, "statistics")
        super().__init__(font, small_font, theme, lang, title, items)

class BandDistributionScreen:
    def __init__(self, log_file, font, small_font, theme, lang="en"):
        self.font, self.small_font, self.lang, self.theme = font, small_font, lang, theme
        self.rect = pygame.Rect(10, 10, 300, 150)
        self.band_data = {}
        self.load_and_process_log(log_file)
        self.colors = [
            (255, 128, 128), (128, 255, 128), (128, 128, 255),
            (255, 255, 128), (128, 255, 255), (255, 128, 255),
            (255, 192, 128), (128, 192, 255), (192, 128, 255)
        ]

    def load_and_process_log(self, log_file):
        if not os.path.exists(log_file): return
        with open(log_file, 'r') as f:
            lines = f.readlines()
        
        bands = {}
        for line in lines:
            if "<BAND:" in line:
                try:
                    band_part = line.split("<BAND:")[1]
                    band = band_part.split(">")[1].split("<")[0]
                    bands[band] = bands.get(band, 0) + 1
                except IndexError:
                    continue
        
        self.band_data = dict(sorted(bands.items()))

    def handle_event(self, event):
        if event.key == pygame.K_ESCAPE or event.key == pygame.K_RETURN:
            return "close"
        return "active"

    def draw(self, screen):
        screen.fill(self.theme.bg_color)
        pygame.draw.rect(screen, self.theme.popup_border_color, self.rect, 2, border_radius=5)
        title_surf = self.font.render(get_string(self.lang, "band_distribution"), True, self.theme.text_color)
        screen.blit(title_surf, (self.rect.centerx - title_surf.get_width()//2, self.rect.y + 5))

        if not self.band_data:
            no_data_surf = self.small_font.render("No QSOs", True, self.theme.text_color)
            screen.blit(no_data_surf, (self.rect.centerx - no_data_surf.get_width()//2, self.rect.centery))
            return

        max_qso = max(self.band_data.values()) if self.band_data else 1
        
        chart_rect = pygame.Rect(self.rect.x + 10, self.rect.y + 40, self.rect.width - 20, self.rect.height - 50)
        
        num_bands = len(self.band_data)
        if num_bands == 0: return

        total_bar_height = chart_rect.height / num_bands
        bar_height = total_bar_height * 0.7
        bar_spacing = total_bar_height * 0.3

        label_area_width = 40
        bar_area_x = chart_rect.x + label_area_width
        max_bar_width = chart_rect.width - label_area_width - 25

        y = chart_rect.y
        color_index = 0

        for band, count in self.band_data.items():
            label_surf = self.small_font.render(band, True, self.theme.text_color)
            label_y = y + (bar_height - label_surf.get_height()) / 2
            screen.blit(label_surf, (chart_rect.x, label_y))

            bar_width = (count / max_qso) * max_bar_width
            bar_rect = pygame.Rect(bar_area_x, y, bar_width, bar_height)
            current_color = self.colors[color_index % len(self.colors)]
            pygame.draw.rect(screen, current_color, bar_rect, border_radius=2)
            
            count_surf = self.small_font.render(str(count), True, self.theme.text_color)
            count_y = y + (bar_height - count_surf.get_height()) / 2
            screen.blit(count_surf, (bar_area_x + bar_width + 5, count_y))

            y += total_bar_height
            color_index += 1

class LogViewer:
    def __init__(self, log_file, font, small_font, theme, flag_sprite_sheet=None, lang="en"):
        self.font, self.small_font, self.lang, self.theme = font, small_font, lang, theme
        self.flag_sprite_sheet = flag_sprite_sheet
        self.rect = pygame.Rect(10, 10, 300, 150)
        self.log_entries = []
        self.parsed_data = []
        self.active_index = 0
        self.scroll_offset = 0
        self.detail_scroll_offset = 0
        self.max_visible_items = (self.rect.height - 30) // 20
        self.selected_qso = None
        self.load_log(log_file)

    @staticmethod
    def parse_line(line):
        data = {}
        parts = line.split("<")
        for p in parts[1:]:
            if ":" in p:
                tag, rest = p.split(":", 1)
                if ">" in rest:
                    val = rest.split(">")[1].strip()
                    data[tag] = val
        return data

    def load_log(self, log_file):
        if not os.path.exists(log_file): return
        with open(log_file, 'r') as f:
            lines = f.readlines()
            temp_entries = []
            for line in lines:
                if "<CALL:" in line:
                    temp_entries.append(line.strip())
            
            self.log_entries = []
            self.parsed_data = []
            
            for entry in reversed(temp_entries):
                self.log_entries.append(entry)
                self.parsed_data.append(self.parse_line(entry))

    def handle_event(self, event):
        if self.selected_qso is not None:
            if event.key == pygame.K_ESCAPE or event.key == pygame.K_RETURN:
                self.selected_qso = None
                self.detail_scroll_offset = 0
            elif event.key == pygame.K_DOWN:
                self.detail_scroll_offset += 1
            elif event.key == pygame.K_UP:
                self.detail_scroll_offset = max(0, self.detail_scroll_offset - 1)
            return "active"

        if event.key == pygame.K_ESCAPE: return "close"
        if event.key == pygame.K_DOWN: self.active_index = min(len(self.log_entries) - 1, self.active_index + 1)
        elif event.key == pygame.K_UP: self.active_index = max(0, self.active_index - 1)
        elif event.key == pygame.K_RETURN:
            if self.log_entries:
                self.selected_qso = self.parsed_data[self.active_index]
                self.detail_scroll_offset = 0
        
        if self.active_index < self.scroll_offset: self.scroll_offset = self.active_index
        elif self.active_index >= self.scroll_offset + self.max_visible_items: self.scroll_offset = self.active_index - self.max_visible_items + 1
        return "active"

    def draw(self, screen):
        screen.fill(self.theme.bg_color)
        pygame.draw.rect(screen, self.theme.popup_border_color, self.rect, 2, border_radius=5)
        
        if self.selected_qso is not None:
            y = self.rect.y + 10
            qso = self.selected_qso
            callsign = qso.get('CALL', 'N/A')
            
            draw_callsign_and_flag(screen, self.font, callsign, self.theme.highlight_color, self.rect.centerx, y, self.flag_sprite_sheet)

            y += 25
            
            raw_date = qso.get('QSO_DATE', '')
            raw_time = qso.get('TIME_ON', '')
            
            date_formatted = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:]}" if len(raw_date) == 8 else raw_date
            time_formatted = f"{raw_time[:2]}:{raw_time[2:]}" if len(raw_time) == 4 else raw_time
            
            details = [
                f"{get_string(self.lang, 'date')}/{get_string(self.lang, 'time')}: {date_formatted} {time_formatted}",
                f"Band: {qso.get('BAND', '')}  Freq: {qso.get('FREQ', '')} MHz",
                f"{get_string(self.lang, 'mode')}: {qso.get('MODE', '')}",
                f"{get_string(self.lang, 'rst_s')}: {qso.get('RST_SENT', '')}  {get_string(self.lang, 'rst_r')}: {qso.get('RST_RCVD', '')}"
            ]
            
            for key, value in self.selected_qso.items():
                if key not in ['CALL', 'QSO_DATE', 'TIME_ON', 'BAND', 'FREQ', 'MODE', 'RST_SENT', 'RST_RCVD'] and value:
                    label = get_string(self.lang, key)
                    details.append(f"{label}: {value}")
            
            max_detail_visible = 4
            self.detail_scroll_offset = max(0, min(self.detail_scroll_offset, len(details) - max_detail_visible))
            
            visible_details = details[self.detail_scroll_offset:self.detail_scroll_offset + max_detail_visible]
            
            pygame.draw.rect(screen, self.theme.detail_bg_color, (self.rect.x + 5, y - 5, self.rect.width - 20, len(visible_details) * 20 + 10), border_radius=5)
            
            for d in visible_details:
                surf = self.small_font.render(d, True, self.theme.text_color)
                screen.blit(surf, (self.rect.x + 10, y))
                y += 20
                
            if len(details) > max_detail_visible:
                track_h = len(visible_details) * 20
                track = pygame.Rect(self.rect.right-12, self.rect.y + 35, 7, track_h)
                pygame.draw.rect(screen, self.theme.scrollbar_track_color, track, border_radius=3)
                handle_h = max(10, track_h*(max_detail_visible/len(details)))
                scroll_perc = self.detail_scroll_offset/(len(details)-max_detail_visible)
                handle_y = track.y+(track_h-handle_h)*scroll_perc
                handle = pygame.Rect(track.x, handle_y, 7, handle_h)
                pygame.draw.rect(screen, self.theme.scrollbar_handle_color, handle, border_radius=3)
            
            exit_hint = self.small_font.render(get_string(self.lang, "press_esc_return") if get_string(self.lang, "press_esc_return") else "Press ESC to return", True, self.theme.popup_border_color)
            screen.blit(exit_hint, (self.rect.centerx - exit_hint.get_width()//2, self.rect.bottom - 20))
            return

        header_y = self.rect.y + 10
        col_x = [self.rect.x + 5, self.rect.x + 65, self.rect.x + 125, self.rect.x + 225]
        
        headers = [get_string(self.lang, "date"), get_string(self.lang, "time"), get_string(self.lang, "call"), get_string(self.lang, "mode")]
        for i, header in enumerate(headers):
            header_surf = self.small_font.render(header, True, self.theme.log_header_color)
            screen.blit(header_surf, (col_x[i], header_y))
        
        pygame.draw.line(screen, self.theme.scrollbar_handle_color, (self.rect.x, header_y + 18), (self.rect.right, header_y + 18), 1)

        y = self.rect.y + 30
        visible_entries = self.log_entries[self.scroll_offset:self.scroll_offset+self.max_visible_items]
        for i, entry in enumerate(visible_entries):
            idx = self.scroll_offset + i
            color = self.theme.highlight_color if idx == self.active_index else self.theme.text_color
            bg_color = self.theme.popup_bg_color if idx == self.active_index else None
            
            qso = self.parsed_data[idx]
            raw_date = qso.get('QSO_DATE', '--------')
            raw_time = qso.get('TIME_ON', '----')
            call = qso.get('CALL', '')
            mode = qso.get('MODE', '')
            
            date_formatted = f"{raw_date[4:6]}-{raw_date[6:]}" if len(raw_date) == 8 else raw_date
            time_formatted = f"{raw_time[:2]}:{raw_time[2:]}" if len(raw_time) == 4 else raw_time
            
            if bg_color:
                pygame.draw.rect(screen, bg_color, (self.rect.x + 2, y - 2, self.rect.width - 4, 18), border_radius=3)
            
            max_mode_width = self.rect.right - col_x[3] - 15
            if self.small_font.size(mode)[0] > max_mode_width:
                temp_mode = mode
                while self.small_font.size(temp_mode + '...')[0] > max_mode_width and len(temp_mode) > 0:
                    temp_mode = temp_mode[:-1]
                mode = temp_mode + '...'

            date_surf = self.small_font.render(date_formatted, True, color)
            time_surf = self.small_font.render(time_formatted, True, color)
            call_surf = self.small_font.render(call, True, color)
            mode_surf = self.small_font.render(mode, True, color)

            screen.blit(date_surf, (col_x[0], y))
            screen.blit(time_surf, (col_x[1], y))
            screen.blit(call_surf, (col_x[2], y))
            screen.blit(mode_surf, (col_x[3], y))
            
            if i < len(visible_entries) - 1:
                 pygame.draw.line(screen, self.theme.separator_color, (self.rect.x + 5, y + 18), (self.rect.right - 15, y + 18), 1)

            y += 20
            
        if len(self.log_entries) > self.max_visible_items:
            track_h = self.rect.height-10; track = pygame.Rect(self.rect.right-12, self.rect.top+5, 7, track_h); pygame.draw.rect(screen, self.theme.scrollbar_track_color, track, border_radius=3)
            handle_h = max(10, track_h*(self.max_visible_items/len(self.log_entries))); scroll_perc = self.scroll_offset/(len(self.log_entries)-self.max_visible_items) if len(self.log_entries) > self.max_visible_items else 0
            handle_y = track.y+(track_h-handle_h)*scroll_perc; handle = pygame.Rect(track.x, handle_y, 7, handle_h); pygame.draw.rect(screen, self.theme.scrollbar_handle_color, handle, border_radius=3)

class LookupInfoScreen:
    def __init__(self, font, small_font, theme, callsign, lookup_data, lang="en"):
        self.font = font
        self.small_font = small_font
        self.theme = theme
        self.callsign = callsign
        self.lookup_data = lookup_data
        self.lang = lang
        self.rect = pygame.Rect(10, 10, 300, 150)
        self.scroll_offset = 0
        
        self.details = []
        if not lookup_data:
            self.details.append(get_string(lang, "lookup_not_found") if get_string(lang, "lookup_not_found") else "Not found")
        else:
            for key, value in lookup_data.items():
                if value:
                    label = get_string(lang, key)
                    self.details.append(f"{label}: {value}")

        self.max_visible_items = (self.rect.height - 40) // 20

    def handle_event(self, event):
        if event.key == pygame.K_ESCAPE or event.key == pygame.K_RETURN:
            return {"action": "close", "data": self.lookup_data}
        if event.key == pygame.K_DOWN:
            self.scroll_offset = min(len(self.details) - self.max_visible_items, self.scroll_offset + 1)
            self.scroll_offset = max(0, self.scroll_offset)
        elif event.key == pygame.K_UP:
            self.scroll_offset = max(0, self.scroll_offset - 1)
        return "active"

    def draw(self, screen):
        screen.fill(self.theme.bg_color)
        pygame.draw.rect(screen, self.theme.popup_border_color, self.rect, 2, border_radius=5)
        
        title = f"{get_string(self.lang, 'lookup_title')}: {self.callsign}"
        title_surf = self.font.render(title, True, self.theme.text_color)
        screen.blit(title_surf, (self.rect.centerx - title_surf.get_width()//2, self.rect.y + 5))
        
        y = self.rect.y + 35
        visible_details = self.details[self.scroll_offset:self.scroll_offset + self.max_visible_items]
        
        for d in visible_details:
            surf = self.small_font.render(d, True, self.theme.text_color)
            screen.blit(surf, (self.rect.x + 10, y))
            y += 20
            
        if len(self.details) > self.max_visible_items:
            track_h = self.max_visible_items * 20
            track = pygame.Rect(self.rect.right-12, self.rect.y + 35, 7, track_h)
            pygame.draw.rect(screen, self.theme.scrollbar_track_color, track, border_radius=3)
            handle_h = max(10, track_h*(self.max_visible_items/len(self.details)))
            scroll_perc = self.scroll_offset/(len(self.details)-self.max_visible_items)
            handle_y = track.y+(track_h-handle_h)*scroll_perc
            handle = pygame.Rect(track.x, handle_y, 7, handle_h)
            pygame.draw.rect(screen, self.theme.scrollbar_handle_color, handle, border_radius=3)