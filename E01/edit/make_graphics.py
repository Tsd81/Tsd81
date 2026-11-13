"""Graphics for E01 (1920x1080 PNG). Every number is from Purkis et al. 2022 unless labelled otherwise."""
import math, os, sys
from PIL import Image, ImageDraw, ImageFont
import shapefile

OUT = sys.argv[1] if len(sys.argv) > 1 else "gfx"
NE = sys.argv[2] if len(sys.argv) > 2 else "ne/ne_10m_land.shp"
os.makedirs(OUT, exist_ok=True)
W, H = 1920, 1080
TOP = (10, 42, 74); BOT = (2, 8, 20)
CYAN = (94, 214, 230); WHITE = (240, 246, 250); GREY = (150, 175, 195); DIM = (70, 100, 125)
SAND = (214, 170, 140); ORANGE = (230, 140, 60); GRAYZ = (120, 125, 120); BRINE = (40, 110, 150)
LAND = (34, 52, 66); RED = (235, 95, 85)
BOLD = "/usr/share/fonts/opentype/inter/InterDisplay-Bold.otf"
SEMI = "/usr/share/fonts/opentype/inter/Inter-SemiBold.otf"
MED = "/usr/share/fonts/opentype/inter/Inter-Medium.otf"
F = lambda p, s: ImageFont.truetype(p, s)


def base():
    im = Image.new("RGB", (W, H)); d = ImageDraw.Draw(im)
    for y in range(H):
        t = y / (H - 1); d.line([(0, y), (W, y)], fill=tuple(int(TOP[i] * (1 - t) + BOT[i] * t) for i in range(3)))
    return im, d


def source(d, text):
    d.text((60, H - 56), text, font=F(MED, 22), fill=DIM)


def title(d, text, sub=None, y=60):
    d.text((80, y), text, font=F(BOLD, 64), fill=WHITE)
    if sub: d.text((82, y + 84), sub, font=F(MED, 32), fill=CYAN)


def ctext(d, xy, text, font, fill, anchor="mm"):
    d.text(xy, text, font=font, fill=fill, anchor=anchor)


def save(im, name):
    im.save(os.path.join(OUT, name + ".png"))


# ---------- maps ----------
sf = shapefile.Reader(NE)
shapes = sf.shapes()


def draw_map(name, lon0, lon1, lat0, lat1, box, marks, ttl, sub, extra=None):
    im, d = base()
    x0, y0, x1, y1 = box
    sx = (x1 - x0) / (lon1 - lon0); sy = (y1 - y0) / (lat1 - lat0)
    kx = math.cos(math.radians((lat0 + lat1) / 2))
    s = min(sx, sy / kx * kx)  # keep simple: fit width/height
    sx = (x1 - x0) / (lon1 - lon0); sy = sx / kx
    if sy * (lat1 - lat0) > (y1 - y0):
        sy = (y1 - y0) / (lat1 - lat0); sx = sy * kx
    def P(lon, lat):
        return (x0 + (lon - lon0) * sx, y0 + (lat1 - lat) * sy)
    d.rectangle(box, fill=(6, 22, 40))
    for shp in shapes:
        bb = shp.bbox
        if bb[2] < lon0 or bb[0] > lon1 or bb[3] < lat0 or bb[1] > lat1: continue
        pts = shp.points; parts = list(shp.parts) + [len(pts)]
        for a, b in zip(parts[:-1], parts[1:]):
            poly = [P(*p) for p in pts[a:b]]
            if len(poly) > 2: d.polygon(poly, fill=LAND, outline=(60, 90, 110))
    # clip outside box
    d.rectangle([0, 0, W, y0 - 1], fill=None)
    im2, d2 = base(); im2.paste(im.crop(box), box[:2]); im, d = im2, d2
    d.rectangle(box, outline=DIM, width=2)
    for lon, lat, label, col, dx, dy in marks:
        x, y = P(lon, lat)
        d.ellipse([x - 11, y - 11, x + 11, y + 11], fill=col, outline=WHITE, width=3)
        d.text((x + dx, y + dy), label, font=F(SEMI, 30), fill=WHITE, anchor="lm" if dx > 0 else "rm")
    if extra: extra(d, P)
    title(d, ttl, sub)
    return im, d


