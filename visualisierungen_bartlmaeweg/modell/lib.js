// Helpers: noise, procedural textures, geometry utilities
import * as THREE from 'three';

// ---------- noise ----------
export function hash2(x, y, s = 0) {
  let h = Math.imul(x | 0, 374761393) ^ Math.imul(y | 0, 668265263) ^ Math.imul(s | 0, 1442695041);
  h = Math.imul(h ^ (h >>> 13), 1274126177);
  h ^= h >>> 16;
  return (h >>> 0) / 4294967296;
}
function mod(a, p) { return ((a % p) + p) % p; }
export function vnoise(x, y, s = 0, px = 0, py = 0) {
  const xi = Math.floor(x), yi = Math.floor(y);
  const xf = x - xi, yf = y - yi;
  const u = xf * xf * (3 - 2 * xf), v = yf * yf * (3 - 2 * yf);
  const X0 = px ? mod(xi, px) : xi, X1 = px ? mod(xi + 1, px) : xi + 1;
  const Y0 = py ? mod(yi, py) : yi, Y1 = py ? mod(yi + 1, py) : yi + 1;
  const a = hash2(X0, Y0, s), b = hash2(X1, Y0, s), c = hash2(X0, Y1, s), d = hash2(X1, Y1, s);
  return a + (b - a) * u + (c - a) * v + (a - b - c + d) * u * v;
}
// periodic fbm: px,py = base period in noise units (0 = none)
export function fbm(x, y, oct = 5, s = 0, px = 0, py = 0) {
  let sum = 0, amp = 0.5, f = 1, n = 0;
  for (let i = 0; i < oct; i++) {
    sum += amp * vnoise(x * f, y * f, s + i * 31, px * f, py * f);
    n += amp; amp *= 0.5; f *= 2;
  }
  return sum / n;
}
export function vnoise3(x, y, z, s = 0) {
  const zi = Math.floor(z), zf = z - zi, w = zf * zf * (3 - 2 * zf);
  const a = vnoise(x, y, s + zi * 7919), b = vnoise(x, y, s + (zi + 1) * 7919);
  return a + (b - a) * w;
}
export function rng(seed) {
  let s = seed >>> 0;
  return () => { s = (Math.imul(s, 1664525) + 1013904223) >>> 0; return s / 4294967296; };
}

// ---------- canvas textures ----------
function canvas(w, h) { const c = document.createElement('canvas'); c.width = w; c.height = h; return c; }
function toTex(c, srgb = true, aniso = 8) {
  const t = new THREE.CanvasTexture(c);
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.anisotropy = aniso;
  if (srgb) t.colorSpace = THREE.SRGBColorSpace;
  t.generateMipmaps = true;
  t.minFilter = THREE.LinearMipmapLinearFilter;
  return t;
}
function pixelFill(w, h, fn) {
  const c = canvas(w, h), ctx = c.getContext('2d');
  const img = ctx.createImageData(w, h), d = img.data;
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
    const [r, g, b, a = 255] = fn(x, y);
    const i = (y * w + x) * 4;
    d[i] = r; d[i + 1] = g; d[i + 2] = b; d[i + 3] = a;
  }
  ctx.putImageData(img, 0, 0);
  return c;
}
const clamp = (v, a = 0, b = 255) => Math.max(a, Math.min(b, v));

