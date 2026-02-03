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

class SmartCleaner:
    @staticmethod
    def clean_title(text):
        if not text: return "Unknown Track"
        # Remove hashtags
        text = re.sub(r'#\w+', '', text)
        # Remove mentions
        text = re.sub(r'@\w+', '', text)
        # Remove text in brackets [] or ()
        text = re.sub(r'\[.*?\]', '', text)
        text = re.sub(r'\(.*?\)', '', text)
        # Remove emojis (basic range)
        text = re.sub(r'[^\w\s,.\'-]', '', text, flags=re.UNICODE)
        # Cleanup whitespace
        return " ".join(text.split())

    @staticmethod
    def sanitize_filename(name):
        return re.sub(r'[<>:"/\\|?*]', '', name).strip()

class NetworkManager:
    async def fetch_tikwm(self, url):
        """TikWM API for TikTok"""
        api_url = "https://www.tikwm.com/api/"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(api_url, data={'url': url}) as resp:
                    data = await resp.json()
                    if data.get('code') == 0:
                        return data.get('data')
        except Exception as e:
            logger.error(f"TikWM Error: {e}")
        return None

    async def fetch_cobalt(self, url):
        """Cobalt API"""
        api_url = "https://api.cobalt.tools/api/json"
        headers = {'Accept': 'application/json', 'Content-Type': 'application/json'}
        payload = {"url": url, "vCodec": "h264", "vQuality": "1080", "aFormat": "mp3", "filenamePattern": "basic"}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(api_url, json=payload, headers=headers) as resp:
                    return await resp.json()
        except Exception as e:
            logger.error(f"Cobalt Error: {e}")
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

class DownloadEngine:
    def __init__(self, network_manager):
        self.net = network_manager

    async def download_reference(self, url):
        """Priority 1: API, Priority 2: Native"""
        # 1. API Strategy
        if "tiktok.com" in url:
            data = await self.net.fetch_tikwm(url)
            if data:
                # Prioritize Video, fallback to Music
                dl_url = data.get('play') or data.get('music')
                title = data.get('title', f"tiktok_{int(time.time())}")
                ext = "mp4" if dl_url == data.get('play') else "mp3"
                path = f"{DIRS['REF']}/{SmartCleaner.sanitize_filename(title)}.{ext}"
                if await self.net.download_file(dl_url, path):
                    return path, title

        # Cobalt Fallback
        cobalt_data = await self.net.fetch_cobalt(url)
        if cobalt_data and 'url' in cobalt_data:
            path = f"{DIRS['REF']}/ref_{int(time.time())}.mp4"
            if await self.net.download_file(cobalt_data['url'], path):
                return path, "Reference"

        # 2. Native Strategy (yt-dlp)
        return await asyncio.to_thread(self._native_download, url)

    def _native_download(self, url):
        opts = {
            'outtmpl': f'{DIRS["REF"]}/%(title)s.%(ext)s',
            'format': 'bestvideo+bestaudio/best', # Try best quality
            'noplaylist': True,
            'quiet': True,
            'ignoreerrors': True,
            'nocheckcertificate': True,
            'ffmpeg_location': FFMPEG_PATH,
            # Android Mobile UA
            'user_agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/93.0.4577.82 Mobile Safari/537.36',
            'extractor_args': {'tiktok': {'app_version': '30.0.0', 'os': 'android'}}
        }

        try:
            with YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                if info:
                    fn = ydl.prepare_filename(info)
                    if os.path.exists(fn): return fn, info.get('title', 'Unknown')
        except (AttributeError, TypeError, Exception) as e:
            logger.error(f"Native Download Crash Prevented: {e}")
        return None, None

    def search_and_download_master(self, query):
        """Search YouTube for 2-10min audio and download HQ MP3"""
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
                # Search first
                search_res = ydl.extract_info(query, download=False)
                if not search_res: return None

                for entry in search_res.get('entries', []):
                    dur = entry.get('duration', 0)
                    if 120 <= dur <= 600: # 2min to 10min
                        # Valid candidate
                        # Force download this specific URL
                        opts['default_search'] = 'auto' # Disable search for direct link
                        with YoutubeDL(opts) as ydl_down:
                            info = ydl_down.extract_info(entry['webpage_url'], download=True)
                            fn = ydl_down.prepare_filename(info)
                            base, _ = os.path.splitext(fn)
                            final_path = f"{base}.mp3"
                            return final_path, entry['webpage_url']
        except Exception as e:
            logger.error(f"Master Download Error: {e}")
        return None, None

