"""Generate a tiny LAB PCAP to validate the Suricata detection rules.

This is SYNTHETIC test traffic (clearly labelled): a TCP SYN from a HOME_NET
host to each PUBLISHED IOC IP, plus a DNS query for published domains.
Purpose: prove that the generated rules fire — never used as threat data.
"""
from __future__ import annotations

import os
import struct
import sys
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.models.ioc import Ioc, IocStatus, IocType  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PCAP_OUT = ROOT / "integrations" / "suricata" / "testdata" / "lab-traffic.pcap"

SRC_IP = "192.168.10.50"      # inside HOME_NET
SRC_PORT = 40000


def _checksum(data: bytes) -> int:
    if len(data) % 2:
        data += b"\x00"
    s = sum(struct.unpack("!%dH" % (len(data) // 2), data))
    s = (s >> 16) + (s & 0xFFFF)
    s += s >> 16
    return ~s & 0xFFFF


def _ipv4(src: str, dst: str, payload: bytes, proto: int) -> bytes:
    def ip2int(ip: str) -> int:
        return struct.unpack("!I", bytes(int(o) for o in ip.split(".")))[0]

    header = struct.pack(
        "!BBHHHBBHII",
        0x45, 0, 20 + len(payload), 0x1234, 0, 64, proto, 0,
        ip2int(src), ip2int(dst),
    )
    csum = _checksum(header)
    header = header[:10] + struct.pack("!H", csum) + header[12:]
    return header + payload


def _tcp_syn(src_ip: str, dst_ip: str, dst_port: int) -> bytes:
    tcp = struct.pack("!HHIIBBHHH", SRC_PORT, dst_port, 1000, 0, 0x50, 0x02, 8192, 0, 0)
    pseudo = (
        struct.pack("!4s4sBBH",
                    bytes(int(o) for o in src_ip.split(".")),
                    bytes(int(o) for o in dst_ip.split(".")),
                    0, 6, len(tcp))
        + tcp
    )
    csum = _checksum(pseudo)
    tcp = tcp[:16] + struct.pack("!H", csum) + tcp[18:]
    return _ipv4(src_ip, dst_ip, tcp, 6)


def _eth(payload: bytes, ethertype: int = 0x0800) -> bytes:
    return bytes.fromhex("aabbccddeeff112233445566") + struct.pack("!H", ethertype) + payload


def _dns_query(name: str) -> bytes:
    """Minimal DNS query packet (A record)."""
    tid = b"\x12\x34"
    flags = b"\x01\x00"
    counts = b"\x00\x01\x00\x00\x00\x00\x00\x00"
    q = b""
    for label in name.split("."):
        q += bytes([len(label)]) + label.encode()
    q += b"\x00\x00\x01\x00\x01"
    udp_payload = tid + flags + counts + q

    src_ip, dst_ip = SRC_IP, "192.168.10.1"      # local resolver
    udp_len = 8 + len(udp_payload)
    udp = struct.pack("!HHHH", SRC_PORT, 53, udp_len, 0) + udp_payload
    ip = _ipv4(src_ip, dst_ip, udp, 17)
    return _eth(ip)


def main() -> int:
    host = os.environ.get("POSTGRES_HOST", "127.0.0.1")
    pwd = os.environ["POSTGRES_PASSWORD"]
    engine = create_engine(
        f"postgresql+psycopg://soar:{pwd}@{host}:5432/soar_ioc", future=True
    )
    with Session(engine) as db:
        published = db.execute(
            select(Ioc).where(Ioc.status == IocStatus.PUBLISHED)
        ).scalars().all()

    if not published:
        print("aucun IOC PUBLISHED — PCAP non genere (rien a tester)")
        return 3

    frames: list[bytes] = []
    for ioc in published:
        if ioc.type == IocType.IP:
            frames.append(_eth(_tcp_syn(SRC_IP, ioc.value, 443)))
            print(f"  frame TCP SYN -> {ioc.value}:443")
        elif ioc.type in (IocType.DOMAIN, IocType.URL):
            frames.append(_dns_query(ioc.value))
            print(f"  frame DNS query -> {ioc.value}")

    if not frames:
        print("aucune frame a generer (types non supportes par ce generateur)")
        return 3

    PCAP_OUT.parent.mkdir(parents=True, exist_ok=True)
    with PCAP_OUT.open("wb") as fh:
        # Global header (magic, v2.4, snaplen 65535, LINKTYPE_ETHERNET)
        fh.write(struct.pack("<IHHIIII", 0xA1B2C3D4, 2, 4, 0, 0, 65535, 1))
        ts = 1794000000
        for i, frame in enumerate(frames):
            fh.write(struct.pack("<IIII", ts + i, 0, len(frame), len(frame)))
            fh.write(frame)

    print(f"PCAP labo synthetique: {PCAP_OUT.relative_to(ROOT)} ({len(frames)} frames)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
