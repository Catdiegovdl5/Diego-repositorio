import os, subprocess, shutil
import sys

# Tenta encontrar o ffmpeg de forma dinâmica ou usa o caminho fixo se falhar
try:
    import imageio_ffmpeg
    FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()
except ImportError:
    FFMPEG_PATH = r"C:\Users\99196\AppData\Local\Programs\Python\Python312-32\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win32-v4.2.2.exe"

# Diretórios
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DIR_FINAL = os.path.join(SCRIPT_DIR, "04_IDENTIFICADOS_FINAL")
DIR_MP3 = os.path.join(SCRIPT_DIR, "07_PENDRIVE_MAURO_MP3")

os.makedirs(DIR_MP3, exist_ok=True)

def limpar_nome(nome_arquivo):
    """Remove extensões e sufixos indesejados como _6720"""
    nome_base = os.path.splitext(nome_arquivo)[0]
    # Remove sufixos comuns de downloads do YouTube/Instagram
    sufixos = ["_6720", "_original", "_hq", " (Official Video)", " (Lyrics)"]
    for s in sufixos:
        nome_base = nome_base.replace(s, "")
    return nome_base.strip()

def converter_para_mp3():
    if not os.path.exists(DIR_FINAL):
        print(f"❌ Erro: Pasta de origem '{DIR_FINAL}' não encontrada!")
        return

    arquivos = [f for f in os.listdir(DIR_FINAL) if f.lower().endswith(('.mp4', '.mp3', '.m4a', '.wav'))]
    total = len(arquivos)
    
    print(f"🚀 Iniciando conversão de {total} arquivos para MP3 Universal...")
    print(f"📂 Origem: {DIR_FINAL}")
    print(f"📂 Destino: {DIR_MP3}")
    print(f"🔧 FFMPEG: {FFMPEG_PATH}")

    convertidos = 0
    duplicatas_evitadas = 0
    analisados = set()

    # Ordena para processar arquivos "limpos" primeiro se possível, ou apenas alfabeticamente
    arquivos.sort()

    for i, arq in enumerate(arquivos):
        entrada = os.path.join(DIR_FINAL, arq)
        nome_base_limpo = limpar_nome(arq)
        nome_saida = f"{nome_base_limpo}.mp3"
        saida = os.path.join(DIR_MP3, nome_saida)
        
        # Evita processar a mesma música duas vezes (ex: videoclipe e áudio separado)
        if nome_base_limpo.lower() in analisados:
            print(f"⏩ [Pular] Duplicata interna: {arq} (já processado como {nome_base_limpo})")
            duplicatas_evitadas += 1
            continue

        if os.path.exists(saida):
            print(f"⏩ [Pular] Arquivo já existe: {nome_saida}")
            analisados.add(nome_base_limpo.lower())
            continue
            
        analisados.add(nome_base_limpo.lower())

        # Tenta extrair Artista e Título do nome do arquivo
        # Padrão esperado: "Artista - Título"
        parts = nome_base_limpo.split(" - ", 1)
        if len(parts) == 2:
            artista, titulo = parts[0].strip(), parts[1].strip()
        else:
            artista, titulo = "Desconhecido", nome_base_limpo.strip()

        print(f"[{i+1}/{total}] 🎵 {artista} - {titulo}...")
        
        # Comando FFMPEG com Metadados ID3 v2.3 (mais compatível com carros antigos)
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
            # Roda o comando silenciosamente (exceto erros)
            result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            if result.returncode != 0:
                print(f"❌ Erro ao converter {arq}: {result.stderr.decode('utf-8', errors='ignore')}")
            else:
                convertidos += 1
        except Exception as e:
            print(f"❌ Falha crítica no arquivo {arq}: {e}")

    print(f"\n🏆 PROCESSO FINALIZADO!")
    print(f"✅ Músicas Prontas: {convertidos}")
    print(f"♻️ Duplicatas Removidas: {duplicatas_evitadas}")
    print(f"📂 Pasta final: {DIR_MP3}")

if __name__ == "__main__":
    converter_para_mp3()
