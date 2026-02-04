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
    "TEMP": "00_TEMP_STAGING",
    "CONFIRMED": "01_CONFIRMED",
    "UNCERTAIN": "02_UNCERTAIN",
    "UNIDENTIFIED": "03_UNIDENTIFIED"
}
for d in DIRS.values():
    os.makedirs(d, exist_ok=True)

class SmartCleaner:
    @staticmethod
    def clean_title(text):
        if not text: return "Unknown Track"
        text = re.sub(r'#\w+', '', text)
        text = re.sub(r'@\w+', '', text)
        text = re.sub(r'\[.*?\]', '', text)
        text = re.sub(r'\(.*?\)', '', text)
        text = re.sub(r'[^\w\s,.\'-]', '', text, flags=re.UNICODE)
        return " ".join(text.split())

    @staticmethod
    def sanitize_filename(name):
        return re.sub(r'[<>:"/\\|?*]', '', name).strip()

class NetworkManager:
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept-Encoding": "identity"
        }
        self.timeout = aiohttp.ClientTimeout(total=20)

    async def fetch_json(self, url, payload=None, headers=None, method='POST'):
        req_headers = self.headers.copy()
        if headers: req_headers.update(headers)

        try:
            async with aiohttp.ClientSession(headers=req_headers, timeout=self.timeout) as session:
                if method == 'POST':
                    if req_headers.get('Content-Type') == 'application/json':
                        async with session.post(url, json=payload) as resp:
                            return await resp.json()
                    else:
                        async with session.post(url, data=payload) as resp:
                            return await resp.json()
                else:
                    async with session.get(url) as resp:
                        return await resp.json()
        except Exception as e:
            logger.error(f"Network JSON Error ({url}): {e}")
        return None

    async def download_file(self, url, filepath):
        try:
            async with aiohttp.ClientSession(headers=self.headers, timeout=self.timeout) as session:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        with open(filepath, 'wb') as f:
                            f.write(await resp.read())
                        return True
        except Exception as e:
            logger.error(f"Download Error: {e}")
        return False

