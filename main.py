import argparse
import os
import select
import signal
import struct
import sys
import threading
import time
from datetime import datetime, timezone
from types import SimpleNamespace

parser = argparse.ArgumentParser(description="Ham Radio Logger")
parser.add_argument("--dev", action="store_true", help="Run in desktop window mode")
_PRE_ARGS, _ = parser.parse_known_args()

if not _PRE_ARGS.dev:
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from config_manager import (
    load_app_state,
    load_callsign_cache,
    load_user_config,
    save_app_state,
    save_user_config,
)
from export_utils import export_by_date_adif, export_today_adif
from font_util import CompositeFont
from language import get_string
from logger import ADIFLogger
from lookup_utils import lookup_callsign
from paths import app_path, data_path
from theme import Theme
from ui_components import (
    AdditionalInfoScreen,
    BandDistributionScreen,
    DateSelector,
    ExportSettingsScreen,
    LanguageSettingsScreen,
    LogSettingsScreen,
    LogViewer,
    LookupInfoScreen,
    LookupSettingsScreen,
    MainMenu,
    MainScreen,
    ModeSelector,
    ModeSettingsScreen,
    SettingsMenu,
    StatisticsMenu,
    ThemeSettingsScreen,
    TimeEditor,
)

W, H = 320, 170
ESC_HOLD_SECONDS = 3.0
ESC_OVERLAY_DELAY = 0.5
KBD_DEV = "/dev/input/by-path/platform-3f804000.i2c-event"

EV_KEY = 1
KEY_ESC = 1
KEY_LEFTSHIFT = 42
KEY_RIGHTSHIFT = 54
KEY_LEFTCTRL = 29
KEY_RIGHTCTRL = 97

