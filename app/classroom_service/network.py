"""Local addresses suggested to a teacher sharing a LAN guest link."""
import ipaddress
import socket


def share_hosts() -> list[str]:
    try:
        addresses = socket.getaddrinfo(socket.gethostname(), None, family=socket.AF_INET,
                                       type=socket.SOCK_STREAM)
    except OSError:
        return []
    result = set()
    for entry in addresses:
        address = ipaddress.ip_address(entry[4][0])
        if not (address.is_loopback or address.is_unspecified or address.is_link_local or address.is_multicast):
            result.add(str(address))
    return sorted(result)
