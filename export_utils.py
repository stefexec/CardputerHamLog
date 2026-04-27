from datetime import datetime, timezone
import os
from language import get_string
from config_manager import load_user_config

def export_today_adif(log_file, lang="en"):
    return export_by_date_adif(log_file, datetime.now(timezone.utc), lang)

def export_by_date_adif(log_file, export_date, lang="en"):
    if not os.path.exists(log_file):
        return None, "Log file not found."

    date_str = export_date.strftime('%Y%m%d')
    
    user_config = load_user_config()
    callsign = user_config.get("station_callsign", "NOCALL")

    suggested_filename = os.path.join("logs", f"{callsign}-{export_date.strftime('%Y-%m-%d')}.adi")

    header = (
        "ADIF from CardputerHamLog\n"
        "<adif_ver:5>3.1.0\n"
        "<programid:15>CardputerHamLog\n"
        "<programversion:5>0.1.0\n"
        f"<eoh>\n\n"
    )
    
    body_lines = []
    with open(log_file, 'r') as f:
        for line in f:
            if f"<QSO_DATE:8>{date_str}" in line:
                body_lines.append(line)

    if not body_lines:
        return None, f"No QSOs on {export_date.strftime('%Y-%m-%d')}."

    os.makedirs(os.path.dirname(suggested_filename), exist_ok=True)
    with open(suggested_filename, 'w') as f:
        f.write(header)
        f.writelines(body_lines)
        
    return suggested_filename, f"Exported {len(body_lines)} QSOs."
