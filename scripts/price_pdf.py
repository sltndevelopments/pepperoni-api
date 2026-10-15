#!/usr/bin/env python3
"""Build prices.pdf from catalog rows without Chrome.

Embeds DejaVuSans (system TTF) as a Type0 CID font so Cyrillic survives.
Used when snap Chromium --print-to-pdf fails on the VPS.
"""
from __future__ import annotations

import struct
import zlib
from pathlib import Path

DEJAVU = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
DEJAVU_BOLD = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")


def _tables(data: bytes) -> dict[bytes, bytes]:
    n = struct.unpack_from(">H", data, 4)[0]
    out: dict[bytes, bytes] = {}
    off = 12
    for _ in range(n):
        tag = data[off : off + 4]
        _csum, offset, length = struct.unpack_from(">III", data, off + 4)
        out[tag] = data[offset : offset + length]
        off += 16
    return out


def _u16(buf: bytes, i: int) -> int:
    return struct.unpack_from(">H", buf, i)[0]


def _i16(buf: bytes, i: int) -> int:
    return struct.unpack_from(">h", buf, i)[0]


def _cmap_map(cmap: bytes) -> dict[int, int]:
    n = _u16(cmap, 2)
    mapping: dict[int, int] = {}
    rec = 4
    best = None
    for _ in range(n):
        plat, enc, offset = struct.unpack_from(">HHI", cmap, rec)
        rec += 8
        if plat == 3 and enc in (1, 10):
            best = offset
            if enc == 10:
                break
        elif plat == 0 and best is None:
            best = offset
    if best is None:
        return mapping
    sub = cmap[best:]
    fmt = _u16(sub, 0)
    if fmt == 4:
        seg = _u16(sub, 6) // 2
        end = [_u16(sub, 14 + 2 * i) for i in range(seg)]
        start_off = 16 + 2 * seg
        start = [_u16(sub, start_off + 2 * i) for i in range(seg)]
        delta_off = start_off + 2 * seg
        delta = [_i16(sub, delta_off + 2 * i) for i in range(seg)]
        ro_off = delta_off + 2 * seg
        ro = [_u16(sub, ro_off + 2 * i) for i in range(seg)]
        for i in range(seg):
            for cp in range(start[i], end[i] + 1):
                if ro[i] == 0:
                    gid = (cp + delta[i]) & 0xFFFF
                else:
                    idx = ro_off + 2 * i + ro[i] + 2 * (cp - start[i])
                    gid = _u16(sub, idx)
                    if gid:
                        gid = (gid + delta[i]) & 0xFFFF
                if gid:
                    mapping[cp] = gid
    elif fmt == 12:
        n_groups = struct.unpack_from(">I", sub, 12)[0]
        p = 16
        for _ in range(n_groups):
            start, end, start_gid = struct.unpack_from(">III", sub, p)
            p += 12
            for i, cp in enumerate(range(start, end + 1)):
                mapping[cp] = start_gid + i
    return mapping


def _hmtx_widths(tables: dict[bytes, bytes]) -> tuple[int, list[int]]:
    head = tables[b"head"]
    units = _u16(head, 18)
    hhea = tables[b"hhea"]
    n_metrics = _u16(hhea, 34)
    hmtx = tables[b"hmtx"]
    widths = []
    for i in range(n_metrics):
        widths.append(_u16(hmtx, i * 4))
    last = widths[-1] if widths else 0
    maxp = tables[b"maxp"]
    n_glyphs = _u16(maxp, 4)
    extra = 2 * n_metrics
    for i in range(n_glyphs - n_metrics):
        widths.append(last)
        extra += 2
    pdf_w = [round(w * 1000 / units) if units else 0 for w in widths]
    return units, pdf_w