// vertical board cladding. covers `meters` (square), `boards` boards across.
export function woodTextures({ size = 1024, boards = 8, base = [200, 160, 118], seed = 1, weather = 0 } = {}) {
  const bw = size / boards;
  const tones = [];
  const r = rng(seed);
  for (let i = 0; i < boards; i++) tones.push([0.86 + r() * 0.22, (r() - 0.5) * 0.06]);
  const knots = [];
  for (let i = 0; i < boards * 0.9; i++) knots.push([r() * size, r() * size, 3 + r() * 6]);
  const lum = new Float32Array(size * size);
  const col = pixelFill(size, size, (x, y) => {
    const bi = Math.floor(x / bw), lx = x - bi * bw;
    const [tone, hueShift] = tones[bi];
    // long grain streaks
    const g1 = fbm(lx * 0.09 + bi * 13.7, y * 4 / size, 4, seed + bi, 0, 4);
    const g2 = vnoise(lx * 0.6 + bi * 5.1, y * 40 / size, seed + 99 + bi, 0, 40);
    let k = tone * (0.88 + 0.22 * g1 + 0.07 * (g2 - 0.5));
    // knots
    for (const [kx, ky, kr] of knots) {
      const dx = x - kx, dy = (y - ky) * 0.55;
      const dd = Math.sqrt(dx * dx + dy * dy);
      if (dd < kr * 2.2) k *= 0.72 + 0.28 * Math.min(1, dd / (kr * 2.2));
    }
    // groove + bevel
    let edge = 1;
    if (lx < 2.2) edge = 0.28;
    else if (lx < 4) edge = 1.1;
    else if (lx > bw - 2.5) edge = 0.82;
    k *= edge;
    lum[y * size + x] = edge < 0.5 ? 0.1 : 0.55 + 0.25 * g1;
    let R = base[0] * k, G = base[1] * k * (1 + hueShift), B = base[2] * k * (1 - hueShift);
    if (weather) { const m = (R + G + B) / 3; R = R + (m * 1.02 - R) * weather; G = G + (m - G) * weather; B = B + (m * 1.03 - B) * weather; }
    return [clamp(R), clamp(G), clamp(B)];
  });
  const bump = pixelFill(size, size, (x, y) => { const v = lum[y * size + x] * 255; return [v, v, v]; });
  return { map: toTex(col), bump: toTex(bump, false) };
}

export function plasterTextures({ size = 512, base = [238, 236, 230], seed = 3 } = {}) {
  const col = pixelFill(size, size, (x, y) => {
    const n = fbm(x / size * 8, y / size * 8, 5, seed, 8, 8);
    const f = vnoise(x * 0.9, y * 0.9, seed + 5, size * 0.9, size * 0.9);
    const k = 0.96 + 0.05 * n + 0.025 * (f - 0.5);
    return [clamp(base[0] * k), clamp(base[1] * k), clamp(base[2] * k)];
  });
  const bump = pixelFill(size, size, (x, y) => {
    const v = 128 + 90 * (vnoise(x * 0.7, y * 0.7, seed + 8, size * 0.7, size * 0.7) - 0.5) + 40 * (fbm(x / size * 16, y / size * 16, 3, seed + 2, 16, 16) - 0.5);
    return [v, v, v];
  });
  return { map: toTex(col), bump: toTex(bump, false) };
}

// standing seam roof. horizontal seams (constant v). covers 2m with 4 seams
export function roofTextures({ size = 1024, base = [118, 121, 124], seed = 5 } = {}) {
  const seams = 4, sp = size / seams;
  const col = pixelFill(size, size, (x, y) => {
    const ly = y % sp;
    const n = fbm(x / size * 6, y / size * 30, 3, seed, 6, 30);
    let k = 0.94 + 0.08 * n;
    if (ly < 5) k *= 1.32; else if (ly < 9) k *= 0.62; else if (ly < 13) k *= 0.85;
    return [clamp(base[0] * k), clamp(base[1] * k), clamp(base[2] * k)];
  });
  const bump = pixelFill(size, size, (x, y) => {
    const ly = y % sp; let v = 110;
    if (ly < 9) v = 255; else if (ly < 13) v = 60;
    return [v, v, v];
  });
  return { map: toTex(col), bump: toTex(bump, false) };
}

