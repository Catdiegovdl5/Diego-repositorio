import os
import subprocess
import time

DIR_COMPLETAS = r"C:\Users\99196\Documents\Diego-repositorio\08_MUSICAS_COMPLETAS_MAURO"

def converter_webm_mp3():
    try:
        import imageio_ffmpeg
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        print(f"✅ FFmpeg encontrado em: {ffmpeg_exe}")
    except ImportError:
        print("❌ imageio-ffmpeg não instalado. Instalando...")
        try:
            subprocess.check_call(["pip", "install", "imageio-ffmpeg"])
            import imageio_ffmpeg
            ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
            print(f"✅ FFmpeg instalado e encontrado em: {ffmpeg_exe}")
        except Exception as e:
            print(f"❌ Erro ao instalar imageio-ffmpeg: {e}")
            return

    if not os.path.exists(DIR_COMPLETAS):
        print(f"❌ Diretório não encontrado: {DIR_COMPLETAS}")
        return

    arquivos = [f for f in os.listdir(DIR_COMPLETAS) if f.lower().endswith('.webm')]
    print(f"🔍 Encontrados {len(arquivos)} arquivos .webm para converter.")

    sucesso = 0
    falha = 0

    for f in arquivos:
        input_file = os.path.join(DIR_COMPLETAS, f)
        base_name = os.path.splitext(f)[0]
        output_file = os.path.join(DIR_COMPLETAS, base_name + ".mp3")
        
        print(f"🔄 Convertendo: {f} -> {base_name}.mp3")
        
        # Comando FFmpeg: -i input -vn (video none) -acodec libmp3lame -ab 192k -ar 44100 -y (overwrite)
        # Se libmp3lame falhar, tentar usar o codec padrão 'mp3' ou 'libmp3lame'
        cmd = [
            ffmpeg_exe,
            "-i", input_file,
            "-vn",
            "-acodec", "libmp3lame",
            "-ab", "192k",
            "-ar", "44100",
            "-y",
            output_file
        ]
        
        try:
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print(f"   ✅ Convertido com sucesso!")
            sucesso += 1
            # Opcional: remover o .webm original se quiser limpar
            try:
                os.remove(input_file)
                print(f"   🗑️ Removido original .webm")
            except OSError as e:
                print(f"   ⚠️ Não foi possível remover o original: {e}")
        except subprocess.CalledProcessError as e:
            print(f"   ❌ Erro na conversão: {e}")
            falha += 1
        except Exception as e:
            print(f"   ❌ Erro inesperado: {e}")
            falha += 1

    print("-" * 40)
    print(f"🏁 Concluído! Sucesso: {sucesso}, Falhas: {falha}")
    print(f"📂 Verifique a pasta: {DIR_COMPLETAS}")

if __name__ == "__main__":
    converter_webm_mp3()
