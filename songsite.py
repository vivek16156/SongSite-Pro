"""
SongSite Pro — Fully local music streaming (no YouTube) with pro UI.

Features:
- Stream your uploaded songs directly
- Download songs if available
- Search songs by title or artist
- Sticky now-playing player
- Beautiful, responsive, dark-themed UI
"""

from flask import Flask, request, render_template_string, send_from_directory, abort
from pathlib import Path
import os

# ---------- CONFIG ----------
BASE_DIR = Path.cwd()
SONGS_DIR = BASE_DIR / "songs"
SONGS_DIR.mkdir(exist_ok=True)

# Map song names to files for download
DOWNLOADABLE_MAP = {
    # Example:
    # "Arijit Singh Song": "songs/arijit_song.mp3"
}
# You can populate DOWNLOADABLE_MAP automatically:
for file in SONGS_DIR.glob("*.*"):
    DOWNLOADABLE_MAP[file.stem] = str(file)

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET", "dev-secret-key")

# ---------- TEMPLATE ----------
BASE_HTML = r"""
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>SongSite Pro - Stream Songs</title>
<style>
:root{
  --bg:#0f0f12; --card:#151519; --accent:#ff3b6b; --muted:#9aa0a6;
  --glass: rgba(255,255,255,0.03);
}
*{box-sizing:border-box}
body{margin:0;font-family:Inter,system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial;background:
linear-gradient(180deg,#070707 0%, #111216 100%);color:#eef1f6;min-height:100vh}
.container{max-width:1200px;margin:22px auto;padding:0 16px}
.header{display:flex;gap:12px;align-items:center;justify-content:space-between;flex-wrap:wrap}
.brand h1{margin:0;font-size:1.6rem;letter-spacing:0.6px;color:var(--accent)}
.controls{display:flex;gap:10px;align-items:center}
.search{display:flex;gap:8px;flex:1;max-width:720px}
input.searchbox{flex:1;padding:10px 12px;border-radius:10px;border:none;background:var(--glass);color:#fff}
button.btn{background:linear-gradient(90deg,var(--accent),#ff7a9a);border:none;padding:10px 14px;border-radius:10px;color:#fff;font-weight:600;cursor:pointer}
.small{padding:8px 10px;border-radius:8px;background:#151515;border:1px solid rgba(255,255,255,0.03);cursor:pointer;color:var(--muted)}
.card{background:linear-gradient(180deg, rgba(255,255,255,0.02), rgba(255,255,255,0.01));border-radius:16px;padding:14px;box-shadow: 0 10px 30px rgba(0,0,0,0.6);border:1px solid rgba(255,255,255,0.02)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:16px;margin-top:18px}
.song-title{font-weight:700;margin:0 0 6px 0}
.song-sub{color:var(--muted);font-size:0.9rem;margin:0}
.player{position:sticky;top:12px;padding:12px;border-radius:12px;background:linear-gradient(90deg, rgba(255,255,255,0.02), rgba(255,255,255,0.01));display:flex;gap:12px;align-items:center}
.play-info{min-width:0}
.play-title{font-weight:700;margin:0}
.play-artist{color:var(--muted);font-size:0.9rem;margin:0}
.play-buttons{display:flex;gap:8px;margin-left:auto}
.play-btn{background:transparent;border:1px solid rgba(255,255,255,0.06);padding:8px;border-radius:10px;color:#fff;cursor:pointer}
.resp-iframe{width:100%;height:0;padding-bottom:56.25%;position:relative;overflow:hidden;border-radius:10px}
.resp-iframe audio{position:absolute;top:0;left:0;width:100%;height:100%;border-radius:10px}
.footer{margin:28px 0;text-align:center;color:var(--muted);font-size:0.9rem}
.badge{background:rgba(255,255,255,0.03);padding:6px 10px;border-radius:8px;border:1px solid rgba(255,255,255,0.02);font-size:0.9rem;color:var(--muted)}
.admin-reset{background:#c53030}
@media(max-width:700px){
  .player{flex-direction:column;align-items:flex-start;gap:8px}
  .play-buttons{margin-left:0}
}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <div class="brand">
      <h1>SongSite Pro</h1>
      <div style="color:var(--muted);font-size:0.95rem">Stream your own music — professional UI</div>
    </div>
    <div class="controls">
      <form method="get" action="/" class="search" style="display:flex;">
        <input class="searchbox" type="search" name="q" placeholder="Search songs or artist" value="{{ q|default('') }}">
        <button class="btn" type="submit">Search</button>
      </form>
    </div>
  </div>

  <!-- sticky player -->
  <div style="margin-top:18px" class="card player">
    <audio id="audio-player" controls style="width:100%;"></audio>
    <div class="play-info">
      <div class="play-title" id="now-title">Nothing playing</div>
      <div class="play-artist" id="now-artist">Select a song to play</div>
    </div>
  </div>

  <!-- results grid -->
  {% if results %}
  <div class="grid">
    {% for r in results %}
    <div class="card">
      <div class="song-title">{{ r.title }}</div>
      <div class="song-sub">{{ r.artist }}</div>
      <div style="height:12px"></div>
      <button class="small" onclick="playSong('{{ r.file_url }}','{{ r.title|e }}','{{ r.artist|e }}')">Play</button>
      {% if r.download_key %}
      <a class="small" href="{{ url_for('download_file', key=r.download_key) }}">Download</a>
      {% endif %}
    </div>
    {% endfor %}
  </div>
  {% elif q %}
  <div class="card" style="margin-top:18px">No results for "<strong>{{ q }}</strong>"</div>
  {% endif %}

  <!-- all songs by popularity (just sorted by name for now) -->
  <h2 style="margin-top:24px;">All Songs</h2>
  <div class="grid">
    {% for title, file in all_songs.items() %}
    <div class="card">
      <div class="song-title">{{ title }}</div>
      <button class="small" onclick="playSong('{{ file }}','{{ title }}','')">Play</button>
      <a class="small" href="{{ url_for('download_file', key=title) }}">Download</a>
    </div>
    {% endfor %}
  </div>

  <div class="footer">Built with ❤️ — SongSite Pro</div>
</div>

<script>
const audioPlayer = document.getElementById('audio-player');
function playSong(url, title, artist){
  audioPlayer.src = url;
  audioPlayer.play();
  document.getElementById('now-title').textContent = title;
  document.getElementById('now-artist').textContent = artist;
}
</script>
</body>
</html>
"""

# ---------- ROUTES ----------
@app.route("/", methods=["GET"])
def index():
    q = (request.args.get("q") or "").strip()
    results = []
    for title, file in DOWNLOADABLE_MAP.items():
        if not q or q.lower() in title.lower():
            results.append({"title": title, "artist": "", "file_url": file, "download_key": title})
    # Sort alphabetically or by "popularity"
    all_songs = dict(sorted(DOWNLOADABLE_MAP.items()))
    return render_template_string(BASE_HTML, results=results, q=q, all_songs=all_songs)

@app.route("/download/<key>")
def download_file(key):
    if key not in DOWNLOADABLE_MAP:
        abort(404)
    path = Path(DOWNLOADABLE_MAP[key])
    if not path.exists():
        abort(404)
    return send_from_directory(str(path.parent), path.name, as_attachment=True)

# ---------- RUN ----------
if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 5000))
    print(f"Starting SongSite Pro on http://{host}:{port}")
    app.run(host=host, port=port, debug=True)