export function grassTexture({ size = 1024, seed = 7, base = [92, 128, 58] } = {}) {
  const c = pixelFill(size, size, (x, y) => {
    const n1 = fbm(x / size * 6, y / size * 6, 5, seed, 6, 6);
    const n2 = vnoise(x * 0.35, y * 0.35, seed + 4, size * 0.35, size * 0.35);
    const n3 = vnoise(x * 1.3, y * 0.5, seed + 9, size * 1.3, size * 0.5);
    const k = 0.72 + 0.45 * n1 + 0.18 * (n2 - 0.5) + 0.22 * (n3 - 0.5);
    const yel = Math.max(0, fbm(x / size * 3, y / size * 3, 3, seed + 20, 3, 3) - 0.55) * 1.4;
    return [clamp(base[0] * k * (1 + yel * 0.5)), clamp(base[1] * k), clamp(base[2] * k * (1 - yel * 0.3))];
  });
  // blades
  const ctx = c.getContext('2d'); const r = rng(seed);
  for (let i = 0; i < 9000; i++) {
    const x = r() * size, y = r() * size, l = 4 + r() * 9, a = -Math.PI / 2 + (r() - 0.5) * 1.2;
    const g = 90 + r() * 90;
    ctx.strokeStyle = `rgba(${g * 0.62 | 0},${g | 0},${g * 0.38 | 0},${0.25 + r() * 0.35})`;
    ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x + Math.cos(a) * l, y + Math.sin(a) * l); ctx.stroke();
  }
  return toTex(c);
}

export function tileTextures({ size = 1024, tiles = 4, base = [190, 186, 178], joint = [120, 118, 112], seed = 11, jw = 5 } = {}) {
  const tw = size / tiles; const r = rng(seed);
  const tone = []; for (let i = 0; i < tiles * tiles; i++) tone.push(0.93 + r() * 0.1);
  const col = pixelFill(size, size, (x, y) => {
    const tx = Math.floor(x / tw), ty = Math.floor(y / tw), lx = x - tx * tw, ly = y - ty * tw;
    if (lx < jw || ly < jw) return joint;
    const n = fbm(x / size * 10, y / size * 10, 4, seed, 10, 10);
    const sp = hash2(x, y, seed) > 0.985 ? 0.85 : 1;
    const k = tone[ty * tiles + tx] * (0.94 + 0.1 * n) * sp;
    return [clamp(base[0] * k), clamp(base[1] * k), clamp(base[2] * k)];
  });
  const bump = pixelFill(size, size, (x, y) => {
    const lx = x % tw, ly = y % tw; const v = (lx < jw || ly < jw) ? 30 : 200 + 30 * hash2(x, y, 4);
    return [v, v, v];
  });
  return { map: toTex(col), bump: toTex(bump, false) };
}

export function noiseTexture({ size = 512, base = [160, 158, 152], amp = 0.12, fine = 0.08, seed = 13, speck = 0, lines = 0 } = {}) {
  const col = pixelFill(size, size, (x, y) => {
    const n = fbm(x / size * 8, y / size * 8, 5, seed, 8, 8);
    const f = hash2(x, y, seed);
    let k = 1 - amp / 2 + amp * n + fine * (f - 0.5);
    if (speck && f > 1 - speck) k *= 1.35;
    if (lines && (y % Math.floor(size / lines)) < 2) k *= 0.9;
    return [clamp(base[0] * k), clamp(base[1] * k), clamp(base[2] * k)];
  });
  return toTex(col);
}

