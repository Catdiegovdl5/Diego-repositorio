import os, shutil, time, hashlib, hmac, base64, requests, subprocess, tkinter as tk
import imageio_ffmpeg, re, uuid, json, asyncio
from shazamio import Shazam

# --- CONFIGURAÇÕES TÉCNICAS ---
CONFIG = {
    'access_key': "16c15aaefa0a10af964b085bd9a3cebc",
    'access_secret': "jdcfprIGFStvczF2BdTx7keSxb3yyJdqJwaKGRvI",
    'host': "identify-us-west-2.acrcloud.com",
    'ffmpeg': imageio_ffmpeg.get_ffmpeg_exe(),
    'repo': r"C:\Users\99196\Documents\Diego-repositorio",
    'whatsapp_file': "Conversa do WhatsApp com Mauro.txt"
}

# Garante que o FFmpeg esteja no PATH (necessário para Shazam/pydub)
os.environ["PATH"] += os.pathsep + os.path.dirname(CONFIG['ffmpeg'])

PASTAS = {
    'referencia': os.path.join(CONFIG['repo'], "04_IDENTIFICADOS_FINAL"),
    'completas': os.path.join(CONFIG['repo'], "08_MUSICAS_COMPLETAS_MAURO"),
    'erradas': os.path.join(CONFIG['repo'], "09_MUSICAS_ERRADAS"),
    'temp': os.path.join(CONFIG['repo'], "TEMP_SAMPLES")
}

for p in PASTAS.values(): os.makedirs(p, exist_ok=True)

# ============================================================
# MÉTODOS DE IDENTIFICAÇÃO (CASCATA DE ELITE)
# ============================================================

def extrair_links():
    caminho_txt = os.path.join(CONFIG['repo'], CONFIG['whatsapp_file'])
    if not os.path.exists(caminho_txt):
        print(f"❌ Arquivo não encontrado: {caminho_txt}")
        return []
    with open(caminho_txt, "r", encoding="utf-8") as f:
        texto = f.read()
    return list(set(re.findall(r'https://\S+tiktok\S+', texto)))

# MOTOR 1: ACRCloud
def identificar_acr(caminho):
    timestamp = str(int(time.time()))
    string_to_sign = f"POST\n/v1/identify\n{CONFIG['access_key']}\naudio\n1\n{timestamp}"
    sign = base64.b64encode(
        hmac.new(CONFIG['access_secret'].encode('ascii'),
                 string_to_sign.encode('ascii'),
                 digestmod=hashlib.sha1).digest()
    ).decode('ascii')
    data = {
        'access_key': CONFIG['access_key'],
        'sample_bytes': os.path.getsize(caminho),
        'timestamp': timestamp,
        'signature': sign,
        'data_type': 'audio',
        "signature_version": "1"
    }
    try:
        with open(caminho, 'rb') as f:
            r = requests.post(
                f"http://{CONFIG['host']}/v1/identify",
                files={'sample': f}, data=data, timeout=25
            )
            res = r.json()
            if res.get('status', {}).get('msg') == 'Success':
                if 'metadata' in res and 'music' in res['metadata'] and len(res['metadata']['music']) > 0:
                    m = res['metadata']['music'][0]
                    artista = m.get('artists', [{}])[0].get('name', 'Desconhecido')
                    titulo = m.get('title', 'Sem Titulo')
                    return f"{artista} - {titulo}"
    except Exception as e:
        print(f"      ⚠️ Erro ACRCloud: {e}")
    return None

# MOTOR 2: Shazam (Apple)
async def _shazam_recognize(caminho):
    shazam = Shazam()
    out = await shazam.recognize(caminho)
    if 'track' in out:
        subtitle = out['track'].get('subtitle', 'Desconhecido')
        title = out['track'].get('title', 'Sem Titulo')
        return f"{subtitle} - {title}"
    return None

def identificar_shazam(caminho):
    try:
        return asyncio.run(_shazam_recognize(caminho))
    except Exception as e:
        print(f"      ⚠️ Erro Shazam: {e}")
    return None

