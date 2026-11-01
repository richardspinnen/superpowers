# Build the Bartlmaeweg 1 B scene in Blender (Cycles).
# Plan coordinates ("T"): x = across plot (0 = left boundary, ramp side), y = up (0 = EG floor), z = -distance from street.
# Blender: X = x, Y = -z (street at Y<0... i.e. Y = distance into plot), Z = y.
import bpy, bmesh, math, random
from mathutils import Vector, Matrix, noise
import mat as MT

TAN = math.tan(math.radians(18))
COS = math.cos(math.radians(18))


def T(x, y, z):
    return Vector((x, -z, y))


# ------------------------------------------------------------------ dimensions (from the plans)
HX0, HX1, HZ0, HZ1 = 6.7, 16.7, -25.4, -9.4
RIDGE_X, RIDGE_Y = 11.7, 7.90
EAVE_OVER, GABLE_OVER = 1.5, 2.25
ROOF_TH, SKIN = 0.30, 0.035
WOOD_FROM, GROUND = 2.62, -0.12
TH, CLAD = 0.42, 0.035


def roof_under(x):
    return RIDGE_Y - SKIN - ROOF_TH / COS - abs(x - RIDGE_X) * TAN


# ------------------------------------------------------------------ mesh builder
class Builder:
    def __init__(self):
        self.bm = bmesh.new()
        self.mats = []

    def _mi(self, m):
        if m not in self.mats:
            self.mats.append(m)
        return self.mats.index(m)

    def faces(self, m, verts, faces, smooth=False):
        mi = self._mi(m)
        vs = [self.bm.verts.new(v) for v in verts]
        for f in faces:
            try:
                fa = self.bm.faces.new([vs[i] for i in f])
                fa.material_index = mi
                fa.smooth = smooth
            except ValueError:
                pass

    def boxb(self, m, a, b):  # blender-space AABB
        x0, y0, z0 = a; x1, y1, z1 = b
        v = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
        f = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
        self.faces(m, v, f)

    def box(self, m, x0, x1, y0, y1, z0, z1):  # T-space
        a = T(min(x0, x1), min(y0, y1), max(z0, z1)); b = T(max(x0, x1), max(y0, y1), min(z0, z1))
        self.boxb(m, a, b)

    def prism(self, m, pts, ext, smooth=False):
        """pts: blender-space planar polygon, ext: extrusion vector"""
        n = len(pts)
        v = [Vector(p) for p in pts] + [Vector(p) + Vector(ext) for p in pts]
        nrm = Vector((0, 0, 0))
        for i in range(n):
            a, b = v[i], v[(i + 1) % n]
            nrm += Vector(((a.y - b.y) * (a.z + b.z), (a.z - b.z) * (a.x + b.x), (a.x - b.x) * (a.y + b.y)))
        bottom = list(range(n))
        if nrm.dot(Vector(ext)) > 0:
            bottom = bottom[::-1]
        top = [i + n for i in bottom[::-1]]
        f = [bottom, top]
        order = list(range(n)) if bottom[0] == 0 and (n < 2 or bottom[1] == 1) else list(range(n))[::-1]
        for k in range(n):
            i, j = order[k], order[(k + 1) % n]
            f.append((i, i + n, j + n, j) if order == list(range(n)) else (i, i + n, j + n, j))
        self.faces(m, v, f, smooth)

    def cyl(self, m, p0, p1, r, seg=12, r1=None, cap=True):
        p0, p1 = Vector(p0), Vector(p1)
        r1 = r if r1 is None else r1
        d = (p1 - p0).normalized()
        a = d.orthogonal().normalized(); b = d.cross(a)
        v = []
        for k in range(seg):
            t = 2 * math.pi * k / seg
            o = a * math.cos(t) + b * math.sin(t)
            v.append(p0 + o * r); v.append(p1 + o * r1)
        f = [(2 * k, 2 * ((k + 1) % seg), 2 * ((k + 1) % seg) + 1, 2 * k + 1) for k in range(seg)]
        if cap:
            f.append(tuple(2 * k for k in range(seg))[::-1]); f.append(tuple(2 * k + 1 for k in range(seg)))
        self.faces(m, v, f, smooth=True)

    def build(self, name, coll, recalc=True):
        me = bpy.data.meshes.new(name)
        if recalc:
            bmesh.ops.recalc_face_normals(self.bm, faces=self.bm.faces[:])
        self.bm.to_mesh(me); self.bm.free()
        for m in self.mats:
            me.materials.append(m)
        ob = bpy.data.objects.new(name, me)
        coll.objects.link(ob)
        return ob


# wall frame: origin (T), tangent t (T), outward normal n = t x up
class WF:
    def __init__(self, o, t):
        self.o = Vector(o); self.t = Vector(t); self.up = Vector((0, 1, 0))
        self.n = self.t.cross(self.up)

    def p(self, u, y, w):  # local -> blender
        q = self.o + self.t * u + self.up * y + self.n * w
        return T(q.x, q.y, q.z)

    def box(self, B, m, u0, u1, y0, y1, w0, w1):
        pts = [self.p(u0, y0, w0), self.p(u1, y0, w0), self.p(u1, y1, w0), self.p(u0, y1, w0)]
        B.prism(m, pts, self.p(0, 0, w1) - self.p(0, 0, w0))


