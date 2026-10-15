#!/usr/bin/env python3
"""Convert the app's original PNG to bounded RGBA data for the startup UI."""
from pathlib import Path
import struct
import sys
from PIL import Image

image = Image.open(sys.argv[1]).convert('RGBA')
width, height = image.size
if not (0 < width <= 8192 and 0 < height <= 8192 and width * height <= 16777216):
    raise ValueError('startup artwork dimensions exceed the reader limit')
Path(sys.argv[2]).write_bytes(struct.pack('<III', 0x47425757, width, height) + image.tobytes())
