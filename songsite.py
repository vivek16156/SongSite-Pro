"""
SongSite Pro — Spotify-style music streaming (YouTube) with professional 3D UI.

Features:
- Search & show multiple results (uses YouTube Data API if YOUTUBE_API_KEY is set)
- Plays songs in a custom on-site player (YouTube iframe controlled via JS API)
- Downloadable files only if present in `downloads/` and listed in DOWNLOADABLE_MAP
- Reset (admin) endpoint protected by ADMIN_KEY env var
- Ready for deployment (HOST/PORT env vars)
"""

from flask import (
    Flask, request, render_template_string, send_from_directory,
    redirect, url_for, flash, abort
)
import os, requests, urllib.parse, datetime
from pathlib import Path

# ---------- CONFIG ----------
BASE_DIR = Path.cwd()
DOWNLOADS_DIR = BASE_DIR / "downloads"
DOWNLOADS_DIR.mkdir(exist_ok=True)
# If you want to allow specific downloadable items, map a friendly key -> file path here:
# The key should match the "download_key" we'll use in templates (e.g. "my_demo_track")
DOWNLOADABLE_MAP = {
    # Example: "demo track": "downloads/demo_track.mp3"
    # Put files in 'downloads/' and add entries here to enable download buttons
}

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "").strip()  # optional
YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"

ADMIN_KEY = os.getenv("ADMIN_KEY", "admin-secret")  # change this in production

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET", "dev-secret-key")

# ---------- UTILITIES ----------
def search_youtube_api(query: str, max_results: int = 8):
    """Return list of dicts with video_id,title,channel using YouTube Data API.
    Requires YOUTUBE_API_KEY; otherwise returns empty list."""
    if not YOUTUBE_API_KEY:
        return []
    params = {
        "part": "snippet",
        "q": query,
        "type": "video",
        "maxResults": max_results,
        "key": YOUTUBE_API_KEY,
        "videoEmbeddable": "true"
    }
    resp = requests.get(YOUTUBE_SEARCH_URL, params=params, timeout=8)
    if resp.status_code != 200:
        return []
    data = resp.json()
    results = []
    for item in data.get("items", []):
        vid = item["id"].get("videoId")
        title = item["snippet"].get("title")
        channel = item["snippet"].get("channelTitle")
        if vid and title:
            results.append({"video_id": vid, "title": title, "artist": channel})
    return results

def smart_fallback_results(query: str):
    """When no API key, produce search-variant cards using YouTube embed search (no video IDs)."""
    # variants produce different search embed lists: official, live, remix, cover
    variants = [
        f"{query} official music video",
        f"{query} audio",
        f"{query} live",
        f"{query} remix",
        f"{query} cover",
        f"{query} full album",
        f"{query} karaoke",
        f"{query} hd"
    ]
    # return dicts with 'query' used to embed listType=search&list=... in iframe
    return [{"embed_query": v, "title": v, "artist": ""} for v in variants[:8]]