def build(view='street', dusk=False, grass=True, quality=1.0):
    random.seed(7)
    sc = bpy.context.scene
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    C = bpy.data.collections.new('Model'); sc.collection.children.link(C)
    CUT = bpy.data.collections.new('Cutters'); sc.collection.children.link(CUT)
    CUT.hide_render = True
    PROTO = bpy.data.collections.new('Proto'); sc.collection.children.link(PROTO)

    house = (HX0, HX1, -HZ1, -HZ0)
    M = {
        'wood_wall': MT.wood('Laerche Fassade', house=house),
        'wood': MT.wood('Laerche'),
        'wood_soffit': MT.wood('Laerche Untersicht', board=0.12, cols=((0.38, 0.22, 0.10), (0.46, 0.28, 0.14), (0.33, 0.19, 0.09), (0.52, 0.33, 0.18))),
        'oak': MT.wood('Eiche Tuer', board=0.11, groove=0.004, cols=((0.25, 0.15, 0.08), (0.3, 0.19, 0.1), (0.22, 0.13, 0.07), (0.33, 0.21, 0.12)), rough=0.5),
        'deck': MT.wood('Laerche Belag', board=0.12, groove=0.006, horizontal_boards=True, cols=((0.30, 0.19, 0.10), (0.36, 0.23, 0.12), (0.27, 0.17, 0.09), (0.40, 0.26, 0.14))),
        'floor': MT.wood('Eiche Boden', board=0.2, groove=0.002, horizontal_boards=True, cols=((0.36, 0.25, 0.15), (0.42, 0.29, 0.17), (0.33, 0.22, 0.13), (0.45, 0.31, 0.19)), rough=0.4),
        'plaster_wall': MT.plaster('Putz Fassade', house=house),
        'plaster': MT.plaster('Putz'),
        'white': MT.simple('Weiss innen', (0.78, 0.77, 0.74), rough=0.9),
        'roof': MT.metal_roof('Stehfalz'),
        'metal': MT.simple('Anthrazit', (0.045, 0.047, 0.05), rough=0.42, metal=0.6),
        'frame': MT.simple('Rahmen', (0.035, 0.037, 0.04), rough=0.38, metal=0.3),
        'zinc': MT.simple('Titanzink', (0.32, 0.33, 0.34), rough=0.35, metal=0.9),
        'steel': MT.simple('Edelstahl', (0.6, 0.6, 0.6), rough=0.25, metal=1.0),
        'glass': MT.glass('Glas'),
        'rail': MT.glass('Glas Gelaender', (0.85, 0.93, 0.9)),
        'tiles': MT.tiles('Terrassenplatten', (0.40, 0.385, 0.36), (0.12, 0.115, 0.11), 0.6, 1.0, 0.08),
        'paver': MT.tiles('Pflaster', (0.30, 0.29, 0.275), (0.09, 0.085, 0.08), 0.2, 1.5, 0.15, 0.85),
        'concrete': MT.simple('Sichtbeton', (0.38, 0.375, 0.36), rough=0.85, bump=0.15, bscale=30, cvar=0.08),
        'ramp': MT.simple('Rampe Beton', (0.30, 0.295, 0.285), rough=0.9, bump=0.25, bscale=60, cvar=0.1),
        'granite': MT.simple('Granit', (0.33, 0.33, 0.32), rough=0.6, bump=0.1, bscale=120, cvar=0.15),
        'asphalt': MT.asphalt('Asphalt'),
        'gravel': MT.gravel('Kies'),
        'soil': MT.simple('Erde', (0.06, 0.045, 0.03), rough=1.0, bump=0.6, bscale=40),
        'ground': MT.ground('Boden'),
        'fabric': MT.simple('Stoff', (0.35, 0.33, 0.30), rough=0.95, bump=0.1, bscale=400),
        'sofa': MT.simple('Sofa', (0.20, 0.20, 0.21), rough=0.95, bump=0.1, bscale=300),
        'garage_door': MT.wood('Garagentor', board=0.146),
    }

    # ------------------------------------------------------------ house walls (boolean openings)
    W = {
        'front': WF((HX0, 0, HZ1), (1, 0, 0)),
        'rear': WF((HX1, 0, HZ0), (-1, 0, 0)),
        'left': WF((HX0, 0, HZ0), (0, 0, 1)),
        'right': WF((HX1, 0, HZ1), (0, 0, -1)),
    }
    EGH, OGS, OGH = 2.47, 4.22, 5.55
    OPEN = {
        'front': [(2.3, 3.4, 0.0, EGH, 1, ''), (6.8, 8.0, 0.0, EGH, 1, ''), (4.25, 6.05, 0.0, EGH, 0, 'door'),
                  (1.2, 3.4, 3.36, OGH, 2, ''), (6.6, 8.8, 3.36, OGH, 2, '')],
        'rear': [(1.0, 3.7, 0.0, 2.5, 2, ''), (6.3, 9.0, 0.0, 2.5, 2, ''), (1.2, 3.3, 3.36, OGH, 2, ''), (6.7, 8.8, 3.36, OGH, 2, '')],
        'left': [(1.0, 2.8, 0.0, EGH, 1, ''), (7.4, 9.2, 0.0, EGH, 1, ''), (1.1, 2.8, OGS, OGH, 1, ''), (7.0, 8.0, OGS, OGH, 1, ''), (12.3, 13.6, OGS, OGH, 1, '')],
        'right': [(13.2, 14.6, 0.0, EGH, 1, ''), (8.6, 11.0, 0.0, EGH, 2, ''), (2.9, 4.0, 0.95, EGH, 1, ''),
                  (3.3, 4.5, OGS, OGH, 1, ''), (6.7, 7.9, OGS, OGH, 1, ''), (9.6, 11.4, OGS, OGH, 2, ''), (13.2, 15.0, OGS, OGH, 2, '')],
    }
    BW = Builder()  # windows, frames, misc house details
    yE, yR = roof_under(HX0), roof_under(RIDGE_X)
    for side, wf in W.items():
        long = side in ('left', 'right')
        L = 16 if long else 10
        u0, u1 = (TH, L - TH) if long else (0, L)
        ops = OPEN[side]
        # EG plaster
        B1 = Builder()
        wf.box(B1, M['plaster_wall'], u0, u1, -0.3, WOOD_FROM, -TH, 0)
        eg = B1.build(f'EG_{side}', C)
        # OG wood
        B2 = Builder(); e = CLAD
        ou0, ou1 = (TH, L - TH) if long else (-e, L + e)
        if long:
            pts = [(ou0, WOOD_FROM), (ou1, WOOD_FROM), (ou1, yE), (ou0, yE)]
        else:
            pts = [(ou0, WOOD_FROM), (ou1, WOOD_FROM), (ou1, yE - e * TAN), (5, yR), (ou0, yE - e * TAN)]
        B2.prism(M['wood_wall'], [wf.p(u, y, e) for u, y in pts], wf.p(0, 0, -TH) - wf.p(0, 0, e))
        og = B2.build(f'OG_{side}', C)
        # drip profile between plaster and wood
        wf.box(BW, M['metal'], ou0 - 0.01, ou1 + 0.01, WOOD_FROM - 0.035, WOOD_FROM + 0.004, -0.06, e + 0.018)
        for (a, b, y0, y1, panels, kind) in ops:
            cb = Builder()
            wf.box(cb, M['white'], a, b, y0 if y0 > 0.05 else -0.05, y1, -TH - 0.3, 0.3)
            cut = cb.build(f'cut_{side}_{a}', CUT)
            target = og if y0 >= WOOD_FROM else eg
            mod = target.modifiers.get('Openings') or target.modifiers.new('Openings', 'BOOLEAN')
            mod.operation = 'DIFFERENCE'; mod.operand_type = 'COLLECTION'; mod.solver = 'EXACT'
            sub = bpy.data.collections.get(f'cut_{target.name}') or bpy.data.collections.new(f'cut_{target.name}')
            if sub.name not in CUT.children:
                CUT.children.link(sub)
            CUT.objects.unlink(cut); sub.objects.link(cut)
            mod.collection = sub
            og_ = y0 >= WOOD_FROM
            inset = 0.15 + (e if og_ else 0)
            if kind == 'door':
                entrance(BW, M, wf, a, b, y0, y1)
            else:
                window(BW, M, wf, a, b, y0, y1, panels, inset, sill=y0 > 0.3)
    BW.build('Fenster_Details', C)

    # ------------------------------------------------------------ interior (floors, ceilings, a few furnishings)
    BI = Builder()
    BI.box(M['floor'], HX0 + TH - 0.01, HX1 - TH + 0.01, -0.3, 0.0, HZ0 + TH - 0.01, HZ1 - TH + 0.01)
    BI.box(M['white'], HX0 + TH - 0.01, HX1 - TH + 0.01, 2.75, 3.13, HZ0 + TH - 0.01, HZ1 - TH + 0.01)
    BI.box(M['floor'], HX0 + TH - 0.01, HX1 - TH + 0.01, 3.13, 3.33, HZ0 + TH - 0.01, HZ1 - TH + 0.01)
    # interior partition walls (to give depth): EG core wall, OG corridor walls
    BI.box(M['white'], HX0 + TH, 10.2, 0, 2.75, -19.0, -18.85)
    BI.box(M['white'], 13.3, HX1 - TH, 0, 2.75, -15.6, -15.45)
    BI.box(M['white'], HX0 + TH, HX1 - TH, 3.33, 5.9, -17.6, -17.45)
    # dining table + chairs near garden glazing, sofa, kitchen island
    BI.box(M['oak'], 13.0, 15.4, 0.72, 0.76, -23.6, -22.6)
    for zz in (-23.35, -22.85):
        BI.box(M['metal'], 13.1, 13.15, 0, 0.72, zz, zz + 0.05); BI.box(M['metal'], 15.25, 15.3, 0, 0.72, zz, zz + 0.05)
    for xx in (13.3, 14.0, 14.7):
        for zz, d in ((-24.15, 1), (-22.05, -1)):
            BI.box(M['fabric'], xx, xx + 0.45, 0.45, 0.5, zz, zz + 0.45 * d)
            BI.box(M['fabric'], xx, xx + 0.45, 0.5, 0.95, zz + (0.42 if d > 0 else -0.42) * 0 - 0.02 * d, zz - 0.06 * d)
    BI.box(M['sofa'], 7.4, 10.0, 0.0, 0.42, -22.6, -21.6); BI.box(M['sofa'], 7.4, 10.0, 0.42, 0.85, -21.8, -21.6)
    BI.box(M['sofa'], 7.4, 7.6, 0.42, 0.65, -22.6, -21.6); BI.box(M['sofa'], 9.8, 10.0, 0.42, 0.65, -22.6, -21.6)
    BI.box(M['white'], 13.4, 15.6, 0, 0.92, -20.2, -19.2); BI.box(M['granite'], 13.35, 15.65, 0.92, 0.96, -20.25, -19.15)
    for xx in (8.3, 14.2):  # pendant lamps
        BI.box(M['metal'], xx - 0.25, xx + 0.25, 2.0, 2.06, -23.3, -22.9)
    BI.build('Innenraum', C)

    # ------------------------------------------------------------ balconies
    BB = Builder()
    for zw, d in ((HZ1, 1), (HZ0, -1)):
        zo = zw + d * 1.5
        za, zb = min(zw, zo), max(zw, zo)
        x0, x1 = HX0 - 0.04, HX1 + 0.04
        BB.box(M['wood_soffit'], x0, x1, 3.03, 3.33, za, zb)
        BB.box(M['deck'], x0 + 0.06, x1 - 0.06, 3.33, 3.36, za, zb)
        t = 0.06
        zf0, zf1 = (zo - t, zo) if d > 0 else (zo, zo + t)
        BB.box(M['wood'], x0, x1, 2.96, 4.36, zf0, zf1)
        BB.box(M['wood'], x0, x0 + t, 2.96, 4.36, za, zb)
        BB.box(M['wood'], x1 - t, x1, 2.96, 4.36, za, zb)
        BB.box(M['metal'], x0 - 0.01, x1 + 0.01, 4.36, 4.39, min(zf0, zf1) - 0.01, max(zf0, zf1) + 0.01)
        BB.box(M['metal'], x0 - 0.01, x0 + t + 0.01, 4.36, 4.39, za, zb)
        BB.box(M['metal'], x1 - t - 0.01, x1 + 0.01, 4.36, 4.39, za, zb)
    BB.build('Balkone', C)

    # ------------------------------------------------------------ roofs
    BR = Builder()
    gable_roof(BR, M, RIDGE_X, RIDGE_Y, 5 + EAVE_OVER, HZ0 - GABLE_OVER, HZ1 + GABLE_OVER, ROOF_TH, SKIN, snow=True)
    # downpipes
    yEo = RIDGE_Y - 6.5 * TAN - SKIN - ROOF_TH / COS
    for xg, xw in ((HX0 - 1.59, HX0 - 0.07), (HX1 + 1.59, HX1 + 0.07)):
        for zc in (HZ1 - 0.35, HZ0 + 0.35):
            BR.cyl(M['zinc'], T(xw, GROUND - 0.05, zc), T(xw, yEo + 0.05, zc), 0.05)
            BR.cyl(M['zinc'], T(xw, yEo + 0.05, zc), T(xg, yEo + 0.05, zc), 0.05)
    # chimney
    cx, cz = 9.7, -20.0
    BR.box(M['plaster'], cx - 0.3, cx + 0.3, roof_under(cx) - 0.2, 8.85, cz - 0.3, cz + 0.3)
    BR.box(M['zinc'], cx - 0.4, cx + 0.4, 8.85, 8.9, cz - 0.4, cz + 0.4)
    BR.box(M['zinc'], cx - 0.36, cx + 0.36, 9.08, 9.12, cz - 0.36, cz + 0.36)
    for a in (-0.34, 0.3):
        for c in (-0.34, 0.3):
            BR.box(M['zinc'], cx + a, cx + a + 0.04, 8.9, 9.08, cz + c, cz + c + 0.04)
    BR.build('Dach', C)

    # ------------------------------------------------------------ hardscape
    BH = Builder()
    BH.box(M['tiles'], HX0 - 0.15, HX1 + 0.15, -0.3, 0.0, HZ0 - 3.7, HZ0)
    BH.box(M['tiles'], 6.2, 17.2, -0.3, 0.0, HZ1, HZ1 + 1.1)
    BH.box(M['paver'], 10.55, 12.85, -0.4, GROUND + 0.04, HZ1 + 1.1, 0.25)
    for x0, x1, z0, z1 in ((HX0 - 0.4, HX0, HZ0, -20.6 - 0.0), (HX0 - 0.4, HX0, -20.6, HZ1), (HX1, HX1 + 0.4, HZ0, HZ1)):
        BH.box(M['gravel'], x0, x1, -0.4, GROUND + 0.03, z0, z1)
    # street, curb, apron
    BH.box(M['asphalt'], -60, 90, -0.5, GROUND + 0.01, 0.35, 6.4)
    BH.box(M['granite'], -60, 90, -0.4, GROUND + 0.04, 0.2, 0.35)
    BH.box(M['granite'], -60, 90, -0.4, GROUND + 0.04, 6.4, 6.55)
    BH.box(M['asphalt'], 0.55, 4.45, -0.5, GROUND + 0.012, 0.0, 0.36)
    # ramp
    def ry(d):
        return GROUND - 0.05 * d if d <= 3 else (GROUND - 0.15 - 0.2 * (d - 3) if d <= 13 else GROUND - 2.15 - 0.1 * (d - 13))
    ds = [0, 1.5, 3, 4.5, 6.2, 8, 10, 12.3, 13, 14]
    for i in range(len(ds) - 1):
        a, b = ds[i], ds[i + 1]
        BH.faces(M['ramp'], [T(0.8, ry(a), -a), T(4.2, ry(a), -a), T(4.2, ry(b), -b), T(0.8, ry(b), -b),
                             T(0.8, ry(a) - 0.3, -a), T(4.2, ry(a) - 0.3, -a), T(4.2, ry(b) - 0.3, -b), T(0.8, ry(b) - 0.3, -b)],
                 [(0, 1, 2, 3), (7, 6, 5, 4), (0, 3, 7, 4), (1, 5, 6, 2), (0, 4, 5, 1), (3, 2, 6, 7)])
    for x0 in (0.55, 4.2):
        pts2 = [(0, -0.02), (6.2, -0.02), (6.2, ry(6.2) - 0.35), (3, ry(3) - 0.35), (0, ry(0) - 0.35)]
        BH.prism(M['concrete'], [T(x0, y, -d) for d, y in pts2], (0.25, 0, 0))
        BH.box(M['metal'], x0 - 0.01, x0 + 0.26, -0.02, 0.0, -6.2, 0)
    BH.box(M['steel'], 0.8, 4.2, GROUND - 0.02, GROUND + 0.003, -0.35, -0.15)
    # ramp housing (gable facing the street)
    za, zb, hx0, hx1, eave, hcx = -12.3, -6.2, 0.55, 4.45, 2.37, 2.5
    top = eave + 1.95 * TAN
    fp = [(hx0, -1.05), (0.8, -1.05), (0.8, 2.15), (4.2, 2.15), (4.2, -1.05), (hx1, -1.05), (hx1, eave), (hcx, top), (hx0, eave)]
    BH.prism(M['wood'], [T(x, y, zb) for x, y in fp], (0, 0.25, 0))
    bp = [(hx0, -0.3), (hx1, -0.3), (hx1, eave), (hcx, top), (hx0, eave)]
    BH.prism(M['wood'], [T(x, y, za + 0.25) for x, y in bp], (0, 0.25, 0))
    BH.box(M['wood'], hx0, 0.8, -2.3, eave, za, zb); BH.box(M['wood'], 4.2, hx1, -2.3, eave, za, zb)
    BH.box(M['garage_door'], 0.8, 4.2, ry(6.35), 2.15, zb - 0.2, zb - 0.14)
    BH.box(M['frame'], 0.8, 4.2, 2.1, 2.15, zb - 0.2, zb - 0.01)
    gable_roof(BH, M, hcx, top + 0.03 + 0.2 / COS, 1.95 + 0.45, za - 0.45, zb + 0.55, 0.2, 0.03, gutter=False)
    # raised planter
    px0, px1, pz0, pz1 = 0.8, 4.1, -18.7, -12.6
    BH.box(M['concrete'], px0, px1, -0.3, 1.0, pz0, pz0 + 0.12); BH.box(M['concrete'], px0, px1, -0.3, 1.0, pz1 - 0.12, pz1)
    BH.box(M['concrete'], px0, px0 + 0.12, -0.3, 1.0, pz0, pz1); BH.box(M['concrete'], px1 - 0.12, px1, -0.3, 1.0, pz0, pz1)
    BH.box(M['soil'], px0 + 0.12, px1 - 0.12, -0.3, 0.9, pz0 + 0.12, pz1 - 0.12)
    # light well
    lx0, lx1, lz0, lz1, bot = 4.05, HX0, HZ0, -20.6, -2.9
    BH.box(M['concrete'], lx0 - 0.2, lx0, bot, 0.05, lz0, lz1)
    BH.box(M['concrete'], lx0 - 0.2, lx1, bot, 0.05, lz0 - 0.2, lz0)
    BH.box(M['concrete'], lx0 - 0.2, lx1, bot, 0.05, lz1, lz1 + 0.2)
    BH.box(M['gravel'], lx0, lx1, bot - 0.1, bot + 0.05, lz0, lz1)
    BH.box(M['concrete'], lx1 - 0.02, lx1 + 0.3, bot, -0.3, lz0 - 0.2, lz1 + 0.2)
    BH.box(M['glass'], lx1 - 0.05, lx1 - 0.03, bot + 0.1, -0.5, lz0 + 0.4, lz1 - 0.4)
    BH.box(M['white'], lx1 + 0.3, lx1 + 0.35, bot, -0.3, lz0, lz1)
    for (ax, az, bx, bz) in ((lx0 - 0.1, lz0 - 0.1, lx0 - 0.1, lz1 + 0.1), (lx0 - 0.1, lz0 - 0.1, lx1, lz0 - 0.1), (lx0 - 0.1, lz1 + 0.1, lx1, lz1 + 0.1)):
        BH.box(M['rail'], min(ax, bx) - 0.01, max(ax, bx) + 0.01, 0.06, 1.0, min(az, bz) - 0.01, max(az, bz) + 0.01)
        BH.box(M['steel'], min(ax, bx) - 0.02, max(ax, bx) + 0.02, 1.0, 1.04, min(az, bz) - 0.025, max(az, bz) + 0.025)
    # terrace furniture
    tx, tz = 13.6, -27.6
    BH.box(M['oak'], tx - 1.1, tx + 1.1, 0.72, 0.76, tz - 0.48, tz + 0.48)
    for sx in (-0.95, 0.95):
        BH.box(M['metal'], tx + sx - 0.04, tx + sx + 0.04, 0, 0.72, tz - 0.4, tz + 0.4)
    for sz in (-0.85, 0.85):
        BH.box(M['oak'], tx - 1.0, tx + 1.0, 0.43, 0.47, tz + sz - 0.18, tz + sz + 0.18)
        for sx in (-0.85, 0.85):
            BH.box(M['metal'], tx + sx - 0.03, tx + sx + 0.03, 0, 0.43, tz + sz - 0.15, tz + sz + 0.15)
    for pxx in (6.95, 16.45):
        BH.box(M['metal'], pxx - 0.35, pxx + 0.35, 0, 0.6, -28.95, -28.25)
        BH.box(M['soil'], pxx - 0.32, pxx + 0.32, 0.5, 0.57, -28.92, -28.28)
    BH.build('Aussenanlagen', C)

    # ------------------------------------------------------------ lawn (grid aligned to exclusions)
    excl = [(HX0 - 0.4, HX1 + 0.4, HZ0, HZ1), (HX0 - 0.15, HX1 + 0.15, HZ0 - 3.7, HZ0), (6.2, 17.2, HZ1, HZ1 + 1.1),
            (10.55, 12.85, HZ1, 0.35), (0.55, 4.45, -12.8, 0.35), (0.8, 4.1, -18.7, -12.6), (3.85, HX0, HZ0 - 0.2, -20.4),
            (-60, 90, 0.2, 6.55)]
    lawn_box = (-30, 55, -60, 26)
    make_lawn(C, M, excl, lawn_box, grass and quality > 0, view)

    # ------------------------------------------------------------ vegetation
    leafB = MT.leaf('Laub Birke', ((0.07, 0.15, 0.03), (0.15, 0.24, 0.05), (0.24, 0.29, 0.07)))
    leafA = MT.leaf('Laub Ahorn', ((0.05, 0.11, 0.025), (0.09, 0.17, 0.035), (0.16, 0.22, 0.05)))
    leafH = MT.leaf('Laub Hecke', ((0.03, 0.07, 0.015), (0.06, 0.11, 0.025), (0.10, 0.15, 0.03)))
    barkB = MT.bark('Rinde Birke', birch=True)
    barkA = MT.bark('Rinde')
    clB = leaf_cluster('cluster_birch', leafB, 0.055, 9, PROTO)
    clA = leaf_cluster('cluster_maple', leafA, 0.09, 7, PROTO)
    clH = leaf_cluster('cluster_hedge', leafH, 0.045, 8, PROTO)
    trees = [(22.3, -6.0, 10.0, 11, 'birch'), (21.3, -15.5, 8.5, 12, 'birch'), (3.0, -31.5, 11.0, 13, 'broad'),
             (21.4, -28.6, 9.0, 14, 'broad'), (7.6, -2.6, 7.0, 15, 'birch'),
             (-6, -6, 9, 21, 'broad'), (-4, -34, 11, 22, 'broad'), (30, -40, 12, 23, 'broad'), (29, -4, 8, 24, 'birch'),
             (-22, -36, 13, 25, 'broad'), (46, -30, 12, 26, 'broad'), (-30, -8, 10, 27, 'birch'), (28, 12, 9, 28, 'broad'),
             (-2, 13, 8, 29, 'birch'), (52, 6, 11, 30, 'broad'), (3, 34, 10, 31, 'broad'), (26, 36, 11, 32, 'birch')]
    for (x, z, h, s, k) in trees:
        make_tree(C, f'Baum_{s}', x, z, h, s, k, barkB if k == 'birch' else barkA, clB if k == 'birch' else clA, quality)
    hedges = [(-0.05, 0.75, -37.7, -19.6, 1.7), (22.95, 23.75, -37.7, -11.0, 1.7), (0.7, 22.95, -37.75, -37.0, 1.7)]
    for i, hd in enumerate(hedges):
        make_hedge(C, f'Hecke_{i}', *hd, clH, M, 40 + i, quality)
    shrubs = [(17.9, -8.0, 0.7, 1.1, GROUND), (5.6, -8.2, 0.6, 0.9, GROUND), (13.8, -1.4, 0.5, 0.7, GROUND),
              (18.0, -27.5, 0.8, 1.3, GROUND), (5.4, -28.8, 0.7, 1.0, GROUND), (6.95, -28.6, 0.4, 0.8, 0.57), (16.45, -28.6, 0.4, 0.8, 0.57)]
    for x in (1.3, 2.2, 3.1):
        for z in (-17.9, -16.6, -15.3, -14.0):
            shrubs.append((x + random.uniform(-0.2, 0.2), z + random.uniform(-0.2, 0.2), random.uniform(0.3, 0.45), random.uniform(0.5, 0.9), 0.9))
    for x in (4.7, 5.6):
        for z in (-24.5, -23.0, -21.5):
            shrubs.append((x, z, 0.35, 0.8, -2.8))
    for i, (x, z, r, h, y0) in enumerate(shrubs):
        make_shrub(C, f'Strauch_{i}', x, z, r, h, y0, clH if i % 3 else clA, barkA, 100 + i, quality)

    # ------------------------------------------------------------ context houses
    ctx = [(-13.5, -19, 11, 14, 5.8), (37.5, -18, 10, 13, 5.6), (-12, 22, 11, 15, 5.8), (14, 24, 12, 14, 6.0),
           (40, 23, 10, 13, 5.6), (10, -62, 12, 15, 6.0), (-25, -55, 11, 14, 5.8)]
    BC = Builder()
    for (cx_, cz_, w, l, ev) in ctx:
        context_house(BC, M, cx_, cz_, w, l, ev)
    BC.build('Nachbarhaeuser', C)

    # ------------------------------------------------------------ distant landscape
    make_landscape(C, quality)
    return M


