# list_ips.py (module-only: no printing, no CLI)
from __future__ import annotations

import json
import shutil
import socket
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple


def _have_ip_cmd() -> bool:
    return shutil.which("ip") is not None


def _read_operstate(ifname: str) -> str:
    p = Path("/sys/class/net") / ifname / "operstate"
    try:
        return p.read_text().strip()
    except Exception:
        return "unknown"


def _run(cmd: List[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, check=True, capture_output=True, text=True)


def _get_ips_via_ip_json() -> List[Tuple[str, str, str, str, str]]:
    """
    Returns list of tuples: (ifname, family, cidr, scope, operstate)
    via `ip -j addr show`.
    """
    out = _run(["ip", "-j", "addr", "show"]).stdout
    data = json.loads(out)
    rows: List[Tuple[str, str, str, str, str]] = []
    for iface in data:
        ifname = iface.get("ifname") or iface.get("name") or "?"
        oper = iface.get("operstate", _read_operstate(ifname))
        for a in iface.get("addr_info", []):
            family = a.get("family")  # 'inet' or 'inet6'
            local = a.get("local")
            prefix = a.get("prefixlen")
            scope = a.get("scope", "")
            if local and prefix is not None:
                rows.append((ifname, family, f"{local}/{prefix}", scope, oper))
    return rows


def _get_ips_via_ip_oneline() -> List[Tuple[str, str, str, str, str]]:
    """
    Fallback: parse `ip -o addr show`.
    Returns list of tuples: (ifname, family, cidr, scope, operstate)
    """
    out_lines = _run(["ip", "-o", "addr", "show"]).stdout.splitlines()
    rows: List[Tuple[str, str, str, str, str]] = []
    for line in out_lines:
        parts = line.split()
        if len(parts) < 4:
            continue
        ifname = parts[1]
        family = parts[2]  # 'inet' or 'inet6'
        cidr = parts[3]
        scope = ""
        if "scope" in parts:
            try:
                scope = parts[parts.index("scope") + 1]
            except Exception:
                scope = ""
        oper = _read_operstate(ifname)
        rows.append((ifname, family, cidr, scope, oper))
    return rows


def _last_resort_primary() -> List[Tuple[str, str, str, str, str]]:
    """
    If `ip` is unavailable, guess the primary outbound IPv4 using a UDP socket.
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))  # no packet actually sent
        ip = s.getsockname()[0]
        s.close()
        return [("primary", "inet", f"{ip}/32", "global", "unknown")]
    except Exception:
        return []


def _collect_addresses(
    include_loopback: bool = False,
    only_up: bool = False,
    want_v4: bool = True,
    want_v6: bool = True,
) -> Dict[str, Dict[str, List[str]]]:
    """
    Returns:
    {
      "eth0": {"ipv4": ["10.0.0.12/24"], "ipv6": ["fe80::.../64"]},
      ...
    }
    """
    rows: List[Tuple[str, str, str, str, str]] = []
    if _have_ip_cmd():
        try:
            rows = _get_ips_via_ip_json()
        except Exception:
            try:
                rows = _get_ips_via_ip_oneline()
            except Exception:
                rows = _last_resort_primary()
    else:
        rows = _last_resort_primary()

    addrs = defaultdict(lambda: {"ipv4": [], "ipv6": []})
    for ifname, family, cidr, scope, oper in rows:
        if only_up and oper.upper() != "UP":
            continue
        if not include_loopback and (scope == "host" or ifname == "lo"):
            continue
        if family == "inet" and want_v4:
            addrs[ifname]["ipv4"].append(cidr)
        elif family == "inet6" and want_v6:
            addrs[ifname]["ipv6"].append(cidr)

    return {k: v for k, v in addrs.items() if v["ipv4"] or v["ipv6"]}


# -------------------- Hostname helpers --------------------

def get_hostname(fqdn: bool = False) -> str:
    """
    Returns the current hostname. If fqdn=True, returns the fully-qualified
    domain name. Falls back to /etc/hostname and 'unknown' as needed.
    """
    try:
        name = socket.getfqdn() if fqdn else socket.gethostname()
        if not name or name in ("localhost", "localhost.localdomain"):
            try:
                name = Path("/etc/hostname").read_text().strip() or name
            except Exception:
                pass
        return name or "unknown"
    except Exception:
        return "unknown"


# -------- Public IP API (import these from other scripts) --------

def get_local_ips(
    include_loopback: bool = False,
    only_up: bool = False,
    ipv4: bool = True,
    ipv6: bool = True,
) -> Dict[str, Dict[str, List[str]]]:
    """
    Dict of interface -> {'ipv4': [...], 'ipv6': [...]}, with CIDR suffixes.
    """
    return _collect_addresses(
        include_loopback=include_loopback,
        only_up=only_up,
        want_v4=ipv4,
        want_v6=ipv6,
    )


def get_ip_strings(
    include_loopback: bool = False,
    only_up: bool = False,
    ipv4: bool = True,
    ipv6: bool = True,
) -> List[str]:
    """
    Flat list of IP strings (CIDR removed), e.g. ['192.168.1.10', 'fe80::1'].
    """
    data = get_local_ips(
        include_loopback=include_loopback,
        only_up=only_up,
        ipv4=ipv4,
        ipv6=ipv6,
    )
    return [a.split("/", 1)[0] for fams in data.values() for a in (fams["ipv4"] + fams["ipv6"])]


def get_primary_ipv4() -> str | None:
    """
    Best-effort primary outbound IPv4 (no CIDR). Returns None if undetectable.
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return None


def get_host_and_ip_strings(
    include_loopback: bool = False,
    only_up: bool = False,
    ipv4: bool = True,
    ipv6: bool = False,
    fqdn: bool = False,
) -> List[str]:
    """
    Convenience helper: returns [hostname, *IP_strings].
    Hostname is first as requested.
    """
    return [get_hostname(fqdn=fqdn)] + get_ip_strings(
        include_loopback=include_loopback,
        only_up=only_up,
        ipv4=ipv4,
        ipv6=ipv6,
    )
