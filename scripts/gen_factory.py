"""Manufacturing RL demo: the robot arm's pre-programmed picks and the camera moves (Lvl_Factory, LS_Factory).

Writes work/factory_keys.json (every frame, for overlay_factory.py) and work/factory_compact.json (sampled keys).
Arm (robot base at the origin): J1 turret yaw -> J2 shoulder pitch -> J3 elbow pitch -> J4 wrist pitch; L1 130, L2 110,
shoulder at z 150, tool tip 60 below the wrist. The wrist keeps the gripper pointing straight down.
Parts are L-shaped brackets (CarryRed, CarryTeal, CarryYellow, CarryGrey) that arrive on the conveyor at the pick point.
"""
import json, math, pathlib

FPS = 30
OUT = pathlib.Path(__file__).parent / 'work'
OUT.mkdir(exist_ok=True)
L1, L2, SH, TOOL = 130.0, 110.0, 150.0, 60.0
PICK = (-160.0, 0.0)
BINS = {'red': (0.0, 200.0), 'teal': (200.0, 0.0), 'yellow': (0.0, -200.0), 'reject': (150.0, 150.0)}
GRIP_Z, CARRY_Z, DROP_Z = 110.0, 185.0, 140.0       # tool tip heights
PART_OFF = (18.75, 0.0, -15.0)                        # bracket base centre relative to the tip, in the turret frame
PARK = {'red': (-700, -3000, -300), 'teal': (-700, -3100, -300), 'yellow': (-700, -3200, -300), 'grey': (-700, -3300, -300)}
OPEN, CLOSED = 17.0, 6.5                              # finger y


def ss(u):
    u = max(0.0, min(1.0, u))
    return u * u * (3 - 2 * u)


def lerp(a, b, u):
    return [a[i] + (b[i] - a[i]) * u for i in range(len(a))]


def ik(tip):
    """Joint angles (yaw, shoulder, elbow, wrist) that put the tool tip at `tip`, gripper straight down."""
    x, y, z = tip
    yaw = math.degrees(math.atan2(y, x))
    r = math.hypot(x, y)
    h = z + TOOL - SH
    d = min(math.hypot(r, h), L1 + L2 - 0.5)
    ca = (d * d - L1 * L1 - L2 * L2) / (2 * L1 * L2)
    a2 = -math.acos(max(-1.0, min(1.0, ca)))
    a1 = math.atan2(h, r) + math.atan2(L2 * math.sin(-a2), L1 + L2 * math.cos(a2))
    a1, a2 = math.degrees(a1), math.degrees(a2)
    return yaw, a1, a2, -(a1 + a2)


def tip_of(yaw, r, z):
    return (r * math.cos(math.radians(yaw)), r * math.sin(math.radians(yaw)), z)


def bin_yaw(name):
    x, y = BINS[name]
    return math.degrees(math.atan2(y, x))


def near(target, ref):
    while target - ref > 180:
        target -= 360
    while target - ref < -180:
        target += 360
    return target


READY = (180.0, 160.0, CARRY_Z)  # yaw, radius, z of the tool tip between picks