class _Font:
    def __init__(self, path: Path):
        self.data = path.read_bytes()
        tables = _tables(self.data)
        self.cmap = _cmap_map(tables[b"cmap"])
        _units, self.widths = _hmtx_widths(tables)
        head = tables[b"head"]
        self.xmin, self.ymin, self.xmax, self.ymax = struct.unpack_from(">hhhh", head, 36)
        hhea = tables[b"hhea"]
        self.ascent = _i16(hhea, 4)
        self.descent = _i16(hhea, 6)
        units = _u16(head, 18) or 1000
        scale = 1000 / units
        self.bbox = [round(v * scale) for v in (self.xmin, self.ymin, self.xmax, self.ymax)]
        self.ascent_pdf = round(self.ascent * scale)
        self.descent_pdf = round(self.descent * scale)

    def gids(self, text: str) -> list[int]:
        out = []
        for ch in text:
            gid = self.cmap.get(ord(ch), self.cmap.get(32, 0))
            out.append(gid)
        return out

    def width_pt(self, text: str, size: float) -> float:
        w = 0
        for gid in self.gids(text):
            if 0 <= gid < len(self.widths):
                w += self.widths[gid]
        return w * size / 1000.0


def _pdf_str_gids(gids: list[int]) -> str:
    return "<" + "".join(f"{g:04X}" for g in gids) + ">"


def _escape_name(name: str) -> str:
    return "".join(ch if ch.isalnum() else "-" for ch in name)


