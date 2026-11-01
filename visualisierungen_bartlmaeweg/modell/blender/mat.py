# Procedural Cycles materials
import bpy


def _n(nt, t, loc=(0, 0), **kw):
    n = nt.nodes.new(t)
    n.location = loc
    for k, v in kw.items():
        if k.startswith('in_'):
            key = k[3:].replace('_', ' ')
            n.inputs[key].default_value = v
        else:
            setattr(n, k, v)
    return n


def _l(nt, a, b):
    nt.links.new(a, b)


def mixrgb(nt, a, b, blend='MIX', fac=1.0):
    n = _n(nt, 'ShaderNodeMix', data_type='RGBA', blend_type=blend)
    fs = [x for x in n.inputs if x.name == 'Factor' and x.type == 'VALUE'][0]
    if isinstance(fac, (int, float)):
        fs.default_value = fac
    else:
        _l(nt, fac, fs)
    ca, cb = [x for x in n.inputs if x.type == 'RGBA'][:2]
    for sock, val in ((ca, a), (cb, b)):
        if isinstance(val, tuple):
            sock.default_value = (*val, 1) if len(val) == 3 else val
        else:
            _l(nt, val, sock)
    return [x for x in n.outputs if x.type == 'RGBA'][0]


def new_mat(name):
    m = bpy.data.materials.new(name)
    try:
        m.use_nodes = True
    except Exception:
        pass
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = _n(nt, 'ShaderNodeOutputMaterial', (900, 0))
    return m, nt, out


def principled(nt, **kw):
    p = _n(nt, 'ShaderNodeBsdfPrincipled', (600, 0))
    for k, v in kw.items():
        p.inputs[k].default_value = v
    return p


def math(nt, op, a=None, b=None, val=None, clamp=False):
    m = _n(nt, 'ShaderNodeMath', operation=op, use_clamp=clamp)
    if a is not None:
        if isinstance(a, (int, float)):
            m.inputs[0].default_value = a
        else:
            _l(nt, a, m.inputs[0])
    if b is not None:
        if isinstance(b, (int, float)):
            m.inputs[1].default_value = b
        else:
            _l(nt, b, m.inputs[1])
    return m.outputs[0]


def box_uv(nt):
    """returns (u, v) sockets: wall-aligned meters. vertical faces: u horizontal along wall, v = Z.
    horizontal faces: u = X, v = Y"""
    geo = _n(nt, 'ShaderNodeNewGeometry')
    sp = _n(nt, 'ShaderNodeSeparateXYZ'); _l(nt, geo.outputs['Position'], sp.inputs[0])
    sn = _n(nt, 'ShaderNodeSeparateXYZ'); _l(nt, geo.outputs['True Normal'], sn.inputs[0])
    ax = math(nt, 'ABSOLUTE', sn.outputs[0]); ay = math(nt, 'ABSOLUTE', sn.outputs[1]); az = math(nt, 'ABSOLUTE', sn.outputs[2])
    isx = math(nt, 'GREATER_THAN', ax, ay)           # faces ±X -> u = Y
    horiz = math(nt, 'GREATER_THAN', az, 0.7)
    mixu = _n(nt, 'ShaderNodeMix', data_type='FLOAT')
    _l(nt, isx, mixu.inputs['Factor']); _l(nt, sp.outputs[0], mixu.inputs['A']); _l(nt, sp.outputs[1], mixu.inputs['B'])
    mixv = _n(nt, 'ShaderNodeMix', data_type='FLOAT')
    _l(nt, horiz, mixv.inputs['Factor']); _l(nt, sp.outputs[2], mixv.inputs['A']); _l(nt, sp.outputs[1], mixv.inputs['B'])
    mixu2 = _n(nt, 'ShaderNodeMix', data_type='FLOAT')
    _l(nt, horiz, mixu2.inputs['Factor']); _l(nt, mixu.outputs[0], mixu2.inputs['A']); _l(nt, sp.outputs[0], mixu2.inputs['B'])
    return mixu2.outputs[0], mixv.outputs[0], geo


