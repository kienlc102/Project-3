"""Detect host IPv4 LANs, including live host metadata for Docker Desktop."""
import ipaddress
import json
import logging
import os
from pathlib import Path
import socket
import time


def normalize_interfaces(interfaces):
    """Use actual interface netmasks; never guess a fixed /24 subnet."""
    networks = set()
    for item in interfaces:
        interface = ipaddress.IPv4Interface(f"{item['address']}/{item['netmask']}")
        if interface.ip.is_private and not interface.ip.is_loopback and not interface.ip.is_link_local:
            networks.add(str(interface.network))
    return sorted(networks)


def detect_host_subnets():
    metadata_path = os.environ.get("ESP32_HOST_NETWORK_FILE", "").strip()
    if metadata_path:
        path = Path(metadata_path)
        # A stopped host launcher must not leave stale LAN settings in use.
        if time.time() - path.stat().st_mtime > 45:
            raise ValueError("Host network metadata is stale; keep scripts/start-system.ps1 running")
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        return normalize_interfaces(data["interfaces"])
    if Path("/.dockerenv").exists():
        raise ValueError("Docker cannot infer the physical host LAN from its NAT address. "
                         "Start with scripts/start-system.ps1 to publish live host interfaces.")
    import psutil
    stats = psutil.net_if_stats()
    interfaces = []
    for name, addresses in psutil.net_if_addrs().items():
        if not stats.get(name) or not stats[name].isup:
            continue
        if any(token in name.lower() for token in ("loopback", "docker", "veth", "vmnet", "virtual", "wsl", "tailscale", "tun", "tap")):
            continue
        interfaces.extend({"address": address.address, "netmask": address.netmask}
                          for address in addresses if address.family == socket.AF_INET and address.netmask)
    return normalize_interfaces(interfaces)


def discovery_subnets():
    override = os.environ.get("ESP32_DISCOVERY_SUBNETS", "").strip()
    if override and override.lower() != "auto":
        return override
    subnets = detect_host_subnets()
    logging.getLogger("uvicorn.error").info("Host LAN discovery subnets: %s", ", ".join(subnets) or "none")
    return ",".join(subnets)
