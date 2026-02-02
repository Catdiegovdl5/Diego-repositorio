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

# Configuration: Setup FFMPEG
FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()
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


class CoreMiner:
    def __init__(self, log_callback=None):
        self.log_callback = log_callback
        self.shazam = Shazam()

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
        # Note: In a real env, we'd point to a cookie file. Here we emulate headers.
        if strategy == 'A':
            opts['user_agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'

        # Strategy B: Android Client (good for TikTok/Shorts)
        elif strategy == 'B':
            opts['extractor_args'] = {'youtube': {'player_client': ['android', 'web']}}
            opts['user_agent'] = 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.0.0 Mobile Safari/537.36'

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

    def download_with_fallback(self, url, output_dir, is_video=False):
        strategies = ['A', 'B', 'C']

        for strategy in strategies:
            self.log(f"Trying Strategy {strategy} for {url}...")
            opts = self.get_ydl_opts(output_dir, strategy, is_video)

            try:
                with YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    if not info:
                        raise Exception("No info extracted")

                    filename = ydl.prepare_filename(info)

                    # Fix extension if post-processed
                    if not is_video:
                        base, _ = os.path.splitext(filename)
                        filename = f"{base}.mp3"
                    elif is_video and info.get('ext') != 'mp4':
                         # If it was merged, it might be mp4 now
                         base, _ = os.path.splitext(filename)
                         if os.path.exists(f"{base}.mp4"):
                             filename = f"{base}.mp4"

                    if os.path.exists(filename):
                        self.log(f"Download Success with Strategy {strategy}")
                        return filename, info
            except Exception as e:
                self.log(f"Strategy {strategy} Failed: {str(e)}")
                time.sleep(1) # Cool down

        self.log(f"All strategies failed for {url}")
        return None, None

    async def precision_recognition(self, file_path):
        """
        Analyzes Start (10s), Mid (50%), End (75%)
        """
        try:
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
                    out = await self.shazam.recognize(tmp_seg)
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

# --- UI Application ---

class MinerApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("AUDIO-PRO-MINER v2.0 - Resilient System")
        self.geometry("1000x800")
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")

        self.miner = CoreMiner(log_callback=self.log_message)

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
        # 1. Top Section: Input
        self.frame_top = ctk.CTkFrame(self)
        self.frame_top.pack(fill="x", padx=10, pady=10)

        self.entry_urls = ctk.CTkEntry(self.frame_top, placeholder_text="Paste URLs (comma separated)", width=600)
        self.entry_urls.pack(side="left", padx=10, pady=10)

        self.btn_start = ctk.CTkButton(self.frame_top, text="START MINING", command=self.on_start)
        self.btn_start.pack(side="left", padx=10)

        self.btn_open_folder = ctk.CTkButton(self.frame_top, text="OPEN FOLDER", command=self.open_folder, fg_color="green")
        self.btn_open_folder.pack(side="right", padx=10)

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
        for i, url in enumerate(urls):
            self.log_message(f"Processing ({i+1}/{total}): {url}")
            # Run async part in the loop
            future = asyncio.run_coroutine_threadsafe(self.process_single(url), self.loop)
            try:
                future.result() # Wait for completion
            except Exception as e:
                self.log_message(f"Error processing {url}: {e}")

            self.after(0, lambda v=(i+1)/total: self.progress_bar.set(v))

        self.after(0, lambda: self.btn_start.configure(state="normal"))
        self.log_message("Batch processing complete. Please Review Grid.")

    async def process_single(self, url):
        # 1. Download Reference (Tmp)
        ref_path, info = self.miner.download_with_fallback(url, DIR_REF)
        if not ref_path:
            self.log_message(f"Failed to download ref: {url}")
            return

        original_title = info.get('title', 'Unknown')

        # 2. Recognize
        title, artist = await self.miner.precision_recognition(ref_path)

        if not title:
            # Fallback to metadata
            title = original_title
            artist = info.get('uploader', 'Unknown')
            self.log_message(f"Shazam failed. Used metadata: {title}")

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
            if 'video' in m_title or 'clip' in m_title or 'official' in m_title:
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

    def add_to_grid(self, original, identified, status, master_info, ref_path, is_video_candidate):
        r = self.grid_row_idx

        lbl_orig = ctk.CTkLabel(self.scroll_frame, text=original[:30]+"...")
        lbl_orig.grid(row=r, column=0, padx=5, sticky="w")

        lbl_ident = ctk.CTkLabel(self.scroll_frame, text=identified[:30]+"...")
        lbl_ident.grid(row=r, column=1, padx=5, sticky="w")

        lbl_stat = ctk.CTkLabel(self.scroll_frame, text=status)
        lbl_stat.grid(row=r, column=2, padx=5, sticky="w")

        # Buttons
        btn_frame = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        btn_frame.grid(row=r, column=3, padx=5, sticky="w")

        if master_info:
            cmd_accept = lambda: self.accept_item(r, identified, master_info, is_video_candidate)
            btn_accept = ctk.CTkButton(btn_frame, text="✔", width=30, fg_color="green", command=cmd_accept)
            btn_accept.pack(side="left", padx=2)

        cmd_discard = lambda: self.discard_item(r, ref_path)
        btn_discard = ctk.CTkButton(btn_frame, text="✖", width=30, fg_color="red", command=cmd_discard)
        btn_discard.pack(side="left", padx=2)

        self.grid_row_idx += 1

    def accept_item(self, row_idx, identified_name, master_info, is_video):
        self.log_message(f"Accepted: {identified_name}")
        # Disable buttons for this row (visual feedback)
        # In a real app we'd access the widgets, here simplified.

        # Download Master
        threading.Thread(target=self.download_final, args=(identified_name, master_info, is_video), daemon=True).start()

    def discard_item(self, row_idx, ref_path):
        self.log_message(f"Discarded item. Removed ref.")
        if os.path.exists(ref_path):
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