# MOTOR 3: Metadados Ocultos do TikTok
def extrair_metadados(url):
    cmd = ["yt-dlp", "--dump-json", "--quiet", "--no-warnings", url]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if res.returncode == 0 and res.stdout.strip():
            data = json.loads(res.stdout)
            track = data.get('track')
            artist = data.get('artist')
            if track and artist:
                return f"{artist} - {track}"
            if track:
                return track
            title = data.get('title', '')
            clean_title = re.split(r'#|@', title)[0].strip()
            if len(clean_title) > 5:
                return clean_title
    except Exception as e:
        print(f"      ⚠️ Erro Metadados: {e}")
    return None

def limpar_nome(nome):
    """Remove caracteres inválidos para nome de arquivo."""
    return "".join(x for x in nome if x.isalnum() or x in "._- ")[:100].strip()

# 🛡️ SANITIZADOR: Extrai 15s de áudio limpo do vídeo
def sanitizar_audio(video_path, audio_path):
    cmd = [
        CONFIG['ffmpeg'], "-y", "-i", video_path,
        "-t", "15", "-vn", "-ar", "44100", "-ac", "1", "-b:a", "64k",
        audio_path
    ]
    result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return result.returncode == 0 and os.path.exists(audio_path)

# ============================================================
# LOOP PRINCIPAL - CASCATA V4 (SANITIZADOR + FILTRO ANTI-ORAÇÕES)
# ============================================================
def processar_novos_links():
    links = extrair_links()
    if not links:
        print("❌ Nenhum link encontrado.")
        return

    # ============================================================
    # 🔥 CONFIGURAÇÃO: Retoma de onde parou
    # Mude para 0 se quiser processar TUDO desde o início
    # ============================================================
    LINKS_PARA_PULAR = 12

    total = len(links)
    print(f"\n🎯 Encontrados {total} links. Retomando do {LINKS_PARA_PULAR + 1}...")
    print("-" * 60)

    contadores = {'acr': 0, 'shazam': 0, 'meta': 0, 'falha': 0, 'skip': 0, 'bloqueado': 0}

    for i, url in enumerate(links, 1):
        if i <= LINKS_PARA_PULAR:
            continue

        print(f"\n[{i}/{total}] 🔗 {url}")

        nome_unico = uuid.uuid4().hex[:6]
        temp_video = os.path.join(PASTAS['temp'], f"vid_{nome_unico}.mp4")
        temp_audio = os.path.join(PASTAS['temp'], f"clean_{nome_unico}.mp3")

        # 1. Baixa o TikTok
        cmd_tk = [
            "yt-dlp", "-o", temp_video, "--max-filesize", "15M",
            "--quiet", "--no-warnings", "--force-overwrites", url
        ]
        try:
            result = subprocess.run(cmd_tk, timeout=60)
            if result.returncode != 0:
                print("   ❌ Erro ao acessar TikTok (Privado/Apagado).")
                contadores['falha'] += 1
                continue
        except FileNotFoundError:
            print("❌ yt-dlp não encontrado! Instale com: pip install yt-dlp")
            return
        except subprocess.TimeoutExpired:
            print("   ❌ Timeout ao baixar TikTok. Pulando...")
            contadores['falha'] += 1
            continue

        # PROTEÇÃO: Arquivo fantasma (carrossel)
        if not os.path.exists(temp_video):
            print("   ❌ Download fantasma (Carrossel de Fotos).")
            contadores['falha'] += 1
            continue

        # 🛡️ SANITIZADOR: Extrai 15s de áudio limpo
        audio_limpo = sanitizar_audio(temp_video, temp_audio)

        # ============================================
        # A CASCATA DE ELITE - 3 MOTORES
        # ============================================
        nome_musica = None
        metodo_usado = ""

        if audio_limpo:
            # MOTOR 1: ACRCloud
            print("   🔍 Motor 1: ACRCloud...")
            nome_musica = identificar_acr(temp_audio)
            if nome_musica:
                metodo_usado = "ACRCloud"
                contadores['acr'] += 1

            # MOTOR 2: Shazam (se ACR falhou)
            if not nome_musica:
                print("   🔍 Motor 2: Shazam (Apple)...")
                nome_musica = identificar_shazam(temp_audio)
                if nome_musica:
                    metodo_usado = "Shazam"
                    contadores['shazam'] += 1
        else:
            print("   ⚠️ Vídeo sem áudio válido. Pulando para metadados...")

        # MOTOR 3: Metadados do TikTok (último recurso)
        if not nome_musica:
            print("   🔍 Motor 3: Metadados Ocultos do TikTok...")
            nome_musica = extrair_metadados(url)
            if nome_musica:
                metodo_usado = "Metadados"
                contadores['meta'] += 1

        # ============================================
        # RESULTADO DA CASCATA
        # ============================================
        if not nome_musica:
            print("   ❌ IMPOSSÍVEL IDENTIFICAR. Todas as IAs falharam.")
            contadores['falha'] += 1
        else:
            nome_limpo = limpar_nome(nome_musica)
            print(f"   ✨ ENCONTRADA via {metodo_usado}: {nome_limpo}")

            # Salva a referência original (clip do TikTok)
            ref_path = os.path.join(PASTAS['referencia'], f"{nome_limpo}.mp4")
            if not os.path.exists(ref_path):
                try:
                    shutil.copy(temp_video, ref_path)
                except Exception as e:
                    print(f"   ⚠️ Erro ao copiar referência: {e}")

            # Baixa a MÚSICA COMPLETA em MP3 (COM FILTRO ANTI-ORAÇÕES)
            saida_completa = os.path.join(PASTAS['completas'], f"{nome_limpo}.mp3")
            if not os.path.exists(saida_completa):
                print(f"   📥 Baixando versão COMPLETA do YouTube (máx 10min)...")
                busca = f"ytsearch1:{nome_musica} official audio"
                cmd_yt = [
                    "yt-dlp",
                    "--extract-audio",
                    "--audio-format", "mp3",
                    "--audio-quality", "192K",
                    "--ffmpeg-location", CONFIG['ffmpeg'],
                    "--match-filter", "duration < 600",  # 🛡️ BLOQUEIA ÁUDIO > 10 MINUTOS
                    "--output", saida_completa,
                    "--no-playlist",
                    "--quiet", "--no-warnings",
                    busca
                ]
                retorno = subprocess.run(cmd_yt)
                if retorno.returncode == 0 and os.path.exists(saida_completa):
                    print("   ✅ MP3 Salvo!")
                else:
                    print("   ⛔ Bloqueado (Áudio > 10min ou Não Encontrado no YouTube).")
                    contadores['bloqueado'] += 1
            else:
                print("   ⏩ Já existe no repositório.")
                contadores['skip'] += 1

        # Limpa temporários
        for f in [temp_video, temp_audio]:
            try:
                if os.path.exists(f):
                    os.remove(f)
            except Exception:
                pass

    # ============================================
    # 📊 RELATÓRIO FINAL
    # ============================================
    print("\n" + "=" * 60)
    print("📊 RELATÓRIO FINAL DA VARREDURA V4")
    print("=" * 60)
    print(f"   🟢 Identificadas via ACRCloud:  {contadores['acr']}")
    print(f"   🟣 Identificadas via Shazam:    {contadores['shazam']}")
    print(f"   🟡 Identificadas via Metadados: {contadores['meta']}")
    print(f"   ⏩ Já existiam no repositório:  {contadores['skip']}")
    print(f"   ⛔ Bloqueadas (>10min):         {contadores['bloqueado']}")
    print(f"   🔴 Falhas totais:               {contadores['falha']}")
    total_proc = sum(contadores.values())
    print(f"   📁 Total processado:            {total_proc}")
    print("=" * 60)

