"""Downsample a supersampled render and apply a gentle photographic grade."""
import sys
import numpy as np
from PIL import Image, ImageFilter

src, dst, w, h = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
strength = float(sys.argv[5]) if len(sys.argv) > 5 else 1.0

im = Image.open(src).convert('RGB').resize((w, h), Image.LANCZOS)
a = np.asarray(im).astype(np.float32) / 255.0

# soft S-curve for a bit more depth
c = 0.10 * strength
a = a + c * (a - 0.5) * (1 - np.abs(2 * a - 1))
# slight saturation reduction on greens (less "CG" lawn)
lum = (0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2])[..., None]
green = np.clip((a[..., 1:2] - np.maximum(a[..., 0:1], a[..., 2:3])) * 4, 0, 1)
a = a * (1 - 0.22 * green * strength) + lum * 0.22 * green * strength
# vignette
yy, xx = np.mgrid[0:h, 0:w]
r = np.sqrt(((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2)
v = 1 - 0.16 * strength * np.clip(r - 0.55, 0, None) ** 1.6
a = a * v[..., None]

out = Image.fromarray((np.clip(a, 0, 1) * 255 + 0.5).astype(np.uint8))
out = out.filter(ImageFilter.UnsharpMask(radius=1.2, percent=45, threshold=2))
out.save(dst, quality=94) if dst.lower().endswith('.jpg') else out.save(dst)
print('saved', dst)
