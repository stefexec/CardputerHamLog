import argparse
import pygame
from datetime import datetime, timezone
import time
import os
from config_manager import load_app_state, save_app_state, load_user_config, save_user_config, load_callsign_cache
from logger import ADIFLogger
from ui_components import MainScreen, TimeEditor, ModeSelector, SettingsMenu, LogSettingsScreen, ModeSettingsScreen, ThemeSettingsScreen, LanguageSettingsScreen, ExportSettingsScreen, AdditionalInfoScreen, MainMenu, LogViewer, DateSelector, StatisticsMenu, BandDistributionScreen, LookupInfoScreen, LookupSettingsScreen
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
        primary_size_normal = 18
        cjk_size_normal = 20
        primary_size_small = 14
        cjk_size_small = 16
        
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

    def start_lookup(callsign, clear_only=False):
        nonlocal lookup_thread, lookup_result, lookup_active, lookup_data_cache
        if clear_only:
            if callsign.upper() in lookup_data_cache:
                del lookup_data_cache[callsign.upper()]
            return

        if lookup_active:
            return
        
        lookup_result = None
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
        nonlocal callsign_cache, main_screen, pending_qso_data
        
        call = qso_data["call"]
        if user_config.get("lookup_auto", "0") == "1" and call.upper() not in lookup_data_cache:
            pending_qso_data = qso_data
            start_lookup(call.upper())
            return
            
        logger = ADIFLogger(user_config)
        
        extra_data = lookup_data_cache.get(call.upper()) or {}
        if not isinstance(extra_data, dict):
            extra_data = {}

        log_kwargs = {}
        if extra_data.get('name'): log_kwargs['NAME'] = extra_data.get('name')
        if extra_data.get('addr2'): log_kwargs['QTH'] = extra_data.get('addr2')
        if extra_data.get('grid'): log_kwargs['GRIDSQUARE'] = extra_data.get('grid')

        logger.log_qso(
            call.upper(), qso_data["rst_s"], qso_data["rst_r"], qso_data["band"], qso_data["mode"], 
            freq=qso_data["freq"], qso_datetime=qso_data["qso_datetime"], 
            my_sota_ref=qso_data["my_sota"], sota_ref=qso_data["sota_ref"], 
            my_pota_ref=qso_data["my_pota"], pota_ref=qso_data["pota_ref"], 
            stx_string=qso_data["stx_str"], srx_string=qso_data["srx_str"], 
            **log_kwargs
        )
        callsign_cache.add(call.upper())
        main_screen.callsign_cache = callsign_cache
        
        stx_str = qso_data["stx_str"]
        if user_config.get("contest_mode", "0") == "1" and stx_str.isdigit():
            stx_str = str(int(stx_str) + 1).zfill(max(3, len(stx_str)))
            main_screen.fields[2][0].value = stx_str
            main_screen.fields[2][1].value = ""
            
        save_app_state(qso_data["freq"], qso_data["mode"], qso_data["my_sota"], qso_data["sota_ref"], qso_data["my_pota"], qso_data["pota_ref"], stx_str, qso_data["srx_str"])
        app_state.update({"freq": qso_data["freq"], "mode": qso_data["mode"], "my_sota": qso_data["my_sota"], "sota_ref": qso_data["sota_ref"], "my_pota": qso_data["my_pota"], "pota_ref": qso_data["pota_ref"], "stx_string": stx_str, "srx_string": qso_data["srx_str"]})
        main_screen.fields[0][0].value = ""
        if call.upper() in lookup_data_cache:
            del lookup_data_cache[call.upper()]
            
        show_popup(get_string(lang, "qso_logged"))

    def open_mode_selector():
        nonlocal mode_selector
        mode_selector = ModeSelector(font, small_font, theme)

    def open_menu():
        nonlocal main_menu
        main_menu = MainMenu(font, small_font, theme, lang)
        
    def open_time_editor():
        nonlocal time_editor
        time_editor = TimeEditor(main_screen.qso_datetime, font, small_font, theme)

    main_screen = MainScreen(font, small_font, theme, user_config, lang, app_state, flag_sprite_sheet, start_lookup, log_qso_and_reset, open_mode_selector, open_menu, open_time_editor)
    main_screen.callsign_cache = callsign_cache

    running = True
    while running:
        if main_screen.is_auto_time and not isinstance(main_screen.qso_datetime, str): 
            main_screen.qso_datetime = datetime.now(timezone.utc)
            
        if lookup_thread and not lookup_active:
            lookup_thread.join()
            lookup_thread = None
            
            callsign_key = pending_qso_data["call"].upper() if pending_qso_data else main_screen.fields[0][0].value.upper()
            
            if lookup_result is None:
                if callsign_key in lookup_data_cache:
                    del lookup_data_cache[callsign_key]
            else:
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
                        theme = Theme(user_config)
                        main_screen.theme = theme
                        active_settings_screen = None
                        
                        lang = user_config.get("language", "en")
                        main_screen.lang = lang
                        main_screen.user_config = user_config
                        main_screen.update_fields()
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
                        if res: 
                            main_screen.qso_datetime = res
                            main_screen.is_auto_time = False
                        time_editor = None
                    continue
                if mode_selector:
                    res = mode_selector.handle_event(event)
                    if res != "active":
                        if res: main_screen.fields[1][2].value = res
                        mode_selector = None
                    continue
                    
                if show_log_popup and time.time() > popup_end_time: show_log_popup = False
                if show_log_popup: continue
                
                if event.key == pygame.K_ESCAPE: running = False
                else:
                    main_screen.handle_event(event)
        
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
            main_screen.draw(screen)

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