# ---------------------------------------------------------------- components
def window(B, M, wf, u0, u1, y0, y1, panels, inset, sill):
    fw, dep = 0.075, 0.075
    w1 = -inset; w0 = w1 - dep
    yb = y0 if y0 > 0.05 else 0.0
    wf.box(B, M['frame'], u0, u1, y1 - fw, y1, w0, w1)
    wf.box(B, M['frame'], u0, u1, yb, yb + fw, w0, w1)
    wf.box(B, M['frame'], u0, u0 + fw, yb + fw, y1 - fw, w0, w1)
    wf.box(B, M['frame'], u1 - fw, u1, yb + fw, y1 - fw, w0, w1)
    n = max(1, panels)
    edges = [u0 + fw + (u1 - u0 - 2 * fw) * i / n for i in range(n + 1)]
    for i in range(1, n):
        wf.box(B, M['frame'], edges[i] - 0.045, edges[i] + 0.045, yb + fw, y1 - fw, w0 - 0.005, w1)
    for i in range(n):
        a, b = edges[i] + (0.0 if i == 0 else 0.045), edges[i + 1] - (0.0 if i == n - 1 else 0.045)
        # sash profile
        sw = 0.045
        wf.box(B, M['frame'], a, b, y1 - fw - sw, y1 - fw, w0 + 0.01, w1 - 0.01)
        wf.box(B, M['frame'], a, b, yb + fw, yb + fw + sw, w0 + 0.01, w1 - 0.01)
        wf.box(B, M['frame'], a, a + sw, yb + fw + sw, y1 - fw - sw, w0 + 0.01, w1 - 0.01)
        wf.box(B, M['frame'], b - sw, b, yb + fw + sw, y1 - fw - sw, w0 + 0.01, w1 - 0.01)
        wf.box(B, M['glass'], a + sw, b - sw, yb + fw + sw, y1 - fw - sw, w0 + 0.025, w0 + 0.049)
    if sill:
        wf.box(B, M['metal'], u0 - 0.03, u1 + 0.03, y0 - 0.05, y0 + 0.005, w1, 0.05)


