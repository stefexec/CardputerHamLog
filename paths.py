import os

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.expanduser("~/hamlog")


def app_path(*parts):
    return os.path.join(APP_DIR, *parts)


def data_path(*parts):
    return os.path.join(DATA_DIR, *parts)


def resolve_data_path(path_str):
    if not path_str:
        return data_path("logs", "hamputer_adif_log.adi")
    if os.path.isabs(path_str):
        return path_str
    clean = path_str[2:] if path_str.startswith("./") else path_str
    return os.path.join(DATA_DIR, clean)
