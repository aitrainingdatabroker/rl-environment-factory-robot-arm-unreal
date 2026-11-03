"""Manufacturing RL demo: draws the PICK SCORECARD (website card style, scorecard.py) on the rendered factory frames,
cuts the clips (NVENC), builds the side-by-side clip and the slide stills.

python overlay_factory.py
"""
import json, math, pathlib, subprocess
from PIL import Image, ImageDraw
from scorecard import Scorecard, card, pill, F, INK, WHITE, LINE

HERE = pathlib.Path(__file__).parent
FR = pathlib.Path(r"C:\rlfilm\LS_Factory_full")   # render.py output (no spaces)
OUT_FR = HERE / 'work' / 'factory_ov'
SLUG = 'rl-environment-factory-robot-arm-manufacturing'
VID = pathlib.Path(r"output") / f'2026-11-03_{SLUG}'
CLIPS = VID / 'clips'
STILLS = pathlib.Path(r"output\stills") / SLUG
FPS = 30
K = json.load(open(HERE / 'work' / 'factory_keys.json'))['frames']
SC = Scorecard('FACTORY ROBOT ARM', 'PICK SCORECARD')
TAN_HALF = 23.76 / 2 / 20

PRACTICE = [(28.0, 30.9, 'DROP  -30', 'bad', 'teal'), (31.4, 33.85, 'WRONG BIN  -20', 'bad', 'teal'),
            (34.4, 37.1, 'TOO SLOW', 'neutral', 'yellow'), (37.2, 39.65, 'SORTED  +20', 'good', 'red')]
PRO = [(40.5, 'red'), (47.0, 'teal'), (53.5, 'yellow')]


def k(t):
    return K[str(max(0, min(len(K) - 1, round(t * FPS))))]


def project(c, P):
    p, w = math.radians(c[3]), math.radians(c[4])
    f = (math.cos(p) * math.cos(w), math.cos(p) * math.sin(w), math.sin(p))
    r = (-math.sin(w), math.cos(w), 0)
    u = (-math.sin(p) * math.cos(w), -math.sin(p) * math.sin(w), math.cos(p))
    dv = (P[0] - c[0], P[1] - c[1], P[2] - c[2])
    df = sum(a * b for a, b in zip(dv, f))
    return (960 + 960 * sum(a * b for a, b in zip(dv, r)) / (df * TAN_HALF),
            540 - 960 * sum(a * b for a, b in zip(dv, u)) / (df * TAN_HALF))


def state(t):
    if t < 12:
        rel = 0.5 + 2.9
        dropped = t >= rel
        score = (5 if t >= 2.5 else 0) - (30 if dropped else 0)
        return dict(mode='FIRST TRY' if t < rel + 0.6 else 'FAILED', tone='bad', score=score,
                    score_tone='bad' if score < 0 else None, rows=[('TIME', f'{min(t, rel):0.1f} s'), ('DROPS', '1' if dropped else '0')],
                    pop='DROP  -30' if rel <= t < rel + 1.4 else '', pop_tone='bad')
    if 28 <= t < 40:
        u = (t - 28) / 12
        st = dict(mode='PRACTICE, SPED UP', tone='neutral', score=int(-30 + 125 * (1 - (1 - u) ** 2.5)), score_label='BEST SCORE',
                  rows=[('TRIES', f'{int(1 + 4199 * u ** 2.2):,}'), ('SPEED', '40x')], pop='')
        for t0, at, txt, tone, col in PRACTICE:
            if at <= t < at + 1.3:
                st.update(pop=txt, pop_tone=tone)
        return st
    if 40 <= t < 64:
        done = [t0 + 5.4 for t0, _ in PRO if t >= t0 + 5.4]
        n = len(done)
        part = 0.0
        for t0, _ in PRO:
            if t0 <= t < t0 + 5.4:
                part = 10 if t >= t0 + 2.6 else 0
        score = min(100, [0, 33, 66, 100][n] + int(part))
        st = dict(mode='SORTED' if n == 3 else 'AFTER PRACTICE', tone='good', score=score, score_tone='good',
                  rows=[('PARTS', f'{n} / 3'), ('DROPS', '0')], pop='')
        for d in done:
            if d <= t < d + 1.3:
                st.update(pop='SORTED  +20', pop_tone='good')
        if t >= PRO[-1][0] + 6.0:
            st.update(banner='3 parts   0 drops   100 points', banner_tag='DONE', banner_tone='good')
        return st
    if 64 <= t < 72:
        slipped = t >= 64.5 + 3.7
        return dict(mode='NEW PART', tone='neutral', score='SLIPPED' if slipped else 'GRIPPING', score_label='RESULT',
                    score_tone='bad' if slipped else None, rows=[('PART', 'GREY'), ('IN TRAINING', 'NO')],
                    pop='')
    return None