def entrance(B, M, wf, u0, u1, y0, y1):
    inset, dep, fw, dw = 0.22, 0.08, 0.07, 1.15
    dc = (u0 + u1) / 2
    w1 = -inset; w0 = w1 - dep
    wf.box(B, M['frame'], u0, u1, y1 - fw, y1, w0, w1)
    wf.box(B, M['frame'], u0, u0 + fw, 0, y1 - fw, w0, w1)
    wf.box(B, M['frame'], u1 - fw, u1, 0, y1 - fw, w0, w1)
    wf.box(B, M['frame'], dc - dw / 2 - 0.06, dc - dw / 2, 0, y1 - fw, w0, w1)
    wf.box(B, M['frame'], dc + dw / 2, dc + dw / 2 + 0.06, 0, y1 - fw, w0, w1)
    wf.box(B, M['oak'], dc - dw / 2, dc + dw / 2, 0.01, y1 - fw, w0 + 0.015, w1 - 0.015)
    wf.box(B, M['steel'], dc + dw / 2 - 0.16, dc + dw / 2 - 0.13, 0.7, 1.9, w1 - 0.015, w1 + 0.045)
    for a, b in ((u0 + fw, dc - dw / 2 - 0.06), (dc + dw / 2 + 0.06, u1 - fw)):
        wf.box(B, M['glass'], a, b, 0.01, y1 - fw, w0 + 0.03, w0 + 0.05)
    wf.box(B, M['granite'], u0 - 0.1, u1 + 0.1, -0.03, 0.02, w1, 0.03)