def comb(nt, x, y, z):
    c = _n(nt, 'ShaderNodeCombineXYZ')
    for i, s in enumerate((x, y, z)):
        if isinstance(s, (int, float)):
            c.inputs[i].default_value = s
        else:
            _l(nt, s, c.inputs[i])
    return c.outputs[0]


def ramp(nt, fac, stops):
    r = _n(nt, 'ShaderNodeValToRGB')
    el = r.color_ramp.elements
    while len(el) < len(stops):
        el.new(0.5)
    for e, (p, c) in zip(el, stops):
        e.position = p
        e.color = (*c, 1) if len(c) == 3 else c
    _l(nt, fac, r.inputs[0])
    return r.outputs[0]


def interior_mix(nt, shader_out, out, house):
    """mix in white interior plaster on faces deeper than 0.36 m inside the house footprint"""
    if house is None:
        _l(nt, shader_out, out.inputs[0]); return
    x0, x1, y0, y1 = house
    geo = _n(nt, 'ShaderNodeNewGeometry')
    sp = _n(nt, 'ShaderNodeSeparateXYZ'); _l(nt, geo.outputs['Position'], sp.inputs[0])
    d1 = math(nt, 'SUBTRACT', sp.outputs[0], x0); d2 = math(nt, 'SUBTRACT', x1, sp.outputs[0])
    d3 = math(nt, 'SUBTRACT', sp.outputs[1], y0); d4 = math(nt, 'SUBTRACT', y1, sp.outputs[1])
    d = math(nt, 'MINIMUM', math(nt, 'MINIMUM', d1, d2), math(nt, 'MINIMUM', d3, d4))
    f = math(nt, 'GREATER_THAN', d, 0.36)
    white = principled(nt, **{'Base Color': (0.8, 0.79, 0.76, 1), 'Roughness': 0.9})
    mx = _n(nt, 'ShaderNodeMixShader'); _l(nt, f, mx.inputs[0]); _l(nt, shader_out, mx.inputs[1]); _l(nt, white.outputs[0], mx.inputs[2])
    _l(nt, mx.outputs[0], out.inputs[0])


