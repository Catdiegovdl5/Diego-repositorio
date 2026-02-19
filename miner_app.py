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
from tkinter import messagebox, filedialog # JULES: Importação nativa para pop-ups e salvar arquivos (Resolve o bug TclError)
import threading
from datetime import datetime
import pyperclip
from flask import Flask, request, render_template_string
import socket
import logging
import aiohttp
import json
import concurrent.futures
from groq import Groq

# Disable Flask logging
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

# Configuration: Setup FFMPEG
try:
    FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()
    os.environ["PATH"] += os.pathsep + os.path.dirname(FFMPEG_PATH)
except Exception:
    pass
# Do NOT override ffprobe path. Let pydub use the system's winget installation.
AudioSegment.converter = "ffmpeg"
AudioSegment.ffmpeg = "ffmpeg"
AudioSegment.ffprobe = "ffprobe"

# Directories
DIR_TMP = "00_TEMP_STAGING"
DIR_MASTER = "01_ESTUDIO_MASTER"
DIR_REF = "02_ORIGINAIS_REFERENCIA"

os.makedirs(DIR_TMP, exist_ok=True)
os.makedirs(DIR_MASTER, exist_ok=True)
os.makedirs(DIR_REF, exist_ok=True)


class ExternalMiners:
    def __init__(self, log_callback):
        self.log = log_callback

    async def download_tikwm(self, url, output_dir):
        api_url = "https://www.tikwm.com/api/"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(api_url, data={'url': url}) as resp:
                    data = await resp.json()
                    if data.get('code') == 0:
                        video_url = data['data']['play']
                        title = data['data'].get('title', f"tiktok_{int(time.time())}")
                        async with session.get(video_url) as v_resp:
                            if v_resp.status == 200:
                                filename = f"{output_dir}/{self._sanitize(title)}.mp4"
                                content = await v_resp.read()
                                with open(filename, 'wb') as f:
                                    f.write(content)
                                self.log("TikWM Download Success")
                                return filename
        except Exception as e:
            self.log(f"TikWM Failed: {e}")
        return None

    async def download_cobalt(self, url, output_dir):
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
                        async with session.get(download_link) as d_resp:
                            if d_resp.status == 200:
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
        try:
            self.groq_client = Groq(api_key="API_KEY_AQUI")
        except Exception as e:
            self.groq_client = None
            self.log(f"Groq Init Failed: {e}")

    def is_it_music(self, title_text):
        if not self.groq_client: return "YES" # Fallback
        try:
            completion = self.groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": "You are a music filter. Return only YES or NO."},
                    {"role": "user", "content": f"Is this video title related to music, song, dance, or lyrics? Title: '{title_text}'. Return YES or NO."}
                ],
                temperature=0,
                max_tokens=5
            )
            return completion.choices[0].message.content.strip().upper()
        except Exception:
            return "YES" # Fail open

    def clean_title_with_groq(self, raw_title):
        if not self.groq_client: return self.sanitize_filename(raw_title)
        try:
            completion = self.groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": "Clean this title for a final filename. Remove emojis, hashtags, and junk. Return ONLY the Artist - Song Name or a clean description. Max 50 chars. Do not use special characters that are invalid in filenames."},
                    {"role": "user", "content": f"Clean this: {raw_title}"}
                ],
                temperature=0.1,
                max_tokens=60
            )
            clean = completion.choices[0].message.content.strip()
            return self.sanitize_filename(clean)
        except Exception:
            return self.sanitize_filename(raw_title)

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
        opts = {
            'outtmpl': f'{output_dir}/%(title)s.%(ext)s',
            'noplaylist': True,
            'quiet': True,
            'no_warnings': True,
            'ffmpeg_location': FFMPEG_PATH,
            'nocheckcertificate': True,
            'ignoreerrors': True,
            'logger': logging.getLogger('quiet_logger'), # Silence logging
        }
        # Silence the custom logger
        logging.getLogger('quiet_logger').setLevel(logging.CRITICAL)

        if is_video:
            opts['format'] = 'bestvideo[height<=1080]+bestaudio/best[height<=1080]'
            opts['merge_output_format'] = 'mp4'
        else:
            opts['format'] = 'bestaudio/best'
            opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '320',
            }]

        if strategy == 'A':
            opts['user_agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        elif strategy == 'B':
            opts['extractor_args'] = {'tiktok': {'app_version': '30.0.0', 'os': 'android'}}
            opts['user_agent'] = 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/93.0.4577.82 Mobile Safari/537.36'
        elif strategy == 'C':
            uas = [
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Safari/605.1.15',
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
                'Mozilla/5.0 (iPad; CPU OS 14_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1'
            ]
            opts['user_agent'] = random.choice(uas)
            opts['sleep_interval'] = 2

        return opts

    async def download_with_fallback(self, url, output_dir, is_video=False, mode="Automático"):
        # JULES FIX: Burlar bloqueio e limpar nomes gigantes (Resolução Errno 22)
        if "tiktok" in url:
            self.log("🚀 [API Turbo] Bypassing TikTok limits...")
            res = await self.external.download_tikwm(url, output_dir)
            if res:
                try:
                    # Tesoura de Nomes: Garante que o nome não quebre o Windows
                    pasta = os.path.dirname(res)
                    nome_original = os.path.basename(res)
                    # Mantém apenas caracteres seguros e limita a 50 chars
                    nome_limpo = "".join(x for x in nome_original if x.isalnum() or x in "._- ")[:50]
                    # Garante extensão mp4
                    if not nome_limpo.endswith(".mp4"):
                        nome_limpo += ".mp4"
                        
                    novo_caminho = os.path.join(pasta, nome_limpo)
                    
                    if res != novo_caminho:
                        os.rename(res, novo_caminho)
                        
                    return novo_caminho, {'title': nome_limpo, 'uploader': 'TikTok API'}
                except Exception as e:
                    self.log(f"Erro ao renomear arquivo (mas download ok): {e}")
                    return res, {'title': os.path.basename(res), 'uploader': 'TikTok API'}
            
            res = await self.external.download_cobalt(url, output_dir)
            if res: return res, {'title': os.path.basename(res), 'uploader': 'Cobalt API'}

        # Se falhar ou for YouTube, usa o yt-dlp (Nativo) com atraso para não tomar BAN
        strategies = ['B', 'A', 'C'] 
        for strategy in strategies:
            self.log(f"[Native] Tentando Motor Nativo {strategy}...")
            opts = self.get_ydl_opts(output_dir, strategy, is_video)
            try:
                info = await asyncio.to_thread(self._run_ytdlp, opts, url)
                if info:
                    return info['filename'], info
            except Exception as e:
                self.log(f"Motor {strategy} falhou: {str(e)}")
                await asyncio.sleep(2) # Pausa de segurança

        self.log(f"❌ Todos os métodos falharam para {url}")
        return None, None

    def _run_ytdlp(self, opts, url):
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if not info: return None
            filename = ydl.prepare_filename(info)
            base, ext = os.path.splitext(filename)
            if not opts.get('merge_output_format'): 
                 if os.path.exists(f"{base}.mp3"):
                     filename = f"{base}.mp3"
            if os.path.exists(filename):
                info['filename'] = filename
                return info
            return None

    async def precision_recognition(self, file_path):
        try:
            shazam = Shazam()
            self.log("🎧 Preparando áudio (Bypass do FFprobe ativo)...")
            
            # JULES FIX: Burlar a falta do FFprobe extraindo o áudio nós mesmos
            import subprocess
            safe_audio = file_path + "_temp.mp3"
            
            # Comando: Usa o FFMPEG que temos para pegar os primeiros 15s do áudio
            # Usa subprocess.run para garantir execução síncrona dentro da thread
            cmd = [
                FFMPEG_PATH, 
                "-y", "-i", file_path, 
                "-t", "15",            # Corta os primeiros 15 segundos (rápido)
                "-q:a", "0", "-map", "a", # Extrai apenas o áudio com qualidade máxima
                safe_audio
            ]
            
            # Roda o comando no fundo sem travar a tela
            await asyncio.to_thread(subprocess.run, cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            if not os.path.exists(safe_audio):
                 self.log("⚠️ Falha ao criar áudio temporário. FFMPEG Path: " + FFMPEG_PATH)
                 return None, None

            # JULES FIX: Usa apenas "recognize" (Resolve o DeprecationWarning do log)
            out = await shazam.recognize(safe_audio)
                
            # Limpeza do arquivo temporário de 15s
            if os.path.exists(safe_audio):
                try: os.remove(safe_audio)
                except: pass
                
            track = out.get('track', {})
            if track:
                title = track.get('title')
                artist = track.get('subtitle')
                if title and artist:
                    self.log(f"✅ IDENTIFICADO: {title} - {artist}")
                    return title, artist
                    
            self.log("⚠️ Shazam não encontrou correspondência para este áudio.")
            return None, None
            
        except Exception as e:
            self.log(f"Erro no Shazam: {e}")
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
                    if 110 < duration < 600:
                         return entry
            except Exception as e:
                self.log(f"Search error: {e}")
        return None

    def fetch_link_metadata(self, url):
        opts = {
            'quiet': True,
            'extract_flat': True,
            'user_agent': 'Mozilla/5.0',
            'ignoreerrors': True,
        }
        with YoutubeDL(opts) as ydl:
            try:
                info = ydl.extract_info(url, download=False)
                if info:
                    title = info.get('title') or 'Unknown'
                    duration = info.get('duration') or 0
                    return title, duration
            except Exception as e:
                self.log(f"Metadata fetch error: {e}")
        return "Unknown", 0


class ClipboardWatcher:
    def __init__(self, callback):
        self.callback = callback
        self.running = False
        self.last_content = ""
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
                    
                    # JULES FIX: Escudo Anti-Travamento de UI
                    # Se o texto copiado for maior que 1000 caracteres (ex: lista gigante), o Radar ignora!
                    if len(content) > 1000:
                        continue
                        
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
        print(f"Lendo arquivo: {filepath}")
        # Regex de alta precisão para vídeos (Ignora o lixo do TikTok Lite)
        padrao = r'https://(?:vm\.tiktok\.com|vt\.tiktok\.com|youtu\.be|youtube\.com/shorts)/\S+'
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                texto = f.read()
            
            links_brutos = re.findall(padrao, texto)

            # Limpeza e remoção de duplicados
            # Ignora links com "tiktoklite"
            links_limpos = list(set([l.strip('.,!?:;"\')]}') for l in links_brutos if "tiktoklite" not in l]))
            
            print(f"✅ Sucesso! {len(links_limpos)} links únicos e válidos detectados.")
            return links_limpos

        except Exception as e:
            print(f"Erro no parser: {e}")
            try:
                 # Fallback para latin-1 se utf-8 falhar
                with open(filepath, 'r', encoding='latin-1') as f:
                    texto = f.read()
                links_brutos = re.findall(padrao, texto)
                links_limpos = list(set([l.strip('.,!?:;"\')]}') for l in links_brutos if "tiktoklite" not in l]))
                return links_limpos
            except Exception as e2:
                pass
        return []

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
        self.bridge_server.start()

        self.setup_ui()
        self.pending_items = [] 

        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self.start_loop, daemon=True)
        self.thread.start()

    def start_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def setup_ui(self):
        self.frame_top = ctk.CTkFrame(self)
        self.frame_top.pack(fill="x", padx=10, pady=10)

        # Essential Buttons Only - Minimalist Layout
        self.btn_import_chat = ctk.CTkButton(self.frame_top, text="IMPORTAR WHATSAPP TXT", width=200, height=40, command=self.import_chat)
        self.btn_import_chat.pack(side="left", padx=10, pady=10)

        self.btn_export_list = ctk.CTkButton(self.frame_top, text="EXPORTAR LISTA LIMPA", width=200, height=40, command=self.export_clean_list, fg_color="#2980B9", state="disabled")
        self.btn_export_list.pack(side="left", padx=10, pady=10)

        self.btn_process_pending = ctk.CTkButton(self.frame_top, text="PROCESS ALL PENDING", width=200, height=40, command=self.process_all_pending, fg_color="#D35400", state="disabled")
        self.btn_process_pending.pack(side="left", padx=10, pady=10)

        self.btn_open_folder = ctk.CTkButton(self.frame_top, text="Open Folder", width=120, height=40, command=self.open_folder, fg_color="green")
        self.btn_open_folder.pack(side="left", padx=10, pady=10)

        # Bridge Info
        ip = self.bridge_server.get_local_ip()
        self.lbl_bridge = ctk.CTkLabel(self.frame_top, text=f"Mobile Bridge:\nhttp://{ip}:5000", font=("Arial", 10), text_color="gray")
        self.lbl_bridge.pack(side="right", padx=10)

        self.label_grid = ctk.CTkLabel(self, text="VERIFICATION GRID (AUDIT)", font=("Arial", 14, "bold"))
        self.label_grid.pack(pady=5)

        self.scroll_frame = ctk.CTkScrollableFrame(self, height=400)
        self.scroll_frame.pack(fill="both", expand=True, padx=10, pady=5)

        headers = ["ORIGINAL", "IDENTIFIED", "STATUS", "ACTIONS"]
        for i, h in enumerate(headers):
            lbl = ctk.CTkLabel(self.scroll_frame, text=h, font=("Arial", 12, "bold"))
            lbl.grid(row=0, column=i, padx=5, pady=5, sticky="w")
            self.scroll_frame.grid_columnconfigure(i, weight=1)

        self.grid_row_idx = 1

        self.console = ctk.CTkTextbox(self, height=150)
        self.console.pack(fill="x", padx=10, pady=10)

        self.progress_bar = ctk.CTkProgressBar(self)
        self.progress_bar.pack(fill="x", padx=10, pady=5)
        self.progress_bar.set(0)

    def log_message(self, msg):
        self.after(0, lambda: self._append_log(msg))

    def _append_log(self, msg):
        self.console.insert("end", msg + "\n")
        self.console.see("end")

    # JULES: Função de importar atualizada com FileDialog nativo, Pop-up e Contador
    def import_chat(self):
        try:
            # Fallback para evitar erro de Tcl com CustomTkinter
            from tkinter import filedialog as fd
            file_path = fd.askopenfilename(parent=self, title="Selecione o arquivo de conversa", filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")])
            
            if file_path:
                links = self.chat_parser.parse_file(file_path)
                if links:
                    self.imported_links = links 
                    total = len(links)
                    self.log_message(f"Sucesso! {total} links extraídos da conversa com o Mauro.")
                    
                    # Atualiza botões
                    self.btn_export_list.configure(state="normal")
                    self.btn_process_pending.configure(state="normal", text=f"PROCESS ALL PENDING ({total})")
                    
                    # Pop-up de Confirmação na Tela
                    messagebox.showinfo(
                        "Sucesso, Diego!", 
                        f"✅ Ação Concluída!\n{total} links do Mauro foram capturados e estão prontos para processamento."
                    )

                    threading.Thread(target=self.analyze_imported_links, args=(links,), daemon=True).start()
                else:
                    self.log_message("Nenhum link válido encontrado no arquivo.")
                    messagebox.showwarning("Aviso", "Nenhum link válido do TikTok/YouTube encontrado.")
        except Exception as e:
            self.log_message(f"Erro ao abrir arquivo: {e}")
            messagebox.showerror("Erro Crítico", f"Falha ao abrir diálogo de arquivo:\n{e}")

    # JULES FIX: Solução Definitiva - Auto-Save Bypass do FileDialog
    def export_clean_list(self):
        if not hasattr(self, 'imported_links') or not self.imported_links:
            self.log_message("Sem links para exportar.")
            return

        try:
            # 1. Cria uma pasta fixa para os exports (ignorando a janela do Windows)
            export_dir = "03_EXPORTADOS"
            if not os.path.exists(export_dir):
                os.makedirs(export_dir)

            # 2. Gera um nome de arquivo automático com a data e hora
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"Links_Mauro_{timestamp}.txt"
            save_path = os.path.abspath(os.path.join(export_dir, filename))

            # 3. Salva os links super rápido
            with open(save_path, 'w', encoding='utf-8') as f:
                for link in self.imported_links:
                    f.write(str(link) + "\n")

            self.log_message(f"✅ Lista salva automaticamente em: {save_path}")
            
            # Notifica na UI também
            messagebox.showinfo("Exportação Automática", f"✅ Arquivo salvo!\n\nPasta: {export_dir}\nArquivo: {filename}")

            # 4. Abre a pasta direto no seu Windows Explorer para você ver o arquivo!
            if sys.platform == 'win32':
                os.startfile(export_dir)

        except Exception as e:
            self.log_message(f"Erro crítico ao salvar: {e}")

    def analyze_imported_links(self, links):
        total = len(links)
        self.log_message(f"⚡ Importação Flash: Carregando {total} links na memória...")
        self.pending_items = []
        for i, url in enumerate(links):
            self.pending_items.append({'url': url, 'row_id': i + 1, 'processed': False})
        self.log_message("✅ Memória carregada instantaneamente! Pronto para processar.")
        self.after(0, lambda: self.btn_process_pending.configure(state="normal", text=f"PROCESS ALL PENDING ({total})"))

    def on_clipboard_link(self, link):
        self.log_message(f"Radar Detected: {link}")
        self.after(0, lambda: self.add_links([link]))

    def on_bridge_link(self, link):
        self.log_message(f"Bridge Received: {link}")
        self.after(0, lambda: self.add_links([link]))

    def add_links(self, links):
        for link in links:
             if not any(item['url'] == link for item in self.pending_items):
                 self.pending_items.append({'url': link, 'row_id': self.grid_row_idx, 'processed': False})
                 self.log_message(f"Added to queue (Pending): {link}")
                 
        total = len(self.pending_items)
        if total > 0:
            self.btn_process_pending.configure(state="normal", text=f"PROCESS ALL PENDING ({total})")

    # Removed on_start (UI processing now handled by process_all_pending)

    def open_folder(self):
        path = os.path.abspath(DIR_MASTER)
        if sys.platform == 'win32':
            os.startfile(path)
        elif sys.platform == 'darwin':
            os.system(f'open "{path}"')
        else:
            os.system(f'xdg-open "{path}"')

    def process_all_pending(self):
        items_to_process = [item for item in self.pending_items if not item['processed']]
        total = len(items_to_process)
        if total == 0: return

        self.log_message(f"🚀 Iniciando Processamento Paralelo (3x Speed) para {total} itens...")
        self.btn_process_pending.configure(state="disabled")

        def process_worker():
            # JULES FIX: Processa 3 links ao MESMO TEMPO. 
            # (Mais do que 4 pode fazer o TikTok bloquear seu IP de novo com Error 530)
            batch_size = 3 
            
            for i in range(0, total, batch_size):
                lote_items = items_to_process[i:min(i+batch_size, total)]
                
                # Atualiza o botão laranja
                curr_count = min(i + batch_size, total)
                self.after(0, lambda c=curr_count: self.btn_process_pending.configure(
                    text=f"PROCESSING... ({c}/{total})"
                ))
                
                futures_list = []
                # Dispara os 3 links simultaneamente
                for item in lote_items:
                    item['processed'] = True
                    self.log_message(f"Processando simultâneo: {item['url']}")
                    futures_list.append(asyncio.run_coroutine_threadsafe(self.process_single(item['url']), self.loop))
                
                # Espera os 3 terminarem antes de puxar os próximos 3
                for f in futures_list:
                    try:
                        f.result() 
                    except Exception as e:
                        self.log_message(f"Erro no lote: {e}")

            # Finalização
            self.after(0, lambda: self.btn_process_pending.configure(text="PROCESSAMENTO CONCLUÍDO"))
            self.after(0, lambda: messagebox.showinfo("Fim do Trabalho", "✅ Todos os links pendentes foram processados com sucesso!"))

        # Inicia a fila em uma Thread separada
        threading.Thread(target=process_worker, daemon=True).start()

    async def process_single(self, url):
        mode = "Automático"
        
        # 1. Fetch Metadata First (Lightweight)
        title, duration = self.miner.fetch_link_metadata(url)
        
        # 2. Smart Filter Logic (Jules Logic)
        if title == "Unknown":
            self.log_message("⚠️ Título desconhecido. Baixando para conferência no Shazam...")
        else:
            # Se temos o título, deixamos o Groq filtrar
            is_music = await asyncio.to_thread(self.miner.is_it_music, title)
            if "NO" in is_music:
                self.log_message(f"⏩ Pular: Não é música ({title})")
                return

        ref_path, info = await self.miner.download_with_fallback(url, DIR_REF, mode=mode)
        if not ref_path:
            self.log_message(f"Failed to download ref: {url}")
            return

        original_title = info.get('title', 'Unknown')
        title, artist = await self.miner.precision_recognition(ref_path)

        if not title:
            clean_title = original_title
            clean_title = re.sub(r'#\w+', '', clean_title)
            clean_title = re.sub(r'@\w+', '', clean_title)
            clean_title = " ".join(clean_title.split())
            title = clean_title if clean_title else "Unknown Track"
            artist = info.get('uploader', 'Unknown Artist')
            self.log_message(f"Shazam failed. Fallback to: {title} - {artist}")

        identified_text = f"{title} - {artist}"
        master_info = await asyncio.to_thread(self.miner.search_master, title, artist)

        is_video_candidate = False
        if master_info:
            m_title = master_info.get('title', '').lower()
            if ('video' in m_title or 'clip' in m_title) and 'audio' not in m_title:
                is_video_candidate = True

        status_text = "Not Found"
        if master_info:
            dur_diff = master_info['duration']
            v_tag = " [VIDEO]" if is_video_candidate else " [AUDIO]"
            status_text = f"Found ({dur_diff}s){v_tag}"
        else:
            status_text = "No Master Found"

        self.after(0, lambda: self.add_to_grid(original_title, identified_text, status_text, master_info, ref_path, is_video_candidate))

    def add_to_grid(self, original, identified, status, master_info, ref_path, is_video_candidate, is_pending=False):
        r = self.grid_row_idx

        if is_pending:
            self.pending_items.append({'url': original, 'row_id': r, 'processed': False})

        lbl_orig = ctk.CTkLabel(self.scroll_frame, text=original[:30]+"...")
        lbl_orig.grid(row=r, column=0, padx=5, sticky="w")

        lbl_ident = ctk.CTkLabel(self.scroll_frame, text=identified[:30]+"...")
        lbl_ident.grid(row=r, column=1, padx=5, sticky="w")

        lbl_stat = ctk.CTkLabel(self.scroll_frame, text=status)
        lbl_stat.grid(row=r, column=2, padx=5, sticky="w")

        btn_frame = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        btn_frame.grid(row=r, column=3, padx=5, sticky="w")

        if is_pending:
            cmd_mine = lambda: self.start_mining_item(r, original)
            btn_mine = ctk.CTkButton(btn_frame, text="Mine", width=40, fg_color="#D35400", command=cmd_mine)
            btn_mine.pack(side="left", padx=2)

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
            cmd_discard = lambda: self.discard_item(r, ref_path)
            btn_discard = ctk.CTkButton(btn_frame, text="✖", width=30, fg_color="red", command=cmd_discard)
            btn_discard.pack(side="left", padx=2)

        self.grid_row_idx += 1

    def remove_grid_row_visual(self, row_idx):
         self.log_message("Item removed from list.")
         for item in self.pending_items:
             if item['row_id'] == row_idx:
                 item['processed'] = True

    def start_mining_item(self, row_idx, url):
        self.log_message(f"Starting mining for: {url}")
        for item in self.pending_items:
             if item['row_id'] == row_idx:
                 item['processed'] = True
        asyncio.run_coroutine_threadsafe(self.process_single(url), self.loop)

    def accept_item(self, row_idx, identified_name, master_info, is_video):
        self.log_message(f"Accepted: {identified_name}")
        threading.Thread(target=self.download_final, args=(identified_name, master_info, is_video), daemon=True).start()

    def discard_item(self, row_idx, ref_path):
        self.log_message(f"Discarded item. Removed ref.")
        if ref_path and os.path.exists(ref_path):
            try:
                os.remove(ref_path)
            except: pass

    def download_final(self, name, info, is_video):
        url = info.get('url') or info.get('webpage_url')
        
        # Groq Cleaning for Final Filename
        cleaned_name = self.miner.clean_title_with_groq(name)
        sanitized = self.miner.sanitize_filename(cleaned_name) # Double check

        opts = self.miner.get_ydl_opts(DIR_MASTER, is_video=is_video)
        opts['outtmpl'] = f'{DIR_MASTER}/{sanitized}.%(ext)s'

        try:
            with YoutubeDL(opts) as ydl:
                ydl.download([url])
            self.log_message(f"DOWNLOAD COMPLETE: {sanitized}")

            if hasattr(os, 'sync'):
                os.sync()
            elif hasattr(os, 'fsync'):
                 pass
        except Exception as e:
            self.log_message(f"Final Download Failed: {e}")

if __name__ == "__main__":
    app = MinerApp()
    app.mainloop()