EVDEV_MAP = {
    # Normal layer (linux,keymap)
    2: (pygame.K_1, "1", "1"),
    3: (pygame.K_2, "2", "2"),
    4: (pygame.K_3, "3", "3"),
    5: (pygame.K_4, "4", "4"),
    6: (pygame.K_5, "5", "5"),
    7: (pygame.K_6, "6", "6"),
    8: (pygame.K_7, "7", "7"),
    9: (pygame.K_8, "8", "8"),
    10: (pygame.K_9, "9", "9"),
    11: (pygame.K_0, "0", "0"),
    12: (pygame.K_MINUS, "-", "_"),
    13: (pygame.K_EQUALS, "=", "+"),
    14: (pygame.K_BACKSPACE, "", ""),
    15: (pygame.K_TAB, "", ""),
    16: (pygame.K_q, "q", "Q"),
    17: (pygame.K_w, "w", "W"),
    18: (pygame.K_e, "e", "E"),
    19: (pygame.K_r, "r", "R"),
    20: (pygame.K_t, "t", "T"),
    21: (pygame.K_y, "y", "Y"),
    22: (pygame.K_u, "u", "U"),
    23: (pygame.K_i, "i", "I"),
    24: (pygame.K_o, "o", "O"),
    25: (pygame.K_p, "p", "P"),
    28: (pygame.K_RETURN, "", ""),
    30: (pygame.K_a, "a", "A"),
    31: (pygame.K_s, "s", "S"),
    32: (pygame.K_d, "d", "D"),
    33: (pygame.K_f, "f", "F"),
    34: (pygame.K_g, "g", "G"),
    35: (pygame.K_h, "h", "H"),
    36: (pygame.K_j, "j", "J"),
    37: (pygame.K_k, "k", "K"),
    38: (pygame.K_l, "l", "L"),
    44: (pygame.K_z, "z", "Z"),
    45: (pygame.K_x, "x", "X"),
    46: (pygame.K_c, "c", "C"),
    47: (pygame.K_v, "v", "V"),
    48: (pygame.K_b, "b", "B"),
    49: (pygame.K_n, "n", "N"),
    50: (pygame.K_m, "m", "M"),
    57: (pygame.K_SPACE, " ", " "),
    # Sym layer (linux,keymap1 -> tca8418_keypad_m5stack_keymap.map)
    26: (pygame.K_EXCLAIM, "!", "!"),
    27: (pygame.K_AT, "@", "@"),
    39: (pygame.K_HASH, "#", "#"),
    40: (pygame.K_DOLLAR, "$", "$"),
    41: (pygame.K_PERCENT, "%", "%"),
    43: (pygame.K_CARET, "^", "^"),
    51: (pygame.K_AMPERSAND, "&", "&"),
    52: (pygame.K_ASTERISK, "*", "*"),
    53: (pygame.K_LEFTPAREN, "(", "("),
    94: (pygame.K_RIGHTPAREN, ")", ")"),
    55: (pygame.K_BACKQUOTE, "~", "~"),
    69: (pygame.K_BACKQUOTE, "`", "`"),
    70: (pygame.K_UNDERSCORE, "_", "_"),
    71: (pygame.K_MINUS, "-", "-"),
    72: (pygame.K_PLUS, "+", "+"),
    73: (pygame.K_EQUALS, "=", "="),
    74: (pygame.K_LEFTBRACKET, "[", "["),
    75: (pygame.K_RIGHTBRACKET, "]", "]"),
    76: (pygame.K_LEFTBRACKET, "{", "{"),
    77: (pygame.K_RIGHTBRACKET, "}", "}"),
    79: (pygame.K_SEMICOLON, ";", ";"),
    80: (pygame.K_COLON, ":", ":"),
    81: (pygame.K_QUOTE, "'", "'"),
    82: (pygame.K_QUOTEDBL, '"', '"'),
    83: (pygame.K_LESS, "<", "<"),
    85: (pygame.K_GREATER, ">", ">"),
    86: (pygame.K_BACKSLASH, "\\", "\\"),
    89: (pygame.K_BACKSLASH, "|", "|"),
    90: (pygame.K_COMMA, ",", ","),
    91: (pygame.K_PERIOD, ".", "."),
    92: (pygame.K_SLASH, "/", "/"),
    93: (pygame.K_QUESTION, "?", "?"),
    # Fn layer (linux,keymap2)
    59: (pygame.K_F1, "", ""),
    60: (pygame.K_F2, "", ""),
    61: (pygame.K_F3, "", ""),
    62: (pygame.K_F4, "", ""),
    63: (pygame.K_F5, "", ""),
    64: (pygame.K_F6, "", ""),
    65: (pygame.K_F7, "", ""),
    66: (pygame.K_F8, "", ""),
    67: (pygame.K_F9, "", ""),
    68: (pygame.K_F10, "", ""),
    87: (pygame.K_F11, "", ""),
    88: (pygame.K_F12, "", ""),
    99: (pygame.K_PRINT, "", ""),
    102: (pygame.K_HOME, "", ""),
    103: (pygame.K_UP, "", ""),
    104: (pygame.K_PAGEUP, "", ""),
    105: (pygame.K_LEFT, "", ""),
    106: (pygame.K_RIGHT, "", ""),
    107: (pygame.K_END, "", ""),
    108: (pygame.K_DOWN, "", ""),
    109: (pygame.K_PAGEDOWN, "", ""),
    110: (pygame.K_INSERT, "", ""),
    111: (pygame.K_DELETE, "", ""),
}


