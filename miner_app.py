import os
import sys
import re
import asyncio
import time
import random
import glob
from yt_dlp import YoutubeDL
from shazamio import Shazam
from tqdm import tqdm
import imageio_ffmpeg
from pydub import AudioSegment
import customtkinter as ctk
import threading
from datetime import datetime
import pyperclip
from flask import Flask, request, render_template_string
import socket
import logging
import aiohttp
import json

# Disable Flask logging
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

# Configuration: Setup FFMPEG
# When frozen with PyInstaller, we need to ensure we can find the binary
try:
    FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()
except Exception:
    # Fallback or manual handling if needed, but get_ffmpeg_exe usually works if collected properly
    FFMPEG_PATH = "ffmpeg"

ffmpeg_dir = os.path.dirname(FFMPEG_PATH)
# Add to PATH so pydub and other tools can find it
os.environ["PATH"] += os.pathsep + ffmpeg_dir

AudioSegment.converter = FFMPEG_PATH
AudioSegment.ffmpeg = FFMPEG_PATH
AudioSegment.ffprobe = FFMPEG_PATH

# Directories
DIR_TMP = "00_TEMP_STAGING"
DIR_MASTER = "01_ESTUDIO_MASTER"
DIR_REF = "02_ORIGINAIS_REFERENCIA"

# Ensure directories exist
os.makedirs(DIR_TMP, exist_ok=True)
os.makedirs(DIR_MASTER, exist_ok=True)
os.makedirs(DIR_REF, exist_ok=True)


class ExternalMiners:
    def __init__(self, log_callback):
        self.log = log_callback

    async def download_tikwm(self, url, output_dir):
        """TikWM API for TikTok"""
        api_url = "https://www.tikwm.com/api/"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(api_url, data={'url': url}) as resp:
                    data = await resp.json()
                    if data.get('code') == 0:
                        data_obj = data.get('data', {})
                        title = data_obj.get('title', f"tiktok_{int(time.time())}")
                        sanitized_title = self._sanitize(title)

                        # Handle Slideshows (Photos)
                        if 'images' in data_obj and data_obj['images']:
                            self.log("Detected TikTok Slideshow. Downloading Audio Only.")
                            music_url = data_obj.get('music')
                            if music_url:
                                async with session.get(music_url) as m_resp:
                                    if m_resp.status == 200:
                                        filename = f"{output_dir}/{sanitized_title}.mp3"
                                        with open(filename, 'wb') as f:
                                            f.write(await m_resp.read())
                                        return filename
                            else:
                                self.log("No music found for slideshow.")
                                return None

                        # Handle Video
                        video_url = data_obj.get('play')
                        if video_url:
                            async with session.get(video_url) as v_resp:
                                if v_resp.status == 200:
                                    filename = f"{output_dir}/{sanitized_title}.mp4"
                                    content = await v_resp.read()
                                    with open(filename, 'wb') as f:
                                        f.write(content)
                                    self.log("TikWM Download Success")
                                    return filename
        except Exception as e:
            self.log(f"TikWM Failed: {e}")
        return None

    async def download_cobalt(self, url, output_dir):
        """Cobalt API (Universal)"""
        # Using a reliable public instance or official
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
                        # Download it
                        async with session.get(download_link) as d_resp:
                            if d_resp.status == 200:
                                # Determine ext from headers or default
                                ext = "mp3" if "audio" in d_resp.headers.get('Content-Type', '') else "mp4"
                                filename = f"{output_dir}/download_{int(time.time())}.{ext}"
                                with open(filename, 'wb') as f:
                                    f.write(await d_resp.read())
                                self.log("Cobalt API Download Success")
                                return filename
        except Exception as e:
            self.log(f"Cobalt API Failed: {e}")
        return None

    def _sanitize(self, name):
        return re.sub(r'[<>:"/\\|?*]', '', name).strip()

