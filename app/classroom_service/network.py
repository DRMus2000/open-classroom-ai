"""Local addresses suggested to a teacher sharing a LAN guest link."""
from __future__ import annotations

import ipaddress
import socket
import sys


_VPN_MARKERS = (
    "vpn", "tap", "tun", "ppp", "wintun", "wireguard", "wg ", "nordlynx", "zerotier",
    "hamachi", "openvpn", "softether", "forticlient", "easyconnect", "cisco", "anyconnect",
    "tailscale", "radmin",
)
_VIRTUAL_MARKERS = (
    "hyper-v", "hyperv", "vethernet", "vmware", "virtualbox", "vbox", "docker", "wsl",
    "bluetooth", "loopback", "pseudo", "virtual", "hosted virtual", "wi-fi direct",
    "microsoft wi-fi direct",
)


def _usable_ipv4(text: str) -> str | None:
    try:
        address = ipaddress.ip_address(text)
    except ValueError:
        return None
    if address.version != 4 or address.is_loopback or address.is_unspecified or address.is_link_local or address.is_multicast:
        return None
    return str(address)


def _kind_for(name: str, if_type: int | None = None) -> str:
    label = (name or "").casefold()
    if if_type in {23, 131} or any(marker in label for marker in _VPN_MARKERS):
        return "vpn"
    if if_type in {24, 53} or any(marker in label for marker in _VIRTUAL_MARKERS):
        return "virtual"
    return "physical"


def _rank(kind: str) -> int:
    return {"physical": 0, "vpn": 2, "virtual": 3}.get(kind, 1)


def _hostname_interfaces() -> list[dict]:
    try:
        entries = socket.getaddrinfo(socket.gethostname(), None, family=socket.AF_INET, type=socket.SOCK_STREAM)
    except OSError:
        return []
    result = []
    seen = set()
    for entry in entries:
        address = _usable_ipv4(entry[4][0])
        if not address or address in seen:
            continue
        seen.add(address)
        result.append({"address": address, "name": socket.gethostname(), "kind": "physical"})
    return result


def _windows_adapters() -> list[dict]:
    import ctypes
    from ctypes import wintypes

    class SOCKADDR_IN(ctypes.Structure):
        _fields_ = [
            ("sin_family", wintypes.USHORT),
            ("sin_port", wintypes.USHORT),
            ("sin_addr", ctypes.c_byte * 4),
            ("sin_zero", ctypes.c_char * 8),
        ]

    class SOCKET_ADDRESS(ctypes.Structure):
        _fields_ = [("lpSockaddr", ctypes.c_void_p), ("iSockaddrLength", wintypes.INT)]

    class IP_ADAPTER_UNICAST_ADDRESS(ctypes.Structure):
        pass

    IP_ADAPTER_UNICAST_ADDRESS._fields_ = [
        ("Length", wintypes.ULONG),
        ("Flags", wintypes.DWORD),
        ("Next", ctypes.POINTER(IP_ADAPTER_UNICAST_ADDRESS)),
        ("Address", SOCKET_ADDRESS),
    ]

    class IP_ADAPTER_ADDRESSES(ctypes.Structure):
        pass

    IP_ADAPTER_ADDRESSES._fields_ = [
        ("Length", wintypes.ULONG),
        ("IfIndex", wintypes.DWORD),
        ("Next", ctypes.POINTER(IP_ADAPTER_ADDRESSES)),
        ("AdapterName", ctypes.c_char_p),
        ("FirstUnicastAddress", ctypes.POINTER(IP_ADAPTER_UNICAST_ADDRESS)),
        ("FirstAnycastAddress", ctypes.c_void_p),
        ("FirstMulticastAddress", ctypes.c_void_p),
        ("FirstDnsServerAddress", ctypes.c_void_p),
        ("DnsSuffix", ctypes.c_wchar_p),
        ("Description", ctypes.c_wchar_p),
        ("FriendlyName", ctypes.c_wchar_p),
        ("PhysicalAddress", ctypes.c_ubyte * 8),
        ("PhysicalAddressLength", wintypes.ULONG),
        ("Flags", wintypes.ULONG),
        ("Mtu", wintypes.ULONG),
        ("IfType", wintypes.ULONG),
        ("OperStatus", ctypes.c_int),
    ]

    iphlpapi = ctypes.WinDLL("iphlpapi")
    flags = 0x0002 | 0x0004 | 0x0008  # skip anycast, multicast, DNS
    size = wintypes.ULONG(15 * 1024)
    buf = ctypes.create_string_buffer(size.value)
    error = iphlpapi.GetAdaptersAddresses(2, flags, None, buf, ctypes.byref(size))
    if error == 111:  # ERROR_BUFFER_OVERFLOW
        buf = ctypes.create_string_buffer(size.value)
        error = iphlpapi.GetAdaptersAddresses(2, flags, None, buf, ctypes.byref(size))
    if error:
        raise OSError(error)
    results = []
    adapter = ctypes.cast(buf, ctypes.POINTER(IP_ADAPTER_ADDRESSES))
    while adapter:
        current = adapter.contents
        if int(current.OperStatus) == 1 and current.FirstUnicastAddress:
            name = current.FriendlyName or current.Description or current.AdapterName or "adapter"
            kind = _kind_for(str(name), int(current.IfType))
            unicast = current.FirstUnicastAddress
            while unicast:
                raw = unicast.contents.Address.lpSockaddr
                if raw:
                    sock = ctypes.cast(raw, ctypes.POINTER(SOCKADDR_IN)).contents
                    if sock.sin_family == 2:
                        address = _usable_ipv4(socket.inet_ntoa(bytes(sock.sin_addr)))
                        if address:
                            results.append({"address": address, "name": str(name), "kind": kind})
                unicast = unicast.contents.Next
        adapter = current.Next
    return results


def _posix_adapters() -> list[dict]:
    import fcntl
    import struct

    sio = 0xC0206921 if sys.platform == "darwin" else 0x8915
    names = []
    try:
        names = [name for _, name in socket.if_nameindex()]
    except (OSError, AttributeError):
        return []
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    results = []
    try:
        for name in names:
            try:
                raw = fcntl.ioctl(sock.fileno(), sio, struct.pack("256s", name.encode("utf-8")[:15]))
                address = _usable_ipv4(socket.inet_ntoa(raw[20:24]))
            except (OSError, ValueError):
                continue
            if address:
                results.append({"address": address, "name": name, "kind": _kind_for(name)})
    finally:
        sock.close()
    return results


def adapter_interfaces() -> list[dict]:
    """Best-effort enabled IPv4 adapters. Tests may monkeypatch this."""
    try:
        if sys.platform == "win32":
            return _windows_adapters()
        return _posix_adapters()
    except Exception:
        return []


def share_interfaces() -> list[dict]:
    found = adapter_interfaces() or _hostname_interfaces()
    unique = []
    seen = set()
    for item in found:
        address = _usable_ipv4(item.get("address", ""))
        if not address or address in seen:
            continue
        seen.add(address)
        name = str(item.get("name") or address)
        kind = item.get("kind") if item.get("kind") in {"physical", "vpn", "virtual"} else _kind_for(name)
        unique.append({"address": address, "name": name, "kind": kind, "rank": _rank(kind)})
    unique.sort(key=lambda item: (item["rank"], item["name"], item["address"]))
    return unique


def share_hosts() -> list[str]:
    return [item["address"] for item in share_interfaces()]