class DownloadManager:
    def __init__(self, net_manager):
        self.net = net_manager

    async def download_reference(self, url):
        """Chain: TikWM -> Cobalt -> yt-dlp. Returns: (path, meta)"""
        # 1. TikWM
        res = await self._try_tikwm(url)
        if res: return res

        # 2. Cobalt
        res = await self._try_cobalt(url)
        if res: return res

        # 3. Native
        res = await asyncio.to_thread(self._try_ytdlp, url)
        if res: return res

        return None, None

    async def _try_tikwm(self, url):
        data = await self.net.fetch_json("https://www.tikwm.com/api/", payload={'url': url})
        if data and data.get('code') == 0:
            d = data.get('data', {})
            meta = {
                'title': d.get('title'),
                'author': d.get('author', {}).get('nickname'),
                'music_title': d.get('music_info', {}).get('title'),
                'music_author': d.get('music_info', {}).get('author'),
                'source': 'TikWM'
            }

            dl_url = d.get('play')
            ext = 'mp4'
            if ('images' in d and d['images']) or not dl_url:
                dl_url = d.get('music')
                ext = 'mp3'

            if dl_url:
                fname = f"{DIRS['TEMP']}/ref_{int(time.time())}.{ext}"
                if await self.net.download_file(dl_url, fname):
                    return fname, meta
        return None

    async def _try_cobalt(self, url):
        headers = {'Accept': 'application/json', 'Content-Type': 'application/json'}
        payload = {"url": url, "vCodec": "h264", "aFormat": "mp3", "filenamePattern": "basic"}
        data = await self.net.fetch_json("https://api.cobalt.tools/api/json", payload=payload, headers=headers)

        if data and 'url' in data:
            dl_url = data['url']
            meta = {'title': 'Cobalt', 'source': 'Cobalt'}
            fname = f"{DIRS['TEMP']}/cobalt_{int(time.time())}.mp4"
            if await self.net.download_file(dl_url, fname):
                return fname, meta
        return None

    def _try_ytdlp(self, url):
        opts = {
            'outtmpl': f'{DIRS["TEMP"]}/ref_%(id)s.%(ext)s',
            'format': 'bestaudio/best',
            'noplaylist': True,
            'quiet': True,
            'nocheckcertificate': True,
            'ignoreerrors': True,
            'ffmpeg_location': FFMPEG_PATH,
            'extractor_args': {'tiktok': {'app_version': '30.0.0', 'os': 'android'}}
        }
        try:
            with YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                if info:
                    fn = ydl.prepare_filename(info)
                    meta = {'title': info.get('title'), 'author': info.get('uploader'), 'source': 'yt-dlp'}
                    # Fix ext check
                    base, _ = os.path.splitext(fn)
                    if os.path.exists(fn): return fn, meta
                    if os.path.exists(f"{base}.mp3"): return f"{base}.mp3", meta
        except Exception: pass
        return None

    def search_master(self, query):
        opts = {
            'outtmpl': f'{DIRS["TEMP"]}/master_%(id)s.%(ext)s',
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
                            return f"{base}.mp3"
        except Exception: pass
        return None

class IdentificationEngine:
    async def triangulate(self, file_path, api_meta):
        # A. Shazam
        shazam_res = None
        try:
            shazam = Shazam()
            out = await shazam.recognize(file_path)
            track = out.get('track', {})
            if track.get('title'):
                shazam_res = f"{track['subtitle']} - {track['title']}"
        except: pass

        # B. API Meta
        api_res = None
        if api_meta:
            t = api_meta.get('music_title') or api_meta.get('title')
            a = api_meta.get('music_author') or api_meta.get('author')
            if t: api_res = f"{a} - {t}" if a else t

        # C. Compare
        final_match = None
        status = "UNIDENTIFIED"
        score = 0

        if shazam_res and api_res:
            score = fuzz.ratio(shazam_res.lower(), api_res.lower()) if fuzz else (100 if shazam_res == api_res else 0)
            if score > 80:
                final_match = shazam_res
                status = "CONFIRMED"
            else:
                final_match = shazam_res
                status = "UNCERTAIN" # Conflict
        elif shazam_res:
            final_match = shazam_res
            status = "UNCERTAIN" # Single source is technically uncertain compared to dual confirmation?
                                   # Prompt says: "Score < 80% (but distinct results): Conflict -> UNCERTAIN".
                                   # If only one exists, let's treat as UNCERTAIN or CONFIRMED?
                                   # Usually Single Source Shazam is pretty good. But for "Forensic", maybe Uncertain?
                                   # Let's trust Shazam as Confirmed if high confidence, but without score, let's say Uncertain
                                   # to be safe, OR Confirmed.
                                   # Prompt: "Score < 80% (but distinct results): Conflict".
                                   # Prompt: "No result: Failure".
                                   # Let's map Single Source to UNCERTAIN to force manual review, safer.
            status = "UNCERTAIN"
        elif api_res:
            final_match = api_res
            status = "UNCERTAIN"
        else:
            status = "UNIDENTIFIED"

        # Clean
        if final_match:
            final_match = SmartCleaner.clean_title(final_match)

        return final_match, status, score, shazam_res, api_res

class BatchProcessor:
    def __init__(self, update_cb):
        self.net = NetworkManager()
        self.dl = DownloadManager(self.net)
        self.id = IdentificationEngine()
        self.update = update_cb
        self.running = False

    async def process_batch(self, urls):
        self.running = True
        total = len(urls)

        for i, url in enumerate(urls):
            if not self.running: break

            self.update(f"Processing {i+1}/{total}...", (i+1)/total)

            try:
                # 1. Download Ref
                ref_path, meta = await self.dl.download_reference(url)
                if not ref_path:
                    self._log_error(url, "Download Failed")
                    continue

                # 2. Identify
                name, status, score, s_res, a_res = await self.id.triangulate(ref_path, meta)

                # 3. Organize Folder
                target_root = DIRS.get(status, DIRS['UNIDENTIFIED'])
                folder_name = SmartCleaner.sanitize_filename(name if name else f"Unknown_{int(time.time())}")
                song_dir = os.path.join(target_root, folder_name)
                os.makedirs(song_dir, exist_ok=True)

                # Move Ref
                ref_ext = os.path.splitext(ref_path)[1]
                final_ref = os.path.join(song_dir, f"reference_clip{ref_ext}")
                shutil.move(ref_path, final_ref)

                # 4. Master
                master_status = "Skipped"
                if name and status != "UNIDENTIFIED":
                    m_path = await asyncio.to_thread(self.dl.search_master, f"{name} official audio")
                    if m_path:
                        final_master = os.path.join(song_dir, "master_audio.mp3")
                        shutil.move(m_path, final_master)
                        master_status = "Downloaded"
                    else:
                        master_status = "Not Found"

                # 5. Report
                with open(os.path.join(song_dir, "report.txt"), "w") as f:
                    f.write(f"URL: {url}\n")
                    f.write(f"Status: {status}\n")
                    f.write(f"Score: {score}\n")
                    f.write(f"Shazam: {s_res}\n")
                    f.write(f"API: {a_res}\n")
                    f.write(f"Final Name: {name}\n")
                    f.write(f"Master: {master_status}\n")

                self.update(f"✅ {status}: {name}", (i+1)/total)

            except Exception as e:
                self._log_error(url, str(e))

        self.update("Process Complete.", 1.0)
        self.running = False

    def _log_error(self, url, err):
        with open("error_log.txt", "a") as f:
            f.write(f"{datetime.now()} - {url} - {err}\n")

class MinerApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("AUDIO-PRO-MINER v4.0 - Forensic Organizer")
        self.geometry("800x600")
        ctk.set_appearance_mode("Dark")

        self.processor = BatchProcessor(self.on_update)
        self.urls = []
        self.loop = asyncio.new_event_loop()
        threading.Thread(target=self._start_loop, daemon=True).start()

        self.setup_ui()

    def _start_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def setup_ui(self):
        # Frame
        f = ctk.CTkFrame(self)
        f.pack(expand=True, fill="both", padx=20, pady=20)

        ctk.CTkLabel(f, text="FORENSIC BATCH PROCESSOR", font=("Arial", 20, "bold")).pack(pady=20)

        self.btn_import = ctk.CTkButton(f, text="📂 IMPORT .TXT", command=self.import_file, height=50)
        self.btn_import.pack(fill="x", padx=50, pady=10)

        self.lbl_count = ctk.CTkLabel(f, text="0 links loaded")
        self.lbl_count.pack(pady=5)

        self.btn_start = ctk.CTkButton(f, text="▶ START FORENSIC PROCESS", command=self.start, height=50, fg_color="#D35400", state="disabled")
        self.btn_start.pack(fill="x", padx=50, pady=10)

        self.progress = ctk.CTkProgressBar(f)
        self.progress.pack(fill="x", padx=50, pady=20)
        self.progress.set(0)

        self.log_box = ctk.CTkTextbox(f, height=200)
        self.log_box.pack(fill="x", padx=50, pady=10)

    def import_file(self):
        path = ctk.filedialog.askopenfilename(filetypes=[("Text", "*.txt")])
        if path:
            with open(path, 'r', encoding='utf-8', errors='ignore') as f: content = f.read()
            regex = r'https?://(?:vm\.tiktok\.com|www\.tiktok\.com|tiktok\.com|youtu\.be|youtube\.com|www\.youtube\.com|instagram\.com|www\.instagram\.com)[^\s]+'
            self.urls = list(set(re.findall(regex, content)))
            self.lbl_count.configure(text=f"{len(self.urls)} links loaded")
            if self.urls: self.btn_start.configure(state="normal")

    def start(self):
        self.btn_start.configure(state="disabled", text="RUNNING...")
        self.btn_import.configure(state="disabled")
        asyncio.run_coroutine_threadsafe(self.processor.process_batch(self.urls), self.loop)

    def on_update(self, msg, progress):
        self.after(0, lambda: self._update_ui(msg, progress))

    def _update_ui(self, msg, progress):
        self.progress.set(progress)
        self.log_box.insert("0.0", f"[{datetime.now().strftime('%H:%M:%S')}] {msg}\n")
        if progress >= 1.0:
            self.btn_start.configure(text="FINISHED", fg_color="green")
            ctk.CTkInputDialog(text="Process Complete.\nCheck folders.", title="Done")

if __name__ == "__main__":
    app = MinerApp()
    app.mainloop()
