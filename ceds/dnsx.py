"""纯标准库的 DNS 查询：只查 MX / A，判定域名能不能收信。

不建立任何 SMTP 连接——这是本工具的硬边界。
"""
from __future__ import annotations

import random
import socket
import struct
from typing import List, Tuple

QTYPE_A = 1
QTYPE_MX = 15
RCODE_NXDOMAIN = 3
SERVERS = ("223.5.5.5", "1.1.1.1", "8.8.8.8")


class DnsError(Exception):
    pass


def _build_query(name: str, qtype: int, qid: int) -> bytes:
    out = bytearray(struct.pack("!HHHHHH", qid, 0x0100, 1, 0, 0, 0))
    labels = [lb for lb in name.rstrip(".").split(".") if lb]
    if not labels:
        raise DnsError("empty name")
    for label in labels:
        try:
            enc = label.encode("idna")
        except UnicodeError:
            enc = label.encode("ascii", "ignore")
        if not enc or len(enc) > 63:
            raise DnsError("bad label: %r" % label)
        out.append(len(enc))
        out.extend(enc)
    out.append(0)
    out.extend(struct.pack("!HH", qtype, 1))
    return bytes(out)


def _read_name(data: bytes, off: int) -> Tuple[str, int]:
    labels: List[str] = []
    jumped = False
    end = off
    for _ in range(128):
        if off >= len(data):
            raise DnsError("truncated name")
        length = data[off]
        if length & 0xC0 == 0xC0:
            if off + 1 >= len(data):
                raise DnsError("bad pointer")
            ptr = ((length & 0x3F) << 8) | data[off + 1]
            if not jumped:
                end = off + 2
                jumped = True
            off = ptr
            continue
        if length == 0:
            off += 1
            return ".".join(labels), (end if jumped else off)
        labels.append(data[off + 1: off + 1 + length].decode("utf-8", "replace"))
        off += 1 + length
    raise DnsError("name too long")


def query(name: str, qtype: int, timeout: float = 4.0,
          servers: Tuple[str, ...] = SERVERS) -> Tuple[bytes, List[Tuple[int, int, int]], int]:
    """返回 (报文, [(rtype, rdata_offset, rdlen)], rcode)。"""
    last: Exception | None = None
    for server in servers:
        try:
            qid = random.getrandbits(16)
            packet = _build_query(name, qtype, qid)
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sk:
                sk.settimeout(timeout)
                sk.sendto(packet, (server, 53))
                data, _ = sk.recvfrom(4096)
            rid, flags, qd, an, _ns, _ar = struct.unpack("!HHHHHH", data[:12])
            if rid != qid:
                raise DnsError("id mismatch")
            rcode = flags & 0x0F
            if rcode == RCODE_NXDOMAIN:
                return data, [], rcode
            if rcode != 0:
                raise DnsError("rcode %d" % rcode)
            off = 12
            for _ in range(qd):
                _, off = _read_name(data, off)
                off += 4
            answers: List[Tuple[int, int, int]] = []
            for _ in range(an):
                _, off = _read_name(data, off)
                if off + 10 > len(data):
                    break
                rtype, _rclass, _ttl, rdlen = struct.unpack("!HHIH", data[off:off + 10])
                off += 10
                answers.append((rtype, off, rdlen))
                off += rdlen
            return data, answers, rcode
        except (socket.timeout, OSError, DnsError) as exc:
            last = exc
            continue
    raise DnsError(str(last))


def mx_records(domain: str, timeout: float = 4.0) -> List[Tuple[int, str]]:
    data, answers, _ = query(domain, QTYPE_MX, timeout)
    out: List[Tuple[int, str]] = []
    for rtype, off, rdlen in answers:
        if rtype != QTYPE_MX or rdlen < 3:
            continue
        pref = struct.unpack("!H", data[off:off + 2])[0]
        host, _ = _read_name(data, off + 2)
        out.append((pref, host.rstrip(".")))
    return sorted(out)


def a_records(domain: str, timeout: float = 4.0) -> List[str]:
    data, answers, _ = query(domain, QTYPE_A, timeout)
    return [socket.inet_ntoa(data[off:off + 4])
            for rtype, off, rdlen in answers
            if rtype == QTYPE_A and rdlen == 4]


def domain_health(domain: str, timeout: float = 4.0) -> dict:
    """state: mx / null_mx / a_only / dead。"""
    result = {"domain": domain, "mx": [], "a": [], "state": "dead", "error": None}
    try:
        result["mx"] = mx_records(domain, timeout)
    except DnsError as exc:
        result["error"] = "mx: %s" % exc
    if result["mx"] == [(0, "")] or (len(result["mx"]) == 1 and result["mx"][0][1] == ""):
        result["state"] = "null_mx"
        return result
    if result["mx"]:
        result["state"] = "mx"
        return result
    try:
        result["a"] = a_records(domain, timeout)
    except DnsError as exc:
        result["error"] = (result["error"] or "") + " a: %s" % exc
    # RFC 5321 §5.1：没有 MX 时退化为 A 记录投递
    result["state"] = "a_only" if result["a"] else "dead"
    return result
