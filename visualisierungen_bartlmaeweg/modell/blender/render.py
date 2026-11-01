# usage: python render.py <view> <width> <height> <samples> <out.png> [quality] [nograss]
import sys, os, math, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy
from mathutils import Vector
import build as BLD
import mat as MT

view, W, H, SPP, out = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), sys.argv[5]
quality = float(sys.argv[6]) if len(sys.argv) > 6 else 1.0
grass = 'nograss' not in sys.argv
EXPO = float(os.environ.get('EXPO', '0'))

VIEWS = {
    'street': dict(eye=(22.4, 1.62, 9.0), target=(10.2, 3.8, -15.5), hfov=60, sun=(-128, 34)),
    'front':  dict(eye=(11.7, 1.62, 12.8), target=(11.7, 3.9, -12), hfov=56, sun=(-115, 38)),
    'garden': dict(eye=(20.8, 1.62, -36.5), target=(10.2, 3.5, -20.5), hfov=64, sun=(30, 36)),
    'aerial': dict(eye=(-16, 25, 19), target=(11.2, 0.8, -18.2), hfov=48, sun=(160, 40), two=False),
    'dusk':   dict(eye=(2.4, 1.62, -36.6), target=(12.0, 3.4, -21.5), hfov=60, sun=(75, -4.0), dusk=True),
}
V = VIEWS[view]
dusk = V.get('dusk', False)
t0 = time.time()
sc = bpy.context.scene
if dusk:
    MT.HAZE.update(col=(0.035, 0.045, 0.08), strength=1.0)
M = BLD.build(view, dusk=dusk, grass=grass, quality=quality)
print('build', round(time.time() - t0, 1), 's')

# ---------------- sun / sky
az, el = math.radians(V['sun'][0]), math.radians(V['sun'][1])
dT = Vector((math.cos(el) * math.cos(az), math.sin(el), -math.cos(el) * math.sin(az)))
d = Vector((dT.x, -dT.z, dT.y)).normalized()
w = bpy.data.worlds.new('Himmel'); sc.world = w
try: w.use_nodes = True
except Exception: pass
nt = w.node_tree
bg = nt.nodes['Background']
sky = nt.nodes.new('ShaderNodeTexSky'); sky.sky_type = 'MULTIPLE_SCATTERING'
sky.sun_elevation = el; sky.sun_rotation = math.atan2(d.x, d.y)
sky.sun_disc = False
sky.air_density = 1.0; sky.aerosol_density = 2.6 if not dusk else 1.2; sky.ozone_density = 1.0; sky.altitude = 750
nt.links.new(sky.outputs[0], bg.inputs[0])
SKY_S = 0.06
bg.inputs['Strength'].default_value = SKY_S if not dusk else SKY_S * 1.0
MT.HAZE['strength'] = 1.0
if not dusk:
    sl = bpy.data.lights.new('Sonne', 'SUN'); sl.energy = 4.2; sl.angle = math.radians(0.55)
    sl.color = (1.0, 0.95, 0.88)
    so = bpy.data.objects.new('Sonne', sl); sc.collection.objects.link(so)
    so.rotation_euler = d.to_track_quat('Z', 'Y').to_euler()
