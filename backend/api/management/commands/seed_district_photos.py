"""Generate one illustrative image per district.

Deliberately artwork, not photography. A stock photo labelled "Sylhet" would
imply it depicts Sylhet, and on a platform that cites sources for case data
that is exactly the kind of claim this project avoids. Instead each district
gets a generated map-style card whose colour and grid are derived from that
district's real coordinates, so the set looks varied and related without
claiming to show anything.

Idempotent: skips districts that already have a photo unless --force is given.
"""

import colorsys
import hashlib
import io
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction

from PIL import Image, ImageDraw

from api.models import City

WIDTH, HEIGHT = 800, 500
GRID = 40
# Brand-adjacent deep tones; each district picks one deterministically so the
# grid reads as a set rather than a random scatter.
PALETTE = [
    (6, 106, 78), (11, 42, 74), (18, 78, 92), (34, 60, 82),
    (12, 84, 66), (46, 74, 66), (24, 52, 88), (8, 92, 84),
]
ACCENT = (244, 42, 65)  # flag red, used only for the pin
# Approximate bounding box of Bangladesh, used to place a district on the card.
LON_SPAN, LAT_SPAN = 8.95, 6.20
LON_MIN, LAT_MAX = 88.05, 26.65

FONT_CANDIDATES = [
    r"C:\Windows\Fonts\segoeui.ttf", r"C:\Windows\Fonts\arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


def _seed(slug, salt=""):
    return int(hashlib.md5((slug + salt).encode()).hexdigest(), 16)


class Command(BaseCommand):
    help = "Generate one illustrative image per district (not a photograph)."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true",
                            help="Regenerate images for districts that already have one.")
        parser.add_argument("--only", help="Restrict to a single district slug.")

    def handle(self, *args, **options):
        districts = City.objects.all().order_by("name")
        if options["only"]:
            districts = districts.filter(slug=options["only"])
        if not districts:
            self.stdout.write(self.style.WARNING("No districts found. Run seed_demo first."))
            return

        made = skipped = 0
        for city in districts:
            if city.photo and not options["force"]:
                skipped += 1
                continue
            self._save(city, self._render(city))
            made += 1
            self.stdout.write(f"  + {city.slug}")

        self.stdout.write(self.style.SUCCESS(
            f"District artwork: {made} generated, {skipped} already present "
            f"(media under {Path(settings.MEDIA_ROOT) / 'district-photos'})"))

    def _save(self, city, image):
        """Store as JPEG and attach to the row, deleting any older file.

        The delete is best-effort: on Windows a previously-read File can still be
        locked, and failing to remove a stale file should not abort the run.
        """
        buffer = io.BytesIO()
        image.convert("RGB").save(buffer, format="JPEG", quality=86, optimize=True)
        buffer.seek(0)
        if city.photo:
            try:
                city.photo.delete(save=False)
            except OSError as error:
                self.stderr.write(f"  ! could not remove old photo for {city.slug}: {error}")
        city.photo.save(f"{city.slug}.jpg", ContentFile(buffer.read()), save=True)

    def _render(self, city):
        base = PALETTE[_seed(city.slug) % len(PALETTE)]
        image = Image.new("RGB", (WIDTH, HEIGHT), base)
        draw = ImageDraw.Draw(image, "RGBA")
        self._gradient(image, base)
        self._graticule(draw, city)
        self._contours(draw, city)
        self._pin(draw, city)
        return image

    def _gradient(self, image, base):
        """Vertical wash, lighter at the top, so the text has room to sit."""
        top = tuple(min(255, c + 46) for c in base)
        bottom = tuple(max(0, c - 26) for c in base)
        strip = Image.new("RGB", (1, HEIGHT))
        pixels = strip.load()
        for y in range(HEIGHT):
            t = y / max(1, HEIGHT - 1)
            pixels[0, y] = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        image.paste(strip.resize((WIDTH, HEIGHT)), (0, 0))

    def _graticule(self, draw, city):
        """A map-like grid, plus a marker at the district's true position.

        Jitter comes from a stable hash of the slug, so re-running the command
        reproduces the same image instead of shifting it around.
        """
        seed = _seed(city.slug, "grid")
        for x in range(0, WIDTH + 1, GRID):
            draw.line([(x, 0), (x, HEIGHT)], fill=(255, 255, 255, 16), width=1)
        for y in range(0, HEIGHT + 1, GRID):
            draw.line([(0, y), (WIDTH, y)], fill=(255, 255, 255, 16), width=1)

        # Faint "settlements" on a coarse lattice, for texture.
        step = GRID * 3
        for gx in range(step // 2, WIDTH, step):
            for gy in range(step // 2, HEIGHT, step):
                if ((gx * 31 + gy * 17 + seed) >> 3) % 11 < 3:
                    draw.rectangle([gx - 9, gy - 9, gx + 9, gy + 9], fill=(255, 255, 255, 10))

        if city.latitude is not None and city.longitude is not None:
            px, py = self._project(city)
            draw.ellipse([px - 5, py - 5, px + 5, py + 5], fill=(255, 255, 255, 70))

    def _project(self, city):
        """Place a district on the card using its real coordinates."""
        px = (city.longitude - LON_MIN) / LON_SPAN * WIDTH
        py = (LAT_MAX - city.latitude) / LAT_SPAN * HEIGHT
        return px, max(96, min(HEIGHT - 150, py))

    def _pin(self, draw, city):
        if city.latitude is None or city.longitude is None:
            return
        px, py = self._project(city)
        draw.ellipse([px - 16, py - 16, px + 16, py + 16], outline=ACCENT, width=3)
        draw.ellipse([px - 6, py - 6, px + 6, py + 6], fill=ACCENT)

    def _contours(self, draw, city):
        """Concentric rings around the district, so the card reads as a map
        tile rather than a flat colour swatch. The whole graphic is kept free
        of text: the UI already prints the district name, and a card crops the
        image to a short band, which sliced any label off the top.
        """
        if city.latitude is None or city.longitude is None:
            return
        px, py = self._project(city)
        for step in range(40, 420, 44):
            wobble = ((_seed(city.slug, f"c{step}") >> 5) % 13) - 6
            draw.ellipse([px - step + wobble, py - step * 0.72 + wobble,
                          px + step + wobble, py + step * 0.72 + wobble],
                         outline=(255, 255, 255, 20), width=2)