class CoreMiner:
    def __init__(self, log_callback=None):
        self.log_callback = log_callback
        self.external = ExternalMiners(self.log)

    def log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        msg = f"[{timestamp}] {message}"
        print(msg)
        if self.log_callback:
            self.log_callback(msg)

    def sanitize_filename(self, name):
        name = re.sub(r'[<>:"/\\|?*]', '', name)
        name = name.strip()
        return name

    def get_ydl_opts(self, output_dir, strategy='A', is_video=False):
        # Base options
        opts = {
            'outtmpl': f'{output_dir}/%(title)s.%(ext)s',
            'noplaylist': True,
            'quiet': True,
            'no_warnings': True,
            'ffmpeg_location': FFMPEG_PATH,
            'nocheckcertificate': True,
            'ignoreerrors': True, # Important for retry logic to catch exceptions
        }

        # Format selection
        if is_video:
             # Best video up to 1080p + best audio, merge to mp4
            opts['format'] = 'bestvideo[height<=1080]+bestaudio/best[height<=1080]'
            opts['merge_output_format'] = 'mp4'
        else:
            opts['format'] = 'bestaudio/best'
            opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '320',
            }]

        # Strategy A: Standard / Browser Emulation (Cookies)
        if strategy == 'A':
            opts['user_agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            # Attempt to load cookies from default browser if available (best effort)
            # opts['cookiesfrombrowser'] = ('chrome',)

        # Strategy B: Android Client (good for TikTok/Shorts)
        # UPDATED: Specific TikTok fixes
        elif strategy == 'B':
            opts['extractor_args'] = {'tiktok': {'app_version': '30.0.0', 'os': 'android'}}
            opts['user_agent'] = 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/93.0.4577.82 Mobile Safari/537.36'

        # Strategy C: Rotation / Anti-blocking (Aggressive)
        elif strategy == 'C':
            # Randomized UA
            uas = [
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Safari/605.1.15',
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
                'Mozilla/5.0 (iPad; CPU OS 14_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1'
            ]
            opts['user_agent'] = random.choice(uas)
            # Add a delay to avoid rate limits
            opts['sleep_interval'] = 2

        return opts

    async def download_with_fallback(self, url, output_dir, is_video=False, mode="Automático"):
        """
        Multi-Mode Download: Native (yt-dlp) + Web APIs (Cobalt/TikWM)
        """
        is_tiktok = "tiktok" in url.lower()

        # Priority Logic: API FIRST for TikTok (to avoid IP blocks)
        if is_tiktok and mode in ["Automático", "API Web"]:
             res = await self._try_web_apis(url, output_dir)
             if res: return res

        # Native Strategies (yt-dlp)
        if mode in ["Automático", "Nativo"]:
            # If it's TikTok and we are here, API failed or Mode is Native.
            # Strategy B (Mobile) is best for TikTok native attempt.
            strategies = ['B', 'A', 'C']
            for strategy in strategies:
                self.log(f"[Native] Trying Strategy {strategy} for {url}...")
                opts = self.get_ydl_opts(output_dir, strategy, is_video)

                try:
                    # Run blocking yt-dlp in executor to not freeze UI
                    info = await asyncio.to_thread(self._run_ytdlp, opts, url)
                    if info:
                        return info['filename'], info
                except Exception as e:
                    self.log(f"Strategy {strategy} Failed: {str(e)}")
                    await asyncio.sleep(1)

        # Web API Strategies (Fallback for non-TikTok or if Native failed for others)
        if mode in ["Automático", "API Web"] and not is_tiktok:
             res = await self._try_web_apis(url, output_dir)
             if res: return res

        self.log(f"All download modes failed for {url}")
        return None, None

    async def _try_web_apis(self, url, output_dir):
        self.log("[API] Attempting Web APIs...")
        # TikWM (Specific for TikTok)
        if "tiktok" in url.lower():
            res = await self.external.download_tikwm(url, output_dir)
            if res: return res, {'title': os.path.basename(res), 'uploader': 'TikTok API'}

        # Cobalt (Universal)
        res = await self.external.download_cobalt(url, output_dir)
        if res: return res, {'title': os.path.basename(res), 'uploader': 'Cobalt API'}
        return None

    def _run_ytdlp(self, opts, url):
        """Helper to run yt-dlp in thread"""
        try:
            with YoutubeDL(opts) as ydl:
                try:
                    info = ydl.extract_info(url, download=True)
                except (AttributeError, TypeError) as e:
                    # Catch internal NoneType errors in yt-dlp
                    print(f"CRITICAL YT-DLP ERROR: {e}")
                    return None
                except Exception:
                    return None # Standard download error

                if not info: return None

                filename = ydl.prepare_filename(info)
                base, ext = os.path.splitext(filename)

                # If audio conversion was requested (not video), check for mp3
                if not opts.get('merge_output_format'):
                     if os.path.exists(f"{base}.mp3"):
                         filename = f"{base}.mp3"

                if os.path.exists(filename):
                    info['filename'] = filename
                    return info
                return None
        except Exception:
            return None

    async def precision_recognition(self, file_path):
        """
        Analyzes Start (10s), Mid (50%), End (75%)
        """
        try:
            # Instantiate Shazam here to ensure it binds to the current thread's event loop
            shazam = Shazam()

            audio = AudioSegment.from_file(file_path)
            duration_ms = len(audio)

            points = [
                10 * 1000, # 10s
                duration_ms * 0.5, # 50%
                duration_ms * 0.75 # 75%
            ]

            candidates = []

            for i, p in enumerate(points):
                if p >= duration_ms: continue

                # Slice 10 seconds
                segment = audio[p : min(p + 10000, duration_ms)]
                # Export temp
                tmp_seg = f"temp_seg_{i}.mp3"
                segment.export(tmp_seg, format="mp3")

                try:
                    out = await shazam.recognize(tmp_seg)
                    track = out.get('track', {})
                    if track:
                        title = track.get('title')
                        artist = track.get('subtitle')
                        if title and artist:
                            candidates.append((title, artist))
                            self.log(f"Segment {i} identified: {title} - {artist}")
                except Exception as e:
                    self.log(f"Segment {i} error: {e}")
                finally:
                    if os.path.exists(tmp_seg):
                        os.remove(tmp_seg)

            if not candidates:
                return None, None

            # Majority vote or first result
            # Simple approach: return most frequent
            from collections import Counter
            c = Counter(candidates)
            best_match = c.most_common(1)[0][0]
            self.log(f"Consensus Identification: {best_match}")
            return best_match # (Title, Artist)

        except Exception as e:
            self.log(f"Precision recognition error: {e}")
            return None, None

    def search_master(self, title, artist):
        query = f"{title} {artist} official audio"
        self.log(f"Searching Master: {query}")

        opts = {
            'quiet': True,
            'extract_flat': True,
            'user_agent': 'Mozilla/5.0',
            'extractor_args': {'youtube': {'player_client': ['android', 'web']}}
        }

        with YoutubeDL(opts) as ydl:
            try:
                results = ydl.extract_info(f"ytsearch5:{query}", download=False)
                if not results: return None

                for entry in results['entries']:
                    duration = entry.get('duration', 0)
                    # Relaxed duration check? User said "Filtro de Tempo" in previous prompt (110s-600s)
                    # Let's stick to it, maybe verify "STATUS" in UI
                    if 110 < duration < 600:
                         return entry
            except Exception as e:
                self.log(f"Search error: {e}")
        return None

    def fetch_link_metadata(self, url):
        """
        Fast check to get Title and Duration without downloading.
        """
        opts = {
            'quiet': True,
            'extract_flat': True, # Fast check
            'user_agent': 'Mozilla/5.0',
            'ignoreerrors': True,
        }

        with YoutubeDL(opts) as ydl:
            try:
                info = ydl.extract_info(url, download=False)
                if info:
                    title = info.get('title', 'Unknown')
                    duration = info.get('duration', 0)
                    return title, duration
            except Exception as e:
                self.log(f"Metadata fetch error: {e}")
        return None, 0

# --- New Feature Classes ---

class ClipboardWatcher:
    def __init__(self, callback):
        self.callback = callback
        self.running = False
        self.last_content = ""
        # Patterns
        self.patterns = [
            r'(?:vm\.tiktok\.com|www\.tiktok\.com|tiktok\.com)',
            r'(?:youtu\.be|youtube\.com|www\.youtube\.com)',
            r'(?:instagram\.com|www\.instagram\.com)'
        ]

    def start(self):
        self.running = True
        threading.Thread(target=self._loop, daemon=True).start()

    def stop(self):
        self.running = False

    def _loop(self):
        while self.running:
            try:
                content = pyperclip.paste()
                if content and content != self.last_content:
                    self.last_content = content
                    if self._is_valid_link(content):
                        self.callback(content)
            except Exception:
                pass
            time.sleep(1)

    def _is_valid_link(self, text):
        for p in self.patterns:
            if re.search(p, text):
                return True
        return False

class ChatParser:
    def parse_file(self, filepath):
        links_unicos = set()
        # Regex calibrada para o padrão do arquivo do Mauro:
        # Pega http/s, domínios específicos, e vai até encontrar um espaço ou fim de linha.
        regex = r'https?://(?:vm\.tiktok\.com|www\.tiktok\.com|tiktok\.com|youtu\.be|youtube\.com|www\.youtube\.com|instagram\.com|www\.instagram\.com)[^\s]+'

        print(f"Lendo arquivo: {filepath}")
        try:
            # O WhatsApp costuma usar UTF-8
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()

            # Encontra todos os padrões que parecem links
            matches = re.findall(regex, content)

            for url in matches:
                # 1. Limpeza bruta: remove caracteres que não pertencem a URL mas colam nela
                clean_url = url.strip('.,!?:;"\')]}')

                # 2. Limpeza específica do WhatsApp/TikTok Lite
                # Às vezes o link vem colado com texto se não houver espaço
                # Mas a regex [^\s] geralmente resolve. Vamos garantir:
                if "tiktok.com" in clean_url and " " in clean_url:
                    clean_url = clean_url.split(" ")[0]

                # 3. Adiciona ao conjunto (set) para remover duplicados automaticamente
                links_unicos.add(clean_url)

            print(f"Links encontrados (sem duplicatas): {len(links_unicos)}")

        except UnicodeDecodeError:
            print("Erro de UTF-8, tentando Latin-1...")
            try:
                with open(filepath, 'r', encoding='latin-1') as f:
                    content = f.read()
                    matches = re.findall(regex, content)
                    for url in matches:
                        clean_url = url.strip('.,!?:;"\')]}')
                        links_unicos.add(clean_url)
            except Exception as e:
                print(f"Falha no fallback Latin-1: {e}")
        except Exception as e:
            print(f"Erro crítico ao ler arquivo: {e}")

        # Retorna lista convertida do set
        return list(links_unicos)

class BridgeServer:
    def __init__(self, port=5000, callback=None):
        self.port = port
        self.callback = callback
        self.app = Flask(__name__)
        self.server_thread = None

        @self.app.route('/', methods=['GET', 'POST'])
        def index():
            if request.method == 'POST':
                link = request.form.get('link')
                if link and self.callback:
                    self.callback(link)
                return "Link Sent! <a href='/'>Back</a>"
            return """
            <html>
                <body style='font-size: 2em; text-align: center; padding-top: 50px;'>
                    <h2>Link Bridge</h2>
                    <form method='post'>
                        <input type='text' name='link' style='width: 80%; padding: 10px; font-size: 1em;' placeholder='Paste URL here' autofocus>
                        <br><br>
                        <input type='submit' value='SEND' style='padding: 10px 20px; font-size: 1em;'>
                    </form>
                </body>
            </html>
            """

    def start(self):
        self.server_thread = threading.Thread(target=lambda: self.app.run(host='0.0.0.0', port=self.port, use_reloader=False), daemon=True)
        self.server_thread.start()

    def get_local_ip(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"

# --- UI Application ---

class MinerApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("AUDIO-PRO-MINER v2.3 - Resilient System")
        self.geometry("1000x800")
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")

        self.miner = CoreMiner(log_callback=self.log_message)
        self.clipboard_watcher = ClipboardWatcher(self.on_clipboard_link)
        self.chat_parser = ChatParser()
        self.bridge_server = BridgeServer(callback=self.on_bridge_link)

        # Start Bridge Server immediately
        self.bridge_server.start()

        self.setup_ui()
        self.pending_items = [] # Stores (original_path, master_info, identified_data, status)

        # Async Loop handling
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self.start_loop, daemon=True)
        self.thread.start()

    def start_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def run_async(self, coro):
        asyncio.run_coroutine_threadsafe(coro, self.loop)

    def setup_ui(self):
        # 1. Top Section: Input & Controls
        self.frame_top = ctk.CTkFrame(self)
        self.frame_top.pack(fill="x", padx=10, pady=10)

        # Left Side: URL Entry & Start
        self.frame_input = ctk.CTkFrame(self.frame_top, fg_color="transparent")
        self.frame_input.pack(side="left", fill="x", expand=True)

        self.entry_urls = ctk.CTkEntry(self.frame_input, placeholder_text="Paste URLs (comma separated)", width=300)
        self.entry_urls.pack(side="left", padx=5, pady=5)

        # Mode Selector
        self.combo_mode = ctk.CTkComboBox(self.frame_input, values=["Automático", "Nativo", "API Web"], width=110)
        self.combo_mode.set("Automático")
        self.combo_mode.pack(side="left", padx=5)

        self.btn_start = ctk.CTkButton(self.frame_input, text="START MINING", command=self.on_start, width=100)
        self.btn_start.pack(side="left", padx=5)

        # Progress Label
        self.lbl_progress = ctk.CTkLabel(self.frame_input, text="Progress: 0/0", font=("Arial", 12, "bold"))
        self.lbl_progress.pack(side="left", padx=10)

        # Right Side: Features
        self.frame_features = ctk.CTkFrame(self.frame_top, fg_color="transparent")
        self.frame_features.pack(side="right", padx=10)

        self.switch_radar = ctk.CTkSwitch(self.frame_features, text="Radar Mode", command=self.toggle_radar)
        self.switch_radar.pack(side="top", pady=2, anchor="e")

        self.btn_import_chat = ctk.CTkButton(self.frame_features, text="IMPORTAR WHATSAPP TXT", width=160, command=self.import_chat)
        self.btn_import_chat.pack(side="top", pady=2, anchor="e")

        self.btn_export_list = ctk.CTkButton(self.frame_features, text="💾 EXPORTAR LISTA LIMPA", width=160, command=self.export_clean_list, fg_color="#2980B9", state="disabled")
        self.btn_export_list.pack(side="top", pady=2, anchor="e")

        self.btn_process_pending = ctk.CTkButton(self.frame_features, text="PROCESS ALL PENDING", width=160, command=self.process_all_pending, fg_color="#D35400", state="disabled")
        self.btn_process_pending.pack(side="top", pady=2, anchor="e")

        self.btn_open_folder = ctk.CTkButton(self.frame_features, text="Open Folder", width=120, command=self.open_folder, fg_color="green")
        self.btn_open_folder.pack(side="top", pady=2, anchor="e")

        # Bridge Info
        ip = self.bridge_server.get_local_ip()
        self.lbl_bridge = ctk.CTkLabel(self.frame_features, text=f"Mobile Bridge:\nhttp://{ip}:5000", font=("Arial", 10), text_color="gray")
        self.lbl_bridge.pack(side="top", pady=5)

        # 2. Middle Section: Verification Grid
        self.label_grid = ctk.CTkLabel(self, text="VERIFICATION GRID (AUDIT)", font=("Arial", 14, "bold"))
        self.label_grid.pack(pady=5)

        self.scroll_frame = ctk.CTkScrollableFrame(self, height=300)
        self.scroll_frame.pack(fill="x", padx=10, pady=5)

        # Grid Headers
        headers = ["ORIGINAL", "IDENTIFIED", "STATUS", "ACTIONS"]
        for i, h in enumerate(headers):
            lbl = ctk.CTkLabel(self.scroll_frame, text=h, font=("Arial", 12, "bold"))
            lbl.grid(row=0, column=i, padx=5, pady=5, sticky="w")
            self.scroll_frame.grid_columnconfigure(i, weight=1)

        self.grid_row_idx = 1

        # 3. Bottom Section: Console & Progress
        self.console = ctk.CTkTextbox(self, height=200)
        self.console.pack(fill="x", padx=10, pady=10)

        self.progress_bar = ctk.CTkProgressBar(self)
        self.progress_bar.pack(fill="x", padx=10, pady=5)
        self.progress_bar.set(0)

    def log_message(self, msg):
        # Must be thread-safe for Tkinter
        self.after(0, lambda: self._append_log(msg))

    def _append_log(self, msg):
        self.console.insert("end", msg + "\n")
        self.console.see("end")

    def toggle_radar(self):
        if self.switch_radar.get():
            self.clipboard_watcher.start()
            self.log_message("Radar Mode Activated (Clipboard Monitor)")
        else:
            self.clipboard_watcher.stop()
            self.log_message("Radar Mode Deactivated")

    def import_chat(self):
        file_path = ctk.filedialog.askopenfilename(filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")])
        if file_path:
            links = self.chat_parser.parse_file(file_path)
            if links:
                self.imported_links = links # Store for export
                self.log_message(f"Sucesso! {len(links)} links extraídos da conversa com o Mauro.")
                self.btn_export_list.configure(state="normal")
                # Run analysis in background
                threading.Thread(target=self.analyze_imported_links, args=(links,), daemon=True).start()
            else:
                self.log_message("Nenhum link válido encontrado no arquivo.")

    def export_clean_list(self):
        if not hasattr(self, 'imported_links') or not self.imported_links:
            self.log_message("Sem links para exportar.")
            return

        save_path = ctk.filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text Files", "*.txt")])
        if save_path:
            try:
                with open(save_path, 'w', encoding='utf-8') as f:
                    for link in self.imported_links:
                        f.write(link + "\n")
                self.log_message(f"Lista exportada com sucesso: {save_path}")
            except Exception as e:
                self.log_message(f"Erro ao salvar: {e}")

    def analyze_imported_links(self, links):
        self.log_message("Analisando Links...")
        # Enable process button if links exist
        if links:
             self.after(0, lambda: self.btn_process_pending.configure(state="normal"))

        for url in links:
             # Fast fetch metadata
             title, duration = self.miner.fetch_link_metadata(url)

             status_text = f"Ready ({duration}s)" if duration else "Ready"

             # Add to Grid as Pending Mining
             # We use a special flag is_pending_mining=True
             self.after(0, lambda u=url, t=title, s=status_text: self.add_to_grid(u, t, s, None, None, False, is_pending=True))

        self.log_message("Análise completa. Revise a Grid.")

    def on_clipboard_link(self, link):
        self.log_message(f"Radar Detected: {link}")
        # Beep sound (cross-platform way is tricky without extra libs, so we just log/visual)
        self.after(0, lambda: self.add_links([link]))

    def on_bridge_link(self, link):
        self.log_message(f"Bridge Received: {link}")
        self.after(0, lambda: self.add_links([link]))

    def add_links(self, links):
        current_text = self.entry_urls.get()
        current_urls = [u.strip() for u in current_text.split(',') if u.strip()]

        new_count = 0
        for link in links:
            if link not in current_urls:
                current_urls.append(link)
                new_count += 1

        if new_count > 0:
            self.entry_urls.delete(0, "end")
            self.entry_urls.insert(0, ", ".join(current_urls))
            self.log_message(f"Added {new_count} new link(s) to queue.")

    def open_folder(self):
        path = os.path.abspath(DIR_MASTER)
        if sys.platform == 'win32':
            os.startfile(path)
        elif sys.platform == 'darwin':
            os.system(f'open "{path}"')
        else:
            os.system(f'xdg-open "{path}"')

    def on_start(self):
        urls_text = self.entry_urls.get()
        if not urls_text.strip():
            self.log_message("Please enter URLs.")
            return

        urls = [u.strip() for u in urls_text.split(',')]
        self.progress_bar.set(0)
        self.btn_start.configure(state="disabled")

        # Start background task
        threading.Thread(target=self.process_batch, args=(urls,), daemon=True).start()

    def process_batch(self, urls):
        total = len(urls)
        self.after(0, lambda: self.lbl_progress.configure(text=f"Progress: 0/{total}"))

        for i, url in enumerate(urls):
            self.log_message(f"Processing ({i+1}/{total}): {url}")

            # Run async part in the loop
            future = asyncio.run_coroutine_threadsafe(self.process_single(url), self.loop)
            try:
                future.result() # Wait for completion
            except Exception as e:
                self.log_message(f"Error processing {url}: {e}")

            # Update Progress
            prog_val = (i+1)/total
            self.after(0, lambda v=prog_val, c=i+1, t=total: [self.progress_bar.set(v), self.lbl_progress.configure(text=f"Progress: {c}/{t}")])

        self.after(0, lambda: self.btn_start.configure(state="normal"))
        self.log_message("Batch processing complete. Please Review Grid.")

    async def process_single(self, url):
        mode = self.combo_mode.get()
        # 1. Download Reference (Tmp)
        # Note: download_with_fallback is now async
        ref_path, info = await self.miner.download_with_fallback(url, DIR_REF, mode=mode)
        if not ref_path:
            self.log_message(f"Failed to download ref: {url}")
            return

        original_title = info.get('title', 'Unknown')

        # 2. Recognize
        title, artist = await self.miner.precision_recognition(ref_path)

        if not title:
            # Fallback to cleaned metadata logic
            clean_title = original_title
            # Remove hashtags
            clean_title = re.sub(r'#\w+', '', clean_title)
            # Remove mentions
            clean_title = re.sub(r'@\w+', '', clean_title)
            # Remove extra whitespace
            clean_title = " ".join(clean_title.split())
            # Clean emojis (basic robust regex for non-alphanumeric/punctuation)
            # Or simplified: accept utf-8 but strip surrounding garbage.
            # Using the re.sub above handles words.

            title = clean_title if clean_title else "Unknown Track"
            artist = info.get('uploader', 'Unknown Artist')
            self.log_message(f"Shazam failed. Fallback to: {title} - {artist}")

        identified_text = f"{title} - {artist}"

        # 3. Find Master (don't download yet, just find)
        master_info = await asyncio.to_thread(self.miner.search_master, title, artist)

        # Detect if "Video" (Clip) logic applies
        # If the original title contains "Official Video", "Clip", "4K", "1080p", we assume user might want video.
        # Or we check if the MASTER info we found is a video (it usually is on YT).
        # The requirement: "Se o link for identificado como clipe (HQ), baixar em MP4... caso contrário, extrair áudio Master"
        # We will use the MASTER info to decide. If the master result title has "Video" or "Clip", we download video.

        is_video_candidate = False
        if master_info:
            m_title = master_info.get('title', '').lower()
            # Refined video detection: Must look like a video/clip, and not explicitly "Audio"
            if ('video' in m_title or 'clip' in m_title) and 'audio' not in m_title:
                is_video_candidate = True

        status_text = "Not Found"
        if master_info:
            dur_diff = master_info['duration']
            v_tag = " [VIDEO]" if is_video_candidate else " [AUDIO]"
            status_text = f"Found ({dur_diff}s){v_tag}"
        else:
            status_text = "No Master Found"

        # 4. Add to Grid (Main Thread)
        self.after(0, lambda: self.add_to_grid(original_title, identified_text, status_text, master_info, ref_path, is_video_candidate))

    def add_to_grid(self, original, identified, status, master_info, ref_path, is_video_candidate, is_pending=False):
        r = self.grid_row_idx

        # If Pending Mining, store in a way we can retrieve for "Process All"
        if is_pending:
            self.pending_items.append({'url': original, 'row_id': r, 'processed': False})

        lbl_orig = ctk.CTkLabel(self.scroll_frame, text=original[:30]+"...")
        lbl_orig.grid(row=r, column=0, padx=5, sticky="w")

        lbl_ident = ctk.CTkLabel(self.scroll_frame, text=identified[:30]+"...")
        lbl_ident.grid(row=r, column=1, padx=5, sticky="w")

        lbl_stat = ctk.CTkLabel(self.scroll_frame, text=status)
        lbl_stat.grid(row=r, column=2, padx=5, sticky="w")

        # Buttons
        btn_frame = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        btn_frame.grid(row=r, column=3, padx=5, sticky="w")

        if is_pending:
            # Action: Mine (Start Process)
            cmd_mine = lambda: self.start_mining_item(r, original)
            btn_mine = ctk.CTkButton(btn_frame, text="Mine", width=40, fg_color="#D35400", command=cmd_mine)
            btn_mine.pack(side="left", padx=2)

            # Pending items don't have a ref_path yet, so simple remove
            cmd_discard = lambda: self.remove_grid_row_visual(r)
            btn_discard = ctk.CTkButton(btn_frame, text="✖", width=30, fg_color="red", command=cmd_discard)
            btn_discard.pack(side="left", padx=2)

        elif master_info:
            cmd_accept = lambda: self.accept_item(r, identified, master_info, is_video_candidate)
            btn_accept = ctk.CTkButton(btn_frame, text="✔", width=30, fg_color="green", command=cmd_accept)
            btn_accept.pack(side="left", padx=2)

            cmd_discard = lambda: self.discard_item(r, ref_path)
            btn_discard = ctk.CTkButton(btn_frame, text="✖", width=30, fg_color="red", command=cmd_discard)
            btn_discard.pack(side="left", padx=2)
        else:
            # Case where Master not found, still allow discard
            cmd_discard = lambda: self.discard_item(r, ref_path)
            btn_discard = ctk.CTkButton(btn_frame, text="✖", width=30, fg_color="red", command=cmd_discard)
            btn_discard.pack(side="left", padx=2)

        self.grid_row_idx += 1

    def remove_grid_row_visual(self, row_idx):
         # In Tkinter grid, removing is hard without keeping refs to widgets.
         # For this specific app, we might just mark it as discarded in logic
         # or "destroy" children of scroll_frame at that row?
         # Simplified: just log and ignore for now or disable buttons.
         # Real impl would require a widget registry.
         self.log_message("Item removed from list.")
         # Mark as processed in pending list so Process All skips it
         for item in self.pending_items:
             if item['row_id'] == row_idx:
                 item['processed'] = True

    def start_mining_item(self, row_idx, url):
        self.log_message(f"Starting mining for: {url}")
        # Mark as processed in pending
        for item in self.pending_items:
             if item['row_id'] == row_idx:
                 item['processed'] = True

        # Run process_single
        asyncio.run_coroutine_threadsafe(self.process_single(url), self.loop)

    def process_all_pending(self):
        count = 0
        for item in self.pending_items:
            if not item['processed']:
                item['processed'] = True
                asyncio.run_coroutine_threadsafe(self.process_single(item['url']), self.loop)
                count += 1
        self.log_message(f"Batch processing started for {count} items.")
        self.pending_items = [] # Clear queue? Or keep history? clearing.

    def accept_item(self, row_idx, identified_name, master_info, is_video):
        self.log_message(f"Accepted: {identified_name}")
        # Disable buttons for this row (visual feedback)
        # In a real app we'd access the widgets, here simplified.

        # Download Master
        threading.Thread(target=self.download_final, args=(identified_name, master_info, is_video), daemon=True).start()

    def discard_item(self, row_idx, ref_path):
        self.log_message(f"Discarded item. Removed ref.")
        if ref_path and os.path.exists(ref_path):
            try:
                os.remove(ref_path)
            except: pass

    def download_final(self, name, info, is_video):
        url = info.get('url') or info.get('webpage_url')
        sanitized = self.miner.sanitize_filename(name)

        opts = self.miner.get_ydl_opts(DIR_MASTER, is_video=is_video)
        opts['outtmpl'] = f'{DIR_MASTER}/{sanitized}.%(ext)s'

        try:
            with YoutubeDL(opts) as ydl:
                ydl.download([url])
            self.log_message(f"DOWNLOAD COMPLETE: {sanitized}")

            # Sync to disk
            if hasattr(os, 'sync'):
                os.sync()
            elif hasattr(os, 'fsync'):
                 # fsync requires a file descriptor, os.sync is global
                 pass

        except Exception as e:
            self.log_message(f"Final Download Failed: {e}")

if __name__ == "__main__":
    app = MinerApp()
    app.mainloop()
