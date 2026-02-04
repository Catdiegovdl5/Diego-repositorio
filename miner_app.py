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
REQUIRED_LIBS = ['customtkinter', 'yt_dlp', 'shazamio', 'aiohttp', 'pydub', 'imageio_ffmpeg', 'acoustid', 'fuzzywuzzy']
for lib in REQUIRED_LIBS:
    try:
        __import__(lib.replace('-', '_').replace('python_', ''))
    except ImportError:
        print(f"[CRITICAL] Missing library: {lib}. Please install via pip.")

import customtkinter as ctk
import aiohttp
from yt_dlp import YoutubeDL
from shazamio import Shazam
from pydub import AudioSegment
import imageio_ffmpeg
import acoustid
from fuzzywuzzy import fuzz

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
ACOUSTID_API_KEY = "zTwwSElBrO"
ROOT_DIR = "04_BENCHMARK_LAB"
os.makedirs(ROOT_DIR, exist_ok=True)
os.makedirs("00_TEMP", exist_ok=True)

class SmartCleaner:
    @staticmethod
    def clean(text):
        if not text: return None
        text = re.sub(r'#\w+', '', text)
        text = re.sub(r'@\w+', '', text)
        text = re.sub(r'\[.*?\]', '', text)
        text = re.sub(r'\(.*?\)', '', text)
        text = re.sub(r'[^\w\s,.\'-]', '', text, flags=re.UNICODE)
        return " ".join(text.split()).strip()

    @staticmethod
    def sanitize(name):
        return re.sub(r'[<>:"/\\|?*]', '', name).strip()

class AudioSanitizer:
    @staticmethod
    def sanitize(input_path):
        """
        Converts to RAW WAV (PCM s16le) to strip all corrupt metadata.
        Command: ffmpeg -y -i "{input_path}" -vn -acodec pcm_s16le -ar 44100 -ac 1 -map_metadata -1 "{out}"
        """
        try:
            base = os.path.basename(input_path)
            name, _ = os.path.splitext(base)
            out_path = f"00_TEMP/clean_{name}_{int(time.time())}.wav"

            cmd = [
                FFMPEG_PATH, '-y',
                '-i', input_path,
                '-vn',
                '-acodec', 'pcm_s16le', # Raw PCM 16-bit
                '-ar', '44100',
                '-ac', '1',
                '-map_metadata', '-1',  # Kill tags
                out_path
            ]

            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

            if os.path.exists(out_path):
                return out_path
        except Exception as e:
            logger.error(f"Audio Sanitizer Error: {e}")
        return None

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
                        async with session.post(url, json=payload) as resp: return await resp.json()
                    else:
                        async with session.post(url, data=payload) as resp: return await resp.json()
                else:
                    async with session.get(url) as resp: return await resp.json()
        except Exception: return None

    async def download_file(self, url, filepath):
        try:
            async with aiohttp.ClientSession(headers=self.headers, timeout=self.timeout) as session:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        with open(filepath, 'wb') as f:
                            f.write(await resp.read())
                        return True
        except Exception: return False

