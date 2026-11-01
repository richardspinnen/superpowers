// Einfamilienhaus mit Tiefgarage – 3D-Modell nach Vorentwurf_01 (Ansichten, Grundrisse, Schnitte 1:100)
// Koordinaten: x = Grundstücksbreite (0 = linke Grenze / Seite Nachbar Nr. 1, Rampe),
//              z = -Abstand von der Straßengrenze (Straße bei z > 0, Garten bei z < 0), y = Höhe, ±0 = OKFF EG
import * as THREE from 'three';
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';
import * as L from './lib.js';

const TAN = Math.tan(18 * Math.PI / 180);

// ------------------------------------------------------------------ key dimensions
export const D = {
  plotW: 23.7, plotD: 37.8,
  hx0: 6.7, hx1: 16.7, hz0: -25.4, hz1: -9.4, // house outer faces
  ridgeX: 11.7, ridgeY: 7.90, eaveOver: 1.5, gableOver: 2.25,
  roofTh: 0.30, skin: 0.035,
  ogFloor: 3.33, woodFrom: 2.62, ground: -0.12,
};
D.roofUnder = (x) => D.ridgeY - D.skin - D.roofTh / Math.cos(18 * Math.PI / 180) - Math.abs(x - D.ridgeX) * TAN;

export function buildScene(opts = {}) {
  const dusk = !!opts.dusk;
  const scene = new THREE.Scene();
  const root = new THREE.Group(); scene.add(root);
  const foliage = []; // objects excluded from AO g-buffer

  // ------------------------------------------------------------ materials
  const wood = L.woodTextures({ boards: 8, seed: 3 });           // 1.2 m per repeat
  const woodDark = L.woodTextures({ boards: 8, seed: 9, base: [168, 128, 92] });
  const plaster = L.plasterTextures({});
  const roofT = L.roofTextures({});
  const tiles = L.tileTextures({});
  const paver = L.tileTextures({ tiles: 8, base: [168, 164, 156], joint: [110, 106, 100], seed: 21, jw: 4 });
  const M = {
    wood: new THREE.MeshStandardMaterial({ map: wood.map, bumpMap: wood.bump, bumpScale: 1.2, roughness: 0.82 }),
    woodDark: new THREE.MeshStandardMaterial({ map: woodDark.map, bumpMap: woodDark.bump, bumpScale: 1.0, roughness: 0.8 }),
    plaster: new THREE.MeshStandardMaterial({ map: plaster.map, bumpMap: plaster.bump, bumpScale: 0.6, roughness: 0.93 }),
    roof: new THREE.MeshStandardMaterial({ map: roofT.map, bumpMap: roofT.bump, bumpScale: 1.5, roughness: 0.42, metalness: 0.55 }),
    metal: new THREE.MeshStandardMaterial({ color: 0x3b3e41, roughness: 0.45, metalness: 0.5 }),
    frame: new THREE.MeshStandardMaterial({ color: 0x34373a, roughness: 0.5, metalness: 0.25 }),
    zinc: new THREE.MeshStandardMaterial({ color: 0x7c8084, roughness: 0.4, metalness: 0.7 }),
    glass: new THREE.MeshPhysicalMaterial({ color: 0x26323a, roughness: 0.03, metalness: 0.0, clearcoat: 1, clearcoatRoughness: 0.02, envMapIntensity: 1.6, ior: 1.5, specularIntensity: 1 }),
    glassRail: new THREE.MeshPhysicalMaterial({ color: 0xcfe3e0, roughness: 0.05, transparent: true, opacity: 0.22, envMapIntensity: 1.4, depthWrite: false }),
    tiles: new THREE.MeshStandardMaterial({ map: tiles.map, bumpMap: tiles.bump, bumpScale: 0.8, roughness: 0.8 }),
    paver: new THREE.MeshStandardMaterial({ map: paver.map, bumpMap: paver.bump, bumpScale: 0.8, roughness: 0.85 }),
    concrete: new THREE.MeshStandardMaterial({ map: L.noiseTexture({ base: [172, 170, 164], seed: 31, lines: 4 }), roughness: 0.9 }),
    ramp: new THREE.MeshStandardMaterial({ map: L.noiseTexture({ base: [150, 149, 145], seed: 33, amp: 0.1, fine: 0.14 }), roughness: 0.9 }),
    asphalt: new THREE.MeshStandardMaterial({ map: L.noiseTexture({ base: [78, 78, 80], seed: 41, amp: 0.14, fine: 0.25, speck: 0.03 }), roughness: 0.92 }),
    grass: new THREE.MeshStandardMaterial({ map: L.grassTexture({ base: [84, 108, 54] }), roughness: 0.97 }),
    soil: new THREE.MeshStandardMaterial({ map: L.noiseTexture({ base: [92, 72, 54], seed: 51, amp: 0.3, fine: 0.4 }), roughness: 1 }),
    gravel: new THREE.MeshStandardMaterial({ map: L.noiseTexture({ base: [176, 172, 164], seed: 53, amp: 0.15, fine: 0.6 }), roughness: 1 }),
    ctxWall: new THREE.MeshStandardMaterial({ color: 0xe9e6df, roughness: 0.92 }),
    ctxRoof: new THREE.MeshStandardMaterial({ color: 0x77736e, roughness: 0.75, metalness: 0.15 }),
    ctxWin: new THREE.MeshStandardMaterial({ color: 0x2a2f33, roughness: 0.15, metalness: 0.3 }),
    ctxWood: new THREE.MeshStandardMaterial({ map: L.woodTextures({ boards: 6, seed: 12, base: [170, 150, 128], weather: 0.55 }).map, roughness: 0.85 }),
  };
  const leafTex = L.leafTexture({ count: 380 });
  const leafTex2 = L.leafTexture({ seed: 23, palette: [[60, 88, 38], [80, 108, 44], [50, 76, 34], [96, 122, 52]], count: 300, leafLen: [12, 22] });
  const leafMat = new THREE.MeshStandardMaterial({ map: leafTex, alphaTest: 0.35, alphaToCoverage: true, side: THREE.DoubleSide, roughness: 0.85, vertexColors: true });
  const leafMat2 = new THREE.MeshStandardMaterial({ map: leafTex2, alphaTest: 0.35, alphaToCoverage: true, side: THREE.DoubleSide, roughness: 0.85, vertexColors: true });
  const barkMat = new THREE.MeshStandardMaterial({ color: 0x5a4c40, roughness: 0.95 });
  const birchMat = new THREE.MeshStandardMaterial({ color: 0xd9d5cc, roughness: 0.9 });
  {
    const macro = L.noiseTexture({ size: 512, base: [128, 128, 128], amp: 0.9, fine: 0.05, seed: 71 });
    macro.colorSpace = THREE.NoColorSpace;
    M.grass.onBeforeCompile = (sh) => {
      sh.uniforms.macroMap = { value: macro };
      sh.fragmentShader = 'uniform sampler2D macroMap;\n' + sh.fragmentShader.replace('#include <map_fragment>', `#include <map_fragment>
        float m1 = texture2D(macroMap, vMapUv * 0.071 + vec2(0.31, 0.17)).r;
        float m2 = texture2D(macroMap, vMapUv * 0.013 + vec2(0.7, 0.2)).r;
        float m3 = texture2D(macroMap, vMapUv * 0.29).r;
        float v = (m1 - 0.5) * 0.9 + (m2 - 0.5) * 0.8 + (m3 - 0.5) * 0.35;
        diffuseColor.rgb *= 1.0 + v * 0.55;
        diffuseColor.rgb = mix(diffuseColor.rgb, diffuseColor.rgb * vec3(1.18, 1.05, 0.72), clamp(v * 1.4 + 0.1, 0.0, 1.0) * 0.5);`);
    };
  }
  // uv scale (meters per repeat) per material
  const S = { wood: 1.2, woodDark: 1.2, plaster: 1.5, roof: 2, tiles: 2.4, paver: 2.4, concrete: 2, ramp: 3, asphalt: 3, grass: 3, soil: 2, gravel: 1.5, ctxWood: 1.2 };
  const matKey = new Map(Object.entries(M).map(([k, v]) => [v, k]));

  function add(geom, mat, { cast = true, receive = true, uv = true, rotUV = false, parent = root } = {}) {
    const k = matKey.get(mat);
    if (uv && S[k]) L.boxUV(geom, S[k], rotUV);
    const m = new THREE.Mesh(geom, mat);
    m.castShadow = cast; m.receiveShadow = receive;
    parent.add(m);
    return m;
  }
  const box = (x0, x1, y0, y1, z0, z1, mat, o) => add(L.boxGeom(x0, x1, y0, y1, z0, z1), mat, o);

  // dusk interior light material for glass
  let glassMat = M.glass;
  if (dusk) {
    const c = document.createElement('canvas'); c.width = 64; c.height = 256;
    const g = c.getContext('2d'); const gr = g.createLinearGradient(0, 0, 0, 256);
    gr.addColorStop(0, '#ffd79a'); gr.addColorStop(0.45, '#e8a95c'); gr.addColorStop(1, '#6b4426');
    g.fillStyle = gr; g.fillRect(0, 0, 64, 256);
    const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace;
    glassMat = new THREE.MeshPhysicalMaterial({ color: 0x111111, emissive: 0xffffff, emissiveMap: t, emissiveIntensity: 1.6, roughness: 0.04, clearcoat: 1, envMapIntensity: 0.6 });
  }

  // ------------------------------------------------------------ house walls
  const H = D;
  const W = {
    front: L.wallFrame([H.hx0, 0, H.hz1], [1, 0, 0]),
    rear: L.wallFrame([H.hx1, 0, H.hz0], [-1, 0, 0]),
    left: L.wallFrame([H.hx0, 0, H.hz0], [0, 0, 1]),
    right: L.wallFrame([H.hx1, 0, H.hz1], [0, 0, -1]),
  };
  const EGH = 2.47, OGS = 4.22, OGH = 5.55; // EG window head, OG sill, OG head
  // openings: [u0,u1,y0,y1,panels,kind]
  const OPEN = {
    front: [
      [2.3, 3.4, 0.02, EGH, 1], [6.8, 8.0, 0.02, EGH, 1],
      [4.25, 6.05, 0.02, EGH, 0, 'door'],
      [1.2, 3.4, 3.36, OGH, 2], [6.6, 8.8, 3.36, OGH, 2],
    ],
    rear: [
      [1.0, 3.7, 0.02, 2.5, 2], [6.3, 9.0, 0.02, 2.5, 2],
      [1.2, 3.3, 3.36, OGH, 2], [6.7, 8.8, 3.36, OGH, 2],
    ],
    left: [
      [1.0, 2.8, 0.02, EGH, 1], [7.4, 9.2, 0.02, EGH, 1],
      [1.1, 2.8, OGS, OGH, 1], [7.0, 8.0, OGS, OGH, 1], [12.3, 13.6, OGS, OGH, 1],
    ],
    right: [
      [13.2, 14.6, 0.02, EGH, 1], [8.6, 11.0, 0.02, EGH, 2], [2.9, 4.0, 0.95, EGH, 1],
      [3.3, 4.5, OGS, OGH, 1], [6.7, 7.9, OGS, OGH, 1], [9.6, 11.4, OGS, OGH, 2], [13.2, 15.0, OGS, OGH, 2],
    ],
  };
  const TH = 0.42, CLAD = 0.035;
  for (const side of ['front', 'rear', 'left', 'right']) {
    const Wf = W[side];
    const len = (side === 'front' || side === 'rear') ? 10 : 16;
    const ops = OPEN[side];
    const egHoles = ops.filter(o => o[3] <= H.woodFrom).map(o => L.rect(o[0], o[2], o[1], o[3]));
    const ogHoles = ops.filter(o => o[2] >= H.woodFrom).map(o => L.rect(o[0], o[2], o[1], o[3]));
    // EG plaster (incl. plinth below terrain)
    add(L.wallPanel(Wf, L.rect(0, -0.3, len, H.woodFrom), egHoles, TH, 0), M.plaster);
    // OG wood cladding
    let pts;
    const e = CLAD;
    if (side === 'front' || side === 'rear') {
      const yE = D.roofUnder(H.hx0), yR = D.roofUnder(H.ridgeX);
      pts = [[-e, H.woodFrom], [len + e, H.woodFrom], [len + e, yE - (e) * TAN], [5, yR], [-e, yE - e * TAN]];
    } else {
      pts = L.rect(-e, H.woodFrom, len + e, D.roofUnder(H.hx0));
    }
    add(L.wallPanel(Wf, pts, ogHoles, TH + e, e), M.wood);
    // shadow joint / drip profile between plaster and wood
    add(L.wallPanel(Wf, L.rect(-e - 0.01, H.woodFrom - 0.03, len + e + 0.01, H.woodFrom + 0.005), [], 0.1, e + 0.015), M.metal);

    for (const [u0, u1, y0, y1, panels, kind] of ops) {
      const og = y0 >= H.woodFrom;
      const inset = og ? 0.14 + e : 0.15;
      if (kind === 'door') { addEntrance(Wf, u0, u1, y0, y1); continue; }
      addWindow(Wf, u0, u1, y0, y1, panels, inset, y0 > 0.3);
    }
  }

  function addWindow(Wf, u0, u1, y0, y1, panels, inset, sill) {
    const fw = 0.075, dep = 0.075;
    const zf = -inset;
    const geoms = [];
    const fr = new THREE.ExtrudeGeometry(L.shapeFrom(L.rect(u0, y0, u1, y1), [L.rect(u0 + fw, y0 + fw, u1 - fw, y1 - fw)]), { depth: dep, bevelEnabled: false });
    fr.translate(0, 0, zf - dep); geoms.push(fr);
    const n = Math.max(1, panels);
    for (let i = 1; i < n; i++) {
      const u = u0 + (u1 - u0) * i / n;
      geoms.push(L.boxGeom(u - 0.045, u + 0.045, y0 + fw, y1 - fw, zf - dep, zf));
    }
    // inner sash profiles for large panes
    const g = mergeGeometries(geoms.map(x => x.toNonIndexed ? (x.index ? x.toNonIndexed() : x) : x).map(x => { x.deleteAttribute('uv'); return x; }));
    g.applyMatrix4(Wf.M);
    add(g, M.frame, { uv: false });
    const gl = new THREE.PlaneGeometry(u1 - u0 - 2 * fw, y1 - y0 - 2 * fw);
    gl.translate((u0 + u1) / 2, (y0 + y1) / 2, zf - dep * 0.5);
    gl.applyMatrix4(Wf.M);
    add(gl, glassMat, { uv: false, cast: false });
    if (sill) {
      const s = L.boxGeom(u0 - 0.03, u1 + 0.03, y0 - 0.05, y0 + 0.005, zf, 0.05);
      s.applyMatrix4(Wf.M); add(s, M.metal, { uv: false });
    }
  }

  function addEntrance(Wf, u0, u1, y0, y1) {
    // recessed entrance: side glazing + oak door
    const inset = 0.22, dep = 0.08, fw = 0.07;
    const doorW = 1.15, dc = (u0 + u1) / 2;
    const parts = [];
    const fr = new THREE.ExtrudeGeometry(L.shapeFrom(L.rect(u0, y0, u1, y1), [L.rect(u0 + fw, y0 + 0.001, u1 - fw, y1 - fw)]), { depth: dep, bevelEnabled: false });
    fr.translate(0, 0, -inset - dep); parts.push(fr);
    parts.push(L.boxGeom(dc - doorW / 2 - 0.06, dc - doorW / 2, y0, y1 - fw, -inset - dep, -inset));
    parts.push(L.boxGeom(dc + doorW / 2, dc + doorW / 2 + 0.06, y0, y1 - fw, -inset - dep, -inset));
    const g = mergeGeometries(parts.map(x => { x = x.index ? x.toNonIndexed() : x; x.deleteAttribute('uv'); return x; }));
    g.applyMatrix4(Wf.M); add(g, M.frame, { uv: false });
    const door = L.boxGeom(dc - doorW / 2, dc + doorW / 2, y0, y1 - fw, -inset - dep * 0.8, -inset - dep * 0.2);
    door.applyMatrix4(Wf.M); add(door, M.woodDark);
    // handle bar
    const hb = L.boxGeom(dc + doorW / 2 - 0.16, dc + doorW / 2 - 0.12, 0.7, 1.9, -inset - 0.02, -inset + 0.03);
    hb.applyMatrix4(Wf.M); add(hb, M.zinc, { uv: false });
    for (const [a, b] of [[u0 + fw, dc - doorW / 2 - 0.06], [dc + doorW / 2 + 0.06, u1 - fw]]) {
      const gl = new THREE.PlaneGeometry(b - a, y1 - fw - y0);
      gl.translate((a + b) / 2, (y0 + y1 - fw) / 2, -inset - dep / 2);
      gl.applyMatrix4(Wf.M); add(gl, glassMat, { uv: false, cast: false });
    }
    // threshold stone
    const th = L.boxGeom(u0 - 0.1, u1 + 0.1, -0.02, 0.02, -inset, 0.02);
    th.applyMatrix4(Wf.M); add(th, M.concrete);
  }

  // ------------------------------------------------------------ OG floor edge / balconies (both gables)
  function balcony(zWall, dir) { // dir = +1 front(+z), -1 rear
    const zOut = zWall + dir * 1.5;
    const [za, zb] = dir > 0 ? [zWall, zOut] : [zOut, zWall];
    const x0 = H.hx0 - 0.04, x1 = H.hx1 + 0.04;
    box(x0, x1, 3.03, 3.33, za, zb, M.wood); // slab (wood soffit)
    box(x0 + 0.06, x1 - 0.06, 3.33, 3.36, za, zb, M.woodDark, { rotUV: true }); // decking
    // balustrade boards: front + returns
    const t = 0.06;
    const zf0 = dir > 0 ? zOut - t : zOut, zf1 = dir > 0 ? zOut : zOut + t;
    box(x0, x1, 2.96, 4.36, zf0, zf1, M.wood);
    box(x0, x0 + t, 2.96, 4.36, za, zb, M.wood);
    box(x1 - t, x1, 2.96, 4.36, za, zb, M.wood);
    // caps
    box(x0 - 0.01, x1 + 0.01, 4.36, 4.39, Math.min(zf0, zf1) - 0.01, Math.max(zf0, zf1) + 0.01, M.metal, { uv: false });
    box(x0 - 0.01, x0 + t + 0.01, 4.36, 4.39, za, zb, M.metal, { uv: false });
    box(x1 - t - 0.01, x1 + 0.01, 4.36, 4.39, za, zb, M.metal, { uv: false });
  }
  balcony(H.hz1, +1);
  balcony(H.hz0, -1);

  // ------------------------------------------------------------ roof
  function gableRoof({ cx, yR, half, z0, z1, th, skin, matBody = M.wood, snow = false, gutter = true }) {
    const yE = yR - half * TAN;
    const cos = Math.cos(18 * Math.PI / 180);
    const thv = th / cos;
    for (const s of [-1, 1]) {
      const xe = cx + s * half;
      // wood body (fascia + soffit)
      const body = new THREE.ExtrudeGeometry(L.shapeFrom(s < 0
        ? [[xe, yE - skin], [cx, yR - skin], [cx, yR - skin - thv], [xe, yE - skin - thv]]
        : [[cx, yR - skin], [xe, yE - skin], [xe, yE - skin - thv], [cx, yR - skin - thv]]), { depth: z1 - z0, bevelEnabled: false });
      body.translate(0, 0, z0);
      add(body, matBody, { rotUV: false });
      // metal skin
      const o = 0.04;
      const xs = xe + s * o, ys = yE - o * TAN;
      const sk = new THREE.ExtrudeGeometry(L.shapeFrom(s < 0
        ? [[xs, ys - skin - 0.01], [xs, ys], [cx, yR], [cx, yR - skin]]
        : [[cx, yR - skin], [cx, yR], [xs, ys], [xs, ys - skin - 0.01]]), { depth: z1 - z0 + 2 * o, bevelEnabled: false });
      sk.translate(0, 0, z0 - o);
      add(sk, M.roof);
      if (gutter) {
        const gg = new THREE.CylinderGeometry(0.075, 0.075, z1 - z0 + 0.1, 16, 1, false, 0, Math.PI);
        gg.rotateX(Math.PI / 2); gg.rotateZ(Math.PI); gg.translate(xe + s * 0.09, yE - skin - thv + 0.08, (z0 + z1) / 2);
        add(gg, M.zinc, { uv: false });
      }
      if (snow) {
        for (const d of [0.9, 1.05]) {
          const xx = xe - s * d, yy = yR - Math.abs(xx - cx) * TAN + 0.11 + (d - 0.9) * 0.0;
          const rod = new THREE.CylinderGeometry(0.014, 0.014, z1 - z0 - 0.4, 6);
          rod.rotateX(Math.PI / 2); rod.translate(xx, yy + (d === 0.9 ? 0 : 0.05), (z0 + z1) / 2);
          add(rod, M.zinc, { uv: false, cast: false });
        }
        for (let z = z0 + 0.4; z < z1 - 0.2; z += 1.0) {
          const xx = xe - s * 0.97, yy = yR - Math.abs(xx - cx) * TAN + 0.06;
          add(L.boxGeom(xx - 0.12, xx + 0.12, yy - 0.06, yy + 0.08, z - 0.015, z + 0.015), M.zinc, { uv: false, cast: false });
        }
      }
    }
    // ridge cap
    const rc = new THREE.ExtrudeGeometry(L.shapeFrom([[cx - 0.16, yR - 0.05], [cx + 0.16, yR - 0.05], [cx + 0.16, yR + 0.0], [cx, yR + 0.07], [cx - 0.16, yR + 0.0]]), { depth: z1 - z0 + 0.1, bevelEnabled: false });
    rc.translate(0, 0, z0 - 0.05); rc.deleteAttribute('uv');
    add(rc, M.zinc, { uv: false });
  }
  gableRoof({ cx: H.ridgeX, yR: H.ridgeY, half: 5 + H.eaveOver, z0: H.hz0 - H.gableOver, z1: H.hz1 + H.gableOver, th: H.roofTh, skin: H.skin, snow: true });

  // downpipes at the 4 corners (long sides)
  {
    const yE = H.ridgeY - 6.5 * TAN - H.skin - H.roofTh / Math.cos(18 * Math.PI / 180);
    for (const [xg, xw] of [[H.hx0 - 1.59, H.hx0 - 0.07], [H.hx1 + 1.59, H.hx1 + 0.07]]) {
      for (const zc of [H.hz1 - 0.35, H.hz0 + 0.35]) {
        const v = new THREE.CylinderGeometry(0.05, 0.05, yE + 0.12, 12); v.translate(xw, (yE + 0.1) / 2 - 0.12, zc);
        add(v, M.zinc, { uv: false });
        const len = Math.abs(xg - xw);
        const hgeo = new THREE.CylinderGeometry(0.05, 0.05, len, 12); hgeo.rotateZ(Math.PI / 2); hgeo.translate((xg + xw) / 2, yE + 0.05, zc);
        add(hgeo, M.zinc, { uv: false });
      }
    }
  }

  // chimney
  {
    const cx = 9.7, cz = -20.0, yb = D.roofUnder(cx) - 0.2;
    box(cx - 0.3, cx + 0.3, yb, 8.85, cz - 0.3, cz + 0.3, M.plaster);
    box(cx - 0.4, cx + 0.4, 8.85, 8.9, cz - 0.4, cz + 0.4, M.zinc, { uv: false });
    box(cx - 0.36, cx + 0.36, 9.08, 9.12, cz - 0.36, cz + 0.36, M.zinc, { uv: false });
    for (const [a, b] of [[-0.34, -0.3], [0.3, 0.34]]) for (const [c, d] of [[-0.34, -0.3], [0.3, 0.34]])
      box(cx + a, cx + b, 8.9, 9.08, cz + c, cz + d, M.zinc, { uv: false });
  }

  // ------------------------------------------------------------ outdoor: terrace, entry, path
  for (const [x0, x1, z0, z1] of [[H.hx0 - 0.4, H.hx0, H.hz0, -20.6], [H.hx0 - 0.4, H.hx0, -20.6 + 0.0, H.hz1], [H.hx1, H.hx1 + 0.4, H.hz0, H.hz1]])
    box(x0, x1, H.ground - 0.05, H.ground + 0.02, z0, z1, M.gravel, { cast: false });
  box(H.hx0 - 0.15, H.hx1 + 0.15, -0.3, 0.0, H.hz0 - 3.7, H.hz0, M.tiles);           // garden terrace
  box(6.2, 17.2, -0.3, 0.0, H.hz1, H.hz1 + 1.1, M.tiles);                              // entry podium
  box(10.55, 12.85, -0.3, -0.06, H.hz1 + 1.1, 0.3, M.paver);                           // path to street
  // podium steps at front edge of path
  // edging along lawn
  {
    // garden table with benches on the terrace (oak)
    const tx = 13.6, tz = -27.6;
    box(tx - 1.1, tx + 1.1, 0.72, 0.76, tz - 0.48, tz + 0.48, M.woodDark);
    for (const sx of [-0.95, 0.95]) box(tx + sx - 0.05, tx + sx + 0.05, 0, 0.72, tz - 0.4, tz + 0.4, M.metal, { uv: false });
    for (const sz of [-0.85, 0.85]) {
      box(tx - 1.0, tx + 1.0, 0.43, 0.47, tz + sz - 0.18, tz + sz + 0.18, M.woodDark);
      for (const sx of [-0.85, 0.85]) box(tx + sx - 0.03, tx + sx + 0.03, 0, 0.43, tz + sz - 0.15, tz + sz + 0.15, M.metal, { uv: false });
    }
    // lounge chairs
    for (const [cx, rot] of [[8.6, 0.25], [10.0, -0.15]]) {
      const g = new THREE.Group(); g.position.set(cx, 0, -27.9); g.rotation.y = rot; root.add(g);
      add(L.boxGeom(-0.35, 0.35, 0.25, 0.4, -0.35, 0.4), M.woodDark, { parent: g });
      add(L.boxGeom(-0.35, 0.35, 0.4, 0.8, 0.28, 0.42), M.woodDark, { parent: g });
      add(L.boxGeom(-0.33, 0.33, 0.38, 0.48, -0.33, 0.3), M.ctxWall, { parent: g, uv: false });
    }
    // large planters at terrace corners
    for (const [px, pz] of [[6.95, -28.6], [16.45, -28.6]]) {
      box(px - 0.35, px + 0.35, 0, 0.6, pz - 0.35, pz + 0.35, M.metal, { uv: false });
      shrub(px, pz, 0.45, 0.9, Math.floor(px * 100), 0.6);
    }
  }
  // ------------------------------------------------------------ ramp to underground garage
  const rampY = (d) => d <= 3 ? H.ground - 0.05 * d : d <= 13 ? H.ground - 0.15 - 0.2 * (d - 3) : H.ground - 2.15 - 0.1 * (d - 13);
  {
    const ds = [0, 1.5, 3, 4.5, 6.2, 8, 10, 12.3, 13, 14];
    const pos = [], idx = [];
    ds.forEach((d, i) => { pos.push(0.8, rampY(d), -d, 4.2, rampY(d), -d); if (i) { const a = (i - 1) * 2; idx.push(a, a + 1, a + 2, a + 1, a + 3, a + 2); } });
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3)); g.setIndex(idx); g.computeVertexNormals();
    add(g, M.ramp);
    // retaining walls of the open part
    for (const x0 of [0.55, 4.2]) {
      const pts = [[0, -0.02], [6.2, -0.02], [6.2, rampY(6.2) - 0.35], [3, rampY(3) - 0.35], [0, rampY(0) - 0.35]];
      const g2 = new THREE.ExtrudeGeometry(L.shapeFrom(pts), { depth: 0.25, bevelEnabled: false });
      const m4 = new THREE.Matrix4().makeBasis(new THREE.Vector3(0, 0, -1), new THREE.Vector3(0, 1, 0), new THREE.Vector3(1, 0, 0)).setPosition(x0, 0, 0);
      g2.applyMatrix4(m4); add(g2, M.concrete);
      box(x0 - 0.01, x0 + 0.26, -0.02, 0.0, -6.2, 0, M.zinc, { uv: false });
    }
    // drainage channel at street
    box(0.8, 4.2, H.ground - 0.005, H.ground + 0.002, -0.35, -0.15, M.metal, { uv: false });
  }
  // ramp housing (Einhausung) with gable roof facing the street
  {
    const za = -12.3, zb = -6.2, x0 = 0.55, x1 = 4.45, eave = 2.37, cx = 2.5;
    const top = eave + 1.95 * TAN;
    // front gable with door opening
    const fp = [[x0, -1.05], [0.8, -1.05], [0.8, 2.15], [4.2, 2.15], [4.2, -1.05], [x1, -1.05], [x1, eave], [cx, top], [x0, eave]];
    const fg = new THREE.ExtrudeGeometry(L.shapeFrom(fp), { depth: 0.25, bevelEnabled: false }); fg.translate(0, 0, zb - 0.25);
    add(fg, M.wood);
    const bp = [[x0, -0.3], [x1, -0.3], [x1, eave], [cx, top], [x0, eave]];
    const bg = new THREE.ExtrudeGeometry(L.shapeFrom(bp), { depth: 0.25, bevelEnabled: false }); bg.translate(0, 0, za);
    add(bg, M.wood);
    box(x0, 0.8, -2.3, eave, za, zb, M.wood);
    box(4.2, x1, -2.3, eave, za, zb, M.wood);
    // garage door (wood-clad sectional door) + frame
    box(0.8, 4.2, rampY(6.35), 2.15, zb - 0.2, zb - 0.14, M.woodDark);
    box(0.8, 4.2, 2.1, 2.15, zb - 0.2, zb - 0.01, M.frame, { uv: false });
    gableRoof({ cx, yR: top + 0.03 + 0.2 / Math.cos(18 * Math.PI / 180), half: 1.95 + 0.45, z0: za - 0.45, z1: zb + 0.55, th: 0.2, skin: 0.03, gutter: false });
  }
  // raised planter (Hochbeet) behind housing
  {
    const x0 = 0.8, x1 = 4.1, z0 = -18.7, z1 = -12.6, h = 1.0;
    box(x0, x1, H.ground, h, z0, z0 + 0.12, M.concrete); box(x0, x1, H.ground, h, z1 - 0.12, z1, M.concrete);
    box(x0, x0 + 0.12, H.ground, h, z0, z1, M.concrete); box(x1 - 0.12, x1, H.ground, h, z0, z1, M.concrete);
    box(x0 + 0.12, x1 - 0.12, H.ground, h - 0.1, z0 + 0.12, z1 - 0.12, M.soil);
    planterPlants(x0 + 0.2, x1 - 0.2, z0 + 0.2, z1 - 0.2, h - 0.1, 101);
  }
  // light well (Lichthof) for the basement studio
  {
    const x0 = 4.05, x1 = H.hx0, z0 = H.hz0 + 0.0, z1 = -20.6, bot = -2.9;
    box(x0 - 0.2, x0, bot, 0.05, z0, z1, M.concrete);
    box(x0 - 0.2, x1, bot, 0.05, z0 - 0.2, z0, M.concrete);
    box(x0 - 0.2, x1, bot, 0.05, z1, z1 + 0.2, M.concrete);
    box(x0, x1, bot - 0.1, bot + 0.05, z0, z1, M.gravel);
    // basement glazing toward light well
    box(x1 - 0.02, x1 + 0.3, bot, -0.05, z0 - 0.2, z1 + 0.2, M.concrete);
    const gl = new THREE.PlaneGeometry(4.2, 2.3); gl.rotateY(-Math.PI / 2); gl.translate(x1 - 0.03, bot + 1.3, (z0 + z1) / 2);
    add(gl, glassMat, { uv: false, cast: false });
    planterPlants(x0 + 0.2, x1 - 0.4, z0 + 0.3, z1 - 0.3, bot + 0.05, 202, 0.7);
    // glass balustrade
    for (const [ax, az, bx, bz] of [[x0 - 0.1, z0 - 0.1, x0 - 0.1, z1 + 0.1], [x0 - 0.1, z0 - 0.1, x1, z0 - 0.1], [x0 - 0.1, z1 + 0.1, x1, z1 + 0.1]]) {
      const len = Math.hypot(bx - ax, bz - az);
      const pg = new THREE.PlaneGeometry(len, 0.95); const ang = Math.atan2(-(bz - az), bx - ax);
      pg.rotateY(ang); pg.translate((ax + bx) / 2, 0.05 + 0.5, (az + bz) / 2);
      const m = add(pg, M.glassRail, { uv: false, cast: false });
      const rail = new THREE.BoxGeometry(len + 0.04, 0.04, 0.05); rail.rotateY(ang); rail.translate((ax + bx) / 2, 1.0, (az + bz) / 2);
      add(rail, M.zinc, { uv: false });
    }
  }

  // ------------------------------------------------------------ ground with holes
  {
    const outer = [[-260, -300], [260, -300], [260, 300], [-260, 300]];
    const holes = [
      [[0.55, 0], [4.45, 0], [4.45, 6.2], [0.55, 6.2]].map(([x, d]) => [x, d]),
      [[4.05, 20.6], [6.7, 20.6], [6.7, 25.4], [4.05, 25.4]],
    ];
    // shape in (x, -z)
    const sh = L.shapeFrom(outer.map(([x, z]) => [x, z]), holes.map(h => h.map(([x, d]) => [x, -d])));
    const g = new THREE.ShapeGeometry(sh);
    g.rotateX(Math.PI / 2); // (x,y) -> (x,0,y) : y=-d -> z=-d? rotateX(+90): y->z
    // after rotateX(+PI/2): (x, y, 0) -> (x, 0, y). shape y = -d -> z = -d. good; normals point -y -> flip
    const p = g.attributes.position;
    for (let i = 0; i < p.count; i++) p.setY(i, H.ground);
    g.computeVertexNormals();
    // fix orientation: ensure normals up
    const n = g.attributes.normal; let flip = n.getY(0) < 0;
    if (flip) { const ia = g.index.array; for (let i = 0; i < ia.length; i += 3) { const t = ia[i]; ia[i] = ia[i + 2]; ia[i + 2] = t; } g.computeVertexNormals(); }
    add(g, M.grass, { cast: false });
    // street
    box(-260, 260, H.ground - 0.2, H.ground + 0.012, 0.35, 6.4, M.asphalt, { cast: false });
    // granite curbstones along plot
    box(-260, 260, H.ground, H.ground + 0.03, 0.2, 0.35, M.concrete, { cast: false });
    box(0.55, 4.45, H.ground - 0.1, H.ground + 0.015, 0, 0.36, M.asphalt, { cast: false });
  }

  // ------------------------------------------------------------ vegetation

  function crown(cx, cy, cz, rx, ry, rz, n, size, seed, tint = [1, 1, 1], mat = leafMat) {
    const r = L.rng(seed);
    const pos = [], nor = [], uv = [], col = [], idx = [];
    const c = new THREE.Vector3(cx, cy, cz);
    for (let i = 0; i < n; i++) {
      // point in ellipsoid, biased to shell
      let x, y, z; do { x = r() * 2 - 1; y = r() * 2 - 1; z = r() * 2 - 1; } while (x * x + y * y + z * z > 1);
      const sh = 0.55 + 0.45 * Math.cbrt(r());
      const l = Math.hypot(x, y, z) || 1, k = sh * l ** 0.3 / l; x *= k; y *= k; z *= k;
      const p = new THREE.Vector3(cx + x * rx, cy + y * ry, cz + z * rz);
      const s = size * (0.7 + r() * 0.6);
      const q = new THREE.Quaternion().setFromEuler(new THREE.Euler(r() * Math.PI, r() * Math.PI, r() * Math.PI));
      const ax = new THREE.Vector3(1, 0, 0).applyQuaternion(q).multiplyScalar(s / 2);
      const ay = new THREE.Vector3(0, 1, 0).applyQuaternion(q).multiplyScalar(s / 2);
      const nrm = p.clone().sub(c).divide(new THREE.Vector3(rx, ry, rz)).normalize().lerp(new THREE.Vector3(0, 1, 0), 0.25).normalize();
      const shade = 0.55 + 0.45 * Math.max(0, (p.y - (cy - ry)) / (2 * ry)) ** 0.7;
      const v = 0.85 + r() * 0.3;
      const base = pos.length / 3;
      for (const [a, b, uu, vv] of [[-1, -1, 0, 0], [1, -1, 1, 0], [1, 1, 1, 1], [-1, 1, 0, 1]]) {
        pos.push(p.x + ax.x * a + ay.x * b, p.y + ax.y * a + ay.y * b, p.z + ax.z * a + ay.z * b);
        nor.push(nrm.x, nrm.y, nrm.z); uv.push(uu, vv);
        col.push(shade * v * tint[0], shade * v * tint[1], shade * v * tint[2]);
      }
      idx.push(base, base + 1, base + 2, base, base + 2, base + 3);
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
    g.setAttribute('normal', new THREE.Float32BufferAttribute(nor, 3));
    g.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2));
    g.setAttribute('color', new THREE.Float32BufferAttribute(col, 3));
    g.setIndex(idx);
    const m = new THREE.Mesh(g, mat); m.castShadow = true; m.receiveShadow = true;
    m.userData.noAO = true; foliage.push(m); root.add(m);
    return m;
  }
  function branchGeom(a, b, r0, r1) {
    const dir = new THREE.Vector3().subVectors(b, a); const len = dir.length();
    const g = new THREE.CylinderGeometry(r1, r0, len, 8, 1);
    g.translate(0, len / 2, 0);
    g.applyQuaternion(new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir.normalize()));
    g.translate(a.x, a.y, a.z);
    g.deleteAttribute('uv');
    return g.index ? g.toNonIndexed() : g;
  }
  function tree(x, z, h, seed, kind = 'broad') {
    const r = L.rng(seed); const y0 = H.ground;
    const birch = kind === 'birch';
    const trunkTop = new THREE.Vector3(x + (r() - 0.5) * 0.3, y0 + h * 0.55, z + (r() - 0.5) * 0.3);
    const gs = [branchGeom(new THREE.Vector3(x, y0 - 0.1, z), trunkTop, birch ? 0.13 : 0.2, birch ? 0.08 : 0.12)];
    const crR = h * (birch ? 0.24 : 0.33);
    const cy = y0 + h * 0.66;
    for (let i = 0; i < 7; i++) {
      const a = r() * Math.PI * 2;
      const tip = new THREE.Vector3(x + Math.cos(a) * crR * 0.8, cy + (r() - 0.2) * crR * 0.9, z + Math.sin(a) * crR * 0.8);
      gs.push(branchGeom(trunkTop.clone().add(new THREE.Vector3(0, -r() * 0.6, 0)), tip, birch ? 0.06 : 0.09, 0.025));
    }
    gs.push(branchGeom(trunkTop, new THREE.Vector3(x, y0 + h * 0.92, z), 0.08, 0.03));
    const tg = mergeGeometries(gs);
    const tm = new THREE.Mesh(tg, birch ? birchMat : barkMat); tm.castShadow = true; tm.receiveShadow = true; root.add(tm);
    const n = Math.round(380 * (h / 9) ** 2 * (birch ? 0.75 : 1));
    crown(x, cy + crR * 0.15, z, crR * (birch ? 1.0 : 1.12), h * (birch ? 0.33 : 0.3), crR * (birch ? 1.0 : 1.1), n, birch ? 1.1 : 1.35, seed + 5,
      birch ? [1.05, 1.08, 0.95] : [1, 1, 1], birch ? leafMat : leafMat2);
  }
  function shrub(x, z, rad, hgt, seed, y0 = H.ground) {
    crown(x, y0 + hgt * 0.5, z, rad, hgt * 0.5, rad, Math.round(60 * rad * rad * 2 + 20), 0.6, seed, [0.95, 1, 0.9], leafMat2);
  }
  function planterPlants(x0, x1, z0, z1, y, seed, scale = 1) {
    const r = L.rng(seed);
    for (let x = x0 + 0.35; x < x1; x += 0.9) for (let z = z0 + 0.35; z < z1; z += 0.9) {
      shrub(x + (r() - 0.5) * 0.3, z + (r() - 0.5) * 0.3, (0.32 + r() * 0.2) * scale, (0.55 + r() * 0.5) * scale, seed + Math.floor(r() * 1e6), y);
    }
  }
  function hedge(x0, x1, z0, z1, h, seed) {
    const g = new THREE.BoxGeometry(x1 - x0, h, z1 - z0, Math.ceil((x1 - x0) * 4), Math.ceil(h * 4), Math.ceil((z1 - z0) * 4));
    g.translate((x0 + x1) / 2, H.ground + h / 2, (z0 + z1) / 2);
    const p = g.attributes.position;
    for (let i = 0; i < p.count; i++) {
      const x = p.getX(i), y = p.getY(i), z = p.getZ(i);
      const n = L.vnoise3(x * 1.3, z * 1.3, y * 1.3, seed) - 0.5;
      p.setX(i, x + n * 0.14); p.setY(i, y + (y > H.ground + 0.05 ? n * 0.12 : 0)); p.setZ(i, z + n * 0.14);
    }
    g.computeVertexNormals();
    const m = add(g, M.hedge ||= new THREE.MeshStandardMaterial({ map: L.noiseTexture({ base: [58, 86, 40], seed: 61, amp: 0.5, fine: 0.7 }), roughness: 0.95 }), { uv: false });
    L.boxUV(g, 1.0);
    // fuzzy leaf layer
    const r = L.rng(seed);
    const nx = Math.ceil((x1 - x0) * 3), nz = Math.ceil((z1 - z0) * 3);
    crown((x0 + x1) / 2, H.ground + h * 0.55, (z0 + z1) / 2, (x1 - x0) / 2 + 0.05, h * 0.5, (z1 - z0) / 2 + 0.05, Math.round((nx + nz) * h * 14), 0.45, seed + 3, [0.8, 0.9, 0.75], leafMat2);
  }
  M.hedge = null;

  // plot vegetation (from the plans: trees at street corner, along the sides and in the garden)
  tree(22.3, -6.0, 9.5, 11, 'birch');
  tree(21.3, -15.5, 8.0, 12, 'birch');
  tree(3.0, -31.5, 10.5, 13, 'broad');
  tree(21.4, -28.6, 8.5, 14, 'broad');
  tree(7.6, -2.6, 6.5, 15, 'birch');
  hedge(-0.05, 0.75, -37.7, -19.6, 1.7, 21);
  hedge(22.95, 23.75, -37.7, -11.0, 1.7, 22);
  hedge(0.7, 22.95, -37.75, -37.0, 1.7, 23);
  shrub(17.9, -8.0, 0.7, 1.1, 31); shrub(5.6, -8.2, 0.6, 0.9, 32); shrub(13.8, -1.4, 0.5, 0.7, 33);
  shrub(18.0, -27.5, 0.8, 1.3, 34); shrub(5.4, -28.8, 0.7, 1.0, 35);

  // ------------------------------------------------------------ context: neighbouring houses (simplified)
  function contextHouse(cx, cz, w, l, eave, rot = 0) {
    const g = new THREE.Group(); g.position.set(cx, 0, cz); g.rotation.y = rot; root.add(g);
    const opt = { parent: g };
    add(L.boxGeom(-w / 2, w / 2, H.ground - 0.2, 2.8, -l / 2, l / 2), M.ctxWall, opt);
    add(L.boxGeom(-w / 2 - 0.02, w / 2 + 0.02, 2.8, eave, -l / 2 - 0.02, l / 2 + 0.02), M.ctxWood, { ...opt, uv: true });
    const gp = [[-w / 2, eave], [w / 2, eave], [0, eave + w / 2 * Math.tan(22 * Math.PI / 180)]];
    for (const zz of [l / 2, -l / 2 - 0.0]) {
      const gg = new THREE.ExtrudeGeometry(L.shapeFrom(gp), { depth: 0.02, bevelEnabled: false }); gg.translate(0, 0, zz - (zz > 0 ? 0 : 0.02));
      add(gg, M.ctxWood, opt);
    }
    const tn = Math.tan(22 * Math.PI / 180), half = w / 2 + 1.2, yR = eave + w / 2 * tn + 0.25;
    for (const s of [-1, 1]) {
      const sh = s < 0 ? [[-half, yR - half * tn], [0, yR], [0, yR - 0.25], [-half, yR - half * tn - 0.25]] : [[0, yR], [half, yR - half * tn], [half, yR - half * tn - 0.25], [0, yR - 0.25]];
      const rg = new THREE.ExtrudeGeometry(L.shapeFrom(sh), { depth: l + 3, bevelEnabled: false }); rg.translate(0, 0, -l / 2 - 1.5);
      add(rg, M.ctxRoof, { ...opt, uv: false });
    }
    // windows
    for (const zz of [l / 2 + 0.01, -l / 2 - 0.01]) for (const xx of [-w / 4, w / 4]) for (const [y0, y1] of [[0.3, 2.3], [3.6, 5.0]]) {
      const pg = new THREE.PlaneGeometry(1.4, y1 - y0); if (zz < 0) pg.rotateY(Math.PI); pg.translate(xx, (y0 + y1) / 2, zz);
      add(pg, M.ctxWin, { ...opt, uv: false, cast: false });
    }
    for (const xx of [w / 2 + 0.01, -w / 2 - 0.01]) for (let zz = -l / 2 + 2; zz < l / 2 - 1; zz += 3.2) for (const [y0, y1] of [[0.6, 2.2], [3.8, 5.0]]) {
      const pg = new THREE.PlaneGeometry(1.2, y1 - y0); pg.rotateY(xx > 0 ? Math.PI / 2 : -Math.PI / 2); pg.translate(xx, (y0 + y1) / 2, zz);
      add(pg, M.ctxWin, { ...opt, uv: false, cast: false });
    }
  }
  contextHouse(-13.5, -19, 11, 14, 5.8);
  contextHouse(37.5, -18, 10, 13, 5.6);
  contextHouse(-12, 22, 11, 15, 5.8, 0.04);
  contextHouse(14, 24, 12, 14, 6.0, -0.03);
  contextHouse(40, 23, 10, 13, 5.6);
  contextHouse(10, -62, 12, 15, 6.0);
  contextHouse(-25, -55, 11, 14, 5.8);
  // context trees
  const rr = L.rng(77);
  for (const [x, z, h] of [[-6, -6, 9], [-4, -34, 11], [30, -40, 12], [29, -4, 8], [-22, -36, 13], [46, -30, 12], [-30, -8, 10], [28, 12, 9], [-2, 13, 8], [52, 6, 11], [-28, 30, 10], [3, 34, 10], [26, 36, 11], [-8, -70, 14], [30, -70, 13], [55, -55, 12]])
    tree(x, z, h * (0.9 + rr() * 0.2), 500 + x * 7 + z, rr() > 0.5 ? 'birch' : 'broad');

  // ------------------------------------------------------------ distant landscape (Tegernseer Berge)
  {
    const size = 9000, seg = 220;
    const g = new THREE.PlaneGeometry(size, size, seg, seg); g.rotateX(-Math.PI / 2);
    const p = g.attributes.position; const col = [];
    const cLow = new THREE.Color(0x56703c), cForest = new THREE.Color(0x2c4126), cRock = new THREE.Color(0x8a8780), cMeadow = new THREE.Color(0x6f8c45);
    for (let i = 0; i < p.count; i++) {
      const x = p.getX(i), z = p.getZ(i); const rdist = Math.hypot(x - 10, z + 20);
      const mask = THREE.MathUtils.smoothstep(rdist, 420, 2200);
      const sink = 1 - THREE.MathUtils.smoothstep(Math.max(Math.abs(x - 10) - 240, Math.abs(z + 20) - 270, 0), 0, 40);
      const ridged = 1 - Math.abs(L.fbm(x / 1400, z / 1400, 5, 91) * 2 - 1);
      const hgt = mask * (180 + 1050 * ridged ** 2 * L.fbm(x / 3000 + 7, z / 3000, 3, 92)) - 1 + (1 - mask) * 0;
      p.setY(i, H.ground - 0.4 + hgt - sink * 3.5);
      const c = cMeadow.clone().lerp(cLow, L.fbm(x / 200, z / 200, 3, 93));
      const fr = THREE.MathUtils.smoothstep(hgt, 60, 220) * (L.fbm(x / 300, z / 300, 4, 94) > 0.42 ? 1 : 0.4);
      c.lerp(cForest, fr);
      c.lerp(cRock, THREE.MathUtils.smoothstep(hgt, 650, 950));
      col.push(c.r, c.g, c.b);
    }
    g.setAttribute('color', new THREE.Float32BufferAttribute(col, 3));
    g.computeVertexNormals();
    const m = new THREE.Mesh(g, new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 1 }));
    m.receiveShadow = false; root.add(m);
    // far forests: instanced spruces
    const coneG = mergeGeometries([new THREE.ConeGeometry(1, 3.2, 7).translate(0, 2.6, 0), new THREE.CylinderGeometry(0.12, 0.15, 1.2, 5).translate(0, 0.6, 0)].map(x => { x.deleteAttribute('uv'); return x.index ? x.toNonIndexed() : x; }));
    const im = new THREE.InstancedMesh(coneG, new THREE.MeshStandardMaterial({ color: 0x2b3f27, roughness: 1 }), 1600);
    const r = L.rng(5); const mtx = new THREE.Matrix4(); let k = 0;
    while (k < 1600) {
      const a = r() * Math.PI * 2, d = 90 + r() ** 0.7 * 520;
      const x = 10 + Math.cos(a) * d, z = -20 + Math.sin(a) * d;
      if (z > -2 && z < 14 && d < 200) continue; // keep street view open
      if (L.fbm(x / 120, z / 120, 3, 77) < 0.5) continue;
      const s = 3 + r() * 4;
      mtx.compose(new THREE.Vector3(x, H.ground - 0.3, z), new THREE.Quaternion(), new THREE.Vector3(s * 0.75, s, s * 0.75));
      im.setMatrixAt(k++, mtx);
    }
    im.castShadow = false; im.receiveShadow = false; root.add(im);
  }

  {
    const size = 1024, c = document.createElement('canvas'); c.width = c.height = size;
    const ctx = c.getContext('2d'), img = ctx.createImageData(size, size);
    for (let y = 0; y < size; y++) for (let x = 0; x < size; x++) {
      const n = L.fbm(x / size * 6, y / size * 6, 6, 404, 6, 6);
      const a = THREE.MathUtils.smoothstep(n, 0.52, 0.78);
      const sh = 0.82 + 0.18 * L.fbm(x / size * 12 + 3, y / size * 12, 3, 405, 12, 12);
      const i = (y * size + x) * 4; img.data[i] = img.data[i + 1] = img.data[i + 2] = 255 * sh; img.data[i + 3] = 255 * a * 0.92;
    }
    ctx.putImageData(img, 0, 0);
    const t = new THREE.CanvasTexture(c); t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(5, 5); t.colorSpace = THREE.SRGBColorSpace;
    const cm = new THREE.MeshBasicMaterial({ map: t, transparent: true, depthWrite: false, fog: false, color: dusk ? 0x5a4a5e : 0xffffff, opacity: dusk ? 0.55 : 0.85 });
    const cl = new THREE.Mesh(new THREE.PlaneGeometry(40000, 40000).rotateX(Math.PI / 2), cm);
    cl.position.y = 1800; cl.renderOrder = -1; cl.userData.noAO = true; foliage.push(cl); scene.add(cl);
  }
  return { scene, foliage, M, glassMat };
}
