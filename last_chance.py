import os, asyncio, subprocess, shutil
from shazamio import Shazam

DIR_REVISAO = "05_REVISAO_MANUAL"
DIR_FINAL = "04_IDENTIFICADOS_FINAL"
DIR_LIXO = "06_LIXO_CONFIRMADO" # Onde o que não é música vai morar
FFMPEG_PATH = r"C:\Users\99196\AppData\Local\Programs\Python\Python312-32\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win32-v4.2.2.exe"

os.makedirs(DIR_LIXO, exist_ok=True)

async def scan_final(caminho):
    shazam = Shazam()
    temp_wav = f"last_{os.getpid()}.wav"
    try:
        # Tenta ouvir aos 80 segundos (refrão garantido)
        cmd = [FFMPEG_PATH, "-y", "-i", caminho, "-ss", "00:01:20", "-t", "12", "-ar", "44100", "-ac", "1", temp_wav]
        subprocess.run(cmd, check=True, capture_output=True)
        return await shazam.recognize(temp_wav)
    except: return None
    finally:
        if os.path.exists(temp_wav): os.remove(temp_wav)

async def main():
    if not os.path.exists(DIR_REVISAO):
        print(f"Pasta {DIR_REVISAO} não encontrada.")
        return

    arquivos = [f for f in os.listdir(DIR_REVISAO) if f.endswith(('.mp4', '.mp3'))]
    print(f"🎯 Varredura de Segurança Máxima em {len(arquivos)} arquivos...")

    for arq in arquivos:
        caminho = os.path.join(DIR_REVISAO, arq)
        res = await scan_final(caminho)
        track = res.get('track', {}) if res else {}
        
        if track:
            nome = f"{track.get('subtitle')} - {track.get('title')}"
            nome_clean = "".join(x for x in nome if x.isalnum() or x in "._- ")[:50]
            
            # Preserva extensão original
            ext = os.path.splitext(arq)[1]
            caminho_final = os.path.join(DIR_FINAL, f"{nome_clean}{ext}")
            
            shutil.move(caminho, caminho_final)
            print(f"✅ RECUPERADO NO REFRÃO: {nome_clean}")
        else:
            # Se falhou aos 80 segundos, move para a pasta de lixo
            shutil.move(caminho, os.path.join(DIR_LIXO, arq))
            print(f"🗑️ LIXO CONFIRMADO: {arq}")

if __name__ == "__main__":
    asyncio.run(main())