def wood(name, board=0.146, groove=0.009, cols=((0.42, 0.25, 0.12), (0.52, 0.33, 0.17), (0.36, 0.21, 0.10), (0.58, 0.38, 0.21)),
         rough=0.72, house=None, horizontal_boards=False, grain_scale=1.0):
    m, nt, out = new_mat(name)
    u, v, geo = box_uv(nt)
    if horizontal_boards:
        u, v = v, u
    ub = math(nt, 'DIVIDE', u, board)
    bid = math(nt, 'FLOOR', ub)
    fr = math(nt, 'FRACT', ub)
    # per-board random
    wn = _n(nt, 'ShaderNodeTexWhiteNoise', noise_dimensions='1D'); _l(nt, bid, wn.inputs['W'])
    wn2 = _n(nt, 'ShaderNodeTexWhiteNoise', noise_dimensions='1D'); _l(nt, math(nt, 'ADD', bid, 17.3), wn2.inputs['W'])
    base = ramp(nt, wn.outputs['Value'], [(0.0, cols[0]), (0.35, cols[1]), (0.7, cols[2]), (1.0, cols[3])])
    # grain: stretched noise along v
    gv = comb(nt, math(nt, 'MULTIPLY', u, 55 * grain_scale), math(nt, 'MULTIPLY', v, 1.6 * grain_scale), math(nt, 'MULTIPLY', bid, 3.7))
    nz = _n(nt, 'ShaderNodeTexNoise', in_Scale=1.0, in_Detail=8.0, in_Roughness=0.62, in_Distortion=0.4); _l(nt, gv, nz.inputs['Vector'])
    gv2 = comb(nt, math(nt, 'MULTIPLY', u, 6), math(nt, 'MULTIPLY', v, 0.35), math(nt, 'MULTIPLY', bid, 9.1))
    wave = _n(nt, 'ShaderNodeTexWave', wave_type='RINGS', in_Scale=2.2, in_Distortion=6.0, in_Detail=4.0); _l(nt, gv2, wave.inputs['Vector'])
    gr = math(nt, 'ADD', math(nt, 'MULTIPLY', nz.outputs['Fac'], 0.65), math(nt, 'MULTIPLY', wave.outputs['Fac'], 0.35))
    grc = ramp(nt, gr, [(0.25, (0.62, 0.62, 0.62)), (0.55, (1.0, 1.0, 1.0)), (0.85, (1.25, 1.2, 1.1))])
    mc = mixrgb(nt, base, grc, 'MULTIPLY')
    # board brightness variation
    bv = ramp(nt, wn2.outputs['Value'], [(0, (0.82, 0.82, 0.82)), (1, (1.12, 1.1, 1.06))])
    mc2 = mixrgb(nt, mc, bv, 'MULTIPLY')
    # groove mask
    g = math(nt, 'LESS_THAN', fr, groove / board)
    gcol = mixrgb(nt, mc2, (0.05, 0.035, 0.02), 'MIX', g)
    # bump: groove + slight board edge rounding + grain
    edge = math(nt, 'MULTIPLY', math(nt, 'SUBTRACT', 1.0, math(nt, 'ABSOLUTE', math(nt, 'SUBTRACT', math(nt, 'MULTIPLY', fr, 2), 1))), 1.0)
    edge = math(nt, 'MINIMUM', math(nt, 'MULTIPLY', edge, 12.0), 1.0)
    h = math(nt, 'ADD', math(nt, 'MULTIPLY', edge, math(nt, 'SUBTRACT', 1, g)), math(nt, 'MULTIPLY', nz.outputs['Fac'], 0.08))
    bump = _n(nt, 'ShaderNodeBump', in_Strength=0.6, in_Distance=0.004); _l(nt, h, bump.inputs['Height'])
    rr = ramp(nt, nz.outputs['Fac'], [(0.3, (rough - 0.1,) * 3), (0.7, (rough + 0.1,) * 3)])
    p = principled(nt, **{'Roughness': rough, 'Specular IOR Level': 0.4})
    _l(nt, gcol, p.inputs['Base Color']); _l(nt, bump.outputs[0], p.inputs['Normal']); _l(nt, rr, p.inputs['Roughness'])
    interior_mix(nt, p.outputs[0], out, house)
    return m


def plaster(name, col=(0.80, 0.79, 0.755), house=None, scale=1.0):
    m, nt, out = new_mat(name)
    tc = _n(nt, 'ShaderNodeTexCoord')
    n1 = _n(nt, 'ShaderNodeTexNoise', in_Scale=180 * scale, in_Detail=6, in_Roughness=0.6); _l(nt, tc.outputs['Object'], n1.inputs['Vector'])
    vo = _n(nt, 'ShaderNodeTexVoronoi', in_Scale=900 * scale); _l(nt, tc.outputs['Object'], vo.inputs['Vector'])
    n2 = _n(nt, 'ShaderNodeTexNoise', in_Scale=1.3, in_Detail=4); _l(nt, tc.outputs['Object'], n2.inputs['Vector'])
    h = math(nt, 'ADD', math(nt, 'MULTIPLY', n1.outputs['Fac'], 0.6), math(nt, 'MULTIPLY', vo.outputs['Distance'], 0.4))
    bump = _n(nt, 'ShaderNodeBump', in_Strength=0.25, in_Distance=0.002); _l(nt, h, bump.inputs['Height'])
    c = ramp(nt, n2.outputs['Fac'], [(0.3, tuple(x * 0.965 for x in col)), (0.7, tuple(min(1, x * 1.02) for x in col))])
    p = principled(nt, **{'Roughness': 0.88, 'Specular IOR Level': 0.35})
    _l(nt, c, p.inputs['Base Color']); _l(nt, bump.outputs[0], p.inputs['Normal'])
    interior_mix(nt, p.outputs[0], out, house)
    return m