export function leafTexture({ size = 512, seed = 17, palette = [[70, 105, 40], [95, 130, 50], [60, 90, 35], [120, 145, 60]], count = 260, leafLen = [16, 30] } = {}) {
  const c = canvas(size, size), ctx = c.getContext('2d'); const r = rng(seed);
  ctx.clearRect(0, 0, size, size);
  // twigs
  ctx.strokeStyle = 'rgba(70,55,40,1)'; ctx.lineWidth = 2.5;
  for (let i = 0; i < 6; i++) {
    ctx.beginPath(); ctx.moveTo(size / 2, size * 0.98);
    ctx.quadraticCurveTo(size * (0.2 + r() * 0.6), size * 0.5, size * (0.1 + r() * 0.8), size * (0.08 + r() * 0.3)); ctx.stroke();
  }
  for (let i = 0; i < count; i++) {
    const ang = r() * Math.PI * 2, rad = Math.sqrt(r()) * size * 0.44;
    const x = size / 2 + Math.cos(ang) * rad, y = size / 2 + Math.sin(ang) * rad * 0.95;
    const p = palette[Math.floor(r() * palette.length)], k = 0.75 + r() * 0.45;
    const L = leafLen[0] + r() * (leafLen[1] - leafLen[0]);
    ctx.save(); ctx.translate(x, y); ctx.rotate(r() * Math.PI * 2);
    ctx.fillStyle = `rgb(${clamp(p[0] * k) | 0},${clamp(p[1] * k) | 0},${clamp(p[2] * k) | 0})`;
    ctx.beginPath(); ctx.ellipse(0, 0, L * 0.5, L * 0.24, 0, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = `rgba(255,255,255,0.10)`;
    ctx.beginPath(); ctx.ellipse(-L * 0.1, -L * 0.05, L * 0.3, L * 0.09, 0, 0, Math.PI * 2); ctx.fill();
    ctx.restore();
  }
  const t = toTex(c);
  t.wrapS = t.wrapT = THREE.ClampToEdgeWrapping;
  t.generateMipmaps = false; t.minFilter = THREE.LinearFilter;
  return t;
}

// ---------- geometry ----------
// world-space box mapping; s = meters per texture repeat
export function boxUV(geom, s = 1, rot = false) {
  const p = geom.attributes.position, n = geom.attributes.normal;
  const uv = new Float32Array(p.count * 2);
  for (let i = 0; i < p.count; i++) {
    const nx = Math.abs(n.getX(i)), ny = Math.abs(n.getY(i)), nz = Math.abs(n.getZ(i));
    let u, v;
    if (ny >= nx && ny >= nz) { u = p.getX(i); v = p.getZ(i); if (rot) [u, v] = [v, u]; }
    else if (nx >= nz) { u = p.getZ(i); v = p.getY(i); }
    else { u = p.getX(i); v = p.getY(i); }
    uv[i * 2] = u / s; uv[i * 2 + 1] = v / s;
  }
  geom.setAttribute('uv', new THREE.BufferAttribute(uv, 2));
  return geom;
}

export function boxGeom(x0, x1, y0, y1, z0, z1) {
  const g = new THREE.BoxGeometry(x1 - x0, y1 - y0, z1 - z0);
  g.translate((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2);
  return g;
}

export function shapeFrom(pts, holes = []) {
  const s = new THREE.Shape(pts.map(([x, y]) => new THREE.Vector2(x, y)));
  for (const h of holes) s.holes.push(new THREE.Path(h.map(([x, y]) => new THREE.Vector2(x, y))));
  return s;
}
export const rect = (x0, y0, x1, y1) => [[x0, y0], [x1, y0], [x1, y1], [x0, y1]];

// wall frame: t (unit along wall), n (outward normal), origin on outer face at y=0
export function wallFrame(origin, t) {
  const T = new THREE.Vector3(...t), U = new THREE.Vector3(0, 1, 0);
  const N = new THREE.Vector3().crossVectors(T, U);
  const M = new THREE.Matrix4().makeBasis(T, U, N).setPosition(new THREE.Vector3(...origin));
  return { M, T, N, O: new THREE.Vector3(...origin) };
}
// extrude polygon in (u,y) with holes; outer face at local z = zOut, thickness th inward
export function wallPanel(W, pts, holes, th, zOut = 0) {
  const g = new THREE.ExtrudeGeometry(shapeFrom(pts, holes), { depth: th, bevelEnabled: false, curveSegments: 1 });
  g.translate(0, 0, zOut - th);
  g.applyMatrix4(W.M);
  return g;
}