# ---------- TEMPLATES ----------
# Single-file template: professional 3D theme, grid of results, now-playing custom player
BASE_HTML = r"""
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>SongSite Pro - Stream Bollywood</title>
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
.resp-iframe iframe{position:absolute;top:0;left:0;width:100%;height:100%;border-radius:10px}
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
      <div style="color:var(--muted);font-size:0.95rem">Bollywood streaming — professional UI</div>
    </div>

    <div class="controls">
      <form method="get" action="/" class="search" style="display:flex;">
        <input class="searchbox" type="search" name="q" placeholder="Search songs or artist (e.g. arijit singh)" value="{{ q|default('') }}">
        <button class="btn" type="submit">Search</button>
      </form>

      <form method="post" action="/reset" style="margin-left:10px;">
        <input type="hidden" name="admin_key" value="">
        <button class="small admin-reset" title="Admin only (set ADMIN_KEY env var)">Reset</button>
      </form>
    </div>
  </div>

  <!-- sticky player -->
  <div style="margin-top:18px" class="card player">
    <div style="width:64px;height:64px;background:linear-gradient(135deg,var(--accent),#ff7a9a);border-radius:8px;display:flex;align-items:center;justify-content:center;font-weight:700">♪</div>
    <div class="play-info">
      <div class="play-title" id="now-title">Nothing playing</div>
      <div class="play-artist" id="now-artist">Search and play a song</div>
    </div>
    <div class="play-buttons">
      <button class="play-btn" id="play-pause">Play</button>
      <button class="play-btn" id="stop-btn">Stop</button>
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
      <!-- If we have a video_id (API mode), embed specific video; otherwise embed search list -->
      {% if r.video_id %}
      <div class="resp-iframe"><iframe id="iframe-{{ loop.index }}" src="https://www.youtube.com/embed/{{ r.video_id }}?enablejsapi=1&controls=0&modestbranding=1" frameborder="0" allow="autoplay; encrypted-media" ></iframe></div>
      <div style="display:flex;gap:8px;margin-top:10px;">
        <button class="small" onclick="playVideo('{{ r.video_id }}','{{ r.title|e }}','{{ r.artist|e }}')">Play on site</button>
        {% if r.download_key and r.download_key in downloadable %}
        <a class="small download-btn" href="{{ url_for('download_file', key=r.download_key) }}">Download</a>
        {% endif %}
        <a class="small" target="_blank" href="https://www.youtube.com/watch?v={{ r.video_id }}">Open on YouTube</a>
      </div>
      {% else %}
      <!-- embed search playlist -->
      <div class="resp-iframe"><iframe id="iframe-{{ loop.index }}" src="https://www.youtube.com/embed?listType=search&list={{ r.embed_query|urlencode }}&enablejsapi=1&controls=0&modestbranding=1" frameborder="0" allow="autoplay; encrypted-media"></iframe></div>
      <div style="display:flex;gap:8px;margin-top:10px;">
        <button class="small" onclick="playSearchList('{{ r.embed_query|e }}','{{ r.title|e }}')">Play results</button>
        <a class="small" target="_blank" href="https://www.youtube.com/results?search_query={{ r.embed_query|urlencode }}">Open on YouTube</a>
      </div>
      {% endif %}
    </div>
    {% endfor %}
  </div>
  {% elif q %}
  <div class="card" style="margin-top:18px">No results for "<strong>{{ q }}</strong>"</div>
  {% endif %}

  <div class="footer">Built with ❤️ — streams via YouTube (we do not provide downloads of copyrighted content)</div>
</div>

<!-- YouTube Player API + custom controller -->
<script src="https://www.youtube.com/iframe_api"></script>
<script>
let ytPlayer = null;
let currentVideoId = null;
function onYouTubeIframeAPIReady(){
  // nothing to do until user plays
}
function createPlayerFor(videoId){
  // if existing, load new video
  if(ytPlayer){
    ytPlayer.loadVideoById(videoId);
    return;
  }
  // create invisible iframe player element dynamically
  const div = document.createElement('div');
  div.style.display='none';
  div.id='yt-player-div';
  document.body.appendChild(div);
  ytPlayer = new YT.Player(div, {
    height: '0', width: '0',
    videoId: videoId,
    playerVars: { 'controls': 0, 'rel': 0, 'modestbranding':1 },
    events: {
      'onStateChange': onPlayerStateChange
    }
  });
}
function playVideo(videoId, title, artist){
  currentVideoId = videoId;
  document.getElementById('now-title').textContent = title || 'Playing';
  document.getElementById('now-artist').textContent = artist || '';
  if(!ytPlayer){
    createPlayerFor(videoId);
    // small delay to let YT player initialize then play
    setTimeout(()=>{ ytPlayer.playVideo(); document.getElementById('play-pause').textContent='Pause'; }, 800);
  } else {
    ytPlayer.loadVideoById(videoId);
    setTimeout(()=>{ ytPlayer.playVideo(); document.getElementById('play-pause').textContent='Pause'; }, 300);
  }
}
function playSearchList(query, title){
  // For search lists we open a hidden iframe playlist and play the first automatically
  const encoded = encodeURIComponent(query);
  // create or reuse an iframe
  let el = document.getElementById('hidden-search-iframe');
  if(el){ el.src = 'https://www.youtube.com/embed?listType=search&list='+encoded+'&enablejsapi=1&controls=0&modestbranding=1'; }
  else {
    el = document.createElement('iframe');
    el.id='hidden-search-iframe';
    el.style.display='none';
    el.src = 'https://www.youtube.com/embed?listType=search&list='+encoded+'&enablejsapi=1&controls=0&modestbranding=1';
    document.body.appendChild(el);
  }
  // when the iframe loads, create a YT player for it
  setTimeout(()=> {
    if(!ytPlayer){
      ytPlayer = new YT.Player('hidden-search-iframe', {
        events: {'onStateChange': onPlayerStateChange}
      });
    } else {
      // load via player (if it supports playlist load)
      try{ ytPlayer.loadPlaylist({listType:'search', list: query}); }catch(e){}
    }
    document.getElementById('now-title').textContent = title || query;
    document.getElementById('now-artist').textContent = '';
    document.getElementById('play-pause').textContent='Pause';
  }, 700);
}
function onPlayerStateChange(e){
  // update UI if needed
  if(e.data == YT.PlayerState.ENDED){
    document.getElementById('play-pause').textContent='Play';
  }
}
document.getElementById('play-pause').addEventListener('click', ()=>{
  if(!ytPlayer){ return; }
  const state = ytPlayer.getPlayerState();
  if(state === YT.PlayerState.PLAYING){ ytPlayer.pauseVideo(); document.getElementById('play-pause').textContent='Play'; }
  else { ytPlayer.playVideo(); document.getElementById('play-pause').textContent='Pause'; }
});
document.getElementById('stop-btn').addEventListener('click', ()=>{
  if(!ytPlayer) return;
  ytPlayer.stopVideo();
  document.getElementById('play-pause').textContent='Play';
  document.getElementById('now-title').textContent='Nothing playing';
  document.getElementById('now-artist').textContent='Search and play a song';
});
</script>
</body>
</html>
"""