def main():
    dev_mode = _PRE_ARGS.dev

    pygame.init()
    screen = pygame.display.set_mode((W, H))
    clock = pygame.time.Clock()

    fb_fd = None
    fb_screen = None
    kbd_fds = []

    if not dev_mode:
        fb_screen = pygame.Surface((W, H), 0, 16, (0xF800, 0x07E0, 0x001F, 0))
        for fb_path in ("/dev/fb0", "/dev/fb1"):
            try:
                fb_fd = os.open(fb_path, os.O_RDWR)
                break
            except Exception:
                pass

        kbd_paths = (
            [KBD_DEV]
            if os.path.exists(KBD_DEV)
            else ["/dev/input/event0", "/dev/input/event1", "/dev/input/event2", "/dev/input/event3"]
        )
        for p in kbd_paths:
            if os.path.exists(p):
                try:
                    kbd_fds.append(os.open(p, os.O_RDONLY | os.O_NONBLOCK))
                except Exception:
                    pass

    os.makedirs(data_path("logs"), exist_ok=True)
    os.makedirs(data_path("config"), exist_ok=True)

    try:
        font = CompositeFont(
            app_path("fonts", "DejaVuSansNerdBold.ttf"),
            18,
            app_path("fonts", "卓特清雅体.ttf"),
            fallback_size=20,
        )
        small_font = CompositeFont(
            app_path("fonts", "DejaVuSansNerdBold.ttf"),
            14,
            app_path("fonts", "卓特清雅体.ttf"),
            fallback_size=16,
        )
    except pygame.error as e:
        print(f"Warnung: Schriftart konnte nicht geladen werden ({e}).")
        font, small_font = pygame.font.Font(None, 24), pygame.font.Font(None, 18)

    user_config = load_user_config()
    theme = Theme(user_config)
    app_state = load_app_state()
    callsign_cache = load_callsign_cache(user_config["logfile"])
    lang = user_config.get("language", "en")

    try:
        flag_sprite_sheet = pygame.image.load(app_path("assets", "flags16.png")).convert_alpha()
    except (pygame.error, FileNotFoundError):
        print("Warning: flags16.png not found. Flag feature disabled.")
        flag_sprite_sheet = None

    show_log_popup, popup_end_time, popup_message = False, 0.0, ""
    (
        time_editor,
        mode_selector,
        settings_menu,
        active_settings_screen,
        about_screen,
        main_menu,
        log_viewer,
        date_selector,
        statistics_menu,
        band_distribution_screen,
        lookup_screen,
    ) = (None,) * 11
    lookup_data_cache = {}
    lookup_thread, lookup_result = None, None
    lookup_active = False
    pending_qso_data = None

    def show_popup(message, duration=2.0):
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
        show_popup(get_string(lang, "fetching_info"), duration=10.0)

        def lookup_worker():
            nonlocal lookup_result, lookup_active
            try:
                provider = user_config.get("lookup_provider", "hamdb")
                username = user_config.get("qrz_username", "")
                password = user_config.get("qrz_password", "")
                lookup_result = lookup_callsign(callsign, provider, username, password)
            finally:
                lookup_active = False

        lookup_thread = threading.Thread(target=lookup_worker, daemon=True)
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
        if extra_data.get("name"):
            log_kwargs["NAME"] = extra_data.get("name")
        if extra_data.get("addr2"):
            log_kwargs["QTH"] = extra_data.get("addr2")
        if extra_data.get("grid"):
            log_kwargs["GRIDSQUARE"] = extra_data.get("grid")

        logger.log_qso(
            call.upper(),
            qso_data["rst_s"],
            qso_data["rst_r"],
            qso_data["band"],
            qso_data["mode"],
            freq=qso_data["freq"],
            qso_datetime=qso_data["qso_datetime"],
            my_sota_ref=qso_data["my_sota"],
            sota_ref=qso_data["sota_ref"],
            my_pota_ref=qso_data["my_pota"],
            pota_ref=qso_data["pota_ref"],
            stx_string=qso_data["stx_str"],
            srx_string=qso_data["srx_str"],
            **log_kwargs,
        )
        callsign_cache.add(call.upper())
        main_screen.callsign_cache = callsign_cache

        stx_str = qso_data["stx_str"]
        if user_config.get("contest_mode", "0") == "1" and stx_str.isdigit():
            stx_str = str(int(stx_str) + 1).zfill(max(3, len(stx_str)))
            main_screen.fields[2][0].value = stx_str
            main_screen.fields[2][1].value = ""

        save_app_state(
            qso_data["freq"],
            qso_data["mode"],
            qso_data["my_sota"],
            qso_data["sota_ref"],
            qso_data["my_pota"],
            qso_data["pota_ref"],
            stx_str,
            qso_data["srx_str"],
        )
        app_state.update(
            {
                "freq": qso_data["freq"],
                "mode": qso_data["mode"],
                "my_sota": qso_data["my_sota"],
                "sota_ref": qso_data["sota_ref"],
                "my_pota": qso_data["my_pota"],
                "pota_ref": qso_data["pota_ref"],
                "stx_string": stx_str,
                "srx_string": qso_data["srx_str"],
            }
        )
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

    main_screen = MainScreen(
        font,
        small_font,
        theme,
        user_config,
        lang,
        app_state,
        flag_sprite_sheet,
        start_lookup,
        log_qso_and_reset,
        open_mode_selector,
        open_menu,
        open_time_editor,
    )
    main_screen.callsign_cache = callsign_cache

    def has_active_subscreen():
        return any(
            (
                lookup_screen,
                band_distribution_screen,
                statistics_menu,
                log_viewer,
                date_selector,
                active_settings_screen,
                settings_menu,
                about_screen,
                main_menu,
                time_editor,
                mode_selector,
            )
        )

    def handle_keydown(event):
        nonlocal running, show_log_popup, lookup_screen, band_distribution_screen, statistics_menu, log_viewer, date_selector, active_settings_screen, settings_menu, about_screen, main_menu, time_editor, mode_selector, user_config, theme, lang

        if event.key == pygame.K_F12:
            shot_dir = data_path("screenshots")
            os.makedirs(shot_dir, exist_ok=True)
            idx = 1
            while os.path.exists(os.path.join(shot_dir, f"{idx}.png")):
                idx += 1
            pygame.image.save(screen, os.path.join(shot_dir, f"{idx}.png"))
            show_popup(f"Saved: {idx}.png", duration=2.0)
            return

        if lookup_screen:
            res = lookup_screen.handle_event(event)
            if res != "active":
                if isinstance(res, dict) and res.get("action") == "close" and res.get("data"):
                    lookup_data_cache[lookup_screen.callsign] = res["data"]
                lookup_screen = None
            return
        if band_distribution_screen:
            if band_distribution_screen.handle_event(event) == "close":
                band_distribution_screen = None
            return
        if statistics_menu:
            res = statistics_menu.handle_event(event)
            if res == "close":
                statistics_menu = None
            elif res == "band_distribution":
                band_distribution_screen = BandDistributionScreen(
                    user_config["logfile"], font, small_font, theme, lang
                )
                statistics_menu = None
            return
        if log_viewer:
            if log_viewer.handle_event(event) == "close":
                if getattr(log_viewer, "log_changed", False):
                    callsign_cache = load_callsign_cache(user_config["logfile"])
                    main_screen.callsign_cache = callsign_cache
                log_viewer = None
            return
        if date_selector:
            res = date_selector.handle_event(event)
            if res != "active":
                if res:
                    filename, message = export_by_date_adif(user_config["logfile"], res)
                    show_popup(message)
                date_selector = None
                active_settings_screen = None
            return
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
            return
        if settings_menu:
            res = settings_menu.handle_event(event)
            if res == "close":
                settings_menu = None
            elif res == "log_settings":
                active_settings_screen = LogSettingsScreen(user_config, font, small_font, theme)
            elif res == "lookup_settings":
                active_settings_screen = LookupSettingsScreen(user_config, font, small_font, theme)
            elif res == "mode_settings":
                active_settings_screen = ModeSettingsScreen(user_config, font, small_font, theme)
            elif res == "theme_settings":
                active_settings_screen = ThemeSettingsScreen(user_config, font, small_font, theme)
            elif res == "language_settings":
                active_settings_screen = LanguageSettingsScreen(
                    user_config, font, small_font, flag_sprite_sheet, theme
                )
            return
        if about_screen:
            if about_screen.handle_event(event) == "close":
                about_screen = None
            return
        if main_menu:
            res = main_menu.handle_event(event)
            if res == "close":
                main_menu = None
            elif res == "settings":
                settings_menu = SettingsMenu(font, small_font, lang, flag_sprite_sheet, theme)
                main_menu = None
            elif res == "view_log":
                log_viewer = LogViewer(
                    user_config["logfile"], font, small_font, theme, flag_sprite_sheet, lang
                )
                main_menu = None
            elif res == "about":
                about_screen = AdditionalInfoScreen(font, small_font, theme, lang)
                main_menu = None
            elif res == "export_settings":
                active_settings_screen = ExportSettingsScreen(user_config, font, small_font, theme)
                main_menu = None
            elif res == "statistics":
                statistics_menu = StatisticsMenu(font, small_font, theme, lang)
                main_menu = None
            return
        if time_editor:
            res = time_editor.handle_event(event)
            if res != "active":
                if res:
                    main_screen.qso_datetime = res
                    main_screen.is_auto_time = False
                time_editor = None
            return
        if mode_selector:
            res = mode_selector.handle_event(event)
            if res != "active":
                if res:
                    main_screen.fields[1][2].value = res
                mode_selector = None
            return

        if show_log_popup and time.time() > popup_end_time:
            show_log_popup = False
        if show_log_popup:
            return

        if event.key == pygame.K_ESCAPE:
            show_popup(f"Hold ESC {int(ESC_HOLD_SECONDS)}s to exit", duration=1.5)
        else:
            main_screen.handle_event(event)

    running = True
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    signal.signal(signal.SIGINT, lambda *_: sys.exit(0))

    esc_down_at = None
    shift_held = False
    ctrl_held = False

    try:
        while running:
            now = time.time()

            if main_screen.is_auto_time and not isinstance(main_screen.qso_datetime, str):
                main_screen.qso_datetime = datetime.now(timezone.utc)

            if lookup_thread and not lookup_active:
                lookup_thread.join()
                lookup_thread = None

                callsign_key = (
                    pending_qso_data["call"].upper()
                    if pending_qso_data
                    else main_screen.fields[0][0].value.upper()
                )

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
                    lookup_screen = LookupInfoScreen(
                        font, small_font, theme, callsign_key, lookup_result, lang
                    )

                lookup_result = None

            if show_log_popup and now > popup_end_time:
                show_log_popup = False

            # Poll raw evdev keyboard in hardware mode
            if kbd_fds:
                r, _, _ = select.select(kbd_fds, [], [], 0.0)
                for fd in r:
                    while True:
                        try:
                            data = os.read(fd, 24)
                            if len(data) < 24:
                                break
                            _, _, ev_type, code, value = struct.unpack("llHHi", data)
                            if ev_type != EV_KEY:
                                continue
                            if code in (KEY_LEFTSHIFT, KEY_RIGHTSHIFT):
                                shift_held = value != 0
                            elif code in (KEY_LEFTCTRL, KEY_RIGHTCTRL):
                                ctrl_held = value != 0
                            elif code == KEY_ESC:
                                if value == 1:
                                    if has_active_subscreen():
                                        esc_down_at = None
                                        handle_keydown(
                                            SimpleNamespace(
                                                type=pygame.KEYDOWN,
                                                key=pygame.K_ESCAPE,
                                                unicode="",
                                                mod=0,
                                            )
                                        )
                                    else:
                                        esc_down_at = now
                                elif value == 0:
                                    if esc_down_at is not None and (now - esc_down_at) < ESC_OVERLAY_DELAY:
                                        handle_keydown(
                                            SimpleNamespace(
                                                type=pygame.KEYDOWN,
                                                key=pygame.K_ESCAPE,
                                                unicode="",
                                                mod=0,
                                            )
                                        )
                                    esc_down_at = None
                            elif value in (1, 2) and code in EVDEV_MAP:
                                pg_key, normal_ch, shift_ch = EVDEV_MAP[code]
                                ch = shift_ch if shift_held else normal_ch
                                mod = (pygame.KMOD_SHIFT if shift_held else 0) | (
                                    pygame.KMOD_CTRL if ctrl_held else 0
                                )
                                handle_keydown(
                                    SimpleNamespace(
                                        type=pygame.KEYDOWN,
                                        key=pg_key,
                                        unicode=ch,
                                        mod=mod,
                                    )
                                )
                        except BlockingIOError:
                            break
                        except Exception:
                            break

            # Poll pygame events (desktop --dev mode + QUIT)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        if has_active_subscreen():
                            esc_down_at = None
                            handle_keydown(event)
                        elif esc_down_at is None:
                            esc_down_at = now
                    else:
                        handle_keydown(event)
                elif event.type == pygame.KEYUP:
                    if event.key == pygame.K_ESCAPE:
                        if esc_down_at is not None and (now - esc_down_at) < ESC_OVERLAY_DELAY:
                            handle_keydown(
                                SimpleNamespace(
                                    type=pygame.KEYDOWN,
                                    key=pygame.K_ESCAPE,
                                    unicode="",
                                    mod=0,
                                )
                            )
                        esc_down_at = None

            if esc_down_at is not None and (now - esc_down_at) >= ESC_HOLD_SECONDS:
                running = False
                break

            if lookup_screen:
                lookup_screen.draw(screen)
            elif band_distribution_screen:
                band_distribution_screen.draw(screen)
            elif statistics_menu:
                statistics_menu.draw(screen)
            elif log_viewer:
                log_viewer.draw(screen)
            elif date_selector:
                date_selector.draw(screen)
            elif active_settings_screen:
                active_settings_screen.draw(screen)
            elif settings_menu:
                settings_menu.draw(screen)
            elif about_screen:
                about_screen.draw(screen)
            elif main_menu:
                main_menu.draw(screen)
            else:
                main_screen.draw(screen)

                if show_log_popup:
                    popup_text = font.render(popup_message, True, theme.highlight_color)
                    popup_width = max(200, popup_text.get_width() + 40)
                    popup_rect = pygame.Rect(
                        (screen.get_width() - popup_width) // 2, 45, popup_width, 60
                    )
                    pygame.draw.rect(screen, theme.popup_bg_color, popup_rect, border_radius=5)
                    pygame.draw.rect(
                        screen, theme.popup_border_color, popup_rect, 2, border_radius=5
                    )
                    text_rect = popup_text.get_rect(center=popup_rect.center)
                    screen.blit(popup_text, text_rect)

                if mode_selector:
                    mode_selector.draw(screen)
                if time_editor:
                    time_editor.draw(screen)

            # 3-second ESC hold exit overlay
            if esc_down_at is not None and (now - esc_down_at) >= ESC_OVERLAY_DELAY:
                elapsed = min(ESC_HOLD_SECONDS, now - esc_down_at)
                pct = elapsed / ESC_HOLD_SECONDS
                rem = max(0.0, ESC_HOLD_SECONDS - elapsed)
                overlay_rect = pygame.Rect(45, 62, 230, 46)
                pygame.draw.rect(screen, theme.popup_bg_color, overlay_rect, border_radius=6)
                pygame.draw.rect(screen, (255, 82, 82), overlay_rect, 2, border_radius=6)
                lbl = small_font.render(f"HOLD ESC TO EXIT... {rem:.1f}s", True, theme.text_color)
                screen.blit(lbl, (W // 2 - lbl.get_width() // 2, 70))
                pygame.draw.rect(screen, theme.bg_color, (60, 90, 200, 8), border_radius=4)
                pygame.draw.rect(screen, (255, 82, 82), (60, 90, int(200 * pct), 8), border_radius=4)

            if fb_fd is not None and fb_screen is not None:
                fb_screen.blit(screen, (0, 0))
                os.lseek(fb_fd, 0, os.SEEK_SET)
                os.write(fb_fd, bytes(fb_screen.get_buffer()))
            else:
                pygame.display.flip()

            clock.tick(30)
    finally:
        for fd in kbd_fds:
            try:
                os.close(fd)
            except Exception:
                pass
        if fb_fd is not None:
            try:
                os.close(fb_fd)
            except Exception:
                pass
        pygame.quit()


if __name__ == "__main__":
    main()