def metal_roof(name, col=(0.075, 0.08, 0.085), seam=0.52):
    m, nt, out = new_mat(name)
    geo = _n(nt, 'ShaderNodeNewGeometry')
    sp = _n(nt, 'ShaderNodeSeparateXYZ'); _l(nt, geo.outputs['Position'], sp.inputs[0])
    fr = math(nt, 'FRACT', math(nt, 'DIVIDE', sp.outputs[1], seam))
    d = math(nt, 'ABSOLUTE', math(nt, 'SUBTRACT', fr, 0.5))           # 0 at middle, .5 at seam
    ridge = math(nt, 'POWER', math(nt, 'MAXIMUM', math(nt, 'SUBTRACT', d, 0.47), 0), 0.5)
    ridge = math(nt, 'MULTIPLY', ridge, 6.0)
    # slight oil-canning
    n = _n(nt, 'ShaderNodeTexNoise', in_Scale=0.9, in_Detail=2); _l(nt, geo.outputs['Position'], n.inputs['Vector'])
    h = math(nt, 'ADD', ridge, math(nt, 'MULTIPLY', n.outputs['Fac'], 0.02))
    bump = _n(nt, 'ShaderNodeBump', in_Strength=1.0, in_Distance=0.02); _l(nt, h, bump.inputs['Height'])
    n2 = _n(nt, 'ShaderNodeTexNoise', in_Scale=3.0, in_Detail=6); _l(nt, geo.outputs['Position'], n2.inputs['Vector'])
    rr = ramp(nt, n2.outputs['Fac'], [(0.3, (0.3,) * 3), (0.7, (0.42,) * 3)])
    p = principled(nt, **{'Base Color': (*col, 1), 'Metallic': 0.75, 'Roughness': 0.42})
    _l(nt, bump.outputs[0], p.inputs['Normal']); _l(nt, rr, p.inputs['Roughness'])
    _l(nt, p.outputs[0], out.inputs[0])
    return m


def simple(name, col, rough=0.5, metal=0.0, spec=0.5, bump=0.0, bscale=50.0, cvar=0.0):
    m, nt, out = new_mat(name)
    p = principled(nt, **{'Base Color': (*col, 1), 'Roughness': rough, 'Metallic': metal, 'Specular IOR Level': spec})
    if bump > 0 or cvar > 0:
        tc = _n(nt, 'ShaderNodeTexCoord')
        n = _n(nt, 'ShaderNodeTexNoise', in_Scale=bscale, in_Detail=8, in_Roughness=0.65); _l(nt, tc.outputs['Object'], n.inputs['Vector'])
        if bump > 0:
            b = _n(nt, 'ShaderNodeBump', in_Strength=bump, in_Distance=0.01); _l(nt, n.outputs['Fac'], b.inputs['Height']); _l(nt, b.outputs[0], p.inputs['Normal'])
        if cvar > 0:
            n2 = _n(nt, 'ShaderNodeTexNoise', in_Scale=bscale / 20, in_Detail=4); _l(nt, tc.outputs['Object'], n2.inputs['Vector'])
            c = ramp(nt, n2.outputs['Fac'], [(0.3, tuple(x * (1 - cvar) for x in col)), (0.7, tuple(min(1, x * (1 + cvar)) for x in col))])
            _l(nt, c, p.inputs['Base Color'])
    _l(nt, p.outputs[0], out.inputs[0])
    return m


def glass(name, tint=(0.92, 0.95, 0.94)):
    m, nt, out = new_mat(name)
    p = principled(nt, **{'Base Color': (*tint, 1), 'Roughness': 0.0, 'Transmission Weight': 1.0, 'IOR': 1.5})
    _l(nt, p.outputs[0], out.inputs[0])
    return m


