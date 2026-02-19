import os, shutil, time, hashlib, hmac, base64
import sys

# Tenta importar requests
try:
    import requests
except ImportError:
    print("❌ Erro: Biblioteca 'requests' não encontrada.")
    print("Execute: pip install requests")
    sys.exit(1)

# CREDENCIAIS DO SEU PROJETO 'Identificador_Mauro'
access_key = "16c15aaefa0a10af964b085bd9a3cebc"
access_secret = "jdcfprIGFStvczF2BdTx7keSxb3yyJdqJwaKGRvI"
requrl = "http://identify-us-west-2.acrcloud.com/v1/identify"

# Diretórios - Robustez para caminho relativo ou absoluto
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DIR_LIXO = os.path.join(SCRIPT_DIR, "06_LIXO_CONFIRMADO")
if not os.path.exists(DIR_LIXO):
    DIR_LIXO = r"C:\Users\99196\Documents\Diego-repositorio\06_LIXO_CONFIRMADO"

DIR_FINAL = os.path.join(SCRIPT_DIR, "04_IDENTIFICADOS_FINAL")
if not os.path.exists(DIR_FINAL):
    DIR_FINAL = r"C:\Users\99196\Documents\Diego-repositorio\04_IDENTIFICADOS_FINAL"

def identificar_acr(filepath):
    # Prepara assinatura para API
    http_method = "POST"
    http_uri = "/v1/identify"
    data_type = "audio"
    signature_version = "1"
    timestamp = str(int(time.time()))
    
    string_to_sign = f"{http_method}\n{http_uri}\n{access_key}\n{data_type}\n{signature_version}\n{timestamp}"
    
    sign = base64.b64encode(
        hmac.new(
            access_secret.encode('ascii'), 
            string_to_sign.encode('utf-8'), 
            digestmod=hashlib.sha1
        ).digest()
    ).decode('ascii')

    # Prepara arquivo e dados
    f_size = os.path.getsize(filepath)
    
    # Files precisa ser aberto em modo binário
    with open(filepath, 'rb') as f:
        files = {'sample': f}
        data = {
            'access_key': access_key,
            'sample_bytes': f_size,
            'timestamp': timestamp,
            'signature': sign,
            'data_type': data_type,
            "signature_version": signature_version
        }

        try:
            r = requests.post(requrl, files=files, data=data, timeout=20)
            r.encoding = "utf-8"
            return r.json()
        except Exception as e:
            # print(f"Erro de conexão: {e}")
            return None

def main():
    if not os.path.exists(DIR_LIXO):
        print(f"❌ Pasta de Lixo não encontrada: {DIR_LIXO}")
        return

    if not os.path.exists(DIR_FINAL): 
        os.makedirs(DIR_FINAL)
        
    arquivos = [f for f in os.listdir(DIR_LIXO) if f.lower().endswith(('.mp4', '.mp3', '.m4a', '.wav'))]
    
    if not arquivos:
        print("✅ Pasta de lixo vazia! Tudo limpo.")
        return

    print(f"🚀 Iniciando Resgate Direto (ACRCloud API) em {len(arquivos)} arquivos...")
    print(f"📂 Lendo de: {DIR_LIXO}")

    resgatados_count = 0

    for i, arq in enumerate(arquivos):
        caminho = os.path.join(DIR_LIXO, arq)
        print(f"[{i+1}/{len(arquivos)}] 🔍 Analisando: {arq}...", end=" ", flush=True)
        
        res = identificar_acr(caminho)
        
        if res and res.get('status', {}).get('msg') == 'Success':
            metadata = res.get('metadata', {})
            if 'music' in metadata and len(metadata['music']) > 0:
                music = metadata['music'][0]
                artists = music.get('artists', [{'name': 'Desconhecido'}])
                artist_name = artists[0]['name']
                title = music.get('title', 'Desconhecido')
                
                nome = f"{artist_name} - {title}"
                # Limpa nome
                nome_clean = "".join(x for x in nome if x.isalnum() or x in " ._-")[:80].strip()
                
                dest_path = os.path.join(DIR_FINAL, f"{nome_clean}.mp4")
                if os.path.exists(dest_path):
                     dest_path = os.path.join(DIR_FINAL, f"{nome_clean}_{i}.mp4")

                try:
                    shutil.move(caminho, dest_path)
                    print(f"✅ RESGATADO: {nome_clean}")
                    resgatados_count += 1
                except Exception as e:
                    print(f"❌ Erro ao mover: {e}")
            else:
                print("❌ Sem metadados de música")
        else:
            # Mostra erro se houver
            msg = "Não identificado"
            if res:
                msg = res.get('status', {}).get('msg', msg)
            print(f"❌ {msg}")
            
        # Pequeno delay para ser gentil com a API
        time.sleep(0.5)

    print("-" * 50)
    print(f"🏆 Fim do Resgate! {resgatados_count} arquivos recuperados.")

if __name__ == "__main__":
    main()
