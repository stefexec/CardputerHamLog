import os
from encryption_utils import encrypt_password, decrypt_password, generate_key, KEY_FILE

USER_CONFIG_FILE = "./config/config.txt"
APP_STATE_FILE = "./config/session.gurk"

def save_app_state(freq, mode, my_sota="", sota_ref="", my_pota="", pota_ref="", stx_string="", srx_string=""):
    os.makedirs(os.path.dirname(APP_STATE_FILE), exist_ok=True)
    with open(APP_STATE_FILE, 'w') as f:
        f.write(f"freq={freq}\nmode={mode}\nmy_sota={my_sota}\nsota_ref={sota_ref}\nmy_pota={my_pota}\npota_ref={pota_ref}\nstx_string={stx_string}\nsrx_string={srx_string}\n")

def load_app_state():
    defaults = {"freq": "145.500", "mode": "FM", "my_sota": "", "sota_ref": "", "my_pota": "", "pota_ref": "", "stx_string": "001", "srx_string": ""}
    if not os.path.exists(APP_STATE_FILE): return defaults
    config = {}
    with open(APP_STATE_FILE, 'r') as f:
        for line in f:
            if '=' in line: key, value = line.strip().split('=', 1); config[key] = value
    for k in defaults:
        if k not in config: config[k] = defaults[k]
    return config

_USER_CONFIG_DEFAULTS = {
    "station_callsign": "NOCALL",
    "logfile": "./logs/hamputer_adif_log.adi",
    "my_gridsquare": "",
    "tx_pwr": "",
    "itu_zone": "",
    "cq_zone": "",
    "sota_mode": "0",
    "pota_mode": "0",
    "contest_mode": "0",
    "language": "en",
    "lookup_provider": "hamdb",
    "qrz_username": "",
    "qrz_password": "",
    "lookup_auto": "0",
    "theme_bg": "20,20,30",
    "theme_text": "200,200,200",
    "theme_highlight": "100,255,100",
    "theme_typing": "255,165,0",
    "theme_dupe": "100,255,100",
    "theme_popup_bg": "40,40,60",
    "theme_popup_border": "150,150,170",
    "theme_separator": "60,60,70",
    "theme_detail_bg": "30,30,40",
    "theme_scrollbar_track": "40,40,60",
    "theme_scrollbar_handle": "80,80,100",
    "theme_log_header": "180,180,180",
}

def save_user_config(config):
    if not os.path.exists(KEY_FILE):
        generate_key()
    
    os.makedirs(os.path.dirname(USER_CONFIG_FILE), exist_ok=True)
    with open(USER_CONFIG_FILE, 'w') as f:
        for key in _USER_CONFIG_DEFAULTS:
            value = config.get(key, _USER_CONFIG_DEFAULTS[key])
            if key == 'qrz_password' and value:
                value = encrypt_password(value)
            f.write(f"{key}={value}\n")

def load_user_config():
    if not os.path.exists(USER_CONFIG_FILE):
        return dict(_USER_CONFIG_DEFAULTS)

    config = dict(_USER_CONFIG_DEFAULTS)
    with open(USER_CONFIG_FILE, 'r') as f:
        for line in f:
            if '=' in line:
                key, value = line.strip().split('=', 1)
                if key in config:
                    if key == 'qrz_password' and value:
                        try:
                            value = decrypt_password(value)
                        except Exception:
                            # handle case where password is not encrypted
                            pass
                    config[key] = value
    for key, value in config.items():
        if key.startswith("theme_") and not isinstance(value, str):
            config[key] = ",".join(map(str, value))
    return config

def load_callsign_cache(log_file):
    cache = set()
    if not os.path.exists(log_file): return cache
    with open(log_file, 'r') as f:
        for line in f:
            if "<CALL:" in line:
                try:
                    call = line.split("<CALL:")[1].split(">")[1].split(" ")[0]
                    cache.add(call.upper())
                except IndexError:
                    continue
    return cache
