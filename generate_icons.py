#!/usr/bin/env python3
"""Generate dependency free PNG icons for the Chip Tips PWA."""
import struct
import zlib
from pathlib import Path

PALETTE = {
    "navy": (16, 36, 62),
    "aqua": (82, 192, 183),
    "cream": (246, 243, 235),
    "white": (255, 255, 255),
}

FONT = {
    "C": ["1111", "1000", "1000", "1000", "1000", "1000", "1111"],
    "T": ["11111", "00100", "00100", "00100", "00100", "00100", "00100"],
}


def png_chunk(kind, data):
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


def write_png(path, width, height, pixels):
    rows = []
    for y in range(height):
        rows.append(b"\x00" + bytes(pixels[y * width * 3:(y + 1) * width * 3]))
    raw = b"".join(rows)
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    data = b"\x89PNG\r\n\x1a\n" + png_chunk(b"IHDR", header) + png_chunk(b"IDAT", zlib.compress(raw, 9)) + png_chunk(b"IEND", b"")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def create_icon(size):
    pixels = list(PALETTE["navy"] * (size * size))

    def paint(x, y, color):
        if 0 <= x < size and 0 <= y < size:
            index = (y * size + x) * 3
            pixels[index:index + 3] = color

    center = size / 2
    radius = size * .34
    inner = size * .245
    for y in range(size):
        for x in range(size):
            distance = ((x - center) ** 2 + (y - center) ** 2) ** .5
            if distance <= radius:
                paint(x, y, PALETTE["aqua"])
            if distance <= inner:
                paint(x, y, PALETTE["cream"])
    block = max(3, size // 42)
    patterns = [("C", int(size * .31)), ("T", int(size * .53))]
    top = int(size * .40)
    for char, left in patterns:
        for row, line in enumerate(FONT[char]):
            for col, value in enumerate(line):
                if value == "1":
                    for dy in range(block):
                        for dx in range(block):
                            paint(left + col * block + dx, top + row * block + dy, PALETTE["navy"])
    return pixels


if __name__ == "__main__":
    root = Path(__file__).resolve().parent / "static" / "icons"
    for size in (192, 512):
        write_png(root / f"icon-{size}.png", size, size, create_icon(size))
        print(root / f"icon-{size}.png")