def tiles(name, col=(0.46, 0.44, 0.41), mortar=(0.2, 0.19, 0.18), size=0.6, ratio=1.0, var=0.12, rough=0.75):
    m, nt, out = new_mat(name)
    geo = _n(nt, 'ShaderNodeNewGeometry')
    br = _n(nt, 'ShaderNodeTexBrick', offset=0.5 if ratio != 1.0 else 0.0, offset_frequency=2, squash=1.0, squash_frequency=2,
            in_Scale=1.0, in_Mortar_Size=0.006, in_Mortar_Smooth=0.15, in_Bias=0.0, in_Brick_Width=size * ratio, in_Row_Height=size)
    _l(nt, geo.outputs['Position'], br.inputs['Vector'])
    br.inputs['Color1'].default_value = (*[x * (1 - var) for x in col], 1)
    br.inputs['Color2'].default_value = (*[min(1, x * (1 + var)) for x in col], 1)
    br.inputs['Mortar'].default_value = (*mortar, 1)
    n = _n(nt, 'ShaderNodeTexNoise', in_Scale=40, in_Detail=8); _l(nt, geo.outputs['Position'], n.inputs['Vector'])
    mc = mixrgb(nt, br.outputs['Color'], n.outputs['Color'], 'OVERLAY', 0.35)
    h = math(nt, 'ADD', math(nt, 'MULTIPLY', math(nt, 'SUBTRACT', 1, br.outputs['Fac']), 1.0), math(nt, 'MULTIPLY', n.outputs['Fac'], 0.1))
    b = _n(nt, 'ShaderNodeBump', in_Strength=0.5, in_Distance=0.004); _l(nt, h, b.inputs['Height'])
    p = principled(nt, **{'Roughness': rough})
    _l(nt, mc, p.inputs['Base Color']); _l(nt, b.outputs[0], p.inputs['Normal'])
    _l(nt, p.outputs[0], out.inputs[0])
    return m


def asphalt(name):
    m, nt, out = new_mat(name)
    geo = _n(nt, 'ShaderNodeNewGeometry')
    vo = _n(nt, 'ShaderNodeTexVoronoi', in_Scale=180); _l(nt, geo.outputs['Position'], vo.inputs['Vector'])
    n = _n(nt, 'ShaderNodeTexNoise', in_Scale=0.6, in_Detail=6); _l(nt, geo.outputs['Position'], n.inputs['Vector'])
    c = ramp(nt, vo.outputs['Distance'], [(0.0, (0.035, 0.035, 0.037)), (0.5, (0.07, 0.07, 0.072)), (1.0, (0.11, 0.11, 0.11))])
    c2 = ramp(nt, n.outputs['Fac'], [(0.35, (0.8, 0.8, 0.8)), (0.65, (1.15, 1.15, 1.15))])
    mc = mixrgb(nt, c, c2, 'MULTIPLY')
    b = _n(nt, 'ShaderNodeBump', in_Strength=0.5, in_Distance=0.003); _l(nt, vo.outputs['Distance'], b.inputs['Height'])
    p = principled(nt, **{'Roughness': 0.85})
    _l(nt, mc, p.inputs['Base Color']); _l(nt, b.outputs[0], p.inputs['Normal'])
    _l(nt, p.outputs[0], out.inputs[0])
    return m


def gravel(name, col=(0.42, 0.40, 0.37)):
    m, nt, out = new_mat(name)
    geo = _n(nt, 'ShaderNodeNewGeometry')
    vo = _n(nt, 'ShaderNodeTexVoronoi', in_Scale=45); _l(nt, geo.outputs['Position'], vo.inputs['Vector'])
    c = ramp(nt, vo.outputs['Color'], [(0.0, tuple(x * 0.6 for x in col)), (0.5, col), (1.0, tuple(min(1, x * 1.35) for x in col))])
    h = math(nt, 'POWER', math(nt, 'SUBTRACT', 1, vo.outputs['Distance']), 3)
    b = _n(nt, 'ShaderNodeBump', in_Strength=1.0, in_Distance=0.012); _l(nt, h, b.inputs['Height'])
    p = principled(nt, **{'Roughness': 0.8})
    _l(nt, c, p.inputs['Base Color']); _l(nt, b.outputs[0], p.inputs['Normal'])
    _l(nt, p.outputs[0], out.inputs[0])
    return m


