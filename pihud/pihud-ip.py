# pihud.py — CH1115 88x48 (landscape) @ 0x3C
# Shows multiple lines simultaneously and toggles every 5s between centered and right-aligned.
import time, board, busio
import adafruit_ssd1306
from smbus2 import SMBus

# ----- Hardware config -----
ADDR = 0x3C
W, H = 88, 48
PAGES = (H + 7) // 8

# ----- Orientation (rotation preset) -----
# ROTATE = 0 → normal
# ROTATE = 1 → rotated 180° (mirrored both axes)
ROTATE = 0

if ROTATE == 0:
    SEG = 0xA0        # normal segment remap
    COM = 0xC0        # normal COM scan
    X_OFFSET = 0
elif ROTATE == 1:
    SEG = 0xA1        # flipped segment remap
    COM = 0xC8        # flipped COM scan
    X_OFFSET = 39
else:
    raise ValueError("ROTATE must be 0 or 1")

START_LINE = 0

# ----- Low-level I2C helpers -----
def _cmd(b, *v): b.write_i2c_block_data(ADDR, 0x00, list(v))
def _data(b, ch):
    i = 0
    while i < len(ch):
        n = min(16, len(ch) - i)
        b.write_i2c_block_data(ADDR, 0x40, list(ch[i:i+n]))
        i += n
def _set_page_col(b, page, col):
    _cmd(b, 0xB0 | (page & 0x0F))         # select PAGE (8-row strip)
    _cmd(b, 0x00 | (col & 0x0F))          # column low nibble
    _cmd(b, 0x10 | ((col >> 4) & 0x0F))   # column high nibble

# ----- Display init / clear -----
def _init_for_48_rows(b):
    # Program 48-row glass and orientation
    _cmd(b, 0xAE)                          # display OFF
    _cmd(b, 0xA8, (H - 1) & 0x3F)          # multiplex = 47 -> 48 rows
    _cmd(b, 0xD3, START_LINE & 0x3F)       # display offset = 0
    _cmd(b, 0x40)                          # start line = 0
    _cmd(b, SEG)                           # segment remap (X mirror)
    _cmd(b, COM)                           # COM scan dir (Y flip)
    _cmd(b, 0xAF)                          # display ON

def _clear_all_pages(b):
    # Wipe up to 64 rows to avoid ghosting
    for p in range(8):
        _set_page_col(b, p, X_OFFSET)
        _data(b, bytes([0x00]) * W)

def init_panel():
    with SMBus(1) as b:
        _init_for_48_rows(b)
        _clear_all_pages(b)

# ----- Push ONLY the current framebuffer (no re-init; ideal for redraws) -----
def push_frame_only(buf):
    with SMBus(1) as b:
        for p in range(PAGES):             # PAGES = 48/8 = 6
            _set_page_col(b, p, X_OFFSET)
            start = p * W                  # byte index of this page in the buffer
            _data(b, buf[start:start + W])

# ----- Drawing helpers (use Adafruit SSD1306 framebuffer) -----
i2c = busio.I2C(board.SCL, board.SDA)
d = adafruit_ssd1306.SSD1306_I2C(W, H, i2c, addr=ADDR)

def text_width(s, char_w=6):
    # Built-in 5x8 font ~5px wide + 1px spacing
    return len(s) * char_w

def show_lines_align(lines, align="center", line_spacing=12, y_start=None):
    """
    Draw multiple lines, then push once (no flicker).

    - lines: list[str], e.g. ["Hello", "World", "Testing 123"]
    - align:
        * "left" / "center" / "right" (applies to all lines), OR
        * list/tuple of per-line aligns, same length as `lines`
          e.g. ["center", "left", "right"]
    - line_spacing: pixels between baselines (8px font -> 12 is comfy)
    - y_start: if None, lines are vertically centered; else top y for first line
    """
    # Normalize align(s)
    if isinstance(align, (list, tuple)):
        aligns = list(align)
        if len(aligns) != len(lines):
            raise ValueError("When align is a list/tuple, its length must match lines")
    else:
        aligns = [align] * len(lines)

    d.fill(0)
    n = len(lines)
    font_h = 8
    total_h = n*font_h + (n-1)*line_spacing
    if y_start is None:
        y0 = max(0, (H - total_h)//2)  # vertical centering
    else:
        y0 = y_start

    for i, s in enumerate(lines):
        a = aligns[i]
        if a == "right":
            x = W - text_width(s)
        elif a == "left":
            x = 2
        else:  # center
            x = max(0, (W - text_width(s)) // 2)
        y = y0 + i*(font_h + line_spacing)
        if 0 <= y <= H - font_h:       # stay in-bounds (no wrapping)
            d.text(s, x, y, 1)

    push_frame_only(d.buffer)

# ---- your data sources ----
from list_ips import get_hostname, get_ip_strings

# ----- Main loop: hostname always centered, body flips left<->right -----
if __name__ == "__main__":
    init_panel()

    HOST = get_hostname()
    IPS  = get_ip_strings(only_up=True)

    # Fit to your display rows (e.g., 3 total rows → 1 header + 2 body)
    MAX_ROWS  = 3
    BODY_ROWS = max(0, MAX_ROWS - 1)
    BODY      = (IPS[:BODY_ROWS] + [""] * BODY_ROWS)[:BODY_ROWS]
    LINES     = [HOST] + BODY

    INTERVAL_SEC = 5
    flip = False

    try:
        while True:
            body_align = "right" if flip else "left"
            # per-line aligns: keep first centered, rest flip
            ALIGNS = ["center"] + [body_align] * len(BODY)

            show_lines_align(LINES, align=ALIGNS, line_spacing=0, y_start=None)
            time.sleep(INTERVAL_SEC)

            flip = not flip
    except KeyboardInterrupt:
        with SMBus(1) as b:
            _clear_all_pages(b)
