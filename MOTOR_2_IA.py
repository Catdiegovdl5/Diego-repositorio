import os, shutil, time, hashlib, hmac, base64, requests, subprocess, json, asyncio
import imageio_ffmpeg
from shazamio import Shazam

# --- INJEÇÃO DO FFMPEG NO SISTEMA ---
ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
os.environ["PATH"] += os.pathsep + os.path.dirname(ffmpeg_path)

CONFIG = {
    'access_key': "16c15aaefa0a10af964b085bd9a3cebc",
    'access_secret': "jdcfprIGFStvczF2BdTx7keSxb3yyJdqJwaKGRvI",
    'host': "identify-us-west-2.acrcloud.com",
    'ffmpeg': ffmpeg_path,
    'repo': r"C:\Users\99196\Documents\Diego-repositorio"
}

FILA = os.path.join(CONFIG['repo'], "00_FILA_TIKTOK")
PASTAS = {
    'ref': os.path.join(CONFIG['repo'], "04_IDENTIFICADOS_FINAL"),
    'mp3': os.path.join(CONFIG['repo'], "08_MUSICAS_COMPLETAS_MAURO"),
    'err': os.path.join(CONFIG['repo'], "09_MUSICAS_ERRADAS")
}
for p in PASTAS.values(): os.makedirs(p, exist_ok=True)
os.makedirs(FILA, exist_ok=True)

# 🛑 O NOVO FILTRO DE OURO (ANTI-LIXO)
def filtro_lixo_tiktok(nome):
    if not nome: return False  # Se não achou nada, não é lixo, é "desconhecido"
    termos_proibidos = [
        'som original', 'original sound', 'sonido original', 
        'son original', 'оригинальный звук', 'eredeti hang',
        'dźwięk oryginalny', 'suono originale', 'nhạc nền'
    ]
    nome_baixo = nome.lower()
    for termo in termos_proibidos:
        if termo in nome_baixo: return True
    
    # Se o nome for muito curto (ex: "A", "Beat"), também é lixo
    if len(nome.strip()) <= 4: return True 
    return False

# --- MOTORES DE IA ---
def identificar_acr(caminho):
    timestamp = str(int(time.time()))
    sign = base64.b64encode(hmac.new(CONFIG['access_secret'].encode('ascii'), f"POST\n/v1/identify\n{CONFIG['access_key']}\naudio\n1\n{timestamp}".encode('ascii'), digestmod=hashlib.sha1).digest()).decode('ascii')
    try:
        with open(caminho, 'rb') as f:
            r = requests.post(f"http://{CONFIG['host']}/v1/identify", files={'sample': f}, data={'access_key': CONFIG['access_key'], 'sample_bytes': os.path.getsize(caminho), 'timestamp': timestamp, 'signature': sign, 'data_type': 'audio', "signature_version": "1"}, timeout=25)
            res = r.json()
            if res.get('status', {}).get('msg') == 'Success': return f"{res['metadata']['music'][0].get('artists', [{}])[0].get('name')} - {res['metadata']['music'][0].get('title')}"
    except: pass
    return None

async def identificar_shazam(caminho):
    try:
        out = await Shazam().recognize(caminho)
        if 'track' in out: return f"{out['track']['subtitle']} - {out['track']['title']}"
    except: pass
    return None

def extrair_metadados(url):
    try:
        res = subprocess.run(["yt-dlp", "--dump-json", "--quiet", "--no-warnings", url], capture_output=True, text=True)
        if res.returncode == 0:
            d = json.loads(res.stdout)
            if d.get('track') and d.get('artist'): return f"{d.get('artist')} - {d.get('track')}"
            clean = d.get('title', '').split('#')[0].strip()
            if len(clean) > 5: return clean
    except: pass
    return None

def vigiar_fila():
    print("\n============================================================")
    print("🧠 MOTOR 2 (V5) LIGADO: MODO SNIPER DE ALTA PRECISÃO")
    print("   Bloqueio Rigoroso de 'Som Original' e Metadados Falsos")
    print("============================================================")
    print("📂 Vigiando a fila... (Pressione CTRL+C para parar)\n")

    while True:
        try:
            arquivos = sorted([f for f in os.listdir(FILA) if f.endswith('.mp4')])
        except:
            arquivos = []
            
        if not arquivos:
            time.sleep(3) 
            continue
            
        video = os.path.join(FILA, arquivos[0])
        txt_url = video.replace(".mp4", ".txt")
        audio_temp = video.replace(".mp4", ".mp3")
        
        print(f"\n⚙️ Analisando: {arquivos[0]}")
        
        url_original = ""
        if os.path.exists(txt_url):
            try:
                with open(txt_url, "r") as f: url_original = f.read().strip()
            except: pass

        # SANITIZADOR
        subprocess.run([CONFIG['ffmpeg'], "-y", "-i", video, "-t", "15", "-vn", "-ar", "44100", "-ac", "1", "-b:a", "64k", audio_temp], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        nome = None
        origem = ""
        
        if os.path.exists(audio_temp):
            nome = identificar_acr(audio_temp)
            if nome: origem = "ACRCloud"
            
            if not nome:
                nome = asyncio.run(identificar_shazam(audio_temp))
                if nome: origem = "Shazam"
        
        if not nome and url_original:
            nome_meta = extrair_metadados(url_original)
            if nome_meta:
                nome = nome_meta
                origem = "Metadados"

        # 🛑 AVALIAÇÃO FINAL DO FILTRO DE OURO
        bloqueado = False
        if nome:
            if filtro_lixo_tiktok(nome):
                print(f"   ⛔ BLOQUEADO: '{nome}' foi classificado como LIXO/Genérico.")
                bloqueado = True
                nome = None # Mata a variável para não baixar

        if nome:
            nome_limpo = "".join(x for x in nome if x.isalnum() or x in "._- ")[:60].strip()
            print(f"   ✨ APROVADO via {origem}: {nome_limpo}")
            
            ref = os.path.join(PASTAS['ref'], f"{nome_limpo}.mp4")
            if not os.path.exists(ref): 
                try: shutil.copy(video, ref)
                except: pass

            mp3 = os.path.join(PASTAS['mp3'], f"{nome_limpo}.mp3")
            if not os.path.exists(mp3):
                # Busca aprimorada para focar no áudio oficial
                busca = f"ytsearch1:{nome} official audio"
                cmd_yt = ["yt-dlp", "--extract-audio", "--audio-format", "mp3", "--audio-quality", "192K", "--ffmpeg-location", CONFIG['ffmpeg'], "--match-filter", "duration < 600", "--output", mp3, "--no-playlist", "--quiet", "--no-warnings", busca]
                subprocess.run(cmd_yt)
                if os.path.exists(mp3): print("   ✅ MP3 Baixado com precisão!")
                else: print("   ⛔ Bloqueado pelo YouTube (Vídeo > 10min)")
            else:
                print("   ⏩ Já existe no acervo.")
        
        elif not bloqueado: # Se não achou nada e não foi bloqueado explicitamente
            print("   ❌ Nenhuma IA reconheceu o áudio.")

        # LIXEIRA
        for f in [video, txt_url, audio_temp]:
            try:
                if os.path.exists(f): os.remove(f)
            except: pass

if __name__ == "__main__":
    vigiar_fila()