def draw(im, t):
    st = state(t)
    if st is None:
        return im
    if 28 <= t < 40:
        col = next((c for t0, at, _, _, c in PRACTICE if t0 <= t < t0 + 3.0), None)
        if col:
            pos = k(t)['P'][col][0]
            if pos[2] > -100:
                x, y = project(k(t)['C'], pos)
                ov = Image.new('RGBA', im.size, (0, 0, 0, 0))
                SC.target_label(ov, x, y, 'BRACKET')
                im = Image.alpha_composite(im.convert('RGBA'), ov).convert('RGB')
    return SC.draw(im, st)


ENC = ['-c:v', 'h264_nvenc', '-preset', 'p5', '-cq', '19', '-pix_fmt', 'yuv420p', '-movflags', '+faststart']
CUTS = {'hook': (0, 12), 'world': (12, 28), 'practice': (28, 40), 'pro': (40, 64), 'limit': (64, 72)}
STILL_AT = {'hook': 3.0, 'world': 17.0, 'practice': 33.0, 'pro': 50.0, 'limit': 68.5}


def side_by_side():
    bg = Image.new('RGBA', (1920, 1080), (251, 251, 249, 255))
    d = ImageDraw.Draw(bg)
    big = F('b', 56)
    t = 'The same pick, 3 times'
    d.text((960, 190), t, font=big, fill=INK, anchor='mm')
    logo = SC.logo
    bg.alpha_composite(logo, (64, 64))
    for i, (lab, tone) in enumerate([('FIRST TRY', 'bad'), ('PRACTICE', 'neutral'), ('AFTER PRACTICE', 'good')]):
        x = 24 + i * 632
        card(bg, (x - 6, 394, x + 630, 757))
        w = d.textlength(lab, font=F('b', 30)) + 32
        pill(ImageDraw.Draw(bg), x + 312 - w / 2, 316, lab, F('b', 30), tone, h=52)
    bg.convert('RGB').save(HERE / 'work' / 'sbs_bg.png')
    seq = str(OUT_FR / 'o%04d.jpg')
    fc = ('[1:v]trim=start_frame=0:end_frame=270,setpts=PTS-STARTPTS,scale=624:351[a];'
          '[2:v]trim=start_frame=840:end_frame=1110,setpts=PTS-STARTPTS,scale=624:351[b];'
          '[3:v]trim=start_frame=1200:end_frame=1470,setpts=PTS-STARTPTS,scale=624:351[c];'
          '[0:v][a]overlay=24:400:shortest=1[x];[x][b]overlay=656:400[y];[y][c]overlay=1288:400,fps=30[v]')
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-loop', '1', '-framerate', '30', '-t', '9', '-i', str(HERE / 'work' / 'sbs_bg.png')]
                   + sum([['-framerate', '30', '-i', seq] for _ in range(3)], [])
                   + ['-filter_complex', fc, '-map', '[v]', '-t', '9'] + ENC + [str(CLIPS / 'sidebyside.mp4')], check=True)
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-ss', '7', '-i', str(CLIPS / 'sidebyside.mp4'), '-frames:v', '1',
                    '-c:v', 'libwebp', '-quality', '80', str(STILLS / 'sidebyside.webp')], check=True)


def main():
    OUT_FR.mkdir(exist_ok=True)
    frames = sorted(FR.glob('f*.jpg'))
    print(len(frames), 'frames')
    for i, p in enumerate(frames):
        draw(Image.open(p), i / FPS).save(OUT_FR / f'o{i:04d}.jpg', quality=94)
    CLIPS.mkdir(parents=True, exist_ok=True)
    n = len(frames)
    for name, (a, b) in CUTS.items():
        a, b = a * FPS, min(b * FPS, n)
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-framerate', str(FPS), '-start_number', str(a), '-i', str(OUT_FR / 'o%04d.jpg'),
                        '-frames:v', str(b - a)] + ENC + [str(CLIPS / f'{name}.mp4')], check=True)
        Image.open(OUT_FR / f'o{min(n - 1, round(STILL_AT[name] * FPS)):04d}.jpg').save(STILLS / f'{name}.webp', quality=80)
    side_by_side()
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-framerate', str(FPS), '-i', str(OUT_FR / 'o%04d.jpg')] + ENC
                   + [str(VID / 'demo-preview.mp4')], check=True)
    print('clips:', sorted(p.name for p in CLIPS.glob('*.mp4')))


if __name__ == '__main__':
    main()