def aqaba_labels(d, P):
    for lon, lat, t in [(33.9, 28.75, "SINAI (EGYPT)"), (35.55, 28.3, "SAUDI ARABIA")]:
        x, y = P(lon, lat); ctext(d, (x, y), t, F(SEMI, 30), GREY)
    x, y = P(34.6, 28.25); ctext(d, (x, y), "Gulf of Aqaba", F(MED, 28), CYAN)


im, d = draw_map("map_aqaba", 33.4, 36.2, 27.75, 29.6, (560, 200, 1860, 1020),
                 [(34.7951, 28.7886, "NEOM Brine Pools · 1,770 m", CYAN, 28, 0),
                  (34.799, 28.826, "1995 epicentre (USGS)", RED, -28, -34),
                  (34.47, 27.98, "Straits of Tiran", GREY, 28, 0)],
                 "Gulf of Aqaba", "Where the lake was found", aqaba_labels)
d.text((80, 300), "2 km from the coast", font=F(SEMI, 40), fill=WHITE)
d.text((80, 360), "1,770 m deep", font=F(SEMI, 40), fill=WHITE)
d.text((80, 420), "found in 2020", font=F(SEMI, 40), fill=WHITE)
source(d, "Pool position: Purkis et al. 2022 (28°47.3′N 34°47.7′E). Epicentre: USGS usp0007788. Coastline: Natural Earth.")
save(im, "map_aqaba")


def rs_labels(d, P):
    for lon, lat, t in [(30.5, 26.5, "EGYPT"), (41.5, 24.5, "SAUDI ARABIA"), (34.2, 19.5, "SUDAN")]:
        x, y = P(lon, lat); ctext(d, (x, y), t, F(SEMI, 30), GREY)
    x, y = P(37.6, 21.0); ctext(d, (x, y), "Red Sea", F(MED, 30), CYAN)


im, d = draw_map("map_redsea", 28.5, 45.5, 12.0, 31.5, (760, 180, 1860, 1020),
                 [(34.7951, 28.7886, "Gulf of Aqaba", CYAN, 28, 0)], "The Red Sea", "and its northeastern arm", rs_labels)
source(d, "Coastline: Natural Earth.")
save(im, "map_redsea")


# ---------- depth profile with ship and sonar ----------
def profile(name, show_sonar=False, show_reef=True, label_lake=True):
    im, d = base()
    # x: 0..2.6 km offshore -> px ; y: 0..1900 m -> px
    X = lambda km: 160 + km / 2.6 * 1600
    Y = lambda m: 250 + m / 1900 * 700
    d.line([(X(0), Y(0)), (X(2.6), Y(0))], fill=CYAN, width=3)  # sea surface
    # coast and slope (schematic): near vertical to 250 m, then ~35 deg to toe at 1770 m, 2 km offshore
    pts = [(X(-0.2), Y(-60)), (X(0), Y(-60)), (X(0.02), Y(0)), (X(0.06), Y(250)),
           (X(2.0), Y(1770)), (X(2.6), Y(1772)), (X(2.6), Y(1900)), (X(-0.2), Y(1900))]
    d.polygon(pts, fill=LAND)
    # lake: dip at toe
    lake = [(X(2.0), Y(1770)), (X(2.07), Y(1776)), (X(2.15), Y(1776)), (X(2.22), Y(1770))]
    d.polygon(lake, fill=BRINE)
    if show_reef:
        d.text((X(0.08), Y(20)), "coral reef", font=F(MED, 28), fill=SAND)
    d.text((X(0.75), Y(900)), "slope", font=F(MED, 30), fill=GREY)
    if label_lake:
        d.line([(X(2.11), Y(1772)), (X(2.11), Y(1600))], fill=CYAN, width=2)
        d.text((X(2.11), Y(1580)), "the lake · 1,770 m", font=F(SEMI, 32), fill=WHITE, anchor="mb")
    for m in (0, 500, 1000, 1500):
        d.text((150, Y(m)), f"{m:,} m", font=F(MED, 24), fill=DIM, anchor="rm")
    d.line([(X(0), Y(1840)), (X(2.0), Y(1840))], fill=GREY, width=2)
    d.text((X(1.0), Y(1860)), "2 km", font=F(MED, 26), fill=GREY, anchor="mt")
    if show_sonar:
        sx = X(2.11); sy = Y(0) - 18
        d.polygon([(sx - 40, sy), (sx + 40, sy), (sx + 28, sy + 18), (sx - 28, sy + 18)], fill=WHITE)
        fan = Image.new("RGBA", (W, H), (0, 0, 0, 0)); fd = ImageDraw.Draw(fan)
        fd.polygon([(sx, sy + 18), (X(1.8), Y(1600)), (X(2.45), Y(1772))], fill=CYAN + (40,))
        im.paste(fan, (0, 0), fan); d = ImageDraw.Draw(im)
        d.text((sx - 70, sy - 80), "ship's multibeam sonar · 70–100 kHz", font=F(SEMI, 30), fill=WHITE, anchor="ra")
        d.text((sx - 70, sy - 38), "set up for ~10 m detail", font=F(MED, 26), fill=GREY, anchor="ra")
    return im, d