def gable_roof(B, M, cx, yR, half, z0, z1, th, skin, snow=False, gutter=True):
    yE = yR - half * TAN
    thv = th / COS
    L = z1 - z0
    for s in (-1, 1):
        xe = cx + s * half
        body = [T(xe, yE - skin, z1), T(cx, yR - skin, z1), T(cx, yR - skin - thv, z1), T(xe, yE - skin - thv, z1)]
        B.prism(M['wood_soffit'], body, (0, L, 0))
        o = 0.04
        xs, ys = xe + s * o, yE - o * TAN
        sk = [T(xs, ys - skin - 0.012, z1 + o), T(xs, ys, z1 + o), T(cx, yR, z1 + o), T(cx, yR - skin, z1 + o)]
        B.prism(M['roof'], sk, (0, L + 2 * o, 0))
        if gutter:
            gx, gy = xe + s * 0.1, yE - skin - thv + 0.07
            # half-round gutter: U shape
            for k in range(10):
                a0 = math.pi * k / 10; a1 = math.pi * (k + 1) / 10
                p = lambda a: (gx + 0.085 * math.cos(a), gy - 0.085 * math.sin(a))
                (x0_, y0_), (x1_, y1_) = p(a0), p(a1)
                B.faces(M['zinc'], [T(x0_, y0_, z0 - 0.05), T(x1_, y1_, z0 - 0.05), T(x1_, y1_, z1 + 0.05), T(x0_, y0_, z1 + 0.05)], [(0, 1, 2, 3)], smooth=True)
            B.cyl(M['zinc'], T(gx + 0.085, gy, z0 - 0.05), T(gx + 0.085, gy, z1 + 0.05), 0.01, 6)
            B.cyl(M['zinc'], T(gx - 0.085, gy, z0 - 0.05), T(gx - 0.085, gy, z1 + 0.05), 0.01, 6)
        if snow:
            for d, dy in ((0.9, 0.11), (0.9, 0.16)):
                xx = xe - s * d
                yy = yR - abs(xx - cx) * TAN + dy
                B.cyl(M['zinc'], T(xx, yy, z0 + 0.2), T(xx, yy, z1 - 0.2), 0.014, 6)
            z = z0 + 0.4
            while z < z1 - 0.2:
                xx = xe - s * 0.9
                yy = yR - abs(xx - cx) * TAN
                B.box(M['zinc'], xx - 0.03, xx + 0.03, yy, yy + 0.19, z - 0.012, z + 0.012)
                z += 1.0
    rc = [T(cx - 0.17, yR - 0.04, z1 + 0.05), T(cx + 0.17, yR - 0.04, z1 + 0.05), T(cx + 0.17, yR + 0.005, z1 + 0.05), T(cx, yR + 0.07, z1 + 0.05), T(cx - 0.17, yR + 0.005, z1 + 0.05)]
    B.prism(M['zinc'], rc, (0, L + 0.1, 0))


