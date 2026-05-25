#!/usr/bin/env python3
from __future__ import annotations

import argparse
import calendar
import datetime as dt
import ipaddress
import re
import struct
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path


SIP_STARTS = (
    b"INVITE ",
    b"ACK ",
    b"BYE ",
    b"CANCEL ",
    b"OPTIONS ",
    b"REGISTER ",
    b"INFO ",
    b"PRACK ",
    b"UPDATE ",
    b"MESSAGE ",
    b"REFER ",
    b"SUBSCRIBE ",
    b"NOTIFY ",
    b"SIP/2.0 ",
)
DEFAULT_IP = "127.0.0.1"
DEFAULT_SIP_PORT = 5060
DEFAULT_TIMEZONE = "+08:00"


@dataclass
class SipMessage:
    offset: int
    payload: bytes
    timestamp: dt.datetime | None
    src_ip: str
    src_port: int
    dst_ip: str
    dst_port: int


@dataclass
class RecordMeta:
    timestamp: dt.datetime | None
    direction: int | None
    sequence: int | None
    src_ip: str | None
    src_port: int | None
    dst_ip: str | None
    dst_port: int | None


def read_inputs(path: Path) -> list[tuple[str, bytes]]:
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as zf:
            items = []
            for name in zf.namelist():
                if name.lower().endswith(".ptmf"):
                    items.append((name, zf.read(name)))
            if not items:
                raise SystemExit(f"{path} 中没有找到 .ptmf 文件")
            return items
    return [(path.name, path.read_bytes())]


def find_sip_offsets(data: bytes) -> list[int]:
    offsets: set[int] = set()
    for marker in SIP_STARTS:
        start = 0
        while True:
            pos = data.find(marker, start)
            if pos < 0:
                break
            offsets.add(pos)
            start = pos + 1
    return sorted(offsets)


def extract_payload(data: bytes, offset: int) -> bytes | None:
    header_end = data.find(b"\r\n\r\n", offset)
    if header_end < 0:
        return None
    headers = data[offset:header_end].decode("latin1", errors="ignore")
    match = re.search(r"(?im)^Content-Length\s*:\s*(\d+)\s*$", headers)
    content_len = int(match.group(1)) if match else 0
    end = header_end + 4 + content_len
    if end > len(data):
        return None
    payload = data[offset:end]
    if not payload.startswith(SIP_STARTS):
        return None
    return payload


def parse_timezone(value: str) -> dt.tzinfo:
    value = value.strip()
    if value.upper() in {"Z", "UTC", "GMT"}:
        return dt.timezone.utc
    match = re.fullmatch(r"([+-])(\d{1,2})(?::?(\d{2}))?", value)
    if not match:
        raise argparse.ArgumentTypeError("timezone must look like +08:00, -0500, UTC, or Z")
    sign = 1 if match.group(1) == "+" else -1
    hours = int(match.group(2))
    minutes = int(match.group(3) or "0")
    if hours > 23 or minutes > 59:
        raise argparse.ArgumentTypeError("invalid timezone offset")
    return dt.timezone(sign * dt.timedelta(hours=hours, minutes=minutes))


def parse_record_time(data: bytes, offset: int, tzinfo: dt.tzinfo) -> tuple[dt.datetime | None, int | None, int | None]:
    window = data[max(0, offset - 768):offset]
    candidates: list[tuple[dt.datetime, int | None, int | None]] = []
    for i in range(len(window) - 6):
        year = int.from_bytes(window[i:i + 2], "big")
        month, day, hour, minute, second = window[i + 2:i + 7]
        if 2000 <= year <= 2099 and 1 <= month <= 12 and 1 <= day <= 31 and hour <= 23 and minute <= 59 and second <= 59:
            try:
                direction = int.from_bytes(window[i + 7:i + 11], "big") if i + 13 <= len(window) else None
                millis = window[i + 11] if i + 12 <= len(window) else 0
                sequence = window[i + 12] if i + 13 <= len(window) else None
                candidates.append((dt.datetime(year, month, day, hour, minute, second, millis * 1000, tzinfo=tzinfo), direction, sequence))
            except ValueError:
                pass
    return candidates[-1] if candidates else (None, None, None)


