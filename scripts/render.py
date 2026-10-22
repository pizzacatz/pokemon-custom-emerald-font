"""Render text with the built TTFs using FreeType (via freetype-py) into PIL images."""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from common import *
import freetype
from PIL import Image, ImageDraw

FONTS = {
    'exact': 'EmeraldPixelVector-Regular.ttf',
    'rounded': 'EmeraldPixelSoft-Regular.ttf',
    'smooth': 'EmeraldRounded-Regular.ttf',
    'smoothgame': 'EmeraldRoundedGame-Regular.ttf',
}

def font_path(key):
    return os.path.join(BUILD, 'fonts', FONTS.get(key, key))

def render_line(text, key, px, hinting=False, color=(0, 0, 0), bg=(255, 255, 255), pad=4, mono=False):
    """Return (image, missing) rendering `text` at `px` pixel size using the font's own metrics."""
    face = freetype.Face(font_path(key))
    face.set_char_size(px*64)
    asc = face.size.ascender >> 6; desc = -(face.size.descender >> 6)
    H = asc + desc + 2*pad
    # measure
    pen = pad; missing = []
    flags = freetype.FT_LOAD_DEFAULT if hinting else freetype.FT_LOAD_NO_HINTING
    if mono:
        flags |= freetype.FT_LOAD_TARGET_MONO
    glyphs = []
    for ch in text:
        gi = face.get_char_index(ord(ch))
        if gi == 0 and ch != '�':
            missing.append(ch)
        face.load_glyph(gi, flags)
        face.glyph.render(freetype.FT_RENDER_MODE_MONO if mono else freetype.FT_RENDER_MODE_NORMAL)
        bm = face.glyph.bitmap
        glyphs.append((pen + face.glyph.bitmap_left, pad + asc - face.glyph.bitmap_top, bm.width, bm.rows, bm.pitch, bytes(bm.buffer), mono))
        pen += face.glyph.advance.x >> 6
    W = pen + pad
    im = Image.new('RGB', (W, H), bg)
    px_ = im.load()
    for x0, y0, w, h, pitch, buf, m in glyphs:
        for y in range(h):
            for x in range(w):
                if m:
                    v = 255 if (buf[y*pitch + x//8] >> (7 - x % 8)) & 1 else 0
                else:
                    v = buf[y*pitch + x]
                if v and 0 <= x0+x < W and 0 <= y0+y < H:
                    a = v/255
                    o = px_[x0+x, y0+y]
                    px_[x0+x, y0+y] = tuple(int(o[i]*(1-a) + color[i]*a) for i in range(3))
    return im, missing

def stack(images, gap=6, bg=(255, 255, 255), label_w=0):
    W = max(i.width for i in images) + label_w
    H = sum(i.height for i in images) + gap*(len(images)-1)
    out = Image.new('RGB', (W, H), bg); y = 0
    for i in images:
        out.paste(i, (label_w, y)); y += i.height + gap
    return out

def label(im, text, w=150):
    out = Image.new('RGB', (im.width + w, im.height), (255, 255, 255))
    out.paste(im, (w, 0)); ImageDraw.Draw(out).text((4, max(0, im.height//2 - 5)), text, fill=(90, 90, 90))
    return out