def context_house(B, M, cx, cz, w, l, eave):
    x0, x1, z0, z1 = cx - w / 2, cx + w / 2, cz - l / 2, cz + l / 2
    B.box(M['plaster'], x0, x1, -0.3, 2.8, z0, z1)
    B.box(M['wood'], x0 - 0.02, x1 + 0.02, 2.8, eave, z0 - 0.02, z1 + 0.02)
    tn = math.tan(math.radians(22))
    for zz, ext in ((z1 + 0.02, 0.3), (z0 - 0.02, -0.3)):
        B.prism(M['wood'], [T(x0, eave, zz), T(x1, eave, zz), T(cx, eave + w / 2 * tn, zz)], (0, ext, 0))
    half, yR = w / 2 + 1.2, eave + w / 2 * tn + 0.25
    for s in (-1, 1):
        xe = cx + s * half
        B.prism(M['roof'], [T(xe, yR - half * tn, z1 + 1.5), T(cx, yR, z1 + 1.5), T(cx, yR - 0.25, z1 + 1.5), T(xe, yR - half * tn - 0.25, z1 + 1.5)], (0, l + 3, 0))
    for zz in (z1 + 0.012, z0 - 0.012):
        for xx in (cx - w / 4, cx + w / 4):
            for y0, y1 in ((0.3, 2.3), (3.6, 5.0)):
                B.box(M['frame'], xx - 0.75, xx + 0.75, y0 - 0.05, y1 + 0.05, zz - 0.01, zz + 0.01)
                B.box(M['glass'], xx - 0.68, xx + 0.68, y0, y1, zz - 0.02 if zz > cz else zz, zz if zz > cz else zz + 0.02)
    for xx in (x1 + 0.012, x0 - 0.012):
        zz = z0 + 2
        while zz < z1 - 1:
            for y0, y1 in ((0.6, 2.2), (3.8, 5.0)):
                B.box(M['frame'], xx - 0.01, xx + 0.01, y0 - 0.05, y1 + 0.05, zz - 0.65, zz + 0.65)
            zz += 3.2