im, d = profile("profile")
title(d, "Toe of the Saudi slope", "Schematic, not to scale horizontally")
source(d, "Depth 1,770 m, 2 km offshore, slope 35° below 250 m: Purkis et al. 2022. Schematic.")
save(im, "profile")
im, d = profile("profile_sonar", show_sonar=True)
title(d, "The pools “lacked a multibeam signature”")
source(d, "Purkis et al. 2022, Methods. Kongsberg EM712/EM304, min. across-track resolution 10 m. Schematic.")
save(im, "profile_sonar")

# ---------- lake outline with scale ----------
im, d = base()
title(d, "The main pool", "260 m long · 70 m wide · ~10,000 m²")
cx, cy = 960, 600; L = 1300; Wd = L * 70 / 260
pts = []
for a in range(0, 360, 4):
    r = 1 + 0.06 * math.sin(math.radians(a) * 3) + 0.03 * math.cos(math.radians(a) * 5)
    c, sn = math.cos(math.radians(a)), math.sin(math.radians(a))
    pts.append((cx + L / 2 * r * math.copysign(abs(c) ** 0.8, c), cy + Wd / 2 * r * math.copysign(abs(sn) ** 1.9, sn)))
d.polygon(pts, fill=BRINE, outline=ORANGE)
d.line([(cx - L / 2, cy + Wd / 2 + 70), (cx + L / 2, cy + Wd / 2 + 70)], fill=WHITE, width=3)
ctext(d, (cx, cy + Wd / 2 + 100), "260 m", F(SEMI, 34), WHITE)
d.line([(cx + L / 2 + 50, cy - Wd / 2), (cx + L / 2 + 50, cy + Wd / 2)], fill=WHITE, width=3)
d.text((cx + L / 2 + 70, cy), "70 m", font=F(SEMI, 34), fill=WHITE, anchor="lm")
ctext(d, (cx, cy), "max. 6 m deep", F(MED, 30), WHITE)
d.text((80, 860), "+ three small pools, each under 10 m²", font=F(MED, 30), fill=GREY)
source(d, "Purkis et al. 2022, Fig. 3c. Outline schematic.")
save(im, "lake_outline")

# ---------- measurements ----------
im, d = base()
title(d, "Across the surface of the lake", "Measured by the team's instruments")
rows = [("Salinity", "40 PSU", "160 PSU", "≈ 4×"), ("Oxygen", "180 μmol/L", "< 10 μmol/L", "at 50 cm"),
        ("Temperature", "21.3 °C", "+1 °C", "at 2 m")]