class DownloadManager:
    def __init__(self, net):
        self.net = net

    async def download_ref(self, url):
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
            # Extract Meta (Source A)
            t = d.get('music_info', {}).get('title') or d.get('title')
            a = d.get('music_info', {}).get('author') or d.get('author', {}).get('nickname')
            meta_str = f"{a} - {t}" if a and t else (t or "Unknown")

            dl_url = d.get('play')
            ext = 'mp4'
            if ('images' in d and d['images']) or not dl_url:
                dl_url = d.get('music')
                ext = 'mp3'

            if dl_url:
                path = f"00_TEMP/ref_{int(time.time())}.{ext}"
                if await self.net.download_file(dl_url, path):
                    return path, SmartCleaner.clean(meta_str)
        return None

    async def _try_cobalt(self, url):
        pl = {"url": url, "vCodec": "h264", "aFormat": "mp3", "filenamePattern": "basic"}
        hd = {'Accept': 'application/json', 'Content-Type': 'application/json'}
        data = await self.net.fetch_json("https://api.cobalt.tools/api/json", payload=pl, headers=hd)
        if data and 'url' in data:
            path = f"00_TEMP/cobalt_{int(time.time())}.mp4"
            if await self.net.download_file(data['url'], path):
                return path, None
        return None

    def _try_ytdlp(self, url):
        opts = {
            'outtmpl': '00_TEMP/ref_%(id)s.%(ext)s', 'format': 'bestaudio/best',
            'noplaylist': True, 'quiet': True, 'no_warnings': True,
            'nocheckcertificate': True, 'ignoreerrors': True, 'ffmpeg_location': FFMPEG_PATH,
            'extractor_args': {'tiktok': {'app_version': '30.0.0', 'os': 'android'}}
        }
        try:
            with YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                if info:
                    fn = ydl.prepare_filename(info)
                    meta = f"{info.get('uploader')} - {info.get('title')}"
                    base, _ = os.path.splitext(fn)
                    if os.path.exists(fn): return fn, SmartCleaner.clean(meta)
                    if os.path.exists(f"{base}.mp3"): return f"{base}.mp3", SmartCleaner.clean(meta)
        except: pass
        return None

    def download_master(self, query, output_dir):
        opts = {
            'outtmpl': f'{output_dir}/master.%(ext)s',
            'format': 'bestaudio/best',
            'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '320'}],
            'noplaylist': True, 'quiet': True, 'no_warnings': True, 'nocheckcertificate': True,
            'ffmpeg_location': FFMPEG_PATH, 'default_search': 'ytsearch5'
        }
        try:
            with YoutubeDL(opts) as ydl:
                res = ydl.extract_info(query, download=False)
                if res:
                    for entry in res.get('entries', []):
                        if 120 <= entry.get('duration', 0) <= 600:
                            opts['default_search'] = 'auto'
                            with YoutubeDL(opts) as yd:
                                yd.download([entry['webpage_url']])
                            return True
        except: pass
        return False

class TriangulationEngine:
    async def run(self, raw_path, meta_a):
        # 1. Sanitize to Clean WAV
        file_path = AudioSanitizer.sanitize(raw_path)
        if not file_path:
            logger.error("Audio Sanitization Failed. Using Raw.")
            file_path = raw_path

        # A. Meta
        res_a = meta_a or "No Result"

        # B. Shazam (Use Clean WAV)
        res_b = "No Result"
        try:
            shazam = Shazam()
            out = await shazam.recognize(file_path)
            track = out.get('track', {})
            if track.get('title'):
                res_b = SmartCleaner.clean(f"{track['subtitle']} - {track['title']}")
        except: pass

        # C. AcoustID (Use Clean WAV)
        res_c = "No Result"
        try:
            for score, rid, title, artist in acoustid.match(ACOUSTID_API_KEY, file_path):
                if title:
                    res_c = SmartCleaner.clean(f"{artist} - {title}")
                    break
        except acoustid.WebServiceError:
            logger.warning("⚠️ API Refused Key/Data")
        except Exception as e:
            logger.warning(f"⚠️ Fingerprint Failed: {e}")

        # Cleanup clean WAV
        if file_path != raw_path and os.path.exists(file_path):
            try: os.remove(file_path)
            except: pass

        # Verdict
        candidates = [c for c in [res_a, res_b, res_c] if c != "No Result"]
        if not candidates:
            return res_a, res_b, res_c, "CONFLICT 🔴", f"Unknown_{int(time.time())}"

        verdict = "CONFLICT 🔴"
        winner = candidates[0]

        if len(candidates) >= 2:
            match_ab = fuzz.token_set_ratio(res_a, res_b) > 80 if res_a!="No Result" and res_b!="No Result" else False
            match_ac = fuzz.token_set_ratio(res_a, res_c) > 80 if res_a!="No Result" and res_c!="No Result" else False
            match_bc = fuzz.token_set_ratio(res_b, res_c) > 80 if res_b!="No Result" and res_c!="No Result" else False

            if match_ab and match_ac: # All 3
                verdict = "PLATINUM MATCH 💎"
                winner = res_b
            elif match_ab or match_ac or match_bc:
                verdict = "GOLD MATCH 🥇"
                if match_bc: winner = res_b
                elif match_ab: winner = res_b
                elif match_ac: winner = res_c

        return res_a, res_b, res_c, verdict, winner