def make_lawn(C, M, excl, box, grass, view):
    X0, X1, Z0, Z1 = box
    xs = set([X0, X1]); zs = set([Z0, Z1])
    for (a, b, c, d) in excl:
        for v in (a, b):
            if X0 < v < X1: xs.add(v)
        for v in (c, d):
            if Z0 < v < Z1: zs.add(v)
    step = 1.0
    x = X0
    while x < X1: xs.add(round(x, 3)); x += step
    z = Z0
    while z < Z1: zs.add(round(z, 3)); z += step
    xs, zs = sorted(xs), sorted(zs)
    bm = bmesh.new()
    vid = {}
    def V(i, j):
        k = (i, j)
        if k not in vid:
            xx, zz = xs[i], zs[j]
            h = GROUND + 0.015 * noise.noise(Vector((xx * 0.4, zz * 0.4, 0)))
            vid[k] = bm.verts.new(T(xx, h, zz))
        return vid[k]
    for i in range(len(xs) - 1):
        for j in range(len(zs) - 1):
            cxm, czm = (xs[i] + xs[i + 1]) / 2, (zs[j] + zs[j + 1]) / 2
            if any(a < cxm < b and c < czm < d for (a, b, c, d) in excl):
                continue
            bm.faces.new([V(i, j), V(i + 1, j), V(i + 1, j + 1), V(i, j + 1)])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    for f in bm.faces:
        if f.normal.z < 0:
            f.normal_flip()
    me = bpy.data.meshes.new('Rasen'); bm.to_mesh(me); bm.free()
    me.materials.append(M['ground'])
    ob = bpy.data.objects.new('Rasen', me); C.objects.link(ob)
    # big ground plane beyond
    B = Builder()
    g = GROUND - 0.02
    for (a, b, c, d) in ((-400, 400, -400, Z0), (-400, 400, Z1, 400), (-400, X0, Z0, Z1), (X1, 400, Z0, Z1)):
        B.faces(M['ground'], [T(a, g, c), T(b, g, c), T(b, g, d), T(a, g, d)], [(0, 3, 2, 1)])
    B.build('Boden_fern', C)
    if not grass:
        return
    # density weight: only near the plot / camera
    vg = ob.vertex_groups.new(name='density')
    for v in me.vertices:
        p = v.co
        x, zz = p.x, -p.y
        d = 1.0
        if x < -12 or x > 36 or zz < -45 or zz > 16:
            d = 0.0
        vg.add([v.index], d, 'REPLACE')
    gm = MT.grass_hair('Grashalme')
    me.materials.append(gm)
    mod = ob.modifiers.new('Gras', 'PARTICLE_SYSTEM')
    ps = mod.particle_system
    ps.vertex_group_density = 'density'
    p = ps.settings
    p.type = 'HAIR'
    area = 48 * 61
    p.count = int(area * 22)
    p.hair_length = 0.085
    p.use_advanced_hair = True
    p.emit_from = 'FACE'
    p.use_emit_random = True
    p.normal_factor = 0.065
    p.factor_random = 0.035
    p.use_velocity_length = True
    p.material_slot = 'Grashalme'
    p.child_type = 'INTERPOLATED'
    p.child_percent = 2
    p.rendered_child_count = 70
    p.child_radius = 0.12
    p.clump_factor = 0.0
    p.roughness_1 = 0.02
    p.roughness_1_size = 0.3
    p.roughness_endpoint = 0.035
    p.roughness_2 = 0.03
    p.child_length = 1.0
    p.child_length_threshold = 0.35
    p.render_step = 3
    p.display_step = 2
    p.root_radius = 1.0
    p.tip_radius = 0.0
    p.radius_scale = 0.0035
    p.use_close_tip = True
    p.kink = 'NO'
    try:
        p.length_random = 0.5
    except Exception:
        pass
    ps.seed = 3


def leaf_cluster(name, mat, leaf_len, n, coll):
    """twig with n leaves lying roughly in the local XY plane, twig along +Y"""
    bm = bmesh.new()
    rnd = random.Random(hash(name) & 0xffff)
    for i in range(n):
        t = i / max(1, n - 1)
        base = Vector((0, t * leaf_len * 2.6, 0))
        ang = (1 if i % 2 else -1) * rnd.uniform(0.5, 1.1) + rnd.uniform(-0.2, 0.2)
        L = leaf_len * rnd.uniform(0.75, 1.15)
        W = L * 0.48
        rot = Matrix.Rotation(ang, 3, 'Z') @ Matrix.Rotation(rnd.uniform(-0.5, 0.5), 3, 'Y') @ Matrix.Rotation(rnd.uniform(-0.3, 0.3), 3, 'X')
        pts = []
        K = 7
        for k in range(K + 1):
            s = k / K
            w = math.sin(math.pi * s) ** 0.8 * W / 2
            pts.append((s * L, w, (s * (1 - s)) * L * 0.25))
        outline = [Vector((x, y, z)) for x, y, z in pts] + [Vector((x, -y, z)) for x, y, z in pts[-2:0:-1]]
        vs = [bm.verts.new(base + rot @ Vector((p.y, p.x, p.z))) for p in outline]
        # fan triangulation around center for smooth shading
        c = bm.verts.new(base + rot @ Vector((0, L * 0.5, L * 0.06)))
        for k in range(len(vs)):
            bm.faces.new([c, vs[k], vs[(k + 1) % len(vs)]])
    # twig
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    me.materials.append(mat)
    for poly in me.polygons:
        poly.use_smooth = True
    ob = bpy.data.objects.new(name, me); coll.objects.link(ob)
    return ob


def instance_on(C, name, cluster, items):
    """items: list of (position Vector(blender), normal Vector, tangent Vector, scale)"""
    bm = bmesh.new()
    for p, nrm, tan, s in items:
        nrm = nrm.normalized(); tan = (tan - nrm * tan.dot(nrm)).normalized()
        b = nrm.cross(tan)
        k = 0.1 * s
        v0 = bm.verts.new(p); v1 = bm.verts.new(p + tan * k); v2 = bm.verts.new(p + b * k)
        bm.faces.new([v0, v1, v2])
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me); C.objects.link(ob)
    inst = bpy.data.objects.new(name + '_c', cluster.data); C.objects.link(inst)
    inst.parent = ob
    ob.instance_type = 'FACES'
    ob.use_instance_faces_scale = True
    ob.instance_faces_scale = 10.0 * 1.4142 / 1.0
    ob.show_instancer_for_render = False
    ob.show_instancer_for_viewport = False
    return ob


