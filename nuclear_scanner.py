import os, asyncio, subprocess, shutil
from shazamio import Shazam

DIR_LIXO = "06_LIXO_CONFIRMADO"
DIR_FINAL = "04_IDENTIFICADOS_FINAL"
# Usamos o ffmpeg do imageio_ffmpeg, mas o ffprobe não existe lá. Vamos usar o próprio ffmpeg para pegar a duração.
FFMPEG_PATH = r"C:\Users\99196\AppData\Local\Programs\Python\Python312-32\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win32-v4.2.2.exe"

async def get_duration(caminho):
    try:
        # Executa ffmpeg -i para pegar metadados no stderr
        cmd = [FFMPEG_PATH, "-i", caminho]
        res = subprocess.run(cmd, capture_output=True, text=True)
        
        # Procura por "Duration: 00:00:00.00"
        for line in res.stderr.split('\n'):
            if "Duration" in line:
                # Exemplo: "  Duration: 00:00:05.12, start: 0.000000, bitrate: 1069 kb/s"
                try:
                    time_str = line.split("Duration:")[1].split(",")[0].strip()
                    h, m, s = time_str.split(':')
                    return float(h) * 3600 + float(m) * 60 + float(s)
                except:
                    pass
        return 0
    except: return 0

async def identificar(caminho):
    duracao = await get_duration(caminho)
    if duracao == 0: return None
    
    # Se o vídeo for curto (<20s), ouve aos 5s. Se for longo, ouve no meio.
    if duracao < 20:
        ponto_corte = "00:00:05"
    else:
        # Formata o tempo do meio
        meio = int(duracao / 2)
        h = meio // 3600
        m = (meio % 3600) // 60
        s = meio % 60
        ponto_corte = f"{h:02d}:{m:02d}:{s:02d}"
    
    shazam = Shazam()
    temp_wav = f"nuke_{os.getpid()}_{abs(hash(caminho))}.wav"
    try:
        # Tenta extrair trecho de áudio
        cmd = [FFMPEG_PATH, "-y", "-i", caminho, "-ss", ponto_corte, "-t", "10", "-ar", "44100", "-ac", "1", temp_wav]
        subprocess.run(cmd, check=True, capture_output=True)
        return await shazam.recognize(temp_wav)
    except: return None
    finally:
        if os.path.exists(temp_wav): os.remove(temp_wav)

async def processar_arquivo(arq, sem):
    async with sem:
        caminho = os.path.join(DIR_LIXO, arq)
        print(f"🧐 Analisando: {arq}...")
        
        try:
            res = await identificar(caminho)
            track = res.get('track', {}) if res else {}
            
            if track:
                nome = f"{track.get('subtitle')} - {track.get('title')}"
                nome_clean = "".join(x for x in nome if x.isalnum() or x in "._- ")[:50]
                
                # Preserva a extensão original ao recuperar
                ext = os.path.splitext(arq)[1]
                caminho_final = os.path.join(DIR_FINAL, f"{nome_clean}{ext}")
                
                shutil.move(caminho, caminho_final)
                print(f"✅ RECUPERADO: {nome_clean}")
            else:
                print(f"🗑️ Confirmado como Lixo/Conversa: {arq}")
                # Opcional: Se quiser deletar automaticamente o que passar por aqui e mudar de ideia, descomente:
                # os.remove(caminho)
                
        except Exception as e:
            print(f"Erro ao processar {arq}: {e}")

async def main():
    if not os.path.exists(DIR_LIXO):
        print(f"Pasta {DIR_LIXO} não encontrada.")
        return

    arquivos = [f for f in os.listdir(DIR_LIXO) if f.endswith(('.mp4', '.mp3'))]
    print(f"☢️ Iniciando Varredura Nuclear em {len(arquivos)} arquivos...")
    
    # Processa 5 arquivos ao mesmo tempo para ser rápido
    sem = asyncio.Semaphore(5)
    tasks = [processar_arquivo(f, sem) for f in arquivos]
    if tasks:
        await asyncio.gather(*tasks)
    else:
        print("Nenhum arquivo para processar.")

if __name__ == "__main__":
    asyncio.run(main())