def ground(name, col=(0.11, 0.15, 0.05)):
    """ground under the grass hair: dirt/grass mix"""
    m, nt, out = new_mat(name)
    geo = _n(nt, 'ShaderNodeNewGeometry')
    n = _n(nt, 'ShaderNodeTexNoise', in_Scale=0.35, in_Detail=6); _l(nt, geo.outputs['Position'], n.inputs['Vector'])
    n2 = _n(nt, 'ShaderNodeTexNoise', in_Scale=25, in_Detail=8); _l(nt, geo.outputs['Position'], n2.inputs['Vector'])
    f = math(nt, 'ADD', math(nt, 'MULTIPLY', n.outputs['Fac'], 0.6), math(nt, 'MULTIPLY', n2.outputs['Fac'], 0.4))
    c = ramp(nt, f, [(0.3, (0.07, 0.06, 0.035)), (0.5, col), (0.75, (0.16, 0.19, 0.07))])
    p = principled(nt, **{'Roughness': 0.95})
    _l(nt, c, p.inputs['Base Color'])
    b = _n(nt, 'ShaderNodeBump', in_Strength=0.6, in_Distance=0.01); _l(nt, n2.outputs['Fac'], b.inputs['Height']); _l(nt, b.outputs[0], p.inputs['Normal'])
    _l(nt, p.outputs[0], out.inputs[0])
    return m


def grass_hair(name):
    m, nt, out = new_mat(name)
    hi = _n(nt, 'ShaderNodeHairInfo')
    geo = _n(nt, 'ShaderNodeNewGeometry')
    n = _n(nt, 'ShaderNodeTexNoise', in_Scale=0.25, in_Detail=4); _l(nt, geo.outputs['Position'], n.inputs['Vector'])
    f = math(nt, 'ADD', math(nt, 'MULTIPLY', hi.outputs['Random'], 0.55), math(nt, 'MULTIPLY', n.outputs['Fac'], 0.45))
    c = ramp(nt, f, [(0.2, (0.05, 0.10, 0.02)), (0.45, (0.10, 0.18, 0.035)), (0.65, (0.16, 0.24, 0.05)), (0.9, (0.30, 0.31, 0.10))])
    root = ramp(nt, hi.outputs['Intercept'], [(0.0, (0.25, 0.25, 0.2)), (0.5, (0.85, 0.85, 0.85)), (1.0, (1.1, 1.1, 1.0))])
    mc = mixrgb(nt, c, root, 'MULTIPLY')
    p = principled(nt, **{'Roughness': 0.55, 'Specular IOR Level': 0.45})
    _l(nt, mc, p.inputs['Base Color'])
    tr = _n(nt, 'ShaderNodeBsdfTranslucent'); _l(nt, mc, tr.inputs['Color'])
    mx = _n(nt, 'ShaderNodeMixShader', in_Fac=0.25); _l(nt, p.outputs[0], mx.inputs[1]); _l(nt, tr.outputs[0], mx.inputs[2])
    _l(nt, mx.outputs[0], out.inputs[0])
    return m


def leaf(name, cols=((0.06, 0.13, 0.025), (0.12, 0.20, 0.04), (0.20, 0.25, 0.06)), autumn=0.0):
    m, nt, out = new_mat(name)
    oi = _n(nt, 'ShaderNodeObjectInfo')
    geo = _n(nt, 'ShaderNodeNewGeometry')
    wn = _n(nt, 'ShaderNodeTexWhiteNoise', noise_dimensions='3D'); _l(nt, geo.outputs['Position'], wn.inputs['Vector'])
    f = math(nt, 'ADD', math(nt, 'MULTIPLY', oi.outputs['Random'], 0.6), math(nt, 'MULTIPLY', wn.outputs['Value'], 0.4))
    stops = [(0.0, cols[0]), (0.5, cols[1]), (1.0, cols[2])]
    c = ramp(nt, f, stops)
    p = principled(nt, **{'Roughness': 0.45, 'Specular IOR Level': 0.5})
    _l(nt, c, p.inputs['Base Color'])
    tr = _n(nt, 'ShaderNodeBsdfTranslucent')
    tc = mixrgb(nt, c, (1.5, 1.7, 0.6), 'MULTIPLY')
    _l(nt, tc, tr.inputs['Color'])
    mx = _n(nt, 'ShaderNodeMixShader', in_Fac=0.3); _l(nt, p.outputs[0], mx.inputs[1]); _l(nt, tr.outputs[0], mx.inputs[2])
    _l(nt, mx.outputs[0], out.inputs[0])
    return m


