import os
import subprocess
import imageio_ffmpeg

# Caminhos das pastas
DIR_WEBM = r"C:\Users\99196\Documents\Diego-repositorio\08_MUSICAS_COMPLETAS_MAURO"

# Garante que o diretório existe
if not os.path.exists(DIR_WEBM):
    os.makedirs(DIR_WEBM)

try:
    FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()
except Exception as e:
    print(f"Erro ao obter executável do FFmpeg: {e}")
    FFMPEG_EXE = "ffmpeg" # Fallback tenta usar do PATH

def converter_tudo():
    if not os.path.exists(DIR_WEBM):
        print(f"Erro: Diretório não encontrado: {DIR_WEBM}")
        return

    arquivos = [f for f in os.listdir(DIR_WEBM) if f.endswith('.webm')]
    print(f"🚀 Iniciando conversão de {len(arquivos)} arquivos para MP3...")

    for i, arq in enumerate(arquivos, 1):
        entrada = os.path.join(DIR_WEBM, arq)
        saida = os.path.join(DIR_WEBM, arq.replace('.webm', '.mp3'))
        
        print(f"[{i}/{len(arquivos)}] 🔄 Convertendo: {arq}")
        
        # Comando para converter mantendo a qualidade
        # Adicionei aspas ao redor do executável caso tenha espaços, mas subprocess.run lida com lista
        cmd = [FFMPEG_EXE, "-i", entrada, "-vn", "-ab", "192k", "-ar", "44100", "-y", saida]
        
        try:
            # subprocess.run é mais seguro que os.system
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            # Verifica se o arquivo de saída foi criado antes de remover a entrada
            if os.path.exists(saida) and os.path.getsize(saida) > 0:
                os.remove(entrada) # Apaga o .webm depois de converter
                print(f"   ✅ Sucesso! .webm removido.")
            else:
                print(f"   ⚠️ Conversão parece ter falhado (arquivo de saída inexistente ou vazio). Mantendo original.")
                
        except subprocess.CalledProcessError as e:
            print(f"❌ Erro no FFmpeg para o arquivo: {arq} - {e}")
        except Exception as e:
            print(f"❌ Erro inesperado no arquivo: {arq} - {e}")

    print("\n✅ TUDO CONVERTIDO! Agora a pasta 08 está cheia de MP3 para o Mauro.")

if __name__ == "__main__":
    converter_tudo()
