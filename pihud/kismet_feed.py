#!/usr/bin/env python3
"""
kismet_feed.py

Fetch Kismet counts (AP/Wifi/BT) and uptime.
- get_counts() returns a dict: { 'ap': int, 'wifi': int, 'bt': int }
- get_uptime() returns a string like "Uptime HH:MM:SS"
- Supports authentication via API token or username/password
- Reads credentials from environment variables by default:
    KISMET_TOKEN, KISMET_USER, KISMET_PASS
"""

import os
import re
import ssl
import base64
import urllib.request
import time
import json
import gps
from pathlib import Path
from dotenv import load_dotenv

# Record script start time
script_start = time.time()

# Load ~/.kismet_creds automatically if it exists
credfile = Path.home() / ".kismet_creds"
if credfile.exists():
    load_dotenv(credfile)

def get_script_uptime():
    """
    Returns a string HH:MM:SS since this script started.
    """
    elapsed = int(time.time() - script_start)
    hh = elapsed // 3600
    mm = (elapsed % 3600) // 60
    ss = elapsed % 60
    return f"Uptime {hh:02}:{mm:02}:{ss:02}"

def _http_get(url, user=None, password=None, token=None):
    """
    HTTP GET with optional Kismet API token or Basic auth.
    Priority:
        1. Explicit token arg
        2. KISMET_TOKEN env var
        3. Explicit user/password
        4. KISMET_USER/KISMET_PASS env vars
    """
    req = urllib.request.Request(url)

    # token wins
    token = token or os.environ.get("KISMET_TOKEN")
    if token:
        req.add_header("KISMET", token)
    else:
        user = user or os.environ.get("KISMET_USER")
        password = password or os.environ.get("KISMET_PASS")
        if user and password:
            creds = f"{user}:{password}".encode("utf-8")
            b64 = base64.b64encode(creds).decode("ascii")
            req.add_header("Authorization", "Basic " + b64)

    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, context=ctx, timeout=10) as fh:
        return fh.read().decode("utf-8")


def parse_all_views_sizes(all_views_json_text):
    """
    Extract sizes from Kismet /devices/views/all_views.json without jq.
    Returns dict: {'ap': int, 'wifi': int, 'bt': int}
    """
    def find_size(viewid):
        pat = f'"kismet.devices.view.id": "{viewid}"'
        idx = all_views_json_text.find(pat)
        if idx == -1:
            return 0
        sub = all_views_json_text[idx: idx + 200]
        m = re.search(r'"kismet.devices.view.size"\s*:\s*([0-9]+)', sub)
        if m:
            return int(m.group(1))
        return 0

    return {
        "ap": find_size("phydot11_accesspoints"),
        "wifi": find_size("phy-IEEE802.11"),
        "bt": find_size("phy-Bluetooth"),
    }


def get_counts(host="localhost", port=2501, user=None, password=None, token=None):
    """
    Query Kismet for AP/WiFi/BT counts.
    """
    base = f"http://{host}:{port}"
    url = f"{base}/devices/views/all_views.json"
    txt = _http_get(url, user=user, password=password, token=token)
    return parse_all_views_sizes(txt)


def get_gps_status():
    """
    Connects to gpsd and returns 'NO', '2D', or '3D' depending on fix mode.
    Requires gpsd to be running (e.g., gpsd /dev/ttyACM0).
    """
    try:
        session = gps.gps(mode=gps.WATCH_ENABLE)
        report = session.next()
        # Loop until we find a TPV report (contains fix data)
        while report['class'] != 'TPV':
            report = session.next()

        mode = getattr(report, 'mode', 1)
        if mode == 3:
            return "3D"
        elif mode == 2:
            return "2D"
        else:
            return "NO-FIX"
    except Exception as e:
        return f"NO"  # default to NO fix if gpsd unavailable


def get_uptime(host="localhost", port=2501, user=None, password=None, token=None):
    """
    Returns a string HH:MM:SS of how long Kismet has been running.
    """
    base = f"http://{host}:{port}"
    url = f"{base}/status.json"
    txt = _http_get(url, user=user, password=password, token=token)
    try:
        js = json.loads(txt)
        start_ts = js.get("kismet.server.starttime", None)
        if start_ts is None:
            return "Uptime: ?"

        elapsed = int(time.time() - start_ts)
        hh = elapsed // 3600
        mm = (elapsed % 3600) // 60
        ss = elapsed % 60
        return f"Uptime {hh:02}:{mm:02}:{ss:02}"
    except Exception:
        return "Uptime: ?"


if __name__ == "__main__":
    try:
        counts = get_counts()
        uptime = get_script_uptime()  # use our new uptime function
        print(f"{uptime}")
        print(f"AP: {counts['ap']}")
        print(f"Wifi: {counts['wifi']}")
        print(f"BT: {counts['bt']}")
    except Exception as e:
        print(f"Error fetching data from Kismet: {e}")
