import os
import sys
import re
import asyncio
import threading
import time
import json
import logging
import subprocess
import shutil
from datetime import datetime

# Dependency Check
REQUIRED_LIBS = ['customtkinter', 'yt_dlp', 'shazamio', 'aiohttp', 'pydub', 'imageio_ffmpeg']
for lib in REQUIRED_LIBS:
    try:
        __import__(lib.replace('-', '_'))
    except ImportError:
        print(f"[CRITICAL] Missing library: {lib}. Please install via pip.")

# Optional fuzzy matching
try:
    from fuzzywuzzy import fuzz
except ImportError:
    print("[WARN] fuzzywuzzy not found. Installing or falling back to exact match.")
    fuzz = None

import customtkinter as ctk
import aiohttp
from yt_dlp import YoutubeDL
from shazamio import Shazam
from pydub import AudioSegment
import imageio_ffmpeg

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# FFMPEG Setup
try:
    FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()
except:
    FFMPEG_PATH = shutil.which("ffmpeg") or "ffmpeg"

os.environ["PATH"] += os.pathsep + os.path.dirname(FFMPEG_PATH)
AudioSegment.converter = FFMPEG_PATH
AudioSegment.ffmpeg = FFMPEG_PATH
AudioSegment.ffprobe = FFMPEG_PATH

# Config
DIRS = {
    "TMP": "00_TEMP_STAGING",
    "MASTER": "01_ESTUDIO_MASTER",
    "REF": "02_ORIGINAIS_REFERENCIA"
}
for d in DIRS.values():
    os.makedirs(d, exist_ok=True)

class NetworkManager:
    async def fetch_json(self, url, payload=None, headers=None, method='POST'):
        try:
            async with aiohttp.ClientSession() as session:
                if method == 'POST':
                    # Ensure data and json are mutually exclusive based on headers (application/json)
                    if headers and 'application/json' in headers.get('Content-Type', ''):
                        async with session.post(url, json=payload, headers=headers) as resp:
                            return await resp.json()
                    else:
                        async with session.post(url, data=payload, headers=headers) as resp:
                            return await resp.json()
                else:
                    async with session.get(url) as resp:
                        return await resp.json()
        except Exception as e:
            logger.error(f"Network JSON Error ({url}): {e}")
        return None

    async def download_file(self, url, filepath):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        with open(filepath, 'wb') as f:
                            f.write(await resp.read())
                        return True
        except Exception as e:
            logger.error(f"Download Error: {e}")
        return False

class DownloadManager:
    def __init__(self, net_manager, log_callback):
        self.net = net_manager
        self.log = log_callback

    def _sanitize(self, name):
        return re.sub(r'[<>:"/\\|?*]', '', name).strip()

    async def download_tiktok_chain(self, url):
        """
        Chain: TikWM -> Cobalt -> yt-dlp
        Returns: (filepath, metadata_dict)
        """
        # 1. TikWM
        self.log("Provider: TikWM...")
        res = await self._try_tikwm(url)
        if res: return res

        # 2. Cobalt
        self.log("Provider: Cobalt...")
        res = await self._try_cobalt(url)
        if res: return res

        # 3. Native
        self.log("Provider: Native (yt-dlp)...")
        return await asyncio.to_thread(self._try_ytdlp, url)

    async def _try_tikwm(self, url):
        data = await self.net.fetch_json("https://www.tikwm.com/api/", payload={'url': url})
        if data and data.get('code') == 0:
            d = data.get('data', {})
            # Metadata
            meta = {
                'title': d.get('title'),
                'author': d.get('author', {}).get('nickname'),
                'music_title': d.get('music_info', {}).get('title'),
                'music_author': d.get('music_info', {}).get('author'),
                'source': 'TikWM'
            }
            # URL (Audio preferred if slideshow)
            dl_url = d.get('play')
            ext = 'mp4'
            if 'images' in d and d['images']:
                dl_url = d.get('music')
                ext = 'mp3'

            if dl_url:
                fname = f"{DIRS['REF']}/{self._sanitize(meta['title'] or 'tiktok')}.{ext}"
                if await self.net.download_file(dl_url, fname):
                    return fname, meta
        return None

    async def _try_cobalt(self, url):
        headers = {'Accept': 'application/json', 'Content-Type': 'application/json'}
        payload = {"url": url, "vCodec": "h264", "aFormat": "mp3", "filenamePattern": "basic"}
        data = await self.net.fetch_json("https://api.cobalt.tools/api/json", payload=payload, headers=headers)

        if data and 'url' in data:
            dl_url = data['url']
            # Cobalt meta is weak, try to guess or leave empty
            meta = {'title': 'Cobalt Download', 'source': 'Cobalt'}
            fname = f"{DIRS['REF']}/cobalt_{int(time.time())}.mp4"
            if await self.net.download_file(dl_url, fname):
                return fname, meta
        return None

    def _try_ytdlp(self, url):
        opts = {
            'outtmpl': f'{DIRS["REF"]}/%(title)s.%(ext)s',
            'format': 'bestaudio/best',
            'noplaylist': True,
            'quiet': True,
            'nocheckcertificate': True,
            'ignoreerrors': True,
            'ffmpeg_location': FFMPEG_PATH,
            'user_agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/93.0.4577.82 Mobile Safari/537.36',
            'extractor_args': {'tiktok': {'app_version': '30.0.0', 'os': 'android'}}
        }
        try:
            with YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                if info:
                    fn = ydl.prepare_filename(info)
                    meta = {'title': info.get('title'), 'author': info.get('uploader'), 'source': 'yt-dlp'}

                    base, _ = os.path.splitext(fn)
                    if os.path.exists(fn): return fn, meta
                    if os.path.exists(f"{base}.mp3"): return f"{base}.mp3", meta
        except Exception as e:
            self.log(f"yt-dlp Error: {e}")
        return None

    def search_master(self, query):
        opts = {
            'outtmpl': f'{DIRS["MASTER"]}/%(title)s.%(ext)s',
            'format': 'bestaudio/best',
            'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '320'}],
            'noplaylist': True,
            'quiet': True,
            'ffmpeg_location': FFMPEG_PATH,
            'default_search': 'ytsearch5'
        }
        try:
            with YoutubeDL(opts) as ydl:
                res = ydl.extract_info(query, download=False)
                if not res: return None

                for entry in res.get('entries', []):
                    dur = entry.get('duration', 0)
                    if 120 <= dur <= 600:
                        opts['default_search'] = 'auto'
                        with YoutubeDL(opts) as yd:
                            inf = yd.extract_info(entry['webpage_url'], download=True)
                            fn = yd.prepare_filename(inf)
                            base, _ = os.path.splitext(fn)
                            return f"{base}.mp3", entry['webpage_url']
        except Exception: pass
        return None

