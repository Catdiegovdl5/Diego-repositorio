import os, asyncio, subprocess, shutil
from shazamio import Shazam

# CONFIGURAÇÃO
DIR_REVISAO = "05_REVISAO_MANUAL"
DIR_FINAL = "04_IDENTIFICADOS_FINAL"
FFMPEG_PATH = r"C:\Users\99196\AppData\Local\Programs\Python\Python312-32\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win32-v4.2.2.exe"

async def deep_scan(caminho, tempo_inicio):
    shazam = Shazam()
    temp_wav = f"verify_{os.getpid()}.wav"
    try:
        # Pega um trecho mais a frente (tempo_inicio) para garantir o refrão
        cmd = [FFMPEG_PATH, "-y", "-i", caminho, "-ss", tempo_inicio, "-t", "12", "-ar", "44100", "-ac", "1", temp_wav]
        subprocess.run(cmd, check=True, capture_output=True)
        return await shazam.recognize(temp_wav)
    except: return None
    finally:
        if os.path.exists(temp_wav): os.remove(temp_wav)

async def main():
    # 1. TENTAR RESGATAR DA REVISÃO
    arquivos_revisao = [f for f in os.listdir(DIR_REVISAO) if f.endswith(('.mp4', '.mp3'))]
    print(f"🔎 Tentando resgatar {len(arquivos_revisao)} arquivos com Varredura Profunda...")

    for arq in arquivos_revisao:
        caminho = os.path.join(DIR_REVISAO, arq)
        # Tentativa aos 45 segundos (Refrão)
        res = await deep_scan(caminho, "00:00:45")
        track = res.get('track', {}) if res else {}
        
        if track:
            nome = f"{track.get('subtitle')} - {track.get('title')}"
            # Limpa nome para o Windows
            nome_clean = "".join(x for x in nome if x.isalnum() or x in "._- ")[:50]
            
            # Preserva a extensão original ao mover
            ext = os.path.splitext(arq)[1]
            caminho_final = os.path.join(DIR_FINAL, f"{nome_clean}{ext}")
            
            shutil.move(caminho, caminho_final)
            print(f"✨ RESGATADO: {nome_clean}")
        else:
            print(f"❌ Ainda não identificado: {arq}")

if __name__ == "__main__":
    asyncio.run(main())
