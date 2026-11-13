"""Build timeline.json for E01: one visual plan per narration paragraph, timed by character share.
Rule: NOAA Gulf-of-Mexico clips only under general sentences; Aqaba numbers get own graphics."""
import json, sys

sections_txt, out = sys.argv[1], sys.argv[2]
secs = open(sections_txt).read().split("\n\n=====\n\n")
import subprocess, os
AUD = sys.argv[3] if len(sys.argv) > 3 else "../audio"
DUR = [float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", os.path.join(AUD, f"s{i:02d}.mp3")])) for i in range(11)]
GAP = 0.8
Y = {"EX1202": "2012", "EX1402": "2014", "EX1711": "2017", "EX1803": "2018"}


def C(f, ss):
    return ("clip", f, ss)


def G(n):
    return ("gfx", n)


LAKE1 = C("EX1711_VID_20171212T165500Z_ROVHD_Low.mp4", "00:03:44")
SHRIMP = C("EX1711_VID_20171212T165500Z_ROVHD_Low.mp4", "00:04:28")
LAKE3 = C("EX1711_VID_20171212T165500Z_ROVHD_Low.mp4", "00:03:10")
FISH_SHELLS = C("EX1711_VID_20171212T165500Z_ROVHD_Low.mp4", "00:02:30")
LAKE7 = C("EX1711_VID_20171212T170000Z_ROVHD_Low.mp4", "00:00:00")
SHORE8 = C("EX1711_VID_20171212T170000Z_ROVHD_Low.mp4", "00:01:52")
MUSSELS = C("EX1711_VID_20171212T170000Z_ROVHD_Low.mp4", "00:00:52")
CLOUD = C("EX1711_VID_20171212T170000Z_ROVHD_Low.mp4", "00:04:06")
PTMAN = C("EX1711_VID_20171212T170052Z_PTMAN_BRINE_Low.mp4", "00:01:05")
CHANNEL = C("EX1711_VID_20171212T172000Z_ROVHD_Low.mp4", "00:00:25")
SHORE14 = C("EX1711_VID_20171212T172000Z_ROVHD_Low.mp4", "00:04:06")
SLED = C("EX1711_VID_20171212T170000Z_CPHD_Low.mp4", "00:01:52")
BUBBLES = C("EX1803_VID_20180419T190500Z_ROVHD_Low.mp4", "00:01:10")
FLOW = C("EX1803_VID_20180419T191500Z_ROVHD_Low.mp4", "00:01:15")
CLAMS = C("EX1803_VID_20180419T191500Z_ROVHD_Low.mp4", "00:03:20")
FLOW22 = C("EX1803_VID_20180419T191500Z_ROVHD_Low.mp4", "00:04:10")
MIRROR = C("EX1202L3_VID_20120420T204701Z_ROVHD_CAR_BRINE_POOL_Low.mp4", "00:00:07")
MATCHAN = C("EX1202L3_VID_20120420T204701Z_ROVHD_CAR_BRINE_POOL_Low.mp4", "00:01:24")
ORANGE = C("EX1202L3_VID_20120420T193512Z_ROVHD_BRINE_POOL_TUB_Low.mp4", "00:00:00")
WHITEDGE = C("EX1202L3_VID_20120421T195454Z_ROVHD_POOL_STUDY_Low.mp4", "00:00:50")
EEL = C("EX1202L3_VID_20120421T195454Z_ROVHD_POOL_STUDY_Low.mp4", "00:02:26")
RIM = C("EX1202L3_VID_20120421T195845Z_ROVHD_BRINEY_POOL_Low.mp4", "00:01:00")
ROVIN = C("EX1202L3_VID_20120421T195845Z_ROVHD_BRINEY_POOL_Low.mp4", "00:01:30")
SONAR = C("EX1202L3_VID_20120420T150836Z_SONAR_SEEP_BED_FOUND_01_Low.mp4", "00:03:18")
MUD = C("EX1402L3_VID_20140416T151320Z_ROVHD_BRINE_AUDIO_Low.mp4", "00:00:00")
SHORE_FMR = C("EX1202L3_VID_20120421T195026Z_ROVHD_FMR_BRINE_POOL_Low.mp4", "00:00:00")

PLAN = [
    # 0 cold open: Aqaba facts -> graphics only
    [[G("profile_sonar")], [G("lake_outline")], [G("map_aqaba")], [G("shore_rings")], [G("measurements")], [G("core")], [G("card_title")]],
    # 1 about the pictures
    [[LAKE1, G("card_footage")]],
    # 2 location
    [[G("map_redsea")], [G("map_aqaba")], [G("map_aqaba")], [G("profile")], [MIRROR, LAKE7, SHORE_FMR], [G("profile")]],
    # 3 how you miss a lake
    [[G("profile_sonar")], [G("profile_sonar")], [G("profile_sonar")], [G("lake_outline")], [SLED, PTMAN], [G("imaging_sonar")], [ROVIN]],
    # 4 lake you can land on
    [[G("rov_landed")], [G("rov_landed")], [G("measurements")], [G("measurements")], [G("measurements")], [G("measurements")], [G("measurements")], [G("syrup")], [CHANNEL]],
    # 5 salt
    [[G("seeps")], [G("seeps")], [G("salt_source")], [G("salt_source")], [G("salt_source")], [ORANGE, MATCHAN]],
    # 6 life on the shore
    [[MUD], [LAKE3], [G("shore_rings"), WHITEDGE], [G("shore_rings")], [SHRIMP], [EEL, FISH_SHELLS], [G("lake_shrimp")], [G("shore_rings")], [ORANGE], [G("core")]],
    # 7 mud that remembers
    [[G("core")], [G("core")], [G("core")], [G("settling")], [G("settling")], [G("syrup")], [G("core")]],
    # 8 event layers
    [[G("core")], [CLOUD, G("core")], [G("core")], [G("core")], [G("core")]],
    # 9 matching layers
    [[G("five_ways")], [G("five_ways")], [G("five_ways")], [G("quake1995")], [G("map_aqaba")], [G("core")]],
    # 10 open questions
    [[G("open_questions")], [G("open_questions"), RIM], [MATCHAN], [FLOW, BUBBLES], [SHORE8, CLAMS], [LAKE1]],
]

tl = []; t = 0.0
for si, (txt, dur) in enumerate(zip(secs, DUR)):
    paras = [p for p in txt.split("\n\n") if p.strip()]
    plan = PLAN[si]
    assert len(plan) == len(paras), (si, len(plan), len(paras))
    total_chars = sum(len(p) for p in paras)
    seg_t = t
    for pi, (p, items) in enumerate(zip(paras, plan)):
        pdur = dur * len(p) / total_chars
        if pi == len(paras) - 1 and si < len(DUR) - 1:
            pdur += GAP
        share = pdur / len(items)
        for it in items:
            if it[0] == "gfx":
                tl.append({"t": round(seg_t, 3), "d": round(share, 3), "kind": "gfx", "name": it[1]})
            else:
                f = it[1]
                label = f"Gulf of Mexico brine pool · NOAA Ocean Exploration · {Y[f[:6]]}"
                if "SONAR" in f:
                    label = f"ROV sonar display · Gulf of Mexico · NOAA Ocean Exploration · {Y[f[:6]]}"
                if f.startswith("EX1803"):
                    label = f"Gulf of Mexico brine seep · NOAA Ocean Exploration · {Y[f[:6]]}"
                tl.append({"t": round(seg_t, 3), "d": round(share, 3), "kind": "clip", "file": f, "ss": it[2], "label": label})
            seg_t += share
    t += dur + GAP
# merge consecutive identical gfx
merged = []
for it in tl:
    if merged and it["kind"] == "gfx" and merged[-1]["kind"] == "gfx" and merged[-1]["name"] == it["name"]:
        merged[-1]["d"] = round(merged[-1]["d"] + it["d"], 3)
    else:
        merged.append(it)
merged.append({"t": round(t - GAP, 3), "d": 6.0, "kind": "gfx", "name": "card_sources", "zoom": 0.0})
json.dump(merged, open(out, "w"), indent=1)
clips = sum(i["d"] for i in merged if i["kind"] == "clip"); tot = sum(i["d"] for i in merged)
print(len(merged), "items", round(tot, 1), "s; clip share", round(100 * clips / tot), "%; max clip", max(i["d"] for i in merged if i["kind"] == "clip"))
