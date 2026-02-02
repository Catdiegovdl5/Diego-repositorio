import os
import sys
import re
import asyncio
import glob
from yt_dlp import YoutubeDL
from shazamio import Shazam
from tqdm import tqdm
import imageio_ffmpeg

# Configuration: Setup FFMPEG
FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()
ffmpeg_dir = os.path.dirname(FFMPEG_PATH)
# Add to PATH so pydub and other tools can find it
os.environ["PATH"] += os.pathsep + ffmpeg_dir

from pydub import AudioSegment

AudioSegment.converter = FFMPEG_PATH
AudioSegment.ffmpeg = FFMPEG_PATH
AudioSegment.ffprobe = FFMPEG_PATH

DIR_MASTER = "01_ESTUDIO_MASTER"
DIR_REF = "02_ORIGINAIS_REFERENCIA"

# Ensure directories exist
os.makedirs(DIR_MASTER, exist_ok=True)
os.makedirs(DIR_REF, exist_ok=True)

def sanitize_filename(name):
    """
    Sanitizes the filename to be FAT32 compatible.
    Removes illegal characters: < > : " / \\ | ? *
    """
    name = re.sub(r'[<>:"/\\|?*]', '', name)
    name = name.strip()
    return name

def get_ydl_opts(output_dir, is_reference=True):
    """
    Returns yt-dlp options.
    """
    opts = {
        'format': 'bestaudio/best',
        'outtmpl': f'{output_dir}/%(title)s.%(ext)s',
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'ffmpeg_location': FFMPEG_PATH,
        # Browser emulation and anti-bot measures
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'nocheckcertificate': True,
        'ignoreerrors': True,
        'extractor_args': {'youtube': {'player_client': ['android', 'web']}}, # Try to be robust
    }

    if is_reference:
        # For reference, we just want the audio, keep it raw or mp3?
        # Shazam likes raw or common formats.
        opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]
    else:
        # For master, we want high fidelity.
        opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3', # Or flac/wav? User said "high fidelity". MP3 320 is good standard.
            'preferredquality': '320',
        }]

    return opts

def download_reference(url):
    """
    Downloads the audio from the given URL to the reference directory.
    """
    print(f"[INFO] Downloading reference: {url}")
    opts = get_ydl_opts(DIR_REF, is_reference=True)

    try:
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if not info:
                return None

            # Find the downloaded file
            filename = ydl.prepare_filename(info)
            base, ext = os.path.splitext(filename)
            final_filename = f"{base}.mp3" # Since we converted to mp3

            if os.path.exists(final_filename):
                return final_filename
            return None
    except Exception as e:
        print(f"[ERROR] Download failed: {e}")
        return None

async def recognize_audio(file_path):
    """
    Recognizes the audio using Shazam.
    """
    print(f"[INFO] Recognizing: {os.path.basename(file_path)}")
    try:
        shazam = Shazam()
        out = await shazam.recognize(file_path)
        track = out.get('track', {})
        title = track.get('title')
        subtitle = track.get('subtitle') # Artist

        if title and subtitle:
            return title, subtitle
        return None, None
    except Exception as e:
        print(f"[ERROR] Recognition failed: {e}")
        return None, None

def search_and_download_master(title, artist):
    """
    Searches for the master version on YouTube, checks duration, and downloads.
    """
    query = f"{title} {artist} official audio"
    print(f"[INFO] Searching for Master: {query}")

    opts = get_ydl_opts(DIR_MASTER, is_reference=False)
    # We don't download yet, just search
    search_opts = opts.copy()
    search_opts['extract_flat'] = True # Don't download

    try:
        with YoutubeDL(search_opts) as ydl:
            # search 5 results
            results = ydl.extract_info(f"ytsearch5:{query}", download=False)

            if not results or 'entries' not in results:
                print("[WARN] No results found.")
                return

            for entry in results['entries']:
                duration = entry.get('duration', 0)
                # Filter: 110s < x < 600s
                if 110 < duration < 600:
                    video_url = entry.get('url') # or webpage_url
                    if not video_url:
                        video_url = entry.get('webpage_url')

                    print(f"[INFO] Found match: {entry.get('title')} ({duration}s)")

                    # Sanitize name
                    sanitized_title = sanitize_filename(f"{artist} - {title}")

                    # Update opts to force filename
                    download_opts = opts.copy()
                    download_opts['outtmpl'] = f'{DIR_MASTER}/{sanitized_title}.%(ext)s'

                    # Download
                    print(f"[INFO] Downloading Master...")
                    with YoutubeDL(download_opts) as ydl_down:
                        ydl_down.download([video_url])

                    print(f"[SUCCESS] Downloaded to {DIR_MASTER}/{sanitized_title}.mp3")
                    return

            print("[WARN] No suitable version found within duration limits (110s - 600s).")

    except Exception as e:
        print(f"[ERROR] Search/Download failed: {e}")

async def process_url(url):
    """
    Main workflow for a single URL.
    """
    # 1. Download Reference
    ref_path = download_reference(url)
    if not ref_path:
        print(f"[FAIL] Could not download reference for {url}")
        return

    # 2. Recognize
    title, artist = await recognize_audio(ref_path)
    if not title:
        print(f"[FAIL] Could not recognize song in {ref_path}")
        return

    print(f"[INFO] Identified: {title} by {artist}")

    # 3. Search and Download Master
    search_and_download_master(title, artist)

async def main():
    if len(sys.argv) < 2:
        print("Usage: python apm.py <url1> <url2> ...")
        # For testing, we can prompt or exit
        # sys.exit(1)
        # Interactive mode
        print("Enter URLs (comma separated) or type 'exit':")
        user_input = input().strip()
        if user_input.lower() == 'exit' or not user_input:
            return
        urls = [u.strip() for u in user_input.split(',')]
    else:
        urls = sys.argv[1:]

    # Use nested asyncio is tricky if loop already running (like in notebook),
    # but here we are in script.
    # shazamio requires async.

    for url in tqdm(urls, desc="Processing URLs"):
        await process_url(url)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[INFO] Interrupted by user.")
    except Exception as e:
        print(f"\n[CRITICAL] Unexpected error: {e}")
