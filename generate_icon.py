"""
Generate BELLA AI icon - purple gradient with stylized B + sparkle.
Run once: python generate_icon.py
"""
from PIL import Image, ImageDraw
import math, os


def _gradient_bg(size, c1, c2):
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    for y in range(size):
        t = y / (size - 1)
        r = int(c1[0] + (c2[0] - c1[0]) * t)
        g = int(c1[1] + (c2[1] - c1[1]) * t)
        b = int(c1[2] + (c2[2] - c1[2]) * t)
        draw.line([(0, y), (size - 1, y)], fill=(r, g, b, 255))
    radius = max(4, int(size * 0.22))
    mask = Image.new('L', (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, size-1, size-1], radius=radius, fill=255)
    img.putalpha(mask)
    return img


def _shine(size):
    layer = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    draw.ellipse([-size // 3, -size // 3, size * 0.85, size * 0.55],
                 fill=(255, 255, 255, 28))
    return layer


def _star4(draw, cx, cy, r, color):
    """4-pointed star (sparkle)."""
    pts = []
    inner = r * 0.30
    for i in range(8):
        angle = math.radians(i * 45 - 90)
        radius = r if i % 2 == 0 else inner
        pts.append((cx + math.cos(angle) * radius,
                    cy + math.sin(angle) * radius))
    draw.polygon(pts, fill=color)


def _letter_b(draw, cx, cy, h, white):
    """Geometric bold B: spine + two right-side bumps."""
    spine_w = h * 0.175
    spine_x0 = cx - h * 0.28
    spine_x1 = spine_x0 + spine_w
    top = cy - h / 2
    bot = cy + h / 2
    mid = cy - h * 0.04

    # Spine
    draw.rectangle([spine_x0, top, spine_x1, bot], fill=white)

    # Top bump
    br_top = (mid - top) * 0.94
    bbox_top = [spine_x1 - 3, top, spine_x1 + br_top * 2 - 3, mid + 3]
    draw.pieslice(bbox_top, start=-90, end=90, fill=white)
    # Cover inner gap
    draw.rectangle([spine_x1 - 3, top + 2, spine_x1 + 3, mid + 2], fill=white)

    # Bottom bump (slightly larger)
    br_bot = (bot - mid) * 0.96
    bbox_bot = [spine_x1 - 3, mid - 3, spine_x1 + br_bot * 2 - 3, bot]
    draw.pieslice(bbox_bot, start=-90, end=90, fill=white)
    draw.rectangle([spine_x1 - 3, mid - 2, spine_x1 + 3, bot - 2], fill=white)


def create_bella_icon(size=256):
    # Background: violet-700 → purple-900
    img = _gradient_bg(size, (109, 40, 217), (59, 7, 100))

    # Shine overlay
    img = Image.alpha_composite(img, _shine(size))

    draw = ImageDraw.Draw(img)
    white = (255, 255, 255, 245)

    # Letter B — centered slightly left
    cx = size * 0.44
    cy = size * 0.50
    _letter_b(draw, cx, cy, size * 0.58, white)

    # Sparkle star — top-right quadrant
    star_cx = size * 0.735
    star_cy = size * 0.255
    star_r  = size * 0.095
    _star4(draw, star_cx, star_cy, star_r, (253, 224, 71, 245))   # yellow-300

    # Tiny second star — bottom-left of main star
    _star4(draw, star_cx - size * 0.13, star_cy + size * 0.16,
           star_r * 0.40, (253, 224, 71, 170))

    # Very tiny dot star
    _star4(draw, star_cx + size * 0.07, star_cy + size * 0.24,
           star_r * 0.22, (253, 224, 71, 120))

    return img


def build_ico(out_path='bella_icon.ico'):
    sizes = [256, 128, 64, 48, 32, 16]
    frames = []
    for s in sizes:
        icon = create_bella_icon(s)
        # Convert to RGBA for ICO compatibility
        frames.append(icon.convert('RGBA'))
    # Save multi-size ICO
    frames[0].save(
        out_path,
        format='ICO',
        sizes=[(s, s) for s in sizes],
        append_images=frames[1:],
    )
    print(f'Saved: {out_path}  ({os.path.getsize(out_path)//1024} KB)')

    # Also save 512px PNG for web/manifest
    big = create_bella_icon(512)
    big.save('bella_icon_512.png', format='PNG')
    print('Saved: bella_icon_512.png')


if __name__ == '__main__':
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    build_ico()
