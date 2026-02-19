import os, asyncio, webbrowser, subprocess
import sys
import glob

# Tenta importar shazamio
try:
    from shazamio import Shazam
except ImportError:
    print("❌ Erro: Biblioteca 'shazamio' não encontrada.")
    print("Execute: pip install shazamio")
    sys.exit(1)

# CONFIGURAÇÕES
# Procura arquivo de links automaticamente na pasta ou em subpastas conhecidas
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
POSSIBLE_PATHS = [
    os.path.join(SCRIPT_DIR, "Links_Mauro_20260215_111455.txt"),
    os.path.join(SCRIPT_DIR, "03_EXPORTADOS", "Links_Mauro_*.txt"),
    os.path.join(SCRIPT_DIR, "Links_Mauro_*.txt")
]

ARQUIVO_LINKS = None
for path in POSSIBLE_PATHS:
    matches = glob.glob(path)
    if matches:
        ARQUIVO_LINKS = matches[0] # Pega o primeiro encontrado
        break

# Tenta encontrar ffmpeg automaticamente
try:
    import imageio_ffmpeg
    FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()
except ImportError:
    FFMPEG_PATH = r"C:\Users\99196\AppData\Local\Programs\Python\Python312-32\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win32-v4.2.2.exe"


async def identificar_por_link(url):
    shazam = Shazam()
    temp_wav = f"link_check_{os.getpid()}.wav"
    try:
        # Usa yt-dlp para pegar apenas a URL do áudio direto do link (muito rápido)
        # -g: get url, -f bestaudio: melhor áudio
        cmd = ["yt-dlp", "-g", "-f", "bestaudio", url]
        
        # Cria startupinfo para esconder janelas pop-up no Windows
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        
        res = subprocess.run(cmd, capture_output=True, text=True, startupinfo=startupinfo)
        audio_url = res.stdout.strip()
        
        if not audio_url: 
            return None

        # Extrai um pedaço do áudio direto da web usando ffmpeg
        # -t 10: 10 segundos
        subprocess.run([
            FFMPEG_PATH, "-y", "-ss", "00:00:05", "-i", audio_url, 
            "-t", "10", "-ar", "44100", "-ac", "1", temp_wav
        ], check=True, capture_output=True, startupinfo=startupinfo)
        
        return await shazam.recognize(temp_wav)
    except Exception as e: 
        # print(f"Erro na identificação: {e}") # Debug se necessário
        return None
    finally:
        if os.path.exists(temp_wav): 
            try:
                os.remove(temp_wav)
            except: pass

async def main():
    if not ARQUIVO_LINKS or not os.path.exists(ARQUIVO_LINKS):
        print(f"❌ Arquivo de Links não encontrado!")
        print(f"Procurei em: {[p for p in POSSIBLE_PATHS]}")
        return

    print(f"📂 Lendo links de: {os.path.basename(ARQUIVO_LINKS)}")
    
    with open(ARQUIVO_LINKS, "r", encoding="utf-8") as f:
        # Filtra linhas com tiktok.com
        links = [linha.strip() for linha in f if "tiktok.com" in linha]

    if not links:
        print("❌ Nenhum link do TikTok encontrado no arquivo.")
        return

    print(f"🤖 Iniciando Verificação Automática de {len(links)} links...")
    print("Pressione CTRL+C para parar a qualquer momento.\n")

    for i, url in enumerate(links):
        print(f"🎬 [{i+1}/{len(links)}] Verificando: {url}")
        
        # 1. Abre o vídeo no navegador para você ver
        webbrowser.open(url)
        
        # 2. Faz a análise automática via código (como se fosse a extensão)
        print("   ⏳ Analisando áudio do link...")
        res = await identificar_por_link(url)
        
        track = res.get('track', {}) if res else {}
        
        if track:
            titulo = track.get('title', 'Desconhecido')
            subtitulo = track.get('subtitle', 'Desconhecido')
            print(f"   🎵 IDENTIFICADO: {subtitulo} - {titulo}")
            print(f"   🔗 Shazam Link: {track.get('url', 'N/A')}")
        else:
            print("   ⚠️ Não é música (Provavelmente conversa/oração ou falha na extração)")
        
        print("\n👇 Ação necessária:")
        input("✅ Olhe o navegador, ouça e pressione ENTER para o próximo... (CTRL+C para sair)")
        print("-" * 50)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Verificação interrompida pelo usuário.")
        sys.exit(0)
