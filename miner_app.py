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

class ExternalMiners:
    def __init__(self, log_callback):
        self.log = log_callback

    async def download_tikwm(self, url, output_dir):
        """
        TikWM API for TikTok.
        Returns: (filename, metadata_dict)
        """
        api_url = "https://www.tikwm.com/api/"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(api_url, data={'url': url}) as resp:
                    data = await resp.json()
                    if data.get('code') == 0:
                        data_obj = data.get('data', {})

                        # Extract Metadata
                        music_info = data_obj.get('music_info', {})
                        meta = {
                            'title': music_info.get('title') or data_obj.get('title'),
                            'author': music_info.get('author') or data_obj.get('author', {}).get('nickname'),
                            'source': 'TikWM'
                        }

                        # Determine Download URL (Audio Preferred if Slideshow)
                        dl_url = data_obj.get('play')
                        ext = "mp4"

                        if 'images' in data_obj and data_obj['images']:
                            self.log("Detected Slideshow. Using Music URL.")
                            dl_url = data_obj.get('music')
                            ext = "mp3"

                        if not dl_url:
                            return None, None

                        # Download
                        title_clean = SmartCleaner.sanitize_filename(meta['title'] or f"tiktok_{int(time.time())}")
                        filename = f"{output_dir}/{title_clean}.{ext}"

                        async with session.get(dl_url) as v_resp:
                            if v_resp.status == 200:
                                with open(filename, 'wb') as f:
                                    f.write(await v_resp.read())
                                self.log("TikWM Download Success")
                                return filename, meta
        except Exception as e:
            self.log(f"TikWM Failed: {e}")
        return None, None

    async def download_cobalt(self, url, output_dir):
        """
        Cobalt API (Universal).
        Returns: (filename, metadata_dict)
        """
        api_url = "https://api.cobalt.tools/api/json"
        headers = {'Accept': 'application/json', 'Content-Type': 'application/json'}
        payload = {
            "url": url,
            "vCodec": "h264",
            "vQuality": "1080",
            "aFormat": "mp3",
            "filenamePattern": "basic"
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(api_url, json=payload, headers=headers) as resp:
                    data = await resp.json()
                    if 'url' in data:
                        download_link = data['url']
                        filename_guess = data.get('filename', f"cobalt_{int(time.time())}.mp4")

                        # Metadata is scarce from Cobalt simple response, assume filename has info
                        meta = {'title': filename_guess, 'author': None, 'source': 'Cobalt'}

                        async with session.get(download_link) as d_resp:
                            if d_resp.status == 200:
                                ext = "mp3" if "audio" in d_resp.headers.get('Content-Type', '') else "mp4"
                                filename = f"{output_dir}/{SmartCleaner.sanitize_filename(filename_guess)}"
                                if not filename.endswith(f".{ext}"): filename += f".{ext}"

                                with open(filename, 'wb') as f:
                                    f.write(await d_resp.read())
                                self.log("Cobalt API Download Success")
                                return filename, meta
        except Exception as e:
            self.log(f"Cobalt API Failed: {e}")
        return None, None

class DownloadEngine:
    def __init__(self, log_callback):
        self.log = log_callback
        self.external = ExternalMiners(log_callback)

    async def download_reference(self, url):
        """
        Strategy: API First -> Native Fallback.
        Returns: (filename, metadata_dict)
        """
        # 1. API Strategy (TikWM/Cobalt)
        if "tiktok.com" in url:
            path, meta = await self.external.download_tikwm(url, DIRS['REF'])
            if path: return path, meta

        path, meta = await self.external.download_cobalt(url, DIRS['REF'])
        if path: return path, meta

        # 2. Native Strategy (yt-dlp)
        return await asyncio.to_thread(self._native_download, url)

    def _native_download(self, url):
        opts = {
            'outtmpl': f'{DIRS["REF"]}/%(title)s.%(ext)s',
            'format': 'bestaudio/best',
            'noplaylist': True,
            'quiet': True,
            'ignoreerrors': True,
            'nocheckcertificate': True,
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

                    # Ensure extension match
                    base, _ = os.path.splitext(fn)
                    # if we asked for audio/best, it might not be mp3 unless converted
                    # let's trust what's on disk
                    if os.path.exists(fn): return fn, meta
                    if os.path.exists(f"{base}.mp3"): return f"{base}.mp3", meta
                    if os.path.exists(f"{base}.m4a"): return f"{base}.m4a", meta

        except (AttributeError, TypeError, Exception) as e:
            self.log(f"Native Download Error: {e}")
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
                search_res = ydl.extract_info(query, download=False)
                if not search_res: return None

                for entry in search_res.get('entries', []):
                    dur = entry.get('duration', 0)
                    if 120 <= dur <= 600: # 2min to 10min
                        opts['default_search'] = 'auto'
                        with YoutubeDL(opts) as ydl_down:
                            info = ydl_down.extract_info(entry['webpage_url'], download=True)
                            fn = ydl_down.prepare_filename(info)
                            base, _ = os.path.splitext(fn)
                            final_path = f"{base}.mp3"
                            return final_path, entry['webpage_url']
        except Exception as e:
            self.log(f"Master Download Error: {e}")
        return None, None

class AudioManager:
    def __init__(self):
        self.cleaner = SmartCleaner()

    async def identify(self, file_path, api_meta=None):
        """
        Layer 1: Shazam
        Layer 2: API Metadata
        Layer 3: Filename
        """
        # Layer 1
        try:
            shazam = Shazam()
            out = await shazam.recognize(file_path)
            track = out.get('track', {})
            if track:
                title = track.get('title')
                artist = track.get('subtitle')
                if title and artist:
                    return f"{artist} - {title}", "Shazam"
        except Exception: pass

        # Layer 2
        if api_meta and api_meta.get('title') and api_meta.get('author'):
            clean_t = self.cleaner.clean_title(api_meta['title'])
            clean_a = self.cleaner.clean_title(api_meta['author'])
            return f"{clean_a} - {clean_t}", "API Meta"

        # Layer 3
        basename = os.path.basename(file_path)
        base, _ = os.path.splitext(basename)
        return self.cleaner.clean_title(base), "Filename"

class MinerApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("AUDIO-PRO-MINER v3.1 - Investigator")
        self.geometry("1300x800")
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")

        self.downloader = DownloadEngine(self.log_message)
        self.audio = AudioManager()

        self.items = []
        self.loop = asyncio.new_event_loop()
        threading.Thread(target=self._start_loop, daemon=True).start()

        self.setup_ui()

    def _start_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def log_message(self, msg):
        print(msg) # To console
        # Could add to UI log if needed, simplified for now

    def setup_ui(self):
        # Header
        top = ctk.CTkFrame(self)
        top.pack(fill="x", padx=10, pady=10)

        ctk.CTkButton(top, text="1. IMPORT (.txt)", command=self.import_chat).pack(side="left", padx=5)
        ctk.CTkButton(top, text="2. INVESTIGATE & DOWNLOAD", fg_color="#D35400", command=self.start_investigation).pack(side="left", padx=5)
        ctk.CTkButton(top, text="3. EXPORT REPORT", fg_color="#2980B9", command=self.export_report).pack(side="left", padx=5)

        self.lbl_status = ctk.CTkLabel(top, text="Idle")
        self.lbl_status.pack(side="right", padx=10)

        # Grid Header
        head = ctk.CTkFrame(self, height=30)
        head.pack(fill="x", padx=10)
        cols = ["Link", "Identified As", "Master Status", "Audit"]
        for c in cols:
            ctk.CTkLabel(head, text=c, font=("Arial", 12, "bold")).pack(side="left", expand=True, fill="x")

        # Scroll
        self.scroll = ctk.CTkScrollableFrame(self)
        self.scroll.pack(fill="both", expand=True, padx=10, pady=5)

    def import_chat(self):
        path = ctk.filedialog.askopenfilename(filetypes=[("Text", "*.txt")])
        if not path: return
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        regex = r'https?://(?:vm\.tiktok\.com|www\.tiktok\.com|tiktok\.com|youtu\.be|youtube\.com|www\.youtube\.com|instagram\.com|www\.instagram\.com)[^\s]+'
        links = set(re.findall(regex, content))

        for url in links:
            self.add_row(url.strip('.,!?:;"\')]}'))
        self.lbl_status.configure(text=f"Imported {len(links)} links")

    def add_row(self, url):
        idx = len(self.items)
        item = {
            'id': idx, 'url': url, 'status': 'Pending',
            'ident': None, 'master_url': None, 'ui': {}
        }

        f = ctk.CTkFrame(self.scroll, height=40)
        f.pack(fill="x", pady=1)

        l1 = ctk.CTkLabel(f, text=url[:40]+"...", anchor="w")
        l1.pack(side="left", expand=True, fill="x")

        l2 = ctk.CTkLabel(f, text="Pending...", anchor="center")
        l2.pack(side="left", expand=True, fill="x")

        l3 = ctk.CTkLabel(f, text="-", anchor="center")
        l3.pack(side="left", expand=True, fill="x")

        act = ctk.CTkFrame(f, fg_color="transparent")
        act.pack(side="left", expand=True, fill="x")

        item['ui'] = {'frame': f, 'lbl_ident': l2, 'lbl_master': l3, 'actions': act}
        self.items.append(item)

    def start_investigation(self):
        threading.Thread(target=self._process_queue, daemon=True).start()

    def _process_queue(self):
        for item in self.items:
            if item['status'] == 'Pending':
                asyncio.run_coroutine_threadsafe(self.process_item(item), self.loop).result()

    async def process_item(self, item):
        idx = item['id']
        ui = item['ui']

        # Step A: Download Ref
        self.update_ui(idx, 'lbl_ident', "Downloading Ref...")
        ref_path, api_meta = await self.downloader.download_reference(item['url'])

        if not ref_path:
            self.update_ui(idx, 'lbl_ident', "Ref Failed", "red")
            return

        # Add Play Ref Button
        self.add_button(idx, "▶ Ref", "#2ECC71", lambda: self.open_file(ref_path))

        # Step B/C: Identify
        self.update_ui(idx, 'lbl_ident', "Identifying...")
        ident, source = await self.audio.identify(ref_path, api_meta)
        item['ident'] = ident
        self.update_ui(idx, 'lbl_ident', f"{ident} ({source})", "white")

        # Step D: Master
        self.update_ui(idx, 'lbl_master', "Searching Master...", "blue")
        m_path, m_url = await asyncio.to_thread(self.downloader.search_and_download_master, f"{ident} official audio")

        if m_path:
            item['master_url'] = m_url
            self.update_ui(idx, 'lbl_master', "Downloaded", "green")
            self.add_button(idx, "▶ Master", "#9B59B6", lambda: self.open_file(m_path))
            # Delete button
            self.add_button(idx, "❌", "red", lambda: self.delete_row(idx))
        else:
            self.update_ui(idx, 'lbl_master', "Not Found", "red")

    def update_ui(self, idx, widget_key, text, color=None):
        self.after(0, lambda: self._update_ui_impl(idx, widget_key, text, color))

    def _update_ui_impl(self, idx, key, text, color):
        lbl = self.items[idx]['ui'][key]
        lbl.configure(text=text)
        if color: lbl.configure(text_color=color)

    def add_button(self, idx, text, color, cmd):
        # Increased width to 110 so "▶ Master" fits clearly
        self.after(0, lambda: ctk.CTkButton(
            self.items[idx]['ui']['actions'],
            text=text,
            width=110,
            height=30,
            fg_color=color,
            command=cmd
        ).pack(side="left", padx=5))

    def delete_row(self, idx):
        # Visual delete
        self.items[idx]['ui']['frame'].destroy()
        self.items[idx]['status'] = 'Deleted'

    def open_file(self, path):
        if sys.platform == 'linux': subprocess.run(['xdg-open', path])
        elif sys.platform == 'win32': os.startfile(path)

    def export_report(self):
        path = ctk.filedialog.asksaveasfilename(defaultextension=".txt")
        if path:
            with open(path, 'w', encoding='utf-8') as f:
                f.write("Original URL | Identified As | Master URL\n")
                for item in self.items:
                    if item.get('ident'):
                        f.write(f"{item['url']} | {item['ident']} | {item.get('master_url', 'N/A')}\n")

if __name__ == "__main__":
    app = MinerApp()
    app.mainloop()
