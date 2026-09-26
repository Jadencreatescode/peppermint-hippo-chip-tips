"""Minimal, dependency free PNG reader used by the app icon checks.

The test suite deliberately avoids Pillow so it can run anywhere.  Only 8 bit
RGB (colour type 2) and RGBA (colour type 6), non interlaced PNG files are
supported, which is exactly what the icon build script writes.
"""

import struct
import zlib
from pathlib import Path

SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _chunks(blob):
    position = len(SIGNATURE)
    while position + 8 <= len(blob):
        length, name = struct.unpack(">I4s", blob[position:position + 8])
        yield name, blob[position + 8:position + 8 + length]
        position += 12 + length


def _unfilter(raw, width, height, channels):
    stride = width * channels
    previous = bytearray(stride)
    rows = []
    position = 0
    for _ in range(height):
        kind = raw[position]
        position += 1
        line = bytearray(raw[position:position + stride])
        position += stride
        if kind == 1:
            for i in range(channels, stride):
                line[i] = (line[i] + line[i - channels]) & 0xFF
        elif kind == 2:
            for i in range(stride):
                line[i] = (line[i] + previous[i]) & 0xFF
        elif kind == 3:
            for i in range(stride):
                left = line[i - channels] if i >= channels else 0
                line[i] = (line[i] + ((left + previous[i]) >> 1)) & 0xFF
        elif kind == 4:
            for i in range(stride):
                left = line[i - channels] if i >= channels else 0
                up = previous[i]
                corner = previous[i - channels] if i >= channels else 0
                estimate = left + up - corner
                distances = (abs(estimate - left), abs(estimate - up), abs(estimate - corner))
                predictor = (left, up, corner)[distances.index(min(distances))]
                line[i] = (line[i] + predictor) & 0xFF
        elif kind != 0:
            raise ValueError(f"unsupported PNG filter {kind}")
        rows.append(bytes(line))
        previous = line
    return rows


class PngImage:
    """Just enough image handling for the icon assertions."""

    def __init__(self, path):
        self.path = Path(path)
        blob = self.path.read_bytes()
        if not blob.startswith(SIGNATURE):
            raise ValueError(f"{self.path} is not a PNG file")
        header = None
        payload = bytearray()
        for name, data in _chunks(blob):
            if name == b"IHDR":
                header = struct.unpack(">IIBBBBB", data)
            elif name == b"IDAT":
                payload += data
        if header is None:
            raise ValueError(f"{self.path} has no IHDR chunk")
        width, height, depth, colour, compression, filtering, interlace = header
        if (depth, colour, interlace, compression, filtering) != (8, colour, 0, 0, 0) or colour not in (2, 6):
            raise ValueError(
                f"unsupported PNG format in {self.path}: depth={depth} colour={colour} interlace={interlace}"
            )
        self.width = width
        self.height = height
        self.channels = 3 if colour == 2 else 4
        self.rows = _unfilter(zlib.decompress(bytes(payload)), width, height, self.channels)
        self._luminance = None
        self._alpha_min = None

    def _grey(self):
        if self._luminance is None:
            channels = self.channels
            self._luminance = [
                [sum(row[index:index + 3]) // 3 for index in range(0, len(row), channels)] for row in self.rows
            ]
            if channels == 4:
                self._alpha_min = min(min(row[3::4]) for row in self.rows)
            else:
                self._alpha_min = 255
        return self._luminance

    def min_alpha(self):
        self._grey()
        return self._alpha_min

    def mean_luminance(self):
        grey = self._grey()
        return sum(sum(row) for row in grey) / (self.width * self.height)

    def dark_ratio(self, threshold=128):
        grey = self._grey()
        dark = sum(1 for row in grey for value in row if value < threshold)
        return dark / (self.width * self.height)

    def content_box(self, threshold=128):
        """Bounding box of the non background (dark) pixels as (left, top, right, bottom)."""
        grey = self._grey()
        left, top, right, bottom = self.width, self.height, -1, -1
        for y, row in enumerate(grey):
            for x, value in enumerate(row):
                if value < threshold:
                    left = min(left, x)
                    right = max(right, x)
                    top = min(top, y)
                    bottom = max(bottom, y)
        if right < 0:
            raise AssertionError(f"{self.path} contains no dark pixels")
        return left, top, right, bottom

    def content_half_diagonal(self, threshold=128):
        """Half of the content diagonal length, expressed as a fraction of the icon width.

        An Android maskable icon is only guaranteed to show the centre circle of
        its 80 percent diameter, so this value must stay at or below 0.4.
        """
        left, top, right, bottom = self.content_box(threshold)
        width = right - left + 1
        height = bottom - top + 1
        return 0.5 * (width ** 2 + height ** 2) ** 0.5 / self.width

    def content_column_groups(self, threshold=128, minimum=1):
        """Number of separate vertical blocks of dark pixels, one per letter."""
        grey = self._grey()
        counts = [sum(1 for row in grey if row[x] < threshold) for x in range(self.width)]
        groups = 0
        inside = False
        for count in counts:
            if count >= minimum and not inside:
                groups += 1
                inside = True
            elif count < minimum:
                inside = False
        return groups


def read_png(path):
    return PngImage(path)
