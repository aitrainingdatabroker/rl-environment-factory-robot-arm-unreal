"""The scorecard, banner and labels drawn over RL demo clips, in the website's card style (owner, 2026-11-02:
"avoid weird borders ... no extra long color on one side and no color on the other side, take designs from our website").

Every box is the website card: white, an even 2px #d9dde2 border on all four sides, 16px corners, a soft even shadow.
Colour only ever fills a whole pill (status, +20, -30), never a strip on one edge. Text is navy #17202c and #46505c.
Used by overlay_*.py:

    from scorecard import Scorecard
    sc = Scorecard('FACTORY ROBOT ARM', 'PICK SCORECARD')
    im = sc.draw(im, state)      # state: mode, tone ('good'|'bad'|'neutral'), score, score_label, rows, pop, pop_tone, banner
"""
import pathlib
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = pathlib.Path(__file__).parent
INK = (23, 32, 44); INK2 = (70, 80, 92); LINE = (217, 221, 226); WHITE = (255, 255, 255)
YEL = (255, 216, 77); GREEN = (31, 122, 77); RED = (180, 35, 24)
TONE = {'good': (GREEN, WHITE), 'bad': (RED, WHITE), 'neutral': (YEL, INK)}
F = lambda w, s: ImageFont.truetype({'b': 'C:/Windows/Fonts/segoeuib.ttf', 's': 'C:/Windows/Fonts/seguisb.ttf'}[w], s)


def card(ov, box, r=16, fill=WHITE + (246,)):
    """The website card on an RGBA overlay: soft even shadow, white body, even 2px border."""
    x0, y0, x1, y1 = box
    sh = Image.new('RGBA', ov.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle((x0, y0 + 6, x1, y1 + 6), r, fill=(0, 0, 0, 70))
    ov.alpha_composite(sh.filter(ImageFilter.GaussianBlur(10)))
    ImageDraw.Draw(ov).rounded_rectangle(box, r, fill=fill, outline=LINE + (255,), width=2)


def pill(d, x, y, text, font, tone, h=40, anchor='left'):
    bg, fg = TONE[tone]
    w = d.textlength(text, font=font) + 32
    if anchor == 'right':
        x -= w
    d.rounded_rectangle((x, y, x + w, y + h), h // 2, fill=bg)
    d.text((x + 16, y + h / 2), text, font=font, fill=fg, anchor='lm')
    return w


class Scorecard:
    def __init__(self, title, subtitle):
        self.title, self.subtitle = title, subtitle
        logo = Image.open(HERE / 'brand' / 'logo120.png').convert('RGBA')
        self.logo = logo.resize((int(logo.width * 44 / logo.height), 44), Image.LANCZOS)
        self.f_title, self.f_sub, self.f_pill = F('b', 30), F('s', 18), F('b', 22)
        self.f_lab, self.f_big, self.f_val, self.f_ban = F('s', 19), F('b', 66), F('b', 32), F('b', 36)

    def draw(self, im, st):
        if not st:
            return im
        ov = Image.new('RGBA', im.size, (0, 0, 0, 0))
        x0, y0, w, h = 1440, 44, 436, 340
        card(ov, (x0, y0, x0 + w, y0 + h))
        d = ImageDraw.Draw(ov)
        ov.alpha_composite(self.logo, (x0 + 24, y0 + 22))
        tx = x0 + 34 + self.logo.width
        d.text((tx, y0 + 16), self.title, font=self.f_title, fill=INK)
        d.text((tx + 1, y0 + 52), self.subtitle, font=self.f_sub, fill=INK2)
        d.line((x0 + 24, y0 + 86, x0 + w - 24, y0 + 86), fill=LINE, width=2)
        pill(d, x0 + 24, y0 + 102, st['mode'], self.f_pill, st.get('tone', 'neutral'))
        d.text((x0 + 26, y0 + 156), st.get('score_label', 'SCORE'), font=self.f_lab, fill=INK2)
        tone = st.get('score_tone')
        col = {'good': GREEN, 'bad': RED}.get(tone, INK)
        d.text((x0 + 22, y0 + 172), str(st['score']), font=self.f_big, fill=col)
        for k, (lab, val) in enumerate(st.get('rows', [])):
            cx = x0 + 26 + k * 200
            d.text((cx, y0 + 262), lab, font=self.f_lab, fill=INK2)
            d.text((cx, y0 + 284), val, font=self.f_val, fill=INK)
        if st.get('pop'):
            pill(d, x0 + w - 24, y0 + 184, st['pop'], self.f_pill, st.get('pop_tone', 'bad'), h=44, anchor='right')
        if st.get('banner'):
            self.banner(ov, st['banner'], st.get('banner_tone', 'good'), st.get('banner_tag', 'DONE'))
        return Image.alpha_composite(im.convert('RGBA'), ov).convert('RGB')

    def banner(self, ov, text, tone, tag):
        """A result line along the bottom: a website card with a status pill inside, no edge strip."""
        d = ImageDraw.Draw(ov)
        tw = d.textlength(tag, font=self.f_pill) + 32
        bw = tw + 24 + d.textlength(text, font=self.f_ban) + 64
        bx, by = (1920 - bw) / 2, 900
        card(ov, (bx, by, bx + bw, by + 76))
        d = ImageDraw.Draw(ov)
        pill(d, bx + 24, by + 18, tag, self.f_pill, tone)
        d.text((bx + 24 + tw + 24, by + 38), text, font=self.f_ban, fill=INK, anchor='lm')

    def target_label(self, ov, x, y, text):
        """A ring and a label pill on the thing to watch (top-down shots)."""
        d = ImageDraw.Draw(ov)
        d.ellipse((x - 58, y - 58, x + 58, y + 58), outline=WHITE + (255,), width=12)
        d.ellipse((x - 56, y - 56, x + 56, y + 56), outline=YEL + (255,), width=8)
        f = self.f_pill
        w = d.textlength(text, font=f) + 32
        d.rounded_rectangle((x - w / 2, y - 112, x + w / 2, y - 72), 20, fill=WHITE, outline=LINE, width=2)
        d.text((x, y - 92), text, font=f, fill=INK, anchor='mm')
