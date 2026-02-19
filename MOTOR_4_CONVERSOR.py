import os, subprocess
import imageio_ffmpeg

REPO = r"C:\Users\99196\Documents\Diego-repositorio"
REF_DIR = os.path.join(REPO, "04_IDENTIFICADOS_FINAL")
ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()

print("🔄 Convertendo Vídeos do TikTok para Áudio MP3...")
try:
    arquivos = [f for f in os.listdir(REF_DIR) if f.endswith('.mp4')]
except FileNotFoundError:
    print(f"❌ Pasta não encontrada: {REF_DIR}")
    arquivos = []

for i, f in enumerate(arquivos, 1):
    mp4_path = os.path.join(REF_DIR, f)
    mp3_path = mp4_path.replace('.mp4', '.mp3')
    
    if not os.path.exists(mp3_path):
        print(f"[{i}/{len(arquivos)}] Extraindo áudio: {f}")
        # Usa o ffmpeg para ripar o áudio sem tocar no vídeo
        subprocess.run([ffmpeg_path, "-y", "-i", mp4_path, "-vn", "-b:a", "128k", mp3_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

print("\n✅ Conversão concluída! Todos os TikToks agora têm versão MP3.")