def bark(name, col=(0.16, 0.13, 0.10), birch=False):
    m, nt, out = new_mat(name)
    tc = _n(nt, 'ShaderNodeTexCoord')
    mp = _n(nt, 'ShaderNodeMapping'); mp.inputs['Scale'].default_value = (6, 6, 1.2) if birch else (14, 14, 3)
    _l(nt, tc.outputs['Object'], mp.inputs[0])
    n = _n(nt, 'ShaderNodeTexNoise', in_Scale=4, in_Detail=10, in_Roughness=0.7); _l(nt, mp.outputs[0], n.inputs['Vector'])
    if birch:
        c = ramp(nt, n.outputs['Fac'], [(0.0, (0.03, 0.03, 0.03)), (0.33, (0.05, 0.045, 0.04)), (0.38, (0.62, 0.6, 0.56)), (1.0, (0.75, 0.73, 0.69))])
    else:
        c = ramp(nt, n.outputs['Fac'], [(0.3, tuple(x * 0.5 for x in col)), (0.7, col)])
    b = _n(nt, 'ShaderNodeBump', in_Strength=0.8, in_Distance=0.01); _l(nt, n.outputs['Fac'], b.inputs['Height'])
    p = principled(nt, **{'Roughness': 0.85})
    _l(nt, c, p.inputs['Base Color']); _l(nt, b.outputs[0], p.inputs['Normal'])
    _l(nt, p.outputs[0], out.inputs[0])
    return m


def terrain(name):
    """distant mountains with aerial haze"""
    m, nt, out = new_mat(name)
    geo = _n(nt, 'ShaderNodeNewGeometry')
    sp = _n(nt, 'ShaderNodeSeparateXYZ'); _l(nt, geo.outputs['Position'], sp.inputs[0])
    sn = _n(nt, 'ShaderNodeSeparateXYZ'); _l(nt, geo.outputs['Normal'], sn.inputs[0])
    n = _n(nt, 'ShaderNodeTexNoise', in_Scale=0.004, in_Detail=10, in_Roughness=0.62); _l(nt, geo.outputs['Position'], n.inputs['Vector'])
    forest = ramp(nt, n.outputs['Fac'], [(0.42, (0.10, 0.14, 0.05)), (0.48, (0.025, 0.045, 0.02))])
    rock = math(nt, 'MULTIPLY', math(nt, 'GREATER_THAN', sp.outputs[2], 900), math(nt, 'LESS_THAN', sn.outputs[2], 0.85))
    rock = math(nt, 'MAXIMUM', rock, math(nt, 'GREATER_THAN', sp.outputs[2], 1250))
    mc = mixrgb(nt, forest, (0.30, 0.29, 0.27), 'MIX', rock)
    p = principled(nt, **{'Roughness': 0.95})
    _l(nt, mc, p.inputs['Base Color'])
    haze_mix(nt, p.outputs[0], out)
    return m


HAZE = {'col': (0.55, 0.68, 0.85), 'dist': 5000.0, 'strength': 1.0}


def haze_mix(nt, shader_out, out):
    cam = _n(nt, 'ShaderNodeCameraData')
    f = math(nt, 'SUBTRACT', 1.0, math(nt, 'EXPONENT', math(nt, 'DIVIDE', math(nt, 'MULTIPLY', cam.outputs['View Distance'], -1.0), HAZE['dist'])))
    f = math(nt, 'MULTIPLY', f, 0.92)
    em = _n(nt, 'ShaderNodeEmission'); em.inputs['Color'].default_value = (*HAZE['col'], 1); em.inputs['Strength'].default_value = HAZE['strength']
    mx = _n(nt, 'ShaderNodeMixShader'); _l(nt, f, mx.inputs[0]); _l(nt, shader_out, mx.inputs[1]); _l(nt, em.outputs[0], mx.inputs[2])
    _l(nt, mx.outputs[0], out.inputs[0])


def emission(name, col, strength):
    m, nt, out = new_mat(name)
    e = _n(nt, 'ShaderNodeEmission'); e.inputs['Color'].default_value = (*col, 1); e.inputs['Strength'].default_value = strength
    _l(nt, e.outputs[0], out.inputs[0])
    return m