# ---------- ROUTES ----------
@app.route("/", methods=["GET"])
def index():
    q = (request.args.get("q") or "").strip()
    results = []
    if q:
        # Prefer real API if key provided
        api_results = search_youtube_api(q, max_results=8)
        if api_results:
            # attach optional download keys if title matches DOWNLOADABLE_MAP keys fuzzy
            for r in api_results:
                # check if title contains any downloadable key
                download_key = None
                for k in DOWNLOADABLE_MAP.keys():
                    if k.lower() in (r['title'] or "").lower():
                        download_key = k
                        break
                results.append({
                    "video_id": r["video_id"],
                    "title": r["title"],
                    "artist": r.get("artist",""),
                    "download_key": download_key
                })
        else:
            # fallback: produce variant search results (no exact video_id)
            results = smart_fallback_results(q)
    return render_template_string(BASE_HTML, results=results, q=q, downloadable=DOWNLOADABLE_MAP)

@app.route("/download/<key>")
def download_file(key):
    # serve only files we've explicitly mapped in DOWNLOADABLE_MAP
    if key not in DOWNLOADABLE_MAP:
        abort(404)
    path = Path(DOWNLOADABLE_MAP[key])
    if not path.exists():
        abort(404)
    return send_from_directory(str(path.parent), path.name, as_attachment=True)

@app.route("/reset", methods=["POST"])
def reset_site():
    # Protect with ADMIN_KEY
    form_key = request.form.get("admin_key","")
    if ADMIN_KEY and form_key != ADMIN_KEY:
        # if ADMIN_KEY not set, allow after manual confirm? safer to require it
        # return 403
        abort(403, "Admin key required to reset site.")
    # Clear downloads directory
    for f in DOWNLOADS_DIR.glob("*"):
        try:
            f.unlink()
        except Exception:
            pass
    # Clear DOWNLOADABLE_MAP (in-memory)
    DOWNLOADABLE_MAP.clear()
    return redirect(url_for("index"))

# ---------- RUN ----------
if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 5000))
    print(f"Starting SongSite Pro on http://{host}:{port}")
    app.run(host=host, port=port, debug=True)