class AudioManager:
    def __init__(self):
        self.cleaner = SmartCleaner()

    async def identify(self, file_path, fallback_title=None):
        try:
            shazam = Shazam()
            out = await shazam.recognize(file_path)
            track = out.get('track', {})
            if track:
                title = track.get('title')
                artist = track.get('subtitle')
                if title and artist:
                    return f"{artist} - {title}", True # True = Shazam Success
        except Exception as e:
            logger.error(f"Shazam Error: {e}")

        # Fallback
        cleaned = self.cleaner.clean_title(fallback_title)
        return cleaned, False # False = Fallback Used

class MinerApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("AUDIO-PRO-MINER v3.0 - The Auditor")
        self.geometry("1200x800")
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")

        self.net = NetworkManager()
        self.downloader = DownloadEngine(self.net)
        self.audio = AudioManager()

        self.items = [] # List of dicts: {id, url, status, ref_path, master_path, master_url}
        self.grid_rows = []

        self.setup_ui()

        self.loop = asyncio.new_event_loop()
        threading.Thread(target=self._start_loop, daemon=True).start()

    def _start_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def setup_ui(self):
        # Header
        top_frame = ctk.CTkFrame(self)
        top_frame.pack(fill="x", padx=10, pady=10)

        ctk.CTkButton(top_frame, text="IMPORTAR WHATSAPP (.txt)", command=self.import_chat).pack(side="left", padx=10)
        ctk.CTkButton(top_frame, text="PROCESSAR FILA", fg_color="#D35400", command=self.start_processing).pack(side="left", padx=10)

        self.lbl_status = ctk.CTkLabel(top_frame, text="Ready", font=("Consolas", 12))
        self.lbl_status.pack(side="right", padx=10)

        # Grid Header
        grid_head = ctk.CTkFrame(self, height=30)
        grid_head.pack(fill="x", padx=10, pady=(0,5))
        cols = [("Original Link", 3), ("Status / ID", 4), ("Auditing Actions", 3)]
        for txt, weight in cols:
            lbl = ctk.CTkLabel(grid_head, text=txt, font=("Arial", 12, "bold"))
            lbl.pack(side="left", expand=True, fill="x")

        # Scrollable Area
        self.scroll = ctk.CTkScrollableFrame(self)
        self.scroll.pack(fill="both", expand=True, padx=10, pady=10)

    def import_chat(self):
        path = ctk.filedialog.askopenfilename(filetypes=[("Text Files", "*.txt")])
        if not path: return

        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        # Regex for links
        regex = r'https?://(?:vm\.tiktok\.com|www\.tiktok\.com|tiktok\.com|youtu\.be|youtube\.com|www\.youtube\.com|instagram\.com|www\.instagram\.com)[^\s]+'
        links = set(re.findall(regex, content))

        for url in links:
            self.add_grid_row(url.strip('.,!?:;"\')]}'))

        self.lbl_status.configure(text=f"Imported {len(links)} links.")

    def add_grid_row(self, url):
        row_idx = len(self.items)
        item_data = {
            'id': row_idx,
            'url': url,
            'status': 'Pending',
            'ref_path': None,
            'master_path': None,
            'master_url': None,
            'ui': {}
        }

        row_frame = ctk.CTkFrame(self.scroll, height=40)
        row_frame.pack(fill="x", pady=2)

        # Col 1: Link
        lbl_link = ctk.CTkLabel(row_frame, text=url[:50]+"...", anchor="w")
        lbl_link.pack(side="left", padx=5, fill="x", expand=True)

        # Col 2: Status
        lbl_stat = ctk.CTkLabel(row_frame, text="Pending", anchor="center")
        lbl_stat.pack(side="left", padx=5, fill="x", expand=True)

        # Col 3: Actions
        action_frame = ctk.CTkFrame(row_frame, fg_color="transparent")
        action_frame.pack(side="left", padx=5, fill="x", expand=True)

        item_data['ui'] = {'frame': row_frame, 'stat': lbl_stat, 'actions': action_frame}
        self.items.append(item_data)

    def update_status(self, idx, text, color=None):
        self.after(0, lambda: self._update_ui_status(idx, text, color))

    def _update_ui_status(self, idx, text, color):
        lbl = self.items[idx]['ui']['stat']
        lbl.configure(text=text)
        if color: lbl.configure(text_color=color)

    def add_action_buttons(self, idx):
        self.after(0, lambda: self._render_buttons(idx))

    def _render_buttons(self, idx):
        item = self.items[idx]
        frame = item['ui']['actions']

        # Clear existing
        for widget in frame.winfo_children(): widget.destroy()

        # Ref Play
        if item['ref_path'] and os.path.exists(item['ref_path']):
            ctk.CTkButton(frame, text="▶ Ref", width=60, fg_color="#2ECC71",
                          command=lambda: self.open_file(item['ref_path'])).pack(side="left", padx=2)

        # Master Play
        if item['master_path'] and os.path.exists(item['master_path']):
            ctk.CTkButton(frame, text="▶ Master", width=60, fg_color="#9B59B6",
                          command=lambda: self.open_file(item['master_path'])).pack(side="left", padx=2)

        # Link Open
        if item['master_url']:
            ctk.CTkButton(frame, text="🔗 Link", width=60, fg_color="#3498DB",
                          command=lambda: self.open_url(item['master_url'])).pack(side="left", padx=2)

    def open_file(self, path):
        if sys.platform == 'linux':
            subprocess.run(['xdg-open', path])
        elif sys.platform == 'win32':
            os.startfile(path)

    def open_url(self, url):
        import webbrowser
        webbrowser.open(url)

    def start_processing(self):
        threading.Thread(target=self._process_queue, daemon=True).start()

    def _process_queue(self):
        for item in self.items:
            if item['status'] == 'Pending':
                asyncio.run_coroutine_threadsafe(self.process_item(item), self.loop).result()

    async def process_item(self, item):
        idx = item['id']
        url = item['url']

        self.update_status(idx, "Downloading Ref...", "yellow")

        # 1. Download Reference
        ref_path, ref_title = await self.downloader.download_reference(url)

        if not ref_path:
            self.update_status(idx, "Ref Download Failed", "red")
            return

        item['ref_path'] = ref_path
        self.update_status(idx, "Identifying...", "orange")
        self.add_action_buttons(idx) # Show Ref button immediately

        # 2. Identify
        ident_name, is_shazam = await self.audio.identify(ref_path, fallback_title=ref_title)
        prefix = "✅" if is_shazam else "⚠️"
        self.update_status(idx, f"{prefix} {ident_name}", "white")

        # 3. Master Download
        self.update_status(idx, f"Finding Master: {ident_name}...", "blue")

        # Run blocking youtube search in thread
        master_res = await asyncio.to_thread(self.downloader.search_and_download_master, f"{ident_name} official audio")

        if master_res:
            m_path, m_url = master_res
            item['master_path'] = m_path
            item['master_url'] = m_url
            self.update_status(idx, f"DONE: {ident_name}", "green")
            self.add_action_buttons(idx)

            # Sync
            if hasattr(os, 'sync'): os.sync()
        else:
            self.update_status(idx, f"Master Not Found: {ident_name}", "red")

if __name__ == "__main__":
    app = MinerApp()
    app.mainloop()
