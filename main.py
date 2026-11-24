import os, shutil, subprocess, tempfile, glob
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

app = FastAPI()
app.add_middleware(
    CORSMiddleware, allow_origins=["*"],
    allow_methods=["*"], allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

MAX_SECONDS = 600  # সর্বোচ্চ ১০ মিনিটের ক্লিপ


def to_sec(t: str) -> int:
    parts = [int(p) for p in t.strip().split(":")]
    s = 0
    for p in parts:
        s = s * 60 + p
    return s


@app.get("/")
def home():
    return {"ok": True}


@app.get("/clip")
def clip(url: str, start: str, end: str, bg: BackgroundTasks,
         quality: int = 1080, precise: bool = False):
    if "youtube.com" not in url and "youtu.be" not in url:
        raise HTTPException(400, "শুধু ইউটিউব লিঙ্ক দিন")
    try:
        s, e = to_sec(start), to_sec(end)
    except ValueError:
        raise HTTPException(400, "সময়ের ফরম্যাট ভুল (যেমন 10:30 বা 1:05:00)")
    if e <= s:
        raise HTTPException(400, "শেষের সময় শুরুর পরে হতে হবে")
    if e - s > MAX_SECONDS:
        raise HTTPException(400, "ক্লিপ সর্বোচ্চ ১০ মিনিটের হতে পারবে")

    tmp = tempfile.mkdtemp()
    bg.add_task(shutil.rmtree, tmp, True)

    fmt = (f"bv*[height<={quality}][vcodec^=avc1]+ba[ext=m4a]"
           f"/b[height<={quality}][ext=mp4]/b[height<={quality}]")
    cmd = [
        "python", "-m", "yt_dlp",
        "--no-playlist",
        "--download-sections", f"*{s}-{e}",
        "-f", fmt,
        "--merge-output-format", "mp4",
        "-o", os.path.join(tmp, "clip.%(ext)s"),
        url,
    ]
    if precise:
        cmd.insert(-1, "--force-keyframes-at-cuts")

    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=280)
    except subprocess.TimeoutExpired:
        raise HTTPException(504, "সময় বেশি লেগেছে, ছোট ক্লিপ চেষ্টা করুন")

    files = glob.glob(os.path.join(tmp, "clip.*"))
    if r.returncode != 0 or not files:
        raise HTTPException(502, "ডাউনলোড হয়নি: " + r.stderr[-300:])

    return FileResponse(files[0], media_type="video/mp4", filename="clip.mp4")