else:
    def area(name, p, size, power, col=(1.0, 0.72, 0.45), rot=None, shape='RECTANGLE', sy=None):
        l = bpy.data.lights.new(name, 'AREA'); l.energy = power; l.color = col; l.shape = shape; l.size = size
        if sy: l.size_y = sy
        o = bpy.data.objects.new(name, l); sc.collection.objects.link(o); o.location = p
        if rot: o.rotation_euler = rot
        return o
    T = BLD.T
    for (x, z) in ((8.5, -22.5), (14.5, -22.5), (8.5, -16), (14.5, -16), (11.7, -12)):
        area('EG', T(x, 2.70, z), 2.2, 420)
    for (x, z) in ((8.5, -22.5), (14.5, -22.5), (8.5, -13), (14.5, -13)):
        area('OG', T(x, 5.6, z), 1.8, 260)
    for x in (8.2, 11.7, 15.2):
        for z in (-26.4, -8.4):
            l = bpy.data.lights.new('Downlight', 'SPOT'); l.energy = 60; l.color = (1.0, 0.78, 0.55); l.spot_size = math.radians(95); l.spot_blend = 0.6; l.shadow_soft_size = 0.03
            o = bpy.data.objects.new('Downlight', l); sc.collection.objects.link(o); o.location = T(x, 2.92, z)
    for (x, z, tz) in ((3.0, -31.0, -31.5), (21.4, -28.0, -28.6)):
        l = bpy.data.lights.new('Uplight', 'SPOT'); l.energy = 220; l.color = (1.0, 0.8, 0.55); l.spot_size = math.radians(50); l.spot_blend = 0.5; l.shadow_soft_size = 0.05
        o = bpy.data.objects.new('Uplight', l); sc.collection.objects.link(o); o.location = T(x, 0.1, z)
        o.rotation_euler = (0, 0, 0)
    for (x, z) in ((8, -30.5), (15.5, -30.5), (11.7, -4.0), (11.7, -1.0)):
        l = bpy.data.lights.new('Pollerleuchte', 'POINT'); l.energy = 8; l.color = (1.0, 0.75, 0.5); l.shadow_soft_size = 0.05
        o = bpy.data.objects.new('Poller', l); sc.collection.objects.link(o); o.location = T(x, 0.55, z)
    area('Lichthof', T(5.4, -0.3, -23), 1.0, 60, rot=(math.pi, 0, 0))

# ---------------- camera
cd = bpy.data.cameras.new('Kamera'); cam = bpy.data.objects.new('Kamera', cd); sc.collection.objects.link(cam); sc.camera = cam
eye, tgt = Vector(V['eye']), Vector(V['target'])
cd.sensor_width = 36; cd.sensor_fit = 'HORIZONTAL'
cd.lens = 18 / math.tan(math.radians(V['hfov']) / 2)
cd.clip_start = 0.1; cd.clip_end = 20000
cam.location = BLD.T(*eye)
if V.get('two', True):
    dx, dz = tgt.x - eye.x, tgt.z - eye.z
    db = Vector((dx, -dz))
    yaw = math.atan2(-db.x, db.y)
    cam.rotation_euler = (math.pi / 2, 0, yaw)
    slope = (tgt.y - eye.y) / db.length
    cd.shift_y = cd.lens * slope / 36 * (1.0)
else:
    dirv = (BLD.T(*tgt) - BLD.T(*eye)).normalized()
    cam.rotation_euler = dirv.to_track_quat('-Z', 'Y').to_euler()

# ---------------- render settings
r = sc.render; r.engine = 'CYCLES'; r.resolution_x = W; r.resolution_y = H; r.resolution_percentage = 100
cy = sc.cycles; cy.device = 'CPU'; cy.samples = SPP; cy.use_adaptive_sampling = True; cy.adaptive_threshold = 0.02
cy.use_denoising = True; cy.denoiser = 'OPENIMAGEDENOISE'
try: cy.denoising_input_passes = 'RGB_ALBEDO_NORMAL'
except Exception: pass
cy.max_bounces = 8; cy.diffuse_bounces = 4; cy.glossy_bounces = 4; cy.transmission_bounces = 8; cy.transparent_max_bounces = 16
cy.caustics_reflective = False; cy.caustics_refractive = False
cy.sample_clamp_indirect = 8.0
cy.blur_glossy = 1.0
r.use_persistent_data = False
sc.view_settings.view_transform = 'AgX'
for lk in ('AgX - Medium High Contrast', 'Medium High Contrast', 'AgX - Base Contrast'):
    try:
        sc.view_settings.look = lk; break
    except Exception:
        pass
sc.view_settings.exposure = EXPO + (0.0 if not dusk else 2.2)
r.image_settings.file_format = 'PNG'; r.image_settings.color_depth = '8'
r.filepath = out
t1 = time.time()
bpy.ops.render.render(write_still=True)
print('render', round(time.time() - t1, 1), 's  total', round(time.time() - t0, 1), 's')
