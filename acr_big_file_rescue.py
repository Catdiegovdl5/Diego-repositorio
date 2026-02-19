import os, shutil, time, hashlib, hmac, base64, subprocess
import sys

# Tenta importar requests
try:
    import requests
except ImportError:
    print("❌ Erro: Biblioteca 'requests' não encontrada.")
    print("Execute: pip install requests")
    sys.exit(1)

# Tenta encontrar ffmpeg automaticamente
try:
    import imageio_ffmpeg
    FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()
except ImportError:
    # Caminho fallback
    FFMPEG_PATH = r"C:\Users\99196\AppData\Local\Programs\Python\Python312-32\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win32-v4.2.2.exe"

# CREDENCIAIS DO SEU PROJETO
access_key = "16c15aaefa0a10af964b085bd9a3cebc"
access_secret = "jdcfprIGFStvczF2BdTx7keSxb3yyJdqJwaKGRvI"
requrl = "http://identify-us-west-2.acrcloud.com/v1/identify"

# Diretórios
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DIR_LIXO = os.path.join(SCRIPT_DIR, "06_LIXO_CONFIRMADO")
if not os.path.exists(DIR_LIXO):
    DIR_LIXO = r"C:\Users\99196\Documents\Diego-repositorio\06_LIXO_CONFIRMADO"

DIR_FINAL = os.path.join(SCRIPT_DIR, "04_IDENTIFICADOS_FINAL")
if not os.path.exists(DIR_FINAL):
    DIR_FINAL = r"C:\Users\99196\Documents\Diego-repositorio\04_IDENTIFICADOS_FINAL"

def identificar_acr_cortado(filepath):
    temp_wav = f"temp_slice_{os.getpid()}_{int(time.time()*1000)}.wav"
    
    # Corta 15 segundos do início/meio do vídeo (start 10s) para garantir que pegue a música
    # -y: overwrite
    # -ss 00:00:10: começa aos 10s
    # -t 15: duração 15s
    # -vn: disable video
    try:
        subprocess.run([
            FFMPEG_PATH, "-y", "-i", filepath, 
            "-ss", "00:00:10", "-t", "15", 
            "-ar", "44100", "-ac", "1", 
            temp_wav
        ], capture_output=True, check=True)
    except subprocess.CalledProcessError:
        # Se falhar (ex: vídeo curto demais), tenta sem o seek (-ss)
        try:
            subprocess.run([
                FFMPEG_PATH, "-y", "-i", filepath, 
                "-t", "15", 
                "-ar", "44100", "-ac", "1", 
                temp_wav
            ], capture_output=True, check=True)
        except:
            return None
            
    if not os.path.exists(temp_wav):
        return None

    timestamp = str(int(time.time()))
    http_method = "POST"
    http_uri = "/v1/identify"
    data_type = "audio"
    signature_version = "1"
    
    string_to_sign = f"{http_method}\n{http_uri}\n{access_key}\n{data_type}\n{signature_version}\n{timestamp}"
    
    sign = base64.b64encode(
        hmac.new(
            access_secret.encode('ascii'), 
            string_to_sign.encode('utf-8'), 
            digestmod=hashlib.sha1
        ).digest()
    ).decode('ascii')

    f_size = os.path.getsize(temp_wav)
    
    res = None
    try:
        with open(temp_wav, 'rb') as f:
            files = {'sample': f}
            data = {
                'access_key': access_key,
                'sample_bytes': f_size,
                'timestamp': timestamp,
                'signature': sign,
                'data_type': data_type,
                "signature_version": signature_version
            }
            
            r = requests.post(requrl, files=files, data=data, timeout=20)
            res = r.json()
    except Exception as e:
        # print(f"Erro request: {e}")
        pass
    finally:
        if os.path.exists(temp_wav):
            try:
                os.remove(temp_wav)
            except: pass
            
    return res

def main():
    if not os.path.exists(DIR_LIXO):
        print(f"❌ Pasta {DIR_LIXO} não encontrada.")
        return
        
    if not os.path.exists(DIR_FINAL):
        os.makedirs(DIR_FINAL)
        
    arquivos = [f for f in os.listdir(DIR_LIXO) if f.lower().endswith(('.mp4', '.mp3', '.m4a', '.wav'))]
    
    if not arquivos:
        print("✅ Pasta de lixo vazia! Tudo limpo.")
        return

    print(f"✂️ Iniciando Resgate com Corte em {len(arquivos)} arquivos grandes/restantes...")
    print(f"📂 Lendo de: {DIR_LIXO}")

    resgatados_count = 0

    for i, arq in enumerate(arquivos):
        caminho = os.path.join(DIR_LIXO, arq)
        print(f"[{i+1}/{len(arquivos)}] 🔍 {arq}...", end=" ", flush=True)
        
        res = identificar_acr_cortado(caminho)
        
        identified = False
        if res and res.get('status', {}).get('msg') == 'Success':
            metadata = res.get('metadata', {})
            if 'music' in metadata and len(metadata['music']) > 0:
                music = metadata['music'][0]
                artists = music.get('artists', [{'name': 'Unknown'}])
                title = music.get('title', 'Unknown')
                
                nome = f"{artists[0]['name']} - {title}"
                nome_clean = "".join(x for x in nome if x.isalnum() or x in " ._-")[:80].strip()
                
                dest_path = os.path.join(DIR_FINAL, f"{nome_clean}.mp4")
                if os.path.exists(dest_path):
                     dest_path = os.path.join(DIR_FINAL, f"{nome_clean}_{i}.mp4")

                try:
                    shutil.move(caminho, dest_path)
                    print(f"✅ RESGATADO: {nome_clean}")
                    identified = True
                    resgatados_count += 1
                except Exception as e:
                    print(f"❌ Erro mover: {e}")
            else:
                 print("❌ Sem música")
        else:
             msg = res.get('status', {}).get('msg', 'Falha') if res else 'Erro'
             print(f"❌ {msg}")

        # Pequeno delay
        time.sleep(1)

    print("-" * 50)
    print(f"🏆 Fim do Resgate Final! {resgatados_count} recuperados.")

if __name__ == "__main__":
    main()