class BatchProcessor:
    def __init__(self, update_cb):
        self.net = NetworkManager()
        self.dl = DownloadManager(self.net)
        self.tri = TriangulationEngine()
        self.update = update_cb

    async def process(self, urls):
        total = len(urls)
        for i, url in enumerate(urls):
            self.update(f"Processing {i+1}/{total}...", (i+1)/total)

            try:
                # 1. Download
                ref_path, meta_a = await self.dl.download_ref(url)
                if not ref_path:
                    self._log_fail(url, "Download Failed")
                    continue

                # 2. Triangulate
                ra, rb, rc, verdict, winner = await self.tri.run(ref_path, meta_a)

                # 3. Organize
                safe_name = SmartCleaner.sanitize(winner)
                folder_name = f"{i+1:03d}_{safe_name}"
                target_dir = os.path.join(ROOT_DIR, folder_name)
                os.makedirs(target_dir, exist_ok=True)

                # Move Ref
                ref_ext = os.path.splitext(ref_path)[1]
                shutil.move(ref_path, os.path.join(target_dir, f"reference{ref_ext}"))

                # Download Master
                if verdict != "CONFLICT 🔴" and "Unknown" not in winner:
                    self.dl.download_master(f"{winner} official audio", target_dir)

                # Report
                with open(os.path.join(target_dir, "VS_REPORT.txt"), "w") as f:
                    f.write("--- FORENSIC ANALYSIS REPORT ---\n")
                    f.write(f"🎵 TIKTOK META:  {ra}\n")
                    f.write(f"🌀 SHAZAM API:   {rb}\n")
                    f.write(f"🧬 ACOUSTID DB:  {rc}\n")
                    f.write("--------------------------------\n")
                    f.write(f"🏆 VERDICT: {verdict}\n")
                    f.write(f"📝 FINAL NAME USED: {winner}\n")
                    f.write(f"🔗 URL: {url}\n")

                self.update(f"{verdict} : {winner}", (i+1)/total)

            except Exception as e:
                self._log_fail(url, str(e))

        self.update("Analysis Complete.", 1.0)

    def _log_fail(self, url, err):
        with open("error_log.txt", "a") as f:
            f.write(f"{url} | {err}\n")

class MinerApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("AUDIO-PRO-MINER v5.3 - WAV Sanitizer")
        self.geometry("800x600")
        ctk.set_appearance_mode("Dark")

        self.proc = BatchProcessor(self.on_update)
        self.loop = asyncio.new_event_loop()
        threading.Thread(target=self._run_loop, daemon=True).start()

        self.setup_ui()

    def _run_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def setup_ui(self):
        f = ctk.CTkFrame(self)
        f.pack(expand=True, fill="both", padx=20, pady=20)
        ctk.CTkLabel(f, text="FORENSIC LAB v5.3", font=("Arial", 24, "bold")).pack(pady=20)

        self.btn_imp = ctk.CTkButton(f, text="📂 IMPORT & START", height=50, command=self.start)
        self.btn_imp.pack(fill="x", padx=50)

        self.prog = ctk.CTkProgressBar(f)
        self.prog.pack(fill="x", padx=50, pady=20)
        self.prog.set(0)

        self.log = ctk.CTkTextbox(f)
        self.log.pack(fill="both", expand=True, padx=50, pady=10)

    def start(self):
        path = ctk.filedialog.askopenfilename()
        if path:
            with open(path, 'r') as f: urls = list(set(re.findall(r'https?://[^\s]+', f.read())))
            self.btn_imp.configure(state="disabled", text="PROCESSING...")
            asyncio.run_coroutine_threadsafe(self.proc.process(urls), self.loop)

    def on_update(self, msg, val):
        self.after(0, lambda: self._up(msg, val))

    def _up(self, msg, val):
        self.prog.set(val)
        self.log.insert("0.0", f"[{datetime.now().strftime('%H:%M:%S')}] {msg}\n")
        self.update_idletasks()
        if val >= 1.0:
            self.btn_imp.configure(text="DONE", fg_color="green")
            ctk.CTkInputDialog(text="Job Done.", title="Info")

if __name__ == "__main__":
    app = MinerApp()
    app.mainloop()
