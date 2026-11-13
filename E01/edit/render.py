"""Render E01 from a timeline (timeline.json) with ffmpeg.

Each timeline item: {"t": start_sec, "d": dur_sec, "kind": "gfx"|"clip", ...}
  gfx:  {"name": "map_aqaba"}                     -> full-screen still with a slow push-in
  clip: {"file": "...mp4", "ss": "00:01:23", "label": "Gulf of Mexico brine pool · NOAA Ocean Exploration · 2012"}
        -> NOAA 640x360 clip shown as a window (1280x720) on the dark background, label below
Usage: python3 render.py timeline.json gfx_dir noaa_dir narration.mp3 out.mp4 [preview]
"""
import json, os, subprocess, sys, tempfile

tl_path, GFX, NOAA, NARR, OUT = sys.argv[1:6]
PREVIEW = len(sys.argv) > 6
W, H = (1280, 720) if PREVIEW else (1920, 1080)
FPS = 30
FONT = "/usr/share/fonts/opentype/inter/Inter-Medium.otf"
BG = os.path.join(GFX, "_bg.png")
tl = json.load(open(tl_path))
tmp = tempfile.mkdtemp(prefix="e01_")


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        print(" ".join(cmd)); print(r.stderr[-2000:]); sys.exit(1)



parts = []
for i, it in enumerate(tl):
    seg = os.path.join(tmp, f"{i:03d}.mp4")
    d = it["d"]; n = int(round(d * FPS))
    common = ["-r", str(FPS), "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-an", "-t", f"{d:.3f}"]
    if it["kind"] == "gfx":
        img = os.path.join(GFX, it["name"] + ".png")
        z = it.get("zoom", 0.04)
        vf = (f"scale=3840:-1,zoompan=z='1+{z}*on/{n}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={n}:s={W}x{H}:fps={FPS}")
        run(["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-i", img, "-vf", vf, "-frames:v", str(n)] + common + [seg])
    else:
        src = os.path.join(NOAA, it["file"])
        win_w = int(W * 2 / 3); win_h = int(win_w * 9 / 16)
        x = (W - win_w) // 2; y = int(H * 0.08)
        fs = int(H / 36)
        label = it["label"].replace(":", r"\:").replace("'", "")
        vf = (f"[0:v]scale={W}:{H}[bg];[1:v]setpts=PTS-STARTPTS,scale={win_w}:{win_h}:flags=lanczos,"
              f"eq=contrast=1.05:saturation=1.08[v];[bg][v]overlay={x}:{y}:shortest=1,"
              f"drawbox=x={x - 3}:y={y - 3}:w={win_w + 6}:h={win_h + 6}:color=0x5ED6E6@0.6:t=3,"
              f"drawtext=fontfile={FONT}:text='{label}':x=(w-tw)/2:y={y + win_h + int(H * 0.04)}:fontsize={fs}:fontcolor=0xF0F6FA")
        run(["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-i", BG, "-ss", it["ss"], "-i", src,
             "-filter_complex", vf] + common + [seg])
    parts.append(seg)
    print(f"{i + 1}/{len(tl)}", it["kind"], it.get("name", it.get("file", ""))[:50], flush=True)

lst = os.path.join(tmp, "list.txt")
open(lst, "w").write("".join(f"file '{p}'\n" for p in parts))
total = sum(it["d"] for it in tl)
run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-i", NARR,
     "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-t", f"{total:.3f}",
     "-movflags", "+faststart", OUT])
print("done", OUT, total)
