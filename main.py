import argparse
import pygame
from datetime import datetime, timezone
import time
import os
from config_manager import load_app_state, save_app_state, load_user_config, save_user_config, load_callsign_cache
from logger import ADIFLogger, get_band_from_freq
from ui_components import UIField, TimeEditor, ModeSelector, SettingsMenu, LogSettingsScreen, ModeSettingsScreen, ThemeSettingsScreen, LanguageSettingsScreen, ExportSettingsScreen, AdditionalInfoScreen, MainMenu, LogViewer, DateSelector, StatisticsMenu, BandDistributionScreen, LookupInfoScreen, LookupSettingsScreen
from flag_utils import get_flag_surface
from export_utils import export_today_adif, export_by_date_adif
from language import get_string
from lookup_utils import lookup_callsign
import threading
from theme import Theme
from font_util import CompositeFont

def main():
    parser = argparse.ArgumentParser(description="Ham Radio Logger")
    parser.add_argument("--dev", action="store_true", help="Startet das Display-Fenster auf dem PC")
    args = parser.parse_args()
    if not args.dev: print("Starte im Hardware-Modus..."); return

    pygame.init()
    screen = pygame.display.set_mode((320, 170))
    clock = pygame.time.Clock()
    
    os.makedirs("./logs", exist_ok=True)

    try:
        # You can now define the size for the primary font and the CJK/Fallback font separately
        primary_size_normal = 18
        cjk_size_normal = 20  # Change this if Chinese characters need to be larger
        
        primary_size_small = 14
        cjk_size_small = 16   # Change this if small Chinese characters need to be larger
        
        font = CompositeFont("./fonts/DejaVuSansNerdBold.ttf", primary_size_normal, "./fonts/卓特清雅体.ttf", fallback_size=cjk_size_normal)
        small_font = CompositeFont("./fonts/DejaVuSansNerdBold.ttf", primary_size_small, "./fonts/卓特清雅体.ttf", fallback_size=cjk_size_small)
    except pygame.error as e:
        print(f"Warnung: Schriftart konnte nicht geladen werden ({e}). Symbole oder CJK-Zeichen werden evtl. nicht korrekt dargestellt.")
        font, small_font = pygame.font.Font(None, 24), pygame.font.Font(None, 18)

    user_config = load_user_config()
    theme = Theme(user_config)
    app_state = load_app_state()
    callsign_cache = load_callsign_cache(user_config["logfile"])
    lang = user_config.get("language", "en")
    
    try:
        flag_sprite_sheet = pygame.image.load("./assets/flags16.png").convert_alpha()
    except (pygame.error, FileNotFoundError):
        print("Warning: flags16.png not found. Flag feature disabled.")
        flag_sprite_sheet = None

    def build_fields():
        sota_active = user_config.get("sota_mode", "0") == "1"
        pota_active = user_config.get("pota_mode", "0") == "1"
        contest_active = user_config.get("contest_mode", "0") == "1"
        base_fields = [
            [UIField(pygame.Rect(10, 23, 140, 25), get_string(lang, "callsign")), UIField(pygame.Rect(0, 0, 0, 0), "lookup", ""), UIField(pygame.Rect(170, 23, 140, 25), get_string(lang, "freq"), app_state["freq"])],
            [UIField(pygame.Rect(10,63,65,25), get_string(lang, "rst_s"), "59"), UIField(pygame.Rect(85,63,65,25), get_string(lang, "rst_r"), "59"), UIField(pygame.Rect(170,63,140,25), get_string(lang, "mode"), app_state["mode"])]
        ]
        if sota_active:
            base_fields.append([UIField(pygame.Rect(10,103,140,25), get_string(lang, "my_sota"), app_state.get("my_sota", "")), UIField(pygame.Rect(170,103,140,25), get_string(lang, "sota_ref"), app_state.get("sota_ref", ""))])
        elif pota_active:
            base_fields.append([UIField(pygame.Rect(10,103,140,25), get_string(lang, "my_pota"), app_state.get("my_pota", "")), UIField(pygame.Rect(170,103,140,25), get_string(lang, "pota_ref"), app_state.get("pota_ref", ""))])
        elif contest_active:
            base_fields.append([UIField(pygame.Rect(10,103,140,25), get_string(lang, "stx"), app_state.get("stx_string", "001")), UIField(pygame.Rect(170,103,140,25), get_string(lang, "srx"), app_state.get("srx_string", ""))])
        base_fields.append([None, None, None]) # Dummy row
        return base_fields

    fields = build_fields()
    
    bottom_nav = [pygame.Rect(10, 138, 240, 25), pygame.Rect(255, 138, 25, 25), pygame.Rect(285, 138, 25, 25)]
    bottom_focus, is_auto_time = 0, True
    qso_datetime = datetime.now(timezone.utc)
    active_pos, main_grid_active = [0,0], True
    fields[0][0].active = True
    clear_on_next_input = True
    show_log_popup, popup_end_time, popup_message = False, 0, ""
    time_editor, mode_selector, settings_menu, active_settings_screen, about_screen, main_menu, log_viewer, date_selector, statistics_menu, band_distribution_screen, lookup_screen = (None,) * 11
    lookup_data_cache = {}
    lookup_thread, lookup_result = None, None
    lookup_active = False
    pending_qso_data = None

    def show_popup(message, duration=2):
        nonlocal show_log_popup, popup_end_time, popup_message
        popup_message = message
        show_log_popup = True
        popup_end_time = time.time() + duration

    def start_lookup(callsign):
        nonlocal lookup_thread, lookup_result, lookup_active
        if lookup_active:
            return
        lookup_active = True
        show_popup(get_string(lang, "fetching_info"), duration=10)
        def lookup_worker():
            nonlocal lookup_result, lookup_active
            try:
                provider = user_config.get("lookup_provider", "hamdb")
                username = user_config.get("qrz_username", "")
                password = user_config.get("qrz_password", "")
                lookup_result = lookup_callsign(callsign, provider, username, password)
            finally:
                lookup_active = False
        lookup_thread = threading.Thread(target=lookup_worker)
        lookup_thread.start()

    def log_qso_and_reset(qso_data):
        nonlocal callsign_cache, fields
        call = qso_data["call"]
        logger = ADIFLogger(user_config)
        
        extra_data = lookup_data_cache.get(call.upper(), {})
        logger.log_qso(
            call.upper(), qso_data["rst_s"], qso_data["rst_r"], qso_data["band"], qso_data["mode"], 
            freq=qso_data["freq"], qso_datetime=qso_data["qso_datetime"], 
            my_sota_ref=qso_data["my_sota"], sota_ref=qso_data["sota_ref"], 
            my_pota_ref=qso_data["my_pota"], pota_ref=qso_data["pota_ref"], 
            stx_string=qso_data["stx_str"], srx_string=qso_data["srx_str"], 
            NAME=extra_data.get('name'), QTH=extra_data.get('addr2'), GRIDSQUARE=extra_data.get('grid')
        )
        callsign_cache.add(call.upper())
        
        stx_str = qso_data["stx_str"]
        if user_config.get("contest_mode", "0") == "1" and stx_str.isdigit():
            stx_str = str(int(stx_str) + 1).zfill(max(3, len(stx_str)))
            fields[2][0].value = stx_str
            fields[2][1].value = ""
            
        save_app_state(qso_data["freq"], qso_data["mode"], qso_data["my_sota"], qso_data["sota_ref"], qso_data["my_pota"], qso_data["pota_ref"], stx_str, qso_data["srx_str"])
        fields[0][0].value = ""
        if call.upper() in lookup_data_cache:
            del lookup_data_cache[call.upper()]
            
        show_popup(get_string(lang, "qso_logged"))

    running = True
    while running:
        if is_auto_time and not isinstance(qso_datetime, str): qso_datetime = datetime.now(timezone.utc)
        
        active_field = None
        if main_grid_active:
            current_row = fields[active_pos[0]]
            if active_pos[1] < len(current_row):
                active_field = current_row[active_pos[1]]

        if lookup_thread and not lookup_active:
            lookup_thread.join()
            lookup_thread = None
            
            callsign_key = pending_qso_data["call"].upper() if pending_qso_data else fields[0][0].value.upper()
            lookup_data_cache[callsign_key] = lookup_result

            if pending_qso_data:
                log_qso_and_reset(pending_qso_data)
                pending_qso_data = None
            else:
                show_log_popup = False
                lookup_screen = LookupInfoScreen(font, small_font, theme, callsign_key, lookup_result, lang)
            
            lookup_result = None

        for event in pygame.event.get():
            if event.type == pygame.QUIT: running = False
            elif event.type == pygame.KEYDOWN:
                if lookup_screen:
                    res = lookup_screen.handle_event(event)
                    if res != "active":
                        if isinstance(res, dict) and res.get("action") == "close" and res.get("data"):
                            lookup_data_cache[lookup_screen.callsign] = res["data"]
                        lookup_screen = None
                    continue
                if band_distribution_screen:
                    if band_distribution_screen.handle_event(event) == "close": band_distribution_screen = None
                    continue
                if statistics_menu:
                    res = statistics_menu.handle_event(event)
                    if res == "close": statistics_menu = None
                    elif res == "band_distribution": band_distribution_screen = BandDistributionScreen(user_config["logfile"], font, small_font, theme, lang); statistics_menu = None
                    continue
                if log_viewer:
                    if log_viewer.handle_event(event) == "close": log_viewer = None
                    continue
                if date_selector:
                    res = date_selector.handle_event(event)
                    if res != "active":
                        if res:
                            filename, message = export_by_date_adif(user_config["logfile"], res)
                            show_popup(message)
                        date_selector = None
                        active_settings_screen = None
                    continue
                if active_settings_screen:
                    res = active_settings_screen.handle_event(event)
                    if res == "export_today":
                        filename, message = export_today_adif(user_config["logfile"])
                        show_popup(message)
                        if filename:
                            active_settings_screen = None
                    elif res == "export_by_date":
                        date_selector = DateSelector(datetime.now(timezone.utc), font, small_font, theme)
                    elif res != "active":
                        user_config.update(res)
                        save_user_config(user_config)
                        theme = Theme(user_config) # reload theme after saving!
                        active_settings_screen = None
                        
                        lang = user_config.get("language", "en")
                        
                        old_extra_row = fields[2] if len(fields) > 3 else None
                        fields = build_fields()
                        if old_extra_row and len(fields) > 3:
                            if fields[2][0].label == old_extra_row[0].label:
                                fields[2][0].value = old_extra_row[0].value
                                fields[2][1].value = old_extra_row[1].value
                        
                        if main_grid_active and active_pos[0] >= len(fields) - 1:
                            active_pos[0] = len(fields) - 2
                            active_pos[1] = 0
                            for r in fields:
                                for f in r:
                                    if f: f.active = False
                            fields[active_pos[0]][active_pos[1]].active = True
                    continue
                if settings_menu:
                    res = settings_menu.handle_event(event)
                    if res == "close": settings_menu = None
                    elif res == "log_settings": active_settings_screen = LogSettingsScreen(user_config, font, small_font, theme)
                    elif res == "lookup_settings": active_settings_screen = LookupSettingsScreen(user_config, font, small_font, theme)
                    elif res == "mode_settings": active_settings_screen = ModeSettingsScreen(user_config, font, small_font, theme)
                    elif res == "theme_settings": active_settings_screen = ThemeSettingsScreen(user_config, font, small_font, theme)
                    elif res == "language_settings": active_settings_screen = LanguageSettingsScreen(user_config, font, small_font, flag_sprite_sheet, theme)
                    continue
                if about_screen:
                    if about_screen.handle_event(event) == "close": about_screen = None
                    continue
                if main_menu:
                    res = main_menu.handle_event(event)
                    if res == "close": main_menu = None
                    elif res == "settings": settings_menu = SettingsMenu(font, small_font, lang, flag_sprite_sheet, theme); main_menu = None
                    elif res == "view_log": log_viewer = LogViewer(user_config["logfile"], font, small_font, theme, flag_sprite_sheet, lang); main_menu = None
                    elif res == "about": about_screen = AdditionalInfoScreen(font, small_font, theme, lang); main_menu = None
                    elif res == "export_settings": active_settings_screen = ExportSettingsScreen(user_config, font, small_font, theme); main_menu = None
                    elif res == "statistics": statistics_menu = StatisticsMenu(font, small_font, theme, lang); main_menu = None
                    continue
                if time_editor:
                    res = time_editor.handle_event(event)
                    if res != "active":
                        if res: qso_datetime, is_auto_time = res, False
                        time_editor = None
                    continue
                if mode_selector:
                    res = mode_selector.handle_event(event)
                    if res != "active":
                        if res: fields[1][2].value = res
                        mode_selector = None
                    continue
                if show_log_popup and time.time() > popup_end_time: show_log_popup = False
                if show_log_popup: continue
                if event.key == pygame.K_ESCAPE: running = False
                elif event.key in (pygame.K_DOWN, pygame.K_UP, pygame.K_RIGHT, pygame.K_LEFT):
                    if active_field: active_field.active = False
                    clear_on_next_input = True
                    if main_grid_active:
                        max_row = len(fields) - 2
                        if event.key == pygame.K_DOWN and active_pos[0] == max_row: main_grid_active = False
                        else:
                            if event.key == pygame.K_DOWN: active_pos[0]=min(max_row, active_pos[0]+1)
                            elif event.key == pygame.K_UP: active_pos[0]=max(0, active_pos[0]-1)
                            elif event.key == pygame.K_RIGHT: active_pos[1]+=1
                            elif event.key == pygame.K_LEFT: active_pos[1]-=1
                            row_len = len([f for f in fields[active_pos[0]] if f is not None])
                            if row_len > 0:
                                active_pos[1] = (active_pos[1] + row_len) % row_len
                            else:
                                active_pos[1] = 0
                    else:
                        max_row = len(fields) - 2
                        if event.key == pygame.K_UP: main_grid_active=True; active_pos=[max_row, min(bottom_focus, len([f for f in fields[max_row] if f is not None])-1)]
                        elif event.key == pygame.K_RIGHT: bottom_focus=(bottom_focus+1)%3
                        elif event.key == pygame.K_LEFT: bottom_focus=(bottom_focus-1+3)%3
                    
                    if main_grid_active:
                        current_row = fields[active_pos[0]]
                        if active_pos[1] < len(current_row) and current_row[active_pos[1]]:
                            current_row[active_pos[1]].active = True

                elif event.key == pygame.K_RETURN:
                    if active_field and active_field.label == "lookup":
                        callsign_to_lookup = fields[0][0].value
                        if callsign_to_lookup:
                            start_lookup(callsign_to_lookup.upper())
                    elif active_field and active_field.label == get_string(lang, "callsign"):
                        call,freq,mode = fields[0][0].value,fields[0][2].value,fields[1][2].value
                        band = get_band_from_freq(freq)
                        if call and band != "N/A":
                            my_sota, sota_ref, my_pota, pota_ref, stx_str, srx_str = "", "", "", "", "", ""
                            if len(fields) > 3:
                                if user_config.get("sota_mode", "0") == "1": my_sota, sota_ref = fields[2][0].value, fields[2][1].value
                                elif user_config.get("pota_mode", "0") == "1": my_pota, pota_ref = fields[2][0].value, fields[2][1].value
                                elif user_config.get("contest_mode", "0") == "1": stx_str, srx_str = fields[2][0].value, fields[2][1].value
                            
                            qso_data = {
                                "call": call, "rst_s": fields[1][0].value, "rst_r": fields[1][1].value, "band": band, "mode": mode, "freq": freq, 
                                "qso_datetime": qso_datetime, "my_sota": my_sota, "sota_ref": sota_ref, "my_pota": my_pota, "pota_ref": pota_ref, 
                                "stx_str": stx_str, "srx_str": srx_str
                            }

                            if user_config.get("lookup_auto", "0") == "1" and call.upper() not in lookup_data_cache:
                                pending_qso_data = qso_data
                                start_lookup(call.upper())
                            else:
                                log_qso_and_reset(qso_data)
                        elif not call:
                            if fields[0][0].value.upper() in lookup_data_cache:
                                del lookup_data_cache[fields[0][0].value.upper()]
                    elif active_field and active_field.label == get_string(lang, "mode"): mode_selector = ModeSelector(font, small_font, theme)
                    elif not main_grid_active:
                        if bottom_focus == 0: time_editor = TimeEditor(qso_datetime, font, small_font, theme)
                        elif bottom_focus == 1: is_auto_time = not is_auto_time
                        elif bottom_focus == 2: main_menu = MainMenu(font, small_font, theme, lang)
                elif event.key == pygame.K_BACKSPACE and active_field and active_field.label != "lookup": 
                    clear_on_next_input=False
                    active_field.value=active_field.value[:-1]
                elif active_field and active_field.label != "lookup" and event.unicode.isprintable():
                    if clear_on_next_input: active_field.value, clear_on_next_input = "", False
                    if active_field.label == get_string(lang, "callsign"):
                        active_field.value += event.unicode.upper()
                    elif active_field.label == get_string(lang, "freq"):
                        val,char=active_field.value,event.unicode
                        if char.isdigit():
                            if '.' in val and len(val.split('.')[1])>=6: pass
                            elif ',' in val and len(val.split(',')[1])>=6: pass
                            else: active_field.value+=char
                        elif char in '.,' and '.' not in val and ',' not in val: active_field.value+=char
                    elif active_field.label in [get_string(lang, "rst_s"), get_string(lang, "rst_r")]:
                        if event.unicode.isdigit() and len(active_field.value)<2: active_field.value+=event.unicode
                    else: active_field.value+=event.unicode.upper()
        
        if lookup_screen: lookup_screen.draw(screen)
        elif band_distribution_screen: band_distribution_screen.draw(screen)
        elif statistics_menu: statistics_menu.draw(screen)
        elif log_viewer: log_viewer.draw(screen)
        elif date_selector: date_selector.draw(screen)
        elif active_settings_screen: active_settings_screen.draw(screen)
        elif settings_menu: settings_menu.draw(screen)
        elif about_screen: about_screen.draw(screen)
        elif main_menu: main_menu.draw(screen)
        else:
            screen.fill(theme.bg_color)
            lookup_icon_active = main_grid_active and active_pos == [0, 1]
            
            for r_idx, r in enumerate(fields):
                if r_idx == len(fields) - 1: continue
                for f_idx, f in enumerate(r):
                    if f:
                        if f.label == "lookup": continue

                        # 1. Draw labels and decorations
                        if f.label == get_string(lang, "freq"):
                            band_val = get_band_from_freq(f.value)
                            display_label = f"{f.label} [{band_val}]" if band_val and band_val != "N/A" else f.label
                            l_surf = small_font.render(display_label, True, theme.text_color)
                            screen.blit(l_surf, (f.rect.x, f.rect.y-14))
                        elif f.label == get_string(lang, "callsign"):
                            l_surf = small_font.render(f.label, True, theme.text_color)
                            screen.blit(l_surf, (f.rect.x, f.rect.y-14))
                            
                            lookup_icon_rect = pygame.Rect(f.rect.x + l_surf.get_width() + 5, f.rect.y - 14, 20, 14)
                            icon_color = theme.highlight_color if lookup_icon_active else theme.text_color
                            lookup_surf = small_font.render("󰍉", True, icon_color)
                            screen.blit(lookup_surf, lookup_icon_rect)
                            if lookup_icon_active:
                                pygame.draw.rect(screen, theme.highlight_color, lookup_icon_rect.inflate(4,4), 1, border_radius=3)

                            current_flag_surf = get_flag_surface(f.value, flag_sprite_sheet)
                            if current_flag_surf:
                                screen.blit(current_flag_surf, (lookup_icon_rect.right + 5, f.rect.y - 14))
                        else:
                            l_surf = small_font.render(f.label, True, theme.text_color)
                            screen.blit(l_surf, (f.rect.x, f.rect.y-14))

                        # 2. Draw field boxes and values
                        b_color = theme.highlight_color if f.active else theme.box_color
                        
                        final_color = theme.text_color
                        if f.label == get_string(lang, "callsign"):
                            if f.value and f.value.upper() in callsign_cache:
                                final_color = theme.dupe_color
                            elif f.value:
                                final_color = theme.typing_color
                        
                        v_surf = font.render(f.value, True, final_color)
                        pygame.draw.rect(screen, b_color, f.rect, 2, border_radius=3)
                        screen.blit(v_surf, (f.rect.x+5, f.rect.y+3))

            
            time_b_color = theme.highlight_color if not main_grid_active and bottom_focus==0 else theme.box_color
            auto_b_color = theme.highlight_color if not main_grid_active and bottom_focus==1 else theme.box_color
            menu_b_color = theme.highlight_color if not main_grid_active and bottom_focus==2 else theme.box_color
            pygame.draw.rect(screen, time_b_color, bottom_nav[0], 2, border_radius=3)
            pygame.draw.rect(screen, auto_b_color, bottom_nav[1], 2, border_radius=3)
            pygame.draw.rect(screen, menu_b_color, bottom_nav[2], 2, border_radius=3)
            time_str = qso_datetime.strftime("%Y-%m-%d %H:%M:%S UTC") if isinstance(qso_datetime, datetime) else "AUTO"
            time_surf = small_font.render(time_str, True, theme.text_color); screen.blit(time_surf, (bottom_nav[0].x+10, bottom_nav[0].centery - time_surf.get_height()//2))
            
            auto_icon_color = theme.highlight_color if is_auto_time else theme.text_color
            auto_surf = font.render("◷", True, auto_icon_color)
            screen.blit(auto_surf, (bottom_nav[1].centerx - auto_surf.get_width()//2, bottom_nav[1].centery - auto_surf.get_height()//2 - 2))
            
            menu_surf = font.render("≡", True, theme.text_color)
            screen.blit(menu_surf, (bottom_nav[2].centerx - menu_surf.get_width()//2, bottom_nav[2].centery - menu_surf.get_height()//2))

            if show_log_popup:
                popup_text = font.render(popup_message, True, theme.highlight_color)
                popup_width = max(200, popup_text.get_width() + 40)
                popup_rect = pygame.Rect((screen.get_width() - popup_width) // 2, 45, popup_width, 60)

                pygame.draw.rect(screen, theme.popup_bg_color, popup_rect, border_radius=5)
                pygame.draw.rect(screen, theme.popup_border_color, popup_rect, 2, border_radius=5)
                
                text_rect = popup_text.get_rect(center=popup_rect.center)
                screen.blit(popup_text, text_rect)
            
            if mode_selector: mode_selector.draw(screen)
            if time_editor: time_editor.draw(screen)

        pygame.display.flip()
        clock.tick(30)
    pygame.quit()

if __name__ == "__main__":
    main()
