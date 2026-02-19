import os, subprocess
import sys

# Tenta configurar o FFMPEG dinamicamente para garantir que funcione
try:
    import imageio_ffmpeg
    FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()
except ImportError:
    # Caminho fallback caso a biblioteca não seja encontrada (o caminho original sugerido)
    FFMPEG_PATH = r"C:\Users\99196\AppData\Local\Programs\Python\Python312-32\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win32-v4.2.2.exe"

DIR_FINAL = r"C:\Users\99196\Documents\Diego-repositorio\04_IDENTIFICADOS_FINAL"
DIR_MP3 = r"C:\Users\99196\Documents\Diego-repositorio\07_PENDRIVE_MAURO_MP3"

os.makedirs(DIR_MP3, exist_ok=True)

def converter():
    if not os.path.exists(DIR_FINAL):
        print(f"❌ Erro: Pasta '{DIR_FINAL}' não encontrada.")
        return

    arquivos = [f for f in os.listdir(DIR_FINAL) if f.lower().endswith(('.mp4', '.mp3', '.m4a', '.wav'))]
    processados = set()
    convertidos = 0
    pulados = 0
    erros = 0
    
    print(f"🚀 Iniciando Conversão Inteligente para o Mauro...")
    print(f"📂 Origem: {DIR_FINAL}")
    print(f"📂 Destino: {DIR_MP3}")

    for i, arq in enumerate(arquivos):
        # Lógica para limpar o nome e ignorar duplicatas
        nome_base = arq
        
        # Remove extensão
        base_sem_ext = os.path.splitext(arq)[0]
        
        # Remove sufixos comuns de downloads (ajuste conforme necessidade)
        remove_list = ['_6720', '_480p', '_720p', '_1080p', '(Official Video)', '(Lyrics)', ' [Official Video]']
        for item in remove_list:
            base_sem_ext = base_sem_ext.replace(item, "")
            
        nome_limpo = base_sem_ext.strip()
        
        # Normaliza para check de duplicatas (lowercase)
        chave_duplicata = nome_limpo.lower()
        
        if chave_duplicata in processados:
            print(f"⏩ [Duplicata] Ignorando '{arq}' (já processado como '{nome_limpo}')")
            pulados += 1
            continue
            
        processados.add(chave_duplicata)
        
        entrada = os.path.join(DIR_FINAL, arq)
        saida = os.path.join(DIR_MP3, f"{nome_limpo}.mp3")

        # Pula se o MP3 já existir na pasta de destino (e tiver tamanho > 0)
        if os.path.exists(saida) and os.path.getsize(saida) > 0:
            print(f"⏩ [Existe] '{nome_limpo}.mp3' já está pronto.")
            pulados += 1
            continue

        print(f"[{i+1}/{len(arquivos)}] 🎵 Convertendo: {nome_limpo}...")
        
        # Tenta extrair metadados básicos do nome do arquivo
        parts = nome_limpo.split(' - ', 1)
        if len(parts) == 2:
            artista, titulo = parts[0], parts[1]
        else:
            artista, titulo = "Desconhecido", nome_limpo

        cmd = [
            FFMPEG_PATH, "-y", 
            "-i", entrada, 
            "-vn", 
            "-ar", "44100", 
            "-ac", "2", 
            "-b:a", "192k", 
            "-id3v2_version", "3",
            "-metadata", f"title={titulo}",
            "-metadata", f"artist={artista}",
            "-metadata", "album=Seleção Mauro",
            saida
        ]
        
        try:
            # Executa ffmpeg
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            convertidos += 1
        except subprocess.CalledProcessError:
            print(f"❌ Erro ao converter: {arq}")
            erros += 1
        except Exception as e:
            print(f"❌ Erro inesperado em {arq}: {e}")
            erros += 1

    print(f"\n🏆 FINALIZADO!")
    print(f"✅ Convertidos: {convertidos}")
    print(f"⏩ Pulados (Duplicatas/Existentes): {pulados}")
    print(f"❌ Erros: {erros}")
    print(f"📂 Pasta Pronta: {DIR_MP3}")

if __name__ == "__main__":
    converter()
