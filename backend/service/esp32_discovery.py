"""Discover only Parkly ESP32 nodes; never select an arbitrary HTTP server."""
import ipaddress
import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlsplit
from urllib.request import urlopen

SERVICE_TYPE = "_parkly._tcp.local."


class DiscoveryError(RuntimeError):
    pass


class MultipleDevicesError(DiscoveryError):
    pass


def check_device(base_url, model_sha256, timeout=2):
    try:
        parsed = urlsplit(base_url)
        address = ipaddress.ip_address(parsed.hostname)
        if parsed.scheme != "http" or address.version != 4 or not address.is_private:
            return False
        with urlopen(base_url + "/health", timeout=timeout) as response:
            health = json.loads(response.read(4096))
        return (health.get("device_type") == "parkly-esp32" and health.get("ready") is True
                and health.get("input_bytes") == 4096
                and health.get("model_sha256") == model_sha256)
    except (OSError, ValueError, TypeError, AttributeError):
        return False


def select_device(candidates, model_sha256):
    """Verify HTTP readiness/model rather than trusting cached mDNS TXT alone."""
    matches = [url for url in sorted(set(candidates)) if check_device(url, model_sha256)]
    if len(matches) != 1:
        error = MultipleDevicesError if len(matches) > 1 else DiscoveryError
        raise error(f"Expected one ready ESP32 with matching model; found {len(matches)}. "
                             "Check Wi-Fi/mDNS, firmware, or set ESP32_URL explicitly for multiple boards.")
    return matches[0]


def discover_mdns(model_sha256, timeout=3):
    from zeroconf import IPVersion, ServiceBrowser, Zeroconf

    names = set()
    lock = threading.Lock()

    class Listener:
        def add_service(self, zc, kind, name):
            with lock:
                names.add(name)

        def update_service(self, zc, kind, name):
            self.add_service(zc, kind, name)

        def remove_service(self, zc, kind, name):
            with lock:
                names.discard(name)

    zc = Zeroconf(ip_version=IPVersion.V4Only)
    browser = None
    try:
        browser = ServiceBrowser(zc, SERVICE_TYPE, listener=Listener())
        threading.Event().wait(timeout)
        with lock:
            discovered_names = sorted(names)
        candidates = []
        for name in discovered_names:
            info = zc.get_service_info(SERVICE_TYPE, name, timeout=1000)
            if info and info.properties.get(b"model_sha256") == model_sha256.encode():
                candidates.extend(f"http://{address}:{info.port}"
                                  for address in info.parsed_addresses(IPVersion.V4Only))
        return select_device(candidates, model_sha256)
    finally:
        if browser:
            browser.cancel()
        zc.close()


def scan_candidates(subnets):
    addresses = set()
    for value in filter(None, (part.strip() for part in subnets.split(","))):
        try:
            network = ipaddress.ip_network(value, strict=False)
        except ValueError as error:
            raise DiscoveryError(f"Invalid ESP32_DISCOVERY_SUBNETS: {value}") from error
        if network.version != 4 or not network.is_private or network.num_addresses > 1024:
            raise DiscoveryError("Discovery requires private IPv4 subnets of /22 or smaller (e.g. /24)")
        addresses.update(str(address) for address in network.hosts())
        if len(addresses) > 1024:
            raise DiscoveryError("Discovery is limited to 1024 LAN addresses")
    return [f"http://{address}:80" for address in sorted(addresses)]


def discover_device(model_sha256):
    # Runs inside the backend. Unicast subnet probing works across Docker NAT.
    from backend.service.host_network import discovery_subnets
    try:
        subnets = discovery_subnets()
        host_error = None
    except (OSError, ValueError, KeyError, TypeError, ImportError) as error:
        subnets, host_error = "", str(error)
    try:
        return discover_mdns(model_sha256)
    except MultipleDevicesError:
        raise
    except (OSError, ImportError, DiscoveryError) as error:
        mdns_error = error
    candidates = scan_candidates(subnets)
    if not candidates:
        raise DiscoveryError("No usable host LAN detected and no mDNS board found. "
                             f"Host: {host_error or 'no active private IPv4 interface'}. mDNS: {mdns_error}")
    with ThreadPoolExecutor(max_workers=32, thread_name_prefix="esp32-probe") as pool:
        matches = list(pool.map(lambda url: url if check_device(url, model_sha256, timeout=0.6)
                                else None, candidates))
    matches = [url for url in matches if url]
    if len(matches) != 1:
        error = MultipleDevicesError if len(matches) > 1 else DiscoveryError
        raise error(f"LAN scan found {len(matches)} ready boards with matching model. "
                    "Check ESP32_DISCOVERY_SUBNETS/Wi-Fi or set ESP32_URL to select a board.")
    return matches[0]