def parse_record_endpoints(data: bytes, offset: int, direction: int | None) -> tuple[str, int | None, str, int | None] | None:
    window_start = max(0, offset - 512)
    window = data[window_start:offset]
    candidates: list[tuple[int, str, int | None]] = []
    for i in range(1, len(window) - 3):
        if window[i - 1] != 0x01:
            continue
        try:
            ip = ipaddress.IPv4Address(window[i:i + 4])
        except ipaddress.AddressValueError:
            continue
        octets = list(ip.packed)
        if ip.is_unspecified or ip.is_loopback or ip.is_multicast or ip.is_reserved:
            continue
        if octets[0] in {0, 127, 224, 239, 255} or octets[-1] in {0, 255}:
            continue
        port = None
        port_pos = i + 16
        if port_pos + 2 <= len(window):
            raw_port = int.from_bytes(window[port_pos:port_pos + 2], "little")
            if 0 < raw_port <= 65535:
                port = raw_port
        candidates.append((window_start + i, str(ip), port))

    # Huawei PTMF message records store source and destination IPv4 addresses
    # as two fields separated by 0x13 bytes. For direction code 0, the pair is
    # stored as destination/source; for the other observed codes it is
    # source/destination. Other byte sequences in the record can look like IPv4
    # addresses, so prefer this structural pair.
    for (pos_a, ip_a, port_a), (pos_b, ip_b, port_b) in zip(candidates, candidates[1:]):
        if pos_b - pos_a == 0x13 and ip_a != ip_b:
            if direction == 0:
                return ip_b, port_b, ip_a, port_a
            return ip_a, port_a, ip_b, port_b
    return None


def parse_record_meta(data: bytes, offset: int, tzinfo: dt.tzinfo) -> RecordMeta:
    timestamp, direction, sequence = parse_record_time(data, offset, tzinfo)
    endpoints = parse_record_endpoints(data, offset, direction)
    if not endpoints:
        return RecordMeta(timestamp, direction, sequence, None, None, None, None)
    src_ip, src_port, dst_ip, dst_port = endpoints
    return RecordMeta(timestamp, direction, sequence, src_ip, src_port, dst_ip, dst_port)


def text(payload: bytes) -> str:
    return payload.decode("latin1", errors="ignore")


def first_header(message: str, name: str) -> str | None:
    match = re.search(rf"(?im)^{re.escape(name)}\s*:\s*(.+?)\s*$", message)
    return match.group(1).strip() if match else None


def parse_host_port(value: str | None, default_port: int = DEFAULT_SIP_PORT) -> tuple[str | None, int | None]:
    if not value:
        return None, None
    value = value.strip()
    host = re.search(r"(?<![\d.])(\d{1,3}(?:\.\d{1,3}){3})(?::(\d+))?", value)
    if host:
        return host.group(1), int(host.group(2) or default_port)
    return None, None