d.text((620, 290), "SEAWATER ABOVE", font=F(SEMI, 28), fill=GREY, anchor="mm")
d.text((1180, 290), "BRINE BELOW", font=F(SEMI, 28), fill=GREY, anchor="mm")
for i, (k, a, b, c) in enumerate(rows):
    y = 400 + i * 180
    d.text((120, y), k, font=F(SEMI, 44), fill=WHITE, anchor="lm")
    d.text((620, y), a, font=F(BOLD, 56), fill=CYAN, anchor="mm")
    d.text((1180, y), b, font=F(BOLD, 56), fill=ORANGE, anchor="mm")
    d.text((1560, y), c, font=F(MED, 34), fill=GREY, anchor="lm")
d.line([(900, 330), (900, 900)], fill=DIM, width=3)
source(d, "Purkis et al. 2022, Fig. 4. Interface at 1,769.46 m. Lab salinity 160 PSU (probe saturated at 120).")
save(im, "measurements")

# ---------- syrup analogy ----------
im, d = base()
title(d, "Like syrup under water", "Dense brine stays in a layer on the floor")
gx, gy, gw, gh = 760, 260, 400, 640
d.rectangle([gx, gy + gh * 0.62, gx + gw, gy + gh], fill=BRINE)
d.rectangle([gx, gy + 40, gx + gw, gy + gh * 0.62], fill=(22, 70, 110))
d.line([(gx, gy), (gx, gy + gh), (gx + gw, gy + gh), (gx + gw, gy)], fill=WHITE, width=6)
d.text((gx + gw + 40, gy + gh * 0.35), "seawater", font=F(SEMI, 36), fill=WHITE, anchor="lm")
d.text((gx + gw + 40, gy + gh * 0.82), "brine · 4× saltier", font=F(SEMI, 36), fill=ORANGE, anchor="lm")
d.line([(gx - 30, gy + gh * 0.62), (gx + gw + 30, gy + gh * 0.62)], fill=CYAN, width=3)
d.text((gx - 40, gy + gh * 0.62), "sharp boundary", font=F(MED, 30), fill=CYAN, anchor="rm")
source(d, "Analogy for illustration.")
save(im, "syrup")

# ---------- seeps on slope ----------
im, d = base()
title(d, "Brine seeping from the slope", "One seep every 2–3 m along the 260 m shore, up to 5 m above the pool")
d.polygon([(200, 260), (1100, 260), (1450, 880), (200, 880)], fill=LAND)
d.polygon([(200, 880), (1900, 880), (1900, 1000), (200, 1000)], fill=LAND)
d.rectangle([1450, 860, 1900, 880], fill=BRINE)
for (x, y) in [(1330, 668), (1365, 730), (1395, 785)]:
    d.ellipse([x - 10, y - 10, x + 10, y + 10], fill=ORANGE)
    t = (860 - y) / (880 - 260)
    d.line([(x, y), (1452, 860)], fill=ORANGE, width=7)
d.text((1600, 840), "pool", font=F(SEMI, 32), fill=WHITE, anchor="mb")
d.text((1150, 700), "seeps (up to 5 m above the pool)", font=F(MED, 28), fill=ORANGE, anchor="rm")
d.text((700, 600), "slope", font=F(MED, 34), fill=GREY, anchor="mm")
source(d, "Purkis et al. 2022, Fig. 5 and text. Cross-section, schematic; spacing is along the shore.")
save(im, "seeps")

# ---------- salt source ----------
im, d = base()
title(d, "Where does the salt come from?", "Two candidates, one fingerprint")
for i, (h, t1, t2, col, verdict) in enumerate([
        ("Evaporated seawater", "heavy-oxygen signal expected:", "δ¹⁸O ≈ 16‰", GREY, "✗  brine has δ¹⁸O ≈ 1‰"),
        ("Buried ancient salt", "Late Miocene evaporites", "under the seafloor", ORANGE, "✓  most plausible source")]):
    x = 160 + i * 820
    d.rounded_rectangle([x, 300, x + 760, 820], radius=24, outline=col, width=4)
    d.text((x + 40, 350), h, font=F(BOLD, 48), fill=WHITE)
    d.text((x + 40, 460), t1, font=F(MED, 34), fill=GREY)
    d.text((x + 40, 510), t2, font=F(SEMI, 40), fill=WHITE)
    d.text((x + 40, 700), verdict, font=F(SEMI, 38), fill=CYAN if i else RED)
