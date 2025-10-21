#!/usr/bin/env python3
"""
pihud-kismet.py

Displays Kismet counts (AP/Wifi/BT) and script uptime on a 88x48 CH1115 OLED.
All lines left-aligned.
"""

import time
import board
import busio
from smbus2 import SMBus
import adafruit_ssd1306

from kismet_feed import get_counts, get_gps_status


# ----- Hardware config -----
ADDR = 0x3C
W, H = 88, 48
PAGES = (H + 7) // 8

SEG = 0xA0
COM = 0xC0
X_OFFSET = 0
START_LINE = 0

# ----- Low-level I2C helpers -----
def _cmd(b, *v):
    b.write_i2c_block_data(ADDR, 0x00, list(v))

def _data(b, ch):
    i = 0
    while i < len(ch):
        n = min(16, len(ch) - i)
        b.write_i2c_block_data(ADDR, 0x40, list(ch[i:i+n]))
        i += n

def _set_page_col(b, page, col):
    _cmd(b, 0xB0 | (page & 0x0F))
    _cmd(b, 0x00 | (col & 0x0F))
    _cmd(b, 0x10 | ((col >> 4) & 0x0F))

# ----- Display init / clear -----
def _init_for_48_rows(b):
    _cmd(b, 0xAE)
    _cmd(b, 0xA8, (H - 1) & 0x3F)
    _cmd(b, 0xD3, START_LINE & 0x3F)
    _cmd(b, 0x40)
    _cmd(b, SEG)
    _cmd(b, COM)
    _cmd(b, 0xAF)

def _clear_all_pages(b):
    for p in range(8):
        _set_page_col(b, p, X_OFFSET)
        _data(b, bytes([0x00]) * W)

def init_panel():
    with SMBus(1) as b:
        _init_for_48_rows(b)
        _clear_all_pages(b)

def push_frame_only(buf):
    with SMBus(1) as b:
        for p in range(PAGES):
            _set_page_col(b, p, X_OFFSET)
            start = p * W
            _data(b, buf[start:start + W])

# ----- Drawing helpers -----
i2c = busio.I2C(board.SCL, board.SDA)
d = adafruit_ssd1306.SSD1306_I2C(W, H, i2c, addr=ADDR)

def text_width(s, char_w=6):
    return len(s) * char_w

def show_lines_align(lines, align="left", line_spacing=12, y_start=None):
    # Force all lines left-aligned
    d.fill(0)
    n = len(lines)
    font_h = 8
    total_h = n * font_h + (n - 1) * line_spacing
#    y0 = (H - total_h)//2 if y_start is None else y_start
    y0 = 2 if y_start is None else y_start  # small top padding to show first line

    for i, s in enumerate(lines):
        x = 2  # always left
        y = y0 + i * (font_h + line_spacing)
        if 0 <= y <= H - font_h:
            d.text(s, x, y, 1)

    push_frame_only(d.buffer)

# ----- Main loop -----
if __name__ == "__main__":
    init_panel()
    INTERVAL_SEC = 5
    script_start = time.time()

    try:
        while True:
            # Calculate script uptime
            elapsed = int(time.time() - script_start)
            hh = elapsed // 3600
            mm = (elapsed % 3600) // 60
            ss = elapsed % 60
            uptime_line = f"Up {hh:02}:{mm:02}:{ss:02}"

            # Get Kismet counts
            counts = get_counts()
            gps_status = get_gps_status()
            lines = [
                uptime_line,
                f"AP: {counts['ap']}",
                f"Wifi: {counts['wifi']}",
                f"BT: {counts['bt']}",
                f"GPS: {gps_status}",
            ]

            # Show all lines left-aligned
            show_lines_align(lines, align="left", line_spacing=0, y_start=8)

            time.sleep(INTERVAL_SEC)

    except KeyboardInterrupt:
        with SMBus(1) as b:
            _clear_all_pages(b)
