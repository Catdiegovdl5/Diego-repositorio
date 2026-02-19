import os, asyncio, subprocess, shutil
from shazamio import Shazam
from groq import Groq

# CONFIGURAÇÕES DE ELITE
GROQ_KEY = "API_KEY_AQUI"
# UPDATED TO ABSOLUTE PATHS FOR ROBUSTNESS
BASE_DIR = r"c:\Users\99196\Documents\Diego-repositorio"
DIR_ORIGEM = os.path.join(BASE_DIR, "02_ORIGINAIS_REFERENCIA")
DIR_FINAL = os.path.join(BASE_DIR, "04_IDENTIFICADOS_FINAL")
DIR_REVISAO = os.path.join(BASE_DIR, "05_REVISAO_MANUAL")

# CAMINHO DO FFMPEG (Verificado no seu log)
FFMPEG_PATH = r"C:\Users\99196\AppData\Local\Programs\Python\Python312-32\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win32-v4.2.2.exe"

client = Groq(api_key=GROQ_KEY)
for d in [DIR_FINAL, DIR_REVISAO]: os.makedirs(d, exist_ok=True)

async def identificar_musica(caminho_arquivo):
    shazam = Shazam()
    temp_audio = f"temp_{os.getpid()}.wav" # WAV é imune ao erro 'divide by zero'
    try:
        # Pula 15s de intro e ouve 12s de refrão em modo mono (mais leve)
        cmd = [FFMPEG_PATH, "-y", "-i", caminho_arquivo, "-ss", "00:00:15", "-t", "12", "-ar", "44100", "-ac", "1", temp_audio]
        subprocess.run(cmd, check=True, capture_output=True)
        
        out = await shazam.recognize(temp_audio)
        track = out.get('track', {})
        if track:
            return f"{track.get('subtitle')} - {track.get('title')}"
    except Exception as e:
        print(f"Erro no áudio: {e}")
    finally:
        if os.path.exists(temp_audio): 
            try: os.remove(temp_audio)
            except: pass
    return None

def limpar_nome_groq(nome_sujo):
    try:
        chat = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": f"Clean this song name for a file. Return ONLY 'Artist - Name'. No emojis. Max 50 chars: {nome_sujo}"}]
        )
        limpo = chat.choices[0].message.content
        return "".join(x for x in limpo if x.isalnum() or x in "._- ")
    except: return "Música Desconhecida"

async def main():
    if not os.path.exists(DIR_ORIGEM):
        print(f"Pasta {DIR_ORIGEM} não existe!")
        return

    arquivos = [f for f in os.listdir(DIR_ORIGEM) if f.lower().strip().endswith(('.mp4', '.mp3'))]
    print(f"🚀 Varrendo {len(arquivos)} arquivos da pasta de Referência...")

    for arq in arquivos:
        caminho = os.path.join(DIR_ORIGEM, arq)
        print(f"🎧 Escaneando: {arq[:30]}...")
        
        resultado = await identificar_musica(caminho)
        
        if resultado:
            nome_limpo = limpar_nome_groq(resultado)
            destino = os.path.join(DIR_FINAL, f"{nome_limpo}.mp4")
            # Duplicate handling
            if os.path.exists(destino):
                 destino = os.path.join(DIR_FINAL, f"{nome_limpo}_{os.getpid()}.mp4")
            
            try:
                shutil.move(caminho, destino)
                print(f"✅ IDENTIFICADO: {nome_limpo}")
            except Exception as e:
                 print(f"Erro ao mover: {e}")
        else:
            destino = os.path.join(DIR_REVISAO, arq)
            try:
                shutil.move(caminho, destino)
                print(f"⚠️ Sem registro. Movido para Revisão.")
            except Exception as e:
                print(f"Erro ao mover para revisão: {e}")

if __name__ == "__main__":
    asyncio.run(main())