source(d, "Purkis et al. 2022, Fig. 6b.")
save(im, "salt_source")

# ---------- shore rings ----------
im, d = base()
title(d, "The shore, in rings", "From ordinary mud to permanent brine")
zones = [("ordinary mud", (70, 70, 64), "burrowed by animals"), ("gray band · 1–2 m", GRAYZ, "microbes that use oxygen"),
         ("orange swash zone", ORANGE, "brine washes over it"), ("brine pool", BRINE, "microbes that live without oxygen")]
x = 120
for i, (n, col, note) in enumerate(zones):
    w = [520, 360, 300, 520][i]
    d.rectangle([x, 520, x + w, 700], fill=col)
    d.text((x + 16, 470 - (i % 2) * 50), n, font=F(SEMI, 30), fill=WHITE)
    d.text((x + 16, 730 + (i % 2) * 44), note, font=F(MED, 26), fill=GREY)
    x += w
d.text((1000, 340), "clams: 20 cm band just above the brine", font=F(MED, 28), fill=CYAN, anchor="mm")
d.line([(1000, 362), (1000, 515)], fill=CYAN, width=3)
d.polygon([(990, 500), (1010, 500), (1000, 516)], fill=CYAN)
source(d, "Purkis et al. 2022, Fig. 7 and 10. Widths schematic.")
save(im, "shore_rings")

# ---------- core ----------
im, d = base()
title(d, "What the mud recorded", "Longest core: ≥ 1,200 years")
cx0, cx1, cy0, cy1 = 760, 960, 230, 980
d.rectangle([cx0, cy0, cx1, cy1], fill=(85, 75, 60))
import random; random.seed(3)
for k in range(55):
    y = random.uniform(cy0 + 5, cy1 - 5); d.line([(cx0, y), (cx1, y)], fill=(120, 105, 80), width=random.choice([1, 2, 3]))
for y, th in [(300, 8), (360, 6), (420, 8), (530, 150), (720, 8), (780, 6), (840, 10), (890, 6), (930, 8), (965, 8)]:
    d.rectangle([cx0, y, cx1, y + th], fill=SAND)
d.text((cx0 - 30, cy0), "top · today", font=F(MED, 28), fill=GREY, anchor="ra")
d.text((cx0 - 30, cy1), "≈ 1,200 years ago", font=F(MED, 28), fill=GREY, anchor="rd")
d.rectangle([1040, 330, 1080, 360], fill=SAND); d.text((1100, 345), "about 10 coarse layers from land · ~1 per century", font=F(SEMI, 34), fill=WHITE, anchor="lm")
d.rectangle([1040, 450, 1080, 480], fill=(120, 105, 80)); d.text((1100, 465), "≥ 50 fine flow layers · ≥ 4 per century", font=F(SEMI, 34), fill=WHITE, anchor="lm")
d.text((1060, 585), "≈", font=F(BOLD, 40), fill=ORANGE, anchor="mm"); d.text((1100, 585), "3 contorted intervals · consistent with shaking", font=F(SEMI, 34), fill=WHITE, anchor="lm")
source(d, "Purkis et al. 2022, Fig. 8 and Discussion. Layer positions schematic.")
save(im, "core")

# ---------- settling ----------
im, d = base()
title(d, "Why the layers survive", "The authors' proposed mechanism")
d.rectangle([600, 300, 1320, 960], fill=(22, 70, 110))
d.rectangle([600, 640, 1320, 960], fill=BRINE)
d.line([(600, 640), (1320, 640)], fill=CYAN, width=4)
random.seed(1)
for k in range(220):
    x = random.uniform(620, 1300); y = random.uniform(330, 630); r = random.choice([2, 3, 5])
    d.ellipse([x - r, y - r, x + r, y + r], fill=SAND)
for k, (y0, r) in enumerate([(930, 6), (900, 4), (875, 2)]):
    for i in range(60):
        x = 620 + i * 11.5; d.ellipse([x - r, y0 - r, x + r, y0 + r], fill=SAND)
