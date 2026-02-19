import os
import subprocess
import imageio_ffmpeg
import sys

# PASTAS DO REPOSITÓRIO - Robustez
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DIR_IDENTIFICADOS = os.path.join(SCRIPT_DIR, "04_IDENTIFICADOS_FINAL")
if not os.path.exists(DIR_IDENTIFICADOS):
    DIR_IDENTIFICADOS = r"C:\Users\99196\Documents\Diego-repositorio\04_IDENTIFICADOS_FINAL"
    
DIR_COMPLETAS = os.path.join(SCRIPT_DIR, "08_MUSICAS_COMPLETAS_MAURO")
os.makedirs(DIR_COMPLETAS, exist_ok=True)

# Obtém o caminho exato do executável do ffmpeg
FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()
FFMPEG_DIR = os.path.dirname(FFMPEG_EXE)

def baixar_musicas_completas():
    # Pega os nomes e remove extensões
    arquivos = [f for f in os.listdir(DIR_IDENTIFICADOS) if f.lower().endswith(('.mp4', '.mp3', '.m4a', '.wav'))]
    
    # Extrai nomes base
    nomes_base = []
    for f in arquivos:
        base = os.path.splitext(f)[0]
        # Limpezas
        base = base.replace("_6720", "").replace("_original", "").strip()
        nomes_base.append(base)
        
    # Remove duplicatas
    nomes_base = sorted(list(set(nomes_base)))
    total = len(nomes_base)
    
    print(f"🚀 FFmpeg localizado: {FFMPEG_EXE}")
    print(f"🎵 Iniciando download de {total} MÚSICAS COMPLETAS...")
    print(f"📂 Destino: {DIR_COMPLETAS}")

    sucessos = 0
    erros = 0
    pulados = 0

    for i, nome_musica in enumerate(nomes_base, 1):
        if len(nome_musica) < 3: continue
        
        # Verifica se já existe algo parecido na pasta de destino
        # (yt-dlp pode salvar com título ligeiramente diferente)
        encontrado = False
        for f in os.listdir(DIR_COMPLETAS):
            # Se o nome buscado estiver contido no arquivo existente
            if nome_musica.lower() in f.lower():
                encontrado = True
                break
        
        if encontrado:
            print(f"[{i}/{total}] ✅ Já existe: {nome_musica}")
            pulados += 1
            continue

        print(f"[{i}/{total}] 📥 Baixando: {nome_musica}...")
        
        # Busca no YouTube pela versão oficial
        busca = f"ytsearch1:{nome_musica} official audio"
        
        cmd = [
            "yt-dlp",
            "--extract-audio",
            "--audio-format", "mp3",
            "--audio-quality", "192K",
            "--ffmpeg-location", FFMPEG_DIR, # yt-dlp costuma querer o DIRETÓRIO, não o exe
            "--output", os.path.join(DIR_COMPLETAS, f"{nome_musica}.%(ext)s"), # Força nome para evitar duplicatas futuras
            "--no-playlist",
            "--quiet",
            "--no-warnings",
            busca
        ]
        
        try:
            subprocess.run(cmd, check=True)
            sucessos += 1
        except Exception as e:
            # Tenta fallback apontando para o EXE se falhar com DIR (algumas versões variam)
            try:
                cmd[6] = FFMPEG_EXE # índice do location
                subprocess.run(cmd, check=True)
                sucessos += 1
            except Exception as e2:
                print(f"❌ Erro ao baixar {nome_musica}")
                erros += 1

    print("\n🏆 Fim do Download!")
    print(f"✅ Baixados: {sucessos}")
    print(f"⏩ Pulados: {pulados}")
    print(f"❌ Erros: {erros}")

if __name__ == "__main__":
    baixar_musicas_completas()