def valid_ip(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return str(ipaddress.IPv4Address(value))
    except ipaddress.AddressValueError:
        return None


def infer_endpoints(payload: bytes) -> tuple[str, int, str, int]:
    message = text(payload)
    first_line = message.splitlines()[0] if message.splitlines() else ""
    via = first_header(message, "Via") or first_header(message, "v")
    contact = first_header(message, "Contact") or first_header(message, "m")
    route = first_header(message, "Route")
    record_route = first_header(message, "Record-Route")

    via_ip, via_port = parse_host_port(via)
    contact_ip, contact_port = parse_host_port(contact)
    route_ip, route_port = parse_host_port(route)
    rr_ip, rr_port = parse_host_port(record_route)

    if first_line.startswith("SIP/2.0"):
        dst_ip, dst_port = via_ip, via_port
        src_ip, src_port = contact_ip or rr_ip or route_ip, contact_port or rr_port or route_port
    else:
        dst_ip, dst_port = parse_host_port(first_line)
        if not dst_ip:
            dst_ip, dst_port = route_ip, route_port
        src_ip, src_port = via_ip, via_port

    src_ip = valid_ip(src_ip) or DEFAULT_IP
    dst_ip = valid_ip(dst_ip) or DEFAULT_IP
    return src_ip, int(src_port or DEFAULT_SIP_PORT), dst_ip, int(dst_port or DEFAULT_SIP_PORT)


def extract_messages(data: bytes, tzinfo: dt.tzinfo) -> list[SipMessage]:
    messages: list[SipMessage] = []
    seen: set[tuple[int, bytes]] = set()
    for offset in find_sip_offsets(data):
        payload = extract_payload(data, offset)
        if not payload:
            continue
        key = (offset, payload[:80])
        if key in seen:
            continue
        seen.add(key)
        src_ip, src_port, dst_ip, dst_port = infer_endpoints(payload)
        meta = parse_record_meta(data, offset, tzinfo)
        if meta.src_ip and meta.dst_ip:
            src_ip, dst_ip = meta.src_ip, meta.dst_ip
        if meta.src_port:
            src_port = meta.src_port
        if meta.dst_port:
            dst_port = meta.dst_port
        messages.append(SipMessage(offset, payload, meta.timestamp, src_ip, src_port, dst_ip, dst_port))
    return messages


def checksum(data: bytes) -> int:
    if len(data) % 2:
        data += b"\x00"
    total = sum(struct.unpack(f"!{len(data) // 2}H", data))
    total = (total >> 16) + (total & 0xFFFF)
    total += total >> 16
    return (~total) & 0xFFFF


def packet_bytes(msg: SipMessage, normalize_ports: bool = False) -> bytes:
    src = ipaddress.IPv4Address(msg.src_ip).packed
    dst = ipaddress.IPv4Address(msg.dst_ip).packed
    src_port = msg.src_port
    dst_port = msg.dst_port
    if normalize_ports:
        if msg.payload.startswith(b"SIP/2.0 "):
            src_port = DEFAULT_SIP_PORT
        else:
            dst_port = DEFAULT_SIP_PORT
    udp_len = 8 + len(msg.payload)
    ip_len = 20 + udp_len

    eth = b"\x02\x00\x00\x00\x00\x01" + b"\x02\x00\x00\x00\x00\x02" + b"\x08\x00"
    ip_header = struct.pack("!BBHHHBBH4s4s", 0x45, 0, ip_len, 0, 0, 64, 17, 0, src, dst)
    ip_header = ip_header[:10] + struct.pack("!H", checksum(ip_header)) + ip_header[12:]
    udp_header = struct.pack("!HHHH", src_port, dst_port, udp_len, 0)
    pseudo = src + dst + struct.pack("!BBH", 0, 17, udp_len)
    udp_sum = checksum(pseudo + udp_header + msg.payload)
    if udp_sum == 0:
        udp_sum = 0xFFFF
    udp_header = struct.pack("!HHHH", src_port, dst_port, udp_len, udp_sum)
    return eth + ip_header + udp_header + msg.payload


def write_pcap(messages: list[SipMessage], out: Path, normalize_ports: bool = False) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    base_time = dt.datetime.now(dt.timezone.utc)
    used_timestamps: dict[tuple[int, int], int] = {}
    with out.open("wb") as f:
        f.write(struct.pack("<IHHIIII", 0xA1B2C3D4, 2, 4, 0, 0, 65535, 1))
        for msg in messages:
            ts = (msg.timestamp or base_time).astimezone(dt.timezone.utc)
            sec = calendar.timegm(ts.timetuple())
            usec = ts.microsecond
            duplicate_key = (sec, usec)
            duplicate_count = used_timestamps.get(duplicate_key, 0)
            used_timestamps[duplicate_key] = duplicate_count + 1
            usec += duplicate_count
            pkt = packet_bytes(msg, normalize_ports=normalize_ports)
            f.write(struct.pack("<IIII", sec, usec, len(pkt), len(pkt)))
            f.write(pkt)


def main() -> int:
    parser = argparse.ArgumentParser(description="Convert Huawei-style PTMF SIP trace files to Wireshark-readable PCAP.")
    parser.add_argument("input", type=Path, help="Input .ptmf file or .zip containing .ptmf files")
    parser.add_argument("-o", "--output", type=Path, help="Output .pcap path")
    parser.add_argument("--summary", action="store_true", help="Print extracted SIP messages")
    parser.add_argument(
        "--timezone",
        default=DEFAULT_TIMEZONE,
        help=f"Timezone of PTMF timestamps, e.g. +08:00 or UTC. Default: {DEFAULT_TIMEZONE}",
    )
    parser.add_argument(
        "--normalize-ports",
        action="store_true",
        help="Set request destination ports and response source ports to 5060 so Wireshark/tcpdump auto-dissect SIP on non-standard ports.",
    )
    args = parser.parse_args()

    if not args.input.exists():
        parser.error(f"input not found: {args.input}")

    tzinfo = parse_timezone(args.timezone)
    all_messages: list[SipMessage] = []
    for name, data in read_inputs(args.input):
        messages = extract_messages(data, tzinfo)
        if args.summary:
            print(f"{name}: {len(messages)} SIP messages")
            for idx, msg in enumerate(messages, 1):
                first = text(msg.payload).splitlines()[0]
                ts = msg.timestamp.isoformat() if msg.timestamp else "no-time"
                print(f"{idx:03d} {ts} {msg.src_ip}:{msg.src_port} -> {msg.dst_ip}:{msg.dst_port} {first}")
        all_messages.extend(messages)

    if not all_messages:
        raise SystemExit("没有从输入文件中提取到 SIP 报文")

    output = args.output or args.input.with_suffix(".pcap")
    write_pcap(all_messages, output, normalize_ports=args.normalize_ports)
    print(f"wrote {output} ({len(all_messages)} SIP packets)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