d.text((1360, 470), "flow stalls at the brine", font=F(SEMI, 32), fill=WHITE, anchor="lm")
d.text((1360, 900), "coarse first, fine last", font=F(SEMI, 32), fill=WHITE, anchor="lm")
d.text((1360, 950), "no scouring below", font=F(MED, 28), fill=GREY, anchor="lm")
source(d, "Purkis et al. 2022, Discussion. Schematic.")
save(im, "settling")

# ---------- five ways ----------
im, d = base()
title(d, "How does gravel from land get down there?", "Five candidates the authors consider")
items = [("Permanent rivers", "none flow into the gulf", "✗", RED), ("Wind", "grains too coarse", "✗", RED),
         ("Storm waves", "gulf too narrow", "✗", RED), ("Flash floods", "grains coarser than expected", "?", ORANGE),
         ("Tsunamis", "“to our minds the most plausible”", "✓", CYAN)]
for i, (a, b, m, col) in enumerate(items):
    y = 300 + i * 135
    d.text((160, y), m, font=F(BOLD, 60), fill=col, anchor="mm")
    d.text((240, y), a, font=F(SEMI, 46), fill=WHITE, anchor="lm")
    d.text((760, y), b, font=F(MED, 36), fill=GREY, anchor="lm")
source(d, "Purkis et al. 2022, Discussion. Not proven.")
save(im, "five_ways")

# ---------- 1995 card ----------
im, d = base()
title(d, "22 November 1995", "Nuweiba earthquake")
d.text((120, 380), "M 7.2", font=F(BOLD, 200), fill=WHITE)
d.text((130, 640), "magnitude according to the USGS", font=F(MED, 34), fill=GREY)
d.text((130, 720), "the paper gives Mw 7.3 and Mw 7.1 in different sections", font=F(MED, 30), fill=DIM)
d.text((1100, 420), "ruptured part of a fault", font=F(SEMI, 40), fill=WHITE)
d.text((1100, 480), "in the same basin", font=F(SEMI, 40), fill=WHITE)
d.text((1100, 580), "generated a modest tsunami", font=F(SEMI, 40), fill=CYAN)
source(d, "USGS event usp0007788. Fault and tsunami: Purkis et al. 2022.")
save(im, "quake1995")

# ---------- open questions ----------
im, d = base()
title(d, "What we don't know yet")
qs = ["Are the coarse layers really tsunamis?", "Which fine layers are floods, which are earthquakes?",
      "Is the brine fully without oxygen?", "Does brine arrive in sudden pulses?"]
for i, q in enumerate(qs):
    d.text((160, 300 + i * 150), f"{i + 1}", font=F(BOLD, 64), fill=CYAN, anchor="mm")
    d.text((240, 300 + i * 150), q, font=F(SEMI, 48), fill=WHITE, anchor="lm")
source(d, "Open questions stated or implied in Purkis et al. 2022.")
save(im, "open_questions")

# ---------- cards ----------
im, d = base()
ctext(d, (W / 2, 420), "About the pictures", F(BOLD, 72), WHITE)
ctext(d, (W / 2, 540), "Underwater footage: NOAA Ocean Exploration, Gulf of Mexico (public domain)", F(MED, 36), GREY)
ctext(d, (W / 2, 600), "It shows the same kind of place, not the lake in the Gulf of Aqaba", F(MED, 36), GREY)
ctext(d, (W / 2, 720), "Purkis et al. 2022 · Communications Earth & Environment 3:146", F(SEMI, 38), CYAN)
ctext(d, (W / 2, 775), "doi.org/10.1038/s43247-022-00482-x", F(MED, 32), CYAN)
save(im, "card_footage")

im, d = base()
ctext(d, (W / 2, 500), "The Seafloor Lake", F(BOLD, 110), WHITE)
ctext(d, (W / 2, 630), "the Ship's Sonar Couldn't See", F(BOLD, 110), WHITE)
ctext(d, (W / 2, 780), "HADAL DISPATCH", F(SEMI, 40), CYAN)
save(im, "card_title")