# ============================================================
# INTERFACE DE AUDITORIA (QA FINAL)
# ============================================================
class AuditoriaUI:
    def __init__(self, root):
        self.root = root
        self.root.title("✅ Auditoria de Elite V4 - Diego vs Mauro")
        self.root.geometry("850x650")
        self.root.configure(bg="#0f172a")

        self.atualizar_lista()

        self.label_count = tk.Label(root, text="", font=("Arial", 14, "bold"), bg="#0f172a", fg="#38bdf8")
        self.label_count.pack(pady=15)
        self._update_count_label()

        self.listbox = tk.Listbox(root, width=100, height=22, font=("Consolas", 10), bg="#1e293b", fg="white", selectbackground="#3b82f6")
        for f in self.arquivos:
            self.listbox.insert(tk.END, f)
        self.listbox.pack(pady=10)

        f_btn = tk.Frame(root, bg="#0f172a")
        f_btn.pack(pady=10)
        tk.Button(f_btn, text="🎬 OUVIR REF (TikTok)", command=self.play_ref, bg="#f59e0b", font=("Arial", 10, "bold"), width=22).grid(row=0, column=0, padx=10)
        tk.Button(f_btn, text="🎵 OUVIR COMPLETA", command=self.play_full, bg="#10b981", fg="white", font=("Arial", 10, "bold"), width=22).grid(row=0, column=1, padx=10)
        tk.Button(f_btn, text="❌ MARCAR ERRADA", command=self.errada, bg="#ef4444", fg="white", font=("Arial", 10, "bold"), width=22).grid(row=1, column=0, columnspan=2, pady=15)
        tk.Button(root, text="🔄 Atualizar Lista", command=self.refresh, bg="#334155", fg="white", font=("Arial", 9)).pack()

    def _update_count_label(self):
        self.label_count.config(text=f"🎶 Músicas prontas para o Pendrive: {len(self.arquivos)}")

    def atualizar_lista(self):
        self.arquivos = [f for f in os.listdir(PASTAS['completas']) if f.endswith('.mp3')]
        self.arquivos.sort()

    def refresh(self):
        self.listbox.delete(0, tk.END)
        self.atualizar_lista()
        for f in self.arquivos:
            self.listbox.insert(tk.END, f)
        self._update_count_label()

    def play_ref(self):
        sel = self.listbox.curselection()
        if sel:
            nome = self.listbox.get(sel[0])
            base = os.path.splitext(nome)[0]
            p = os.path.join(PASTAS['referencia'], base + ".mp4")
            if os.path.exists(p):
                os.startfile(p)
            else:
                for f in os.listdir(PASTAS['referencia']):
                    if base in f:
                        os.startfile(os.path.join(PASTAS['referencia'], f))
                        return

    def play_full(self):
        sel = self.listbox.curselection()
        if sel:
            os.startfile(os.path.join(PASTAS['completas'], self.listbox.get(sel[0])))

    def errada(self):
        sel = self.listbox.curselection()
        if sel:
            nome = self.listbox.get(sel[0])
            try:
                shutil.move(
                    os.path.join(PASTAS['completas'], nome),
                    os.path.join(PASTAS['erradas'], nome)
                )
                print(f"🚩 Movido para ERRADAS: {nome}")
                self.listbox.delete(sel[0])
                self._update_count_label()
            except Exception:
                pass

# ============================================================
# MAIN - PAINEL DE CONTROLE
# ============================================================
if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("🚀 MAURO ULTIMATE ENGINE V4 - CASCATA + FILTRO ANTI-ORAÇÕES")
    print("   ACRCloud + Shazam + Metadados + Sanitizador + Filtro <10min")
    print("=" * 60)
    print("1 - Processar TUDO (WhatsApp → Sanitizar → Cascata → MP3)")
    print("2 - Abrir Painel de Auditoria (QA Final)")
    print("3 - Sair")

    escolha = input("\nEscolha: ")
    if escolha == "1":
        processar_novos_links()
    elif escolha == "2":
        root = tk.Tk()
        AuditoriaUI(root)
        root.mainloop()