def make_tree(C, name, x, z, h, seed, kind, bark, cluster, quality):
    rnd = random.Random(seed)
    birch = kind == 'birch'
    cu = bpy.data.curves.new(name + '_holz', 'CURVE'); cu.dimensions = '3D'
    cu.bevel_depth = 1.0; cu.bevel_resolution = 2; cu.use_fill_caps = True
    leaves = []
    base = T(x, GROUND - 0.2, z)

    def add_branch(pts_rad):
        sp = cu.splines.new('POLY'); sp.points.add(len(pts_rad) - 1)
        for i, (p, r) in enumerate(pts_rad):
            sp.points[i].co = (p.x, p.y, p.z, 1); sp.points[i].radius = r

    def grow(p0, d, length, r0, depth):
        segs = max(3, int(length / 0.35))
        pts = [(p0.copy(), r0)]
        p = p0.copy(); dd = d.normalized()
        for i in range(1, segs + 1):
            t = i / segs
            dd = (dd + Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-1, 1))) * 0.18).normalized()
            if birch and depth >= 1:
                dd = (dd + Vector((0, 0, -0.08 * depth * t))).normalized()
            elif not birch:
                dd = (dd + Vector((0, 0, 0.04))).normalized()
            p = p + dd * (length / segs)
            pts.append((p.copy(), r0 * (1 - 0.75 * t) + 0.004))
        add_branch(pts)
        maxd = 3
        if depth < maxd:
            nchild = {0: 6 if birch else 5, 1: 5, 2: 5}[depth]
            for k in range(nchild):
                t = rnd.uniform(0.35, 0.95) if depth == 0 else rnd.uniform(0.2, 0.95)
                idx = min(len(pts) - 1, int(t * (len(pts) - 1)))
                q, rq = pts[idx]
                axis = (pts[min(idx + 1, len(pts) - 1)][0] - pts[max(idx - 1, 0)][0]).normalized()
                side = axis.orthogonal().normalized()
                side.rotate(Matrix.Rotation(rnd.uniform(0, 2 * math.pi), 3, axis))
                ang = rnd.uniform(0.6, 1.0) if not birch else rnd.uniform(0.7, 1.2)
                nd = (axis * math.cos(ang) + side * math.sin(ang)).normalized()
                grow(q, nd, length * rnd.uniform(0.45, 0.6), rq * 0.6, depth + 1)
        if depth >= 2:
            # leaf clusters along the last part
            nl = int(((26 if birch else 30) if depth == 3 else (10 if birch else 12)) * quality)
            for k in range(nl):
                t = rnd.uniform(0.3, 1.0)
                idx = min(len(pts) - 1, int(t * (len(pts) - 1)))
                q = pts[idx][0] + Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-1, 1))) * 0.12
                out = (q - crown_c)
                nrm = (out.normalized() * 0.5 + Vector((0, 0, 1)) * 0.5 + Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-1, 1))) * 0.6)
                tan = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-0.5, 0.5)))
                if birch:
                    tan = tan + Vector((0, 0, -1.2))
                leaves.append((q, nrm, tan, rnd.uniform(0.8, 1.25)))

    trunk_h = h * (0.95 if birch else 0.45)
    crown_c = base + Vector((0, 0, h * 0.62))
    # trunk
    pts = []
    p = base.copy(); r0 = h * (0.016 if birch else 0.024)
    n = 10
    lean = Vector((rnd.uniform(-0.04, 0.04), rnd.uniform(-0.04, 0.04), 1)).normalized()
    for i in range(n + 1):
        t = i / n
        pts.append((p.copy(), r0 * (1 - 0.7 * t) + 0.01))
        p = p + (lean + Vector((rnd.uniform(-0.05, 0.05), rnd.uniform(-0.05, 0.05), 0))) * (trunk_h / n)
    add_branch(pts)
    if birch:
        for k in range(13):
            t = rnd.uniform(0.35, 0.95)
            idx = int(t * n)
            q, rq = pts[idx]
            a = rnd.uniform(0, 2 * math.pi)
            nd = Vector((math.cos(a), math.sin(a), rnd.uniform(0.5, 1.1))).normalized()
            grow(q, nd, h * rnd.uniform(0.22, 0.32) * (1.15 - t * 0.5), rq * 0.45, 1)
    else:
        top = pts[-1][0]
        for k in range(5):
            a = 2 * math.pi * k / 5 + rnd.uniform(-0.3, 0.3)
            nd = Vector((math.cos(a) * 0.8, math.sin(a) * 0.8, rnd.uniform(0.7, 1.2))).normalized()
            grow(top, nd, h * rnd.uniform(0.32, 0.4), pts[-1][1] * 0.7, 1)
    cu_ob = bpy.data.objects.new(name + '_holz', cu); C.objects.link(cu_ob)
    cu.materials.append(bark)
    instance_on(C, name + '_laub', cluster, leaves)


def make_shrub(C, name, x, z, r, h, y0, cluster, bark, seed, quality):
    rnd = random.Random(seed)
    items = []
    c = T(x, y0 + h * 0.5, z)
    n = int(70 * r * r * h * 9 * quality) + 30
    for i in range(n):
        while True:
            v = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-1, 1)))
            if v.length <= 1: break
        v = v.normalized() * (0.55 + 0.45 * rnd.random() ** 0.5)
        p = c + Vector((v.x * r, v.y * r, v.z * h * 0.5))
        items.append((p, v + Vector((0, 0, 0.5)) + Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-1, 1))) * 0.5,
                      Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-1, 1))), rnd.uniform(0.8, 1.2)))
    instance_on(C, name, cluster, items)


def make_hedge(C, name, x0, x1, z0, z1, h, cluster, M, seed, quality):
    rnd = random.Random(seed)
    B = Builder()
    B.box(M['soil'], x0 + 0.12, x1 - 0.12, GROUND, h - 0.12, z0 + 0.12, z1 - 0.12)
    B.build(name + '_kern', C)
    items = []
    lx, lz = x1 - x0, z1 - z0
    faces = [((x0, 0, 0), lx, lz, 'top'), ((x0, 0, 0), lz, h, 'x0'), ((x1, 0, 0), lz, h, 'x1'), ((0, 0, z0), lx, h, 'z0'), ((0, 0, z1), lx, h, 'z1')]
    dens = 260 * quality
    for _, a, b, tag in faces:
        n = int(a * b * dens)
        for i in range(n):
            u, v = rnd.random(), rnd.random()
            if tag == 'top':
                x, y, z = x0 + u * lx, GROUND + h, z0 + v * lz; nrm = Vector((0, 0, 1))
            elif tag in ('x0', 'x1'):
                x, y, z = (x0 if tag == 'x0' else x1), GROUND + v * h, z0 + u * lz; nrm = Vector((-1 if tag == 'x0' else 1, 0, 0))
            else:
                x, y, z = x0 + u * lx, GROUND + v * h, (z0 if tag == 'z0' else z1); nrm = Vector((0, 1 if tag == 'z0' else -1, 0))
            jitter = noise.noise(Vector((x * 1.7, y * 1.7, z * 1.7))) * 0.08 + rnd.uniform(-0.06, 0.02)
            p = T(x, y, z) + nrm * jitter
            items.append((p, nrm + Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-1, 1))) * 0.7 + Vector((0, 0, 0.4)),
                          Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-1, 1))), rnd.uniform(0.8, 1.2)))
    instance_on(C, name, cluster, items)


def make_landscape(C, quality):
    tm = MT.terrain('Berge')
    N = 220
    size = 22000
    bm = bmesh.new()
    grid = []
    for j in range(N + 1):
        row = []
        for i in range(N + 1):
            x = -size / 2 + size * i / N + 10
            y = -size / 2 + size * j / N + 20
            r = math.hypot(x - 10, y - 20)
            mask = max(0.0, min(1.0, (r - 1300) / 3500))
            mask = mask * mask * (3 - 2 * mask)
            rid = noise.ridged_multi_fractal(Vector((x / 2600, y / 2600, 0.3)), 1.0, 2.0, 6, 1.0, 2.0)
            hh = mask * (90 + 620 * rid + 260 * noise.noise(Vector((x / 4000, y / 4000, 3.1)))) + 25 * max(0.0, min(1.0, (r - 420) / 600)) * (1 + noise.noise(Vector((x / 300, y / 300, 1.3))))
            sink = 0 if r > 380 else 4
            row.append(bm.verts.new((x, y, GROUND - 0.6 + hh - sink)))
        grid.append(row)
    for j in range(N):
        for i in range(N):
            f = bm.faces.new([grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]])
            f.smooth = True
    me = bpy.data.meshes.new('Berge'); bm.to_mesh(me); bm.free()
    me.materials.append(tm)
    ob = bpy.data.objects.new('Berge', me); C.objects.link(ob)
    ob.visible_shadow = False