class Pick:
    """One pick and place in polar tool-tip coordinates. kind: 'ok', 'drop' (falls on the way), 'wrong' (wrong bin),
    'slip' (new part slips back on the belt), 'slow' (same as ok, slower)."""

    def __init__(self, t0, color, target, kind='ok', speed=1.0, arrive=True):
        self.t0, self.color, self.target, self.kind, self.k = t0, color, target, kind, speed
        yb = near(bin_yaw(target), 180.0)
        rb = math.hypot(*BINS[target])
        g = 1.0 / speed
        # (time, yaw, radius, z, fingers)
        k = [(0.0, 180, 160, CARRY_Z, OPEN), (1.5 * g, 180, 160, CARRY_Z, OPEN), (2.3 * g, 180, 160, GRIP_Z, OPEN),
             (2.6 * g, 180, 160, GRIP_Z, CLOSED), (3.3 * g, 180, 160, CARRY_Z, CLOSED), (4.8 * g, yb, rb, CARRY_Z, CLOSED),
             (5.2 * g, yb, rb, DROP_Z, CLOSED), (5.4 * g, yb, rb, DROP_Z, OPEN), (6.4 * g, 180, 160, CARRY_Z, OPEN)]
        if kind == 'drop':      # grabbed off-centre, swung too fast: lets go half way
            k = [(0.0, 180, 160, CARRY_Z, OPEN), (1.2, 180, 160, CARRY_Z, OPEN), (1.8, 180, 150, GRIP_Z + 8, OPEN),
                 (2.0, 180, 150, GRIP_Z + 8, CLOSED), (2.4, 180, 150, CARRY_Z, CLOSED), (3.4, near(bin_yaw('teal'), 180), 190, CARRY_Z, CLOSED),
                 (4.4, near(bin_yaw('teal'), 180), 200, CARRY_Z, OPEN)]
            self.release = 2.9
        if kind == 'slip':      # new part: grips too low, it slips back onto the belt
            k = [(0.0, 180, 160, CARRY_Z, OPEN), (1.5, 180, 160, CARRY_Z, OPEN), (2.6, 180, 160, GRIP_Z - 4, OPEN),
                 (2.9, 180, 160, GRIP_Z - 4, CLOSED), (3.5, 180, 160, CARRY_Z - 30, CLOSED), (4.1, 180, 160, CARRY_Z - 30, CLOSED),
                 (4.4, 180, 160, CARRY_Z - 30, OPEN), (6.0, 180, 160, CARRY_Z, OPEN)]
            self.release = 3.7
        self.keys = k
        self.end = k[-1][0]

    def arm(self, u):
        k = self.keys
        if u <= 0:
            return k[0][1:]
        for a, b in zip(k, k[1:]):
            if u <= b[0]:
                w = ss((u - a[0]) / (b[0] - a[0]))
                return tuple(a[i] + (b[i] - a[i]) * w for i in range(1, 5))
        return k[-1][1:]

    def part(self, u):
        """World position and (pitch, yaw, roll) of this pick's bracket at local time u."""
        if u < 1.5 / self.k if self.kind not in ('drop',) else u < 1.2:
            arr = 1.5 / self.k if self.kind != 'drop' else 1.2
            x = -560 + (PICK[0] - -560) * ss(u / arr)
            return (x + PART_OFF[0], 0.0, 95.0), (0, 0, 0)
        grip = {'drop': 2.0, 'slip': 2.9}.get(self.kind, 2.6 / self.k)
        if u < grip:
            return (PICK[0] + PART_OFF[0], 0.0, 95.0), (0, 0, 0)
        rel = getattr(self, 'release', None)
        if self.kind in ('ok', 'wrong', 'slow'):
            rel = 5.4 / self.k
        if u < rel:
            yaw, r, z, _ = self.arm(u)
            t = tip_of(yaw, r, z)
            c, s = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
            return (t[0] + PART_OFF[0] * c, t[1] + PART_OFF[0] * s, t[2] + PART_OFF[2]), (0, yaw, 0)
        # falling
        yaw, r, z, _ = self.arm(rel)
        t = tip_of(yaw, r, z)
        c, s = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
        p0 = (t[0] + PART_OFF[0] * c, t[1] + PART_OFF[0] * s, t[2] + PART_OFF[2])
        if self.kind == 'drop':
            floor, spin = 3.0, (70, yaw + 40, 25)
            land = (p0[0] + 35, p0[1] - 40)
        elif self.kind == 'slip':
            floor, spin = 95.0, (0, 12, 18)
            land = (p0[0], p0[1])
        else:
            floor, spin = 12.0, (0, yaw, 0)
            land = (p0[0], p0[1])
        f = min(1.0, (u - rel) / 0.45)
        zz = p0[2] + (floor - p0[2]) * f * f
        return (p0[0] + (land[0] - p0[0]) * f, p0[1] + (land[1] - p0[1]) * f, zz), tuple(spin[i] * f + (0 if i != 1 else yaw * (1 - f)) for i in range(3))


# Segments (seconds): hook 0-12, world 12-28 (flyover then CAD screen), practice 28-40, pro 40-64, limit 64-72
SEG = [('hook', 0, 12), ('world', 12, 28), ('practice', 28, 40), ('pro', 40, 64), ('limit', 64, 72)]
END = 72
PLAN = [
    Pick(0.5, 'teal', 'teal', 'drop'),
    Pick(28.0, 'teal', 'teal', 'drop'), Pick(31.4, 'teal', 'red', 'wrong', speed=2.2), Pick(34.4, 'yellow', 'yellow', 'slow', speed=2.0),
    Pick(37.2, 'red', 'red', 'ok', speed=2.2),
    Pick(40.5, 'red', 'red'), Pick(47.0, 'teal', 'teal'), Pick(53.5, 'yellow', 'yellow'),
    Pick(64.5, 'grey', 'reject', 'slip'),
]
SEG_OF = lambda t: next(s for s in SEG if s[1] <= t < s[2]) if t < END else SEG[-1]


