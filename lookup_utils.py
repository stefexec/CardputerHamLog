import urllib.request
import json
import xml.etree.ElementTree as ET

def lookup_callsign_hamdb(callsign):
    """
    Looks up a callsign using the hamdb.org API.
    Returns a dictionary with the callsign data or None on failure.
    """
    if not callsign:
        return None
    
    url = f"https://api.hamdb.org/v1/{callsign}/json/cardputerhamlog"
    
    try:
        req = urllib.request.Request(
            url, 
            headers={'User-Agent': 'CardputerHamLog/0.1 (https://github.com/DN9GRK/CardputerHamLog)'}
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status == 200:
                data = json.loads(response.read().decode('utf-8'))
                if data.get("hamdb", {}).get("messages", {}).get("status") == "OK":
                    return data["hamdb"]["callsign"]
    except Exception as e:
        print(f"Error looking up callsign {callsign} on hamdb.org: {e}")

    return None

def _get_qrz_session_key(username, password):
    """
    Authenticates with QRZ.com and returns a session key.
    """
    if not username or not password:
        return None, "Username or password not provided"

    url = f"https://xmldata.qrz.com/xml/current/?username={username};password={password}"
    try:
        req = urllib.request.Request(
            url,
            headers={'User-Agent': 'CardputerHamLog/0.1 (https://github.com/DN9GRK/CardputerHamLog)'}
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status == 200:
                xml_data = response.read().decode('utf-8')
                root = ET.fromstring(xml_data)
                session_node = root.find('{http://xmldata.qrz.com}Session')
                if session_node is not None:
                    key = session_node.findtext('{http://xmldata.qrz.com}Key')
                    if key:
                        return key, None
                    else:
                        error = session_node.findtext('{http://xmldata.qrz.com}Error')
                        return None, error or "Unknown authentication error"
    except Exception as e:
        return None, str(e)
    
    return None, "Failed to connect to QRZ.com"

def lookup_callsign_qrz(callsign, username, password):
    """
    Looks up a callsign using the QRZ.com API.
    Returns a dictionary with the callsign data or None on failure.
    """
    if not callsign:
        return None

    session_key, error = _get_qrz_session_key(username, password)
    
    if error:
        print(f"QRZ.com Auth Error: {error}")
        return None
    
    if not session_key:
        return None

    url = f"https://xmldata.qrz.com/xml/current/?s={session_key};callsign={callsign}"

    try:
        req = urllib.request.Request(
            url,
            headers={'User-Agent': 'CardputerHamLog/0.1 (https://github.com/DN9GRK/CardputerHamLog)'}
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status == 200:
                xml_data = response.read().decode('utf-8')
                root = ET.fromstring(xml_data)
                
                session_node = root.find('{http://xmldata.qrz.com}Session')
                if session_node is not None:
                    error = session_node.findtext('{http://xmldata.qrz.com}Error')
                    if error:
                        print(f"QRZ.com API Error: {error}")
                        return None

                callsign_node = root.find('{http://xmldata.qrz.com}Callsign')
                if callsign_node is not None:
                    return {
                        "call": callsign_node.findtext('{http://xmldata.qrz.com}call'),
                        "name": callsign_node.findtext('{http://xmldata.qrz.com}fname'),
                        "addr1": callsign_node.findtext('{http://xmldata.qrz.com}addr1'),
                        "addr2": callsign_node.findtext('{http://xmldata.qrz.com}addr2'),
                        "country": callsign_node.findtext('{http://xmldata.qrz.com}country'),
                        "grid": callsign_node.findtext('{http://xmldata.qrz.com}grid'),
                    }
    except Exception as e:
        print(f"Error looking up callsign {callsign} on QRZ.com: {e}")

    return None

def lookup_callsign(callsign, provider, username=None, password=None):
    if provider == 'qrz':
        return lookup_callsign_qrz(callsign, username, password)
    else: # Default to hamdb
        return lookup_callsign_hamdb(callsign)