im, d = base()
ctext(d, (W / 2, 330), "Sources", F(BOLD, 72), WHITE)
lines = ["Purkis S.J. et al. (2022) Discovery of the deep-sea NEOM Brine Pools in the Gulf of Aqaba, Red Sea.",
         "Communications Earth & Environment 3:146 · doi.org/10.1038/s43247-022-00482-x · CC BY 4.0",
         "University of Miami news, 11 July 2022 · USGS event usp0007788",
         "Footage: NOAA Ocean Exploration (Okeanos Explorer, Gulf of Mexico 2012–2018)",
         "Narration: AI voice"]
for i, l in enumerate(lines):
    ctext(d, (W / 2, 460 + i * 70), l, F(MED, 32), GREY if i else WHITE)
save(im, "card_sources")
print("ok", sorted(os.listdir(OUT)))

im, d = base()
save(im, "_bg")

im, d = base()
title(d, "A lake you can land on", "The team set its robot down on the brine surface")
d.rectangle([300, 640, 1620, 900], fill=BRINE)
d.line([(300, 640), (1620, 640)], fill=CYAN, width=4)
d.rounded_rectangle([780, 470, 1140, 640], radius=18, fill=(200, 205, 210))
d.text((960, 555), "ROV", font=F(BOLD, 60), fill=(20, 40, 60), anchor="mm")
d.text((1180, 520), "10,000 lb (about 4.5 t on deck)", font=F(SEMI, 36), fill=WHITE, anchor="lm")
d.text((960, 770), "brine · 160 PSU", font=F(SEMI, 36), fill=WHITE, anchor="mm")
d.text((960, 420), "dye showed a sharp boundary", font=F(MED, 30), fill=CYAN, anchor="mm")
source(d, "Purkis et al. 2022, Fig. 2 and Discussion. Schematic.")
save(im, "rov_landed")

im, d = base()
title(d, "Imaging sonar on the robot", "450–900 kHz: the brine showed as a weak, \u201cdampened\u201d echo")
d.pieslice([360, 300, 1560, 1500], 225, 315, fill=(14, 40, 62), outline=DIM)
for k in range(1, 6):
    r = k * 120; d.arc([960 - r, 900 - r, 960 + r, 900 + r], 225, 315, fill=DIM, width=1)
import random as _r; _r.seed(5)
for i in range(1400):
    a = math.radians(_r.uniform(228, 312)); rr = _r.uniform(60, 590)
    x, y = 960 + rr * math.cos(a), 900 + rr * math.sin(a)
    inside = ((x - 960) / 260) ** 2 + ((y - 520) / 80) ** 2 < 1
    v = _r.randint(40, 80) if inside else _r.randint(120, 230)
    d.ellipse([x - 3, y - 3, x + 3, y + 3], fill=(v, v + 20, v + 30))
d.text((960, 520), "brine", font=F(SEMI, 34), fill=CYAN, anchor="mm")
source(d, "Purkis et al. 2022, Methods. Illustration, not the team's sonar image.")
save(im, "imaging_sonar")

im, d = base()
title(d, "Shrimp out over the lake", "Seen as far as mid-pool, more than 30 m from the shore")
cx, cy = 960, 620
pts = []
for a in range(0, 360, 4):
    c, sn = math.cos(math.radians(a)), math.sin(math.radians(a))
    pts.append((cx + 650 * math.copysign(abs(c) ** 0.8, c), cy + 175 * math.copysign(abs(sn) ** 1.9, sn)))
d.polygon(pts, fill=BRINE, outline=ORANGE)
d.ellipse([cx - 14, cy - 14, cx + 14, cy + 14], fill=RED)
d.line([(cx, cy), (cx, cy - 175)], fill=WHITE, width=3)
d.text((cx + 24, cy - 90), "> 30 m", font=F(SEMI, 34), fill=WHITE, anchor="lm")
d.text((cx, cy + 50), "shrimp (Plesionika sp.)", font=F(MED, 28), fill=WHITE, anchor="mt")
source(d, "Purkis et al. 2022, Fig. 9. Positions schematic.")
save(im, "lake_shrimp")