def write_catalog_pdf(dest: Path, title: str, subtitle: list[str],
                      headers: list[str], rows: list[list[str]]) -> None:
    """Write a landscape A4 table PDF. All strings are Unicode."""
    regular = _Font(DEJAVU)
    bold_path = DEJAVU_BOLD if DEJAVU_BOLD.is_file() else DEJAVU
    bold = _Font(bold_path)
    page_w, page_h = 841.89, 595.28  # A4 landscape
    margin = 24
    header_h = 56 + 12 * len(subtitle)
    row_h = 12
    col_w = [
        48, 190, 48, 58, 52, 48, 40, 52, 70, 70, 55,
    ]
    while len(col_w) < len(headers):
        col_w.append(50)
    col_w = col_w[: len(headers)]
    usable = page_w - 2 * margin
    scale = usable / sum(col_w)
    col_w = [c * scale for c in col_w]
    rows_per_page = max(1, int((page_h - margin - header_h - 20) // row_h) - 1)

    def cell_fit(text: str, width: float, size: float, font: _Font) -> str:
        text = " ".join(str(text).split())
        if font.width_pt(text, size) <= width - 3:
            return text
        while text and font.width_pt(text + "…", size) > width - 3:
            text = text[:-1]
        return text + "…"

    pages: list[list[list[str]]] = []
    for i in range(0, len(rows), rows_per_page):
        pages.append(rows[i : i + rows_per_page])
    if not pages:
        pages = [[]]

    objects: list[bytes] = []

    def add(obj: bytes) -> int:
        objects.append(obj)
        return len(objects)

    font_objs = []
    for tag, font in (("F1", regular), ("F2", bold)):
        fontfile = zlib.compress(font.data)
        ff_id = add(
            f"<< /Length {len(fontfile)} /Length1 {len(font.data)} /Filter /FlateDecode >>".encode()
            + b"\nstream\n" + fontfile + b"\nendstream"
        )
        fd_id = add(
            (
                f"<< /Type /FontDescriptor /FontName /{_escape_name('DejaVuSans')} "
                f"/Flags 4 /FontBBox [{' '.join(str(x) for x in font.bbox)}] "
                f"/ItalicAngle 0 /Ascent {font.ascent_pdf} /Descent {font.descent_pdf} "
                f"/CapHeight {font.ascent_pdf} /StemV 80 /FontFile2 {ff_id} 0 R >>"
            ).encode()
        )
        w_chunks = []
        for gid, w in enumerate(font.widths):
            if w:
                w_chunks.append(f"{gid} [{w}]")
        cid_id = add(
            (
                f"<< /Type /Font /Subtype /CIDFontType2 /BaseFont /DejaVuSans "
                f"/CIDSystemInfo << /Registry (Adobe) /Ordering (Identity) /Supplement 0 >> "
                f"/FontDescriptor {fd_id} 0 R /DW 500 /W [{' '.join(w_chunks)}] "
                f"/CIDToGIDMap /Identity >>"
            ).encode()
        )
        type0 = add(
            (
                f"<< /Type /Font /Subtype /Type0 /BaseFont /DejaVuSans "
                f"/Encoding /Identity-H /DescendantFonts [{cid_id} 0 R] >>"
            ).encode()
        )
        font_objs.append((tag, type0, font))

    page_ids = []
    content_ids = []

    def draw_page(page_rows: list[list[str]], page_no: int, page_count: int) -> str:
        cmds = ["BT"]
        y = page_h - margin - 14
        cmds.append(f"/F2 12 Tf 1 0 0 1 {margin:.2f} {y:.2f} Tm {_pdf_str_gids(bold.gids(title))} Tj")
        y -= 14
        cmds.append("/F1 8 Tf")
        for line in subtitle:
            cmds.append(f"1 0 0 1 {margin:.2f} {y:.2f} Tm {_pdf_str_gids(regular.gids(line))} Tj")
            y -= 11
        y -= 6
        x = margin
        cmds.append("/F2 7 Tf")
        for i, h in enumerate(headers):
            txt = cell_fit(h, col_w[i], 7, bold)
            cmds.append(f"1 0 0 1 {x + 1:.2f} {y:.2f} Tm {_pdf_str_gids(bold.gids(txt))} Tj")
            x += col_w[i]
        y -= row_h
        cmds.append("/F1 7 Tf")
        for row in page_rows:
            x = margin
            for i, cell in enumerate(row):
                txt = cell_fit(cell, col_w[i], 7, regular)
                cmds.append(
                    f"1 0 0 1 {x + 1:.2f} {y:.2f} Tm {_pdf_str_gids(regular.gids(txt))} Tj"
                )
                x += col_w[i]
            y -= row_h
        foot = f"{page_no}/{page_count}"
        cmds.append(
            f"1 0 0 1 {page_w - margin - 30:.2f} {margin:.2f} Tm {_pdf_str_gids(regular.gids(foot))} Tj"
        )
        cmds.append("ET")
        return "\n".join(cmds)

    n_pages = len(pages)
    for idx, prow in enumerate(pages, 1):
        stream = draw_page(prow, idx, n_pages).encode("latin-1", "replace")
        compressed = zlib.compress(stream)
        cid = add(
            f"<< /Length {len(compressed)} /Filter /FlateDecode >>".encode()
            + b"\nstream\n" + compressed + b"\nendstream"
        )
        content_ids.append(cid)

    pages_id = len(objects) + 1 + n_pages  # placeholder; we'll append pages then kids
    # page objects first, then pages node, then catalog
    page_obj_ids = []
    for cid in content_ids:
        pid = add(b"__PAGE__")  # replaced below
        page_obj_ids.append(pid)

    pages_node = add(b"__PAGES__")
    catalog = add(b"__CAT__")

    for i, pid in enumerate(page_obj_ids):
        objects[pid - 1] = (
            f"<< /Type /Page /Parent {pages_node} 0 R /MediaBox [0 0 {page_w:.2f} {page_h:.2f}] "
            f"/Resources << /Font << /F1 {font_objs[0][1]} 0 R /F2 {font_objs[1][1]} 0 R >> >> "
            f"/Contents {content_ids[i]} 0 R >>"
        ).encode()
    kids = " ".join(f"{pid} 0 R" for pid in page_obj_ids)
    objects[pages_node - 1] = (
        f"<< /Type /Pages /Kids [{kids}] /Count {n_pages} >>"
    ).encode()
    objects[catalog - 1] = (
        f"<< /Type /Catalog /Pages {pages_node} 0 R >>"
    ).encode()

    buf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for i, obj in enumerate(objects, 1):
        offsets.append(len(buf))
        buf.extend(f"{i} 0 obj\n".encode())
        buf.extend(obj)
        buf.extend(b"\nendobj\n")
    xref = len(buf)
    buf.extend(f"xref\n0 {len(objects) + 1}\n".encode())
    buf.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        buf.extend(f"{off:010d} 00000 n \n".encode())
    buf.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root {catalog} 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    )
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(bytes(buf))
