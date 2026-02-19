import os, shutil
import sys
import json

# Garante acrcloud
try:
    from acrcloud.recognizer import ACRCloudRecognizer
except ImportError:
    print("❌ Erro: Biblioteca 'acrcloud' não encontrada.")
    print("Execute: pip install acrcloud")
    sys.exit(1)

# CONFIGURAÇÕES DA API ACRCLOUD (Extraídas do seu dashboard)
config = {
    'host': 'identify-us-west-2.acrcloud.com',
    'access_key': '16c15aaefa0a10af964b085bd9a3cebc',
    'access_secret': 'jdcfprIGFStvczF2BdTx7keSxb3yyJdqJwaKGRvI',
    'timeout': 10 # segundos
}

# CAMINHOS
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DIR_LIXO = os.path.join(SCRIPT_DIR, "06_LIXO_CONFIRMADO")
if not os.path.exists(DIR_LIXO):
    DIR_LIXO = r"C:\Users\99196\Documents\Diego-repositorio\06_LIXO_CONFIRMADO"

DIR_FINAL = os.path.join(SCRIPT_DIR, "04_IDENTIFICADOS_FINAL")
if not os.path.exists(DIR_FINAL):
    DIR_FINAL = r"C:\Users\99196\Documents\Diego-repositorio\04_IDENTIFICADOS_FINAL"

# Cria diretório final se não existir
os.makedirs(DIR_FINAL, exist_ok=True)

def resgatar_musicas():
    if not os.path.exists(DIR_LIXO):
        print(f"❌ Erro: Pasta {DIR_LIXO} não encontrada.")
        return

    print("🔧 Inicializando ACRCloud Recognizer...")
    try:
        recognizer = ACRCloudRecognizer(config)
    except Exception as e:
        print(f"❌ Erro ao inicializar ACRCloud: {e}")
        return

    arquivos = [f for f in os.listdir(DIR_LIXO) if f.lower().endswith(('.mp4', '.mp3', '.m4a', '.wav'))]
    
    if not arquivos:
        print("✅ Pasta de lixo vazia! Tudo limpo.")
        return

    print(f"🕵️ Iniciando Varredura ACRCloud em {len(arquivos)} arquivos...")

    analisados = 0
    resgatados = 0

    for i, arq in enumerate(arquivos):
        caminho = os.path.join(DIR_LIXO, arq)
        print(f"[{i+1}/{len(arquivos)}] 🔍 {arq}...", end=" ")
        
        try:
            # Reconhece o arquivo (envia os primeiros segundos automaticamente)
            # start_seconds=0
            resultado_json = recognizer.recognize_by_file(caminho, 0)
            
            data = json.loads(resultado_json)
            
            if data.get('status', {}).get('msg') == 'Success' and data.get('metadata'):
                # Extrai nome da música e artista
                musicas = data['metadata'].get('music', [])
                if musicas:
                    music = musicas[0]
                    titulo = music.get('title', 'Unknown')
                    artistas = music.get('artists', [{'name': 'Unknown'}])
                    artista = artistas[0].get('name')
                    
                    nome_completo = f"{artista} - {titulo}"
                    
                    # Limpa o nome para o Windows
                    nome_clean = "".join(x for x in nome_completo if x.isalnum() or x in " ._-")[:80].strip()
                    
                    dest_path = os.path.join(DIR_FINAL, f"{nome_clean}.mp4")
                    # Evita overwrites
                    if os.path.exists(dest_path):
                         dest_path = os.path.join(DIR_FINAL, f"{nome_clean}_{i}.mp4")
                    
                    shutil.move(caminho, dest_path)
                    print(f"✨ RESGATADO: {nome_clean}")
                    resgatados += 1
                else:
                    print(f"⚠️ Metadados vazios.")
            else:
                msg = data.get('status', {}).get('msg', 'Unknown Error')
                print(f"❌ Não identificado ({msg})")
                
        except Exception as e:
            print(f"❌ Erro na API ou arquivo: {e}")
        
        analisados += 1

    print("-" * 50)
    print(f"🏆 Fim da Varredura ACRCloud!")
    print(f"📊 Analisados: {analisados}")
    print(f"♻️ Resgatados: {resgatados}")
    print(f"🗑️ Restantes no Lixo: {len(os.listdir(DIR_LIXO))}")

if __name__ == "__main__":
    resgatar_musicas()