class IdentificationEngine:
    async def triangulate(self, file_path, api_meta):
        """
        Step A: Shazam
        Step B: API Meta
        Step C: Compare
        """
        # A. Shazam
        shazam_res = None
        try:
            shazam = Shazam()
            out = await shazam.recognize(file_path)
            track = out.get('track', {})
            if track.get('title') and track.get('subtitle'):
                shazam_res = f"{track['subtitle']} - {track['title']}"
        except: pass

        # B. API Meta
        api_res = None
        if api_meta:
            # Prefer music info if available
            t = api_meta.get('music_title') or api_meta.get('title')
            a = api_meta.get('music_author') or api_meta.get('author')
            if t and a:
                api_res = f"{a} - {t}"
            elif t:
                api_res = t

        # C. Compare
        final_ident = None
        status_label = "UNKNOWN"
        status_color = "gray"

        if shazam_res and api_res:
            ratio = 0
            if fuzz:
                ratio = fuzz.ratio(shazam_res.lower(), api_res.lower())
            else:
                ratio = 100 if shazam_res.lower() in api_res.lower() else 0

            if ratio > 80:
                final_ident = shazam_res
                status_label = "CONFIRMED MATCH ✅"
                status_color = "#2ECC71" # Green
            else:
                final_ident = shazam_res # Default to Shazam but warn
                status_label = f"CONFLICT ⚠️\nS: {shazam_res}\nT: {api_res}"
                status_color = "#F1C40F" # Yellow

        elif shazam_res:
            final_ident = shazam_res
            status_label = "SINGLE SOURCE (SHAZAM) 🔹"
            status_color = "#3498DB" # Blue

        elif api_res:
            final_ident = api_res
            status_label = "SINGLE SOURCE (TIKTOK) 🔸"
            status_color = "#E67E22" # Orange

        else:
            # Fallback to filename
            base = os.path.basename(file_path)
            final_ident = os.path.splitext(base)[0]
            status_label = "FILENAME FALLBACK 🔻"
            status_color = "white"

        # Cleanup
        final_ident = self._clean_string(final_ident)
        return final_ident, status_label, status_color

    def _clean_string(self, text):
        # Remove hashtags, mentions, brackets
        text = re.sub(r'[#@]\w+', '', text)
        text = re.sub(r'[\[\(].*?[\]\)]', '', text)
        return " ".join(text.split())

class MinerApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("AUDIO-PRO-MINER v3.2 - Triangulation Core")
        self.geometry("1400x900")
        ctk.set_appearance_mode("Dark")

        self.net = NetworkManager()
        self.dl = DownloadManager(self.net, self.log)
        self.id_engine = IdentificationEngine()

        self.items = []
        self.loop = asyncio.new_event_loop()
        threading.Thread(target=self._start_loop, daemon=True).start()

        self.setup_ui()

    def _start_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def log(self, msg):
        print(msg)

    def setup_ui(self):
        # Top Bar
        top = ctk.CTkFrame(self, height=60, corner_radius=0)
        top.pack(fill="x")

        ctk.CTkLabel(top, text="AUDIO MINER v3.2", font=("Arial", 20, "bold")).pack(side="left", padx=20, pady=10)

        ctk.CTkButton(top, text="IMPORT .TXT", width=120, command=self.import_file).pack(side="right", padx=10, pady=10)
        ctk.CTkButton(top, text="START QUEUE", width=120, fg_color="#D35400", command=self.start_queue).pack(side="right", padx=10, pady=10)

        # Scroll
        self.scroll = ctk.CTkScrollableFrame(self, fg_color="#1a1a1a")
        self.scroll.pack(fill="both", expand=True, padx=10, pady=10)

    def import_file(self):
        path = ctk.filedialog.askopenfilename(filetypes=[("Text", "*.txt")])
        if not path: return

        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        regex = r'https?://(?:vm\.tiktok\.com|www\.tiktok\.com|tiktok\.com|youtu\.be|youtube\.com|www\.youtube\.com|instagram\.com|www\.instagram\.com)[^\s]+'
        links = set(re.findall(regex, content))

        for url in links:
            self.create_card(url.strip('.,!?:;"\')]}'))

    def create_card(self, url):
        idx = len(self.items)
        item = {'id': idx, 'url': url, 'status': 'Pending', 'ui': {}}

        # CARD FRAME
        card = ctk.CTkFrame(self.scroll, height=80, corner_radius=10, fg_color="#2b2b2b")
        card.pack(fill="x", pady=5)

        # Left: Icon + Link
        left = ctk.CTkFrame(card, fg_color="transparent", width=400)
        left.pack(side="left", fill="y", padx=10)
        ctk.CTkLabel(left, text="🎵", font=("Arial", 24)).pack(side="left", padx=5)
        ctk.CTkLabel(left, text=url, font=("Arial", 12), text_color="gray", anchor="w").pack(side="left", padx=5)

        # Center: Truth Table
        center = ctk.CTkFrame(card, fg_color="transparent")
        center.pack(side="left", fill="both", expand=True, padx=10)
        l_status = ctk.CTkLabel(center, text="WAITING FOR QUEUE...", font=("Arial", 14, "bold"), text_color="gray")
        l_status.pack(expand=True)

        # Right: Actions
        right = ctk.CTkFrame(card, fg_color="transparent", width=300)
        right.pack(side="right", fill="y", padx=10)

        item['ui'] = {'card': card, 'status': l_status, 'actions': right}
        self.items.append(item)

    def start_queue(self):
        threading.Thread(target=self._run_queue, daemon=True).start()

    def _run_queue(self):
        for item in self.items:
            if item['status'] == 'Pending':
                asyncio.run_coroutine_threadsafe(self.process_item(item), self.loop).result()

    async def process_item(self, item):
        ui = item['ui']

        # 1. Download
        self.update_label(ui['status'], "DOWNLOADING REF...", "#3498DB")
        ref_path, meta = await self.dl.download_tiktok_chain(item['url'])

        if not ref_path:
            self.update_label(ui['status'], "DOWNLOAD FAILED ❌", "#C0392B")
            return

        # Add Play Ref
        self.add_btn(ui['actions'], "▶ ORIG", "#34495E", lambda: self.open_file(ref_path))

        # 2. Identify (Triangulation)
        self.update_label(ui['status'], "TRIANGULATING ID...", "#E67E22")
        ident_name, status_txt, status_col = await self.id_engine.triangulate(ref_path, meta)
        self.update_label(ui['status'], f"{status_txt}\n{ident_name}", status_col)

        # 3. Master
        m_path, m_url = await asyncio.to_thread(self.dl.search_master, f"{ident_name} official audio")
        if m_path:
            self.add_btn(ui['actions'], "▶ MASTER", "#27AE60", lambda: self.open_file(m_path))
            self.add_btn(ui['actions'], "🔍 GO", "#8E44AD", lambda: self.open_url(m_url))
        else:
            self.add_btn(ui['actions'], "NO MASTER", "gray", None)

    def update_label(self, lbl, text, color):
        self.after(0, lambda: lbl.configure(text=text, text_color=color))

    def add_btn(self, parent, text, color, cmd):
        self.after(0, lambda: ctk.CTkButton(parent, text=text, width=120, height=32, fg_color=color, command=cmd).pack(side="right", padx=5, pady=24))

    def open_file(self, path):
        if sys.platform == 'linux': subprocess.run(['xdg-open', path])
        elif sys.platform == 'win32': os.startfile(path)

    def open_url(self, url):
        import webbrowser
        webbrowser.open(url)

if __name__ == "__main__":
    app = MinerApp()
    app.mainloop()