def state(t):
    """Arm (yaw, r, z, fingers) and every bracket's pose at time t."""
    seg = SEG_OF(t)
    picks = [p for p in PLAN if seg[1] <= p.t0 < seg[2]]
    arm = READY + (OPEN,)
    parts = {c: (PARK[c], (0, 0, 0)) for c in PARK}
    for p in picks:
        u = t - p.t0
        if u >= 0:
            if u <= p.end:
                arm = p.arm(u)
            parts[p.color] = p.part(u)
    return arm, parts


def look(p, tg):
    dx, dy, dz = tg[0] - p[0], tg[1] - p[1], tg[2] - p[2]
    return (p[0], p[1], p[2], math.degrees(math.atan2(dz, math.hypot(dx, dy))), math.degrees(math.atan2(dy, dx)))


def camera(t, tipsm):
    name, a, b = SEG_OF(t)
    u = (t - a) / (b - a)
    if name == 'hook':
        return look(lerp((560, -640, 430), (470, -540, 390), ss(u)), lerp((0, 10, 80), tipsm, 0.3))
    if name == 'world':
        if t < 22:
            v = (t - 12) / 10
            ang = math.radians(-120 + 80 * ss(v))
            return look((1700 * math.cos(ang), 1700 * math.sin(ang) - 100, 650 - 150 * v), (-300, 200, 180))
        v = (t - 22) / 6
        return look(lerp((-800, -470, 200), (-800, -560, 186), ss(v)), (-800, -742, 180))
    if name == 'practice':
        return look((420, -760, 820), (-20, 10, 70))
    if name == 'pro':
        if t < 52:
            return look(lerp((600, -560, 420), (520, -500, 390), ss((t - 40) / 12)), lerp((0, 10, 80), tipsm, 0.35))
        return look(lerp((470, -470, 380), (420, -420, 350), ss((t - 52) / 12)), lerp((20, 0, 70), tipsm, 0.3))
    return look(lerp((-60, -330, 240), (-90, -290, 225), ss(u)), (-150, 0, 110))


def main():
    every = {}
    tipsm = None
    for f in range(0, END * FPS + 1):
        t = f / FPS
        arm, parts = state(t)
        yaw, r, z, fing = arm
        tip = tip_of(yaw, r, z)
        if f in [round(s[1] * FPS) for s in SEG] or tipsm is None:
            tipsm = list(tip)
        k = 1 - math.exp(-(1 / FPS) / 0.5)
        tipsm = [tipsm[i] + (tip[i] - tipsm[i]) * k for i in range(3)]
        j = ik(tip)
        every[f] = dict(J=j, F=fing, tip=tip, P={c: [list(v[0]), list(v[1])] for c, v in parts.items()}, C=camera(t, tipsm))
    json.dump({'fps': FPS, 'seg': SEG, 'frames': every}, open(OUT / 'factory_keys.json', 'w'))
    cuts = sorted({round(s[1] * FPS) for s in SEG[1:]} | {round(p.t0 * FPS) for p in PLAN if p.t0 > 28 and p.t0 < 40})
    frames = set(range(0, END * FPS + 1, 3))
    for c in cuts:
        frames |= {c - 1, c}
    frames = sorted(frames)
    hold = sorted(c - 1 for c in cuts)
    ch = {k: [] for k in ['j1', 'j2', 'j3', 'j4', 'fl', 'fr', 'CX', 'CY', 'CZ', 'CP', 'CW']}
    for c in PARK:
        for k in ('x', 'y', 'z', 'p', 'w', 'r'):
            ch[c + '_' + k] = []
    prev = {}
    for f in frames:
        e = every[f]
        j = e['J']
        vals = {'j1': j[0], 'j2': j[1], 'j3': j[2], 'j4': j[3], 'fl': e['F'], 'fr': -e['F']}
        cam = e['C']
        vals.update({'CX': cam[0], 'CY': cam[1], 'CZ': cam[2], 'CP': cam[3], 'CW': cam[4]})
        for c, (pos, rot) in e['P'].items():
            vals.update({c + '_x': pos[0], c + '_y': pos[1], c + '_z': pos[2], c + '_p': rot[0], c + '_w': rot[1], c + '_r': rot[2]})
        for k, v in vals.items():
            if k in ('j1', 'CW') or k.endswith('_w'):
                if k in prev:
                    while v - prev[k] > 180: v -= 360
                    while v - prev[k] < -180: v += 360
                prev[k] = v
            ch[k].append(round(v, 2))
    json.dump({'f': frames, 'cut': hold, **ch}, open(OUT / 'factory_compact.json', 'w'))
    print(len(frames), 'frames sampled,', len(frames) * len(ch), 'keys')


if __name__ == '__main__':
    main()
