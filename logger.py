import os
from datetime import datetime, timezone

# --- ADIF Logger Klasse ---
class ADIFLogger:
    def __init__(self, user_config):
        self.filename = user_config.get("logfile", "adif_export.adi")
        self.station_callsign = user_config.get("station_callsign", "")
        self.my_gridsquare = user_config.get("my_gridsquare", "")
        self.tx_pwr = user_config.get("tx_pwr", "")
        self.itu_zone = user_config.get("itu_zone", "")
        self.cq_zone = user_config.get("cq_zone", "")
        self.sota_mode = user_config.get("sota_mode", "0")
        self.pota_mode = user_config.get("pota_mode", "0")
        self.contest_mode = user_config.get("contest_mode", "0")
        self._ensure_header()

    def _ensure_header(self):
        if not os.path.exists(self.filename):
            with open(self.filename, 'w') as f:
                f.write(f"Cardputer Zero Ham Log - Station {self.station_callsign}\n")
                f.write("<EOH>\n")

    def sort_log_file(self):
        with open(self.filename, 'r') as f:
            lines = f.readlines()

        header = []
        records = []
        in_header = True
        for line in lines:
            if in_header:
                header.append(line)
                if "<EOH>" in line:
                    in_header = False
            elif line.strip(): # ignore empty lines
                records.append(line)

        def get_qso_datetime(record_line):
            date_str = ""
            time_str = ""

            # --- QSO_DATE ---
            tag = "<QSO_DATE:"
            start_idx = record_line.find(tag)
            if start_idx != -1:
                len_start = start_idx + len(tag)
                len_end = record_line.find(">", len_start)
                if len_end != -1:
                    try:
                        length = int(record_line[len_start:len_end])
                        val_start = len_end + 1
                        date_str = record_line[val_start : val_start + length]
                    except (ValueError, IndexError):
                        pass # Malformed tag

            # --- TIME_ON ---
            tag = "<TIME_ON:"
            start_idx = record_line.find(tag)
            if start_idx != -1:
                len_start = start_idx + len(tag)
                len_end = record_line.find(">", len_start)
                if len_end != -1:
                    try:
                        length = int(record_line[len_start:len_end])
                        val_start = len_end + 1
                        time_str = record_line[val_start : val_start + length]
                    except (ValueError, IndexError):
                        pass # Malformed tag

            if date_str and time_str:
                try:
                    if len(time_str) == 4:
                        return datetime.strptime(date_str + time_str, "%Y%m%d%H%M")
                    elif len(time_str) == 6:
                        return datetime.strptime(date_str + time_str, "%Y%m%d%H%M%S")
                except ValueError:
                    return datetime.min # Parsing failed for date/time format
            
            return datetime.min # One of the tags was not found

        sorted_records = sorted(records, key=get_qso_datetime)

        with open(self.filename, 'w') as f:
            f.writelines(header)
            f.writelines(sorted_records)

    def log_qso(self, call, rst_s, rst_r, band, mode, freq="", qso_datetime=None, my_sota_ref="", sota_ref="", my_pota_ref="", pota_ref="", stx_string="", srx_string="", **kwargs):
        if qso_datetime is None: qso_datetime = datetime.now(timezone.utc)
        date_str, time_str = qso_datetime.strftime("%Y%m%d"), qso_datetime.strftime("%H%M")
        
        adif_record = (
            f"<CALL:{len(call)}>{call} "
            f"<RST_SENT:{len(rst_s)}>{rst_s} "
            f"<RST_RCVD:{len(rst_r)}>{rst_r} "
            f"<QSO_DATE:8>{date_str} "
            f"<TIME_ON:4>{time_str} "
            f"<BAND:{len(band)}>{band} "
            f"<MODE:{len(mode)}>{mode} "
        )
        if freq: 
            freq_formatted = freq.replace(',', '.')
            adif_record += f"<FREQ:{len(freq_formatted)}>{freq_formatted} "
        if self.station_callsign:
            adif_record += f"<STATION_CALLSIGN:{len(self.station_callsign)}>{self.station_callsign} "
        if self.my_gridsquare:
            adif_record += f"<MY_GRIDSQUARE:{len(self.my_gridsquare)}>{self.my_gridsquare} "
        if self.tx_pwr:
            adif_record += f"<TX_PWR:{len(self.tx_pwr)}>{self.tx_pwr} "
        if self.itu_zone:
            adif_record += f"<MY_ITU_ZONE:{len(self.itu_zone)}>{self.itu_zone} "
        if self.cq_zone:
            adif_record += f"<MY_CQ_ZONE:{len(self.cq_zone)}>{self.cq_zone} "
            
        if self.sota_mode == "1":
            if my_sota_ref:
                adif_record += f"<MY_SOTA_REF:{len(my_sota_ref)}>{my_sota_ref} "
            if sota_ref:
                adif_record += f"<SOTA_REF:{len(sota_ref)}>{sota_ref} "
        elif self.pota_mode == "1":
            if my_pota_ref:
                adif_record += f"<MY_POTA_REF:{len(my_pota_ref)}>{my_pota_ref} "
            if pota_ref:
                adif_record += f"<POTA_REF:{len(pota_ref)}>{pota_ref} "
            # P2P tag is useful for some tools even if implied by both refs
            if my_pota_ref and pota_ref:
                adif_record += f"<P2P:3>YES "
        elif self.contest_mode == "1":
            if stx_string:
                # If numeric, log as STX, else STX_STRING
                if stx_string.isdigit():
                    adif_record += f"<STX:{len(stx_string)}>{stx_string} "
                else:
                    adif_record += f"<STX_STRING:{len(stx_string)}>{stx_string} "
            if srx_string:
                # If numeric, log as SRX, else SRX_STRING
                if srx_string.isdigit():
                    adif_record += f"<SRX:{len(srx_string)}>{srx_string} "
                else:
                    adif_record += f"<SRX_STRING:{len(srx_string)}>{srx_string} "

        for k, v in kwargs.items():
            if v:
                v_str = str(v)
                adif_record += f"<{k}:{len(v_str)}>{v_str} "

        adif_record += "<EOR>\n"

        with open(self.filename, 'a') as f: f.write(adif_record)
        self.sort_log_file() # This was causing the overwrite issue
        print(f"[+] Logged: {call} on {band} ({freq} MHz) at {date_str} {time_str}")

# --- Hilfsfunktionen ---
def get_band_from_freq(freq_str):
    try:
        f = float(freq_str.replace(',', '.'))
        if 1.8 <= f <= 2.0: return "160m"
        if 3.5 <= f <= 3.8: return "80m"
        if 7.0 <= f <= 7.2: return "40m"
        if 10.1 <= f <= 10.15: return "30m"
        if 14.0 <= f <= 14.35: return "20m"
        if 18.068 <= f <= 18.168: return "17m"
        if 21.0 <= f <= 21.45: return "15m"
        if 24.89 <= f <= 24.99: return "12m"
        if 28.0 <= f <= 29.7: return "10m"
        if 50 <= f <= 54: return "6m"
        if 144 <= f <= 148: return "2m"
        if 430 <= f <= 440: return "70cm"
        return "N/A"
    except (ValueError, TypeError): return "N/A"
