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
    "TMP": "00_TEMP_STAGING",
    "MASTER": "01_ESTUDIO_MASTER",
    "REF": "02_ORIGINAIS_REFERENCIA"
}
for d in DIRS.values():
    os.makedirs(d, exist_ok=True)

class NetworkManager:
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept-Encoding": "identity" # Fix for 'br' decompression error
        }

    async def fetch_json(self, url, payload=None, headers=None, method='POST'):
        req_headers = self.headers.copy()
        if headers: req_headers.update(headers)

        try:
            async with aiohttp.ClientSession(headers=req_headers) as session:
                if method == 'POST':
                    # Ensure correct payload type
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
            async with aiohttp.ClientSession(headers=self.headers) as session:
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
        Returns: (filepath, metadata_dict) OR None
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
        res = await asyncio.to_thread(self._try_ytdlp, url)
        if res: return res

        return None

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

            # Smart URL Selection (Video vs Slideshow Audio)
            dl_url = d.get('play')
            ext = 'mp4'

            # If slideshow or explicit music request or missing video URL
            if ('images' in d and d['images']) or not dl_url:
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
        status = "UNKNOWN"
        match_score = 0

        if shazam_res and api_res:
            ratio = fuzz.ratio(shazam_res.lower(), api_res.lower()) if fuzz else (100 if shazam_res == api_res else 0)
            match_score = ratio
            if ratio > 80:
                final_match = shazam_res
                status = "CONFIRMED"
            else:
                status = "CONFLICT"

        elif shazam_res:
            final_match = shazam_res
            status = "SINGLE_SHAZAM"

        elif api_res:
            final_match = api_res
            status = "SINGLE_API"

        else:
            base = os.path.basename(file_path)
            final_match = os.path.splitext(base)[0]
            status = "FILENAME"

        return {
            'shazam': shazam_res,
            'api': api_res,
            'final': self._clean(final_match),
            'status': status,
            'score': match_score
        }

    def _clean(self, text):
        if not text: return "Unknown Track"
        text = re.sub(r'[#@]\w+', '', text)
        text = re.sub(r'[\[\(].*?[\]\)]', '', text)
        return " ".join(text.split())

class MinerApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("AUDIO-PRO-MINER v3.4 - Control Panel")
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
        top = ctk.CTkFrame(self, height=60, fg_color="#1a1a1a")
        top.pack(fill="x", padx=10, pady=10)

        ctk.CTkButton(top, text="📂 IMPORT .TXT", command=self.import_file).pack(side="left", padx=10)
        ctk.CTkButton(top, text="▶ START QUEUE", fg_color="#D35400", command=self.start_queue).pack(side="left", padx=10)

        self.lbl_status = ctk.CTkLabel(top, text="Ready", font=("Arial", 14))
        self.lbl_status.pack(side="right", padx=20)

        # Scroll
        self.scroll = ctk.CTkScrollableFrame(self, fg_color="#121212")
        self.scroll.pack(fill="both", expand=True, padx=10, pady=5)

    def import_file(self):
        path = ctk.filedialog.askopenfilename(filetypes=[("Text", "*.txt")])
        if not path: return
        with open(path, 'r', encoding='utf-8', errors='ignore') as f: content = f.read()

        # Regex allowing /video/ or /photo/ or generic
        regex = r'https?://(?:vm\.tiktok\.com|www\.tiktok\.com|tiktok\.com|youtu\.be|youtube\.com|www\.youtube\.com|instagram\.com|www\.instagram\.com)[^\s]+'
        links = set(re.findall(regex, content))

        for url in links:
            self.create_panel_row(url.strip('.,!?:;"\')]}'))
        self.lbl_status.configure(text=f"Imported {len(links)} links")

    def create_panel_row(self, url):
        idx = len(self.items)
        item = {
            'id': idx, 'url': url, 'status': 'Pending',
            'data': {}, 'ui': {}
        }

        # MAIN CARD FRAME
        card = ctk.CTkFrame(self.scroll, fg_color="#2b2b2b", corner_radius=8)
        card.pack(fill="x", pady=5, padx=5)

        # LINE 1: Header
        l1 = ctk.CTkFrame(card, fg_color="transparent", height=25)
        l1.pack(fill="x", padx=10, pady=2)
        ctk.CTkLabel(l1, text=f"🔗 {url}", font=("Arial", 12, "bold"), text_color="#F1C40F", anchor="w").pack(side="left")
        lbl_status = ctk.CTkLabel(l1, text="[ READY ]", text_color="white", font=("Arial", 12, "bold"), anchor="e")
        lbl_status.pack(side="right")

        # LINE 2: Data Dump
        l2 = ctk.CTkFrame(card, fg_color="#222222", height=40)
        l2.pack(fill="x", padx=10, pady=2)
        lbl_meta = ctk.CTkLabel(l2, text="Waiting for data...", font=("Consolas", 11), text_color="gray", anchor="w")
        lbl_meta.pack(fill="both", padx=5)

        # LINE 3: Decision
        l3 = ctk.CTkFrame(card, fg_color="transparent", height=30)
        l3.pack(fill="x", padx=10, pady=2)
        ctk.CTkLabel(l3, text="FINAL MATCH:", font=("Arial", 12, "bold"), text_color="gray").pack(side="left")
        lbl_final = ctk.CTkLabel(l3, text="-", font=("Arial", 13, "bold"), text_color="white", fg_color="#333333", corner_radius=4, padx=10)
        lbl_final.pack(side="left", padx=10)

        # LINE 4: Action Bar
        l4 = ctk.CTkFrame(card, fg_color="transparent", height=40)
        l4.pack(fill="x", padx=10, pady=(5,10))

        # Buttons
        btns = {}
        btns['play_ref'] = self._mk_btn(l4, "▶ Ref", "#2ECC71", lambda: self.play_ref(idx))
        btns['play_mast'] = self._mk_btn(l4, "▶ Master", "#9B59B6", lambda: self.play_master(idx))
        btns['edit'] = self._mk_btn(l4, "✏️ EDIT", "#E67E22", lambda: self.edit_name(idx))
        btns['force'] = self._mk_btn(l4, "⬇️ FORCE DL", "#3498DB", lambda: self.force_download_master(idx))
        btns['del'] = self._mk_btn(l4, "❌ DEL", "#C0392B", lambda: self.delete_row(idx))

        item['ui'] = {
            'card': card, 'status': lbl_status, 'meta': lbl_meta,
            'final': lbl_final, 'btns': btns
        }
        self.items.append(item)

    def _mk_btn(self, parent, text, col, cmd):
        btn = ctk.CTkButton(parent, text=text, fg_color=col, width=110, height=30, command=cmd)
        btn.pack(side="left", padx=4)
        return btn

    def start_queue(self):
        threading.Thread(target=self._run_queue, daemon=True).start()

    def _run_queue(self):
        for item in self.items:
            if item['status'] == 'Pending':
                asyncio.run_coroutine_threadsafe(self.process_item(item), self.loop).result()

    async def process_item(self, item):
        ui = item['ui']
        idx = item['id']

        # 1. Download
        self.update_ui(item, "DOWNLOADING...", "#3498DB")

        # FIX: Handle None return properly
        dl_result = await self.dl.download_tiktok_chain(item['url'])
        if not dl_result:
            self.update_ui(item, "DOWNLOAD FAILED ❌", "#C0392B")
            ui['meta'].configure(text="All providers failed.")
            return

        ref_path, meta = dl_result
        item['data']['ref_path'] = ref_path
        item['data']['meta'] = meta

        # 2. Identify
        self.update_ui(item, "TRIANGULATING...", "#E67E22")
        id_res = await self.id_engine.triangulate(ref_path, meta)
        item['data']['id'] = id_res

        # Update Data Dump UI
        dump_txt = f"API: {id_res['api']} | SHAZAM: {id_res['shazam']}"
        self.update_widget(ui['meta'], text=dump_txt)
        self.update_widget(ui['final'], text=id_res['final'])

        if id_res['status'] == 'CONFLICT':
            self.update_ui(item, "CONFLICT ⚠️", "#F1C40F")
            self.update_widget(ui['final'], fg_color="#F1C40F", text_color="black")
            # Stop here for manual edit
        else:
            self.update_ui(item, "MATCH CONFIRMED ✅", "#2ECC71")
            self.update_widget(ui['final'], fg_color="#2ECC71")
            # Auto trigger master
            await self.trigger_master_download(item)

    async def trigger_master_download(self, item):
        name = item['data']['id']['final']
        self.update_ui(item, f"GETTING MASTER: {name}...", "#8E44AD")

        res = await asyncio.to_thread(self.dl.search_master, f"{name} official audio")
        if res:
            m_path, m_url = res
            item['data']['master_path'] = m_path
            item['data']['master_url'] = m_url
            self.update_ui(item, "COMPLETED 🎵", "#27AE60")
        else:
            self.update_ui(item, "MASTER NOT FOUND", "gray")

    def edit_name(self, idx):
        item = self.items[idx]
        dialog = ctk.CTkInputDialog(text="Enter correct song name:", title="Edit Metadata")
        new_name = dialog.get_input()
        if new_name:
            item['data']['id']['final'] = new_name
            self.update_widget(item['ui']['final'], text=new_name, fg_color="#3498DB")
            # Trigger download
            asyncio.run_coroutine_threadsafe(self.trigger_master_download(item), self.loop)

    def force_download_master(self, idx):
        item = self.items[idx]
        asyncio.run_coroutine_threadsafe(self.trigger_master_download(item), self.loop)

    def update_ui(self, item, text, color):
        self.after(0, lambda: item['ui']['status'].configure(text=text, text_color=color))

    def update_widget(self, widget, **kwargs):
        self.after(0, lambda: widget.configure(**kwargs))

    # Button Actions
    def play_ref(self, idx):
        path = self.items[idx]['data'].get('ref_path')
        if path and os.path.exists(path): self.open_file(path)

    def play_master(self, idx):
        path = self.items[idx]['data'].get('master_path')
        if path and os.path.exists(path): self.open_file(path)

    def delete_row(self, idx):
        self.items[idx]['ui']['card'].destroy()
        self.items[idx]['status'] = 'Deleted'

    def open_file(self, path):
        if sys.platform == 'linux': subprocess.run(['xdg-open', path])
        elif sys.platform == 'win32': os.startfile(path)

if __name__ == "__main__":
    app = MinerApp()
    app.mainloop()
