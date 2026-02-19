import os, shutil, time, hashlib, hmac, base64, requests, subprocess
import tkinter as tk
from tkinter import messagebox
import imageio_ffmpeg

# --- CONFIGURAÇÕES DE ELITE ---
# Chaves fornecidas - Em um cenário real, não devem ser hardcoded
CONFIG = {
    'access_key': "16c15aaefa0a10af964b085bd9a3cebc", 
    'access_secret': "jdcfprIGFStvczF2BdTx7keSxb3yyJdqJwaKGRvI", 
    'host': "identify-us-west-2.acrcloud.com",
    'ffmpeg': imageio_ffmpeg.get_ffmpeg_exe(),
    'repo': r"C:\Users\99196\Documents\Diego-repositorio"
}

# Pastas de Trabalho - Ajustando para o contexto do usuário
PASTAS = {
    'ref': os.path.join(CONFIG['repo'], "04_IDENTIFICADOS_FINAL"),
    'lixo': os.path.join(CONFIG['repo'], "06_LIXO_CONFIRMADO"),
    'completas': os.path.join(CONFIG['repo'], "08_MUSICAS_COMPLETAS_MAURO"),
    'erradas': os.path.join(CONFIG['repo'], "09_MUSICAS_ERRADAS")
}

for p in PASTAS.values(): os.makedirs(p, exist_ok=True)

# --- MÓDULO 1: IDENTIFICAÇÃO ACRCLOUD ---
# Nota: Esta função é uma implementação da API da ACRCloud para identificar áudio.
# Ela precisa de um arquivo de áudio para enviar.
def identificar_audio_demo(caminho):
    timestamp = str(int(time.time()))
    http_method = "POST"
    http_uri = "/v1/identify"
    data_type = "audio"
    signature_version = "1"
    timestamp = str(int(time.time()))
    
    string_to_sign = http_method + "\n" + http_uri + "\n" + CONFIG['access_key'] + "\n" + data_type + "\n" + signature_version + "\n" + timestamp

    sign = base64.b64encode(hmac.new(CONFIG['access_secret'].encode('ascii'), string_to_sign.encode('ascii'), digestmod=hashlib.sha1).digest()).decode('ascii')
    
    files = {'sample': open(caminho, 'rb')}
    data = {'access_key': CONFIG['access_key'], 'sample_bytes': os.path.getsize(caminho), 'timestamp': timestamp, 'signature': sign, 'data_type': data_type, "signature_version": signature_version}
    
    try:
        req_url = "http://" + CONFIG['host'] + "/v1/identify"
        r = requests.post(req_url, files=files, data=data, timeout=20)
        return r.json()
    except Exception as e:
        print(f"Erro na requisição ACRCloud: {e}")
        return None

# --- MÓDULO 2: DOWNLOAD DA MÚSICA COMPLETA ---
def baixar_completa(nome_musica):
    # Verifica se já existe mp3
    saida = os.path.join(PASTAS['completas'], f"{nome_musica}.mp3")
    if os.path.exists(saida): 
        print(f"⏩ {nome_musica} já existe.")
        return True
    
    print(f"📥 Baixando Versão Completa: {nome_musica}")
    # Busca por "official audio" para tentar pegar a melhor qualidade
    busca = f"ytsearch1:{nome_musica} official audio"
    
    # Template de saída
    out_tmpl = os.path.join(PASTAS['completas'], f"{nome_musica}.%(ext)s")
    
    cmd = [
        "yt-dlp", 
        "--extract-audio", 
        "--audio-format", "mp3", 
        "--audio-quality", "192K",
        "--ffmpeg-location", CONFIG['ffmpeg'], 
        "--output", out_tmpl,
        "--no-playlist", 
        "--quiet",
        "--no-warnings",
        busca
    ]
    
    try:
        res = subprocess.run(cmd)
        return res.returncode == 0
    except FileNotFoundError:
        print("❌ yt-dlp não encontrado. Instale com 'pip install yt-dlp'")
        return False

# --- MÓDULO 3: INTERFACE DE AUDITORIA (QA) ---
class AuditoriaUI:
    def __init__(self, root):
        self.root = root
        self.root.title("🏁 Auditoria Final do Mauro")
        self.root.geometry("600x450")
        
        self.arquivos = [f for f in os.listdir(PASTAS['completas']) if f.endswith('.mp3')]
        self.arquivos.sort()
        
        tk.Label(root, text=f"Total: {len(self.arquivos)} músicas", font=("Arial", 14, "bold")).pack(pady=10)
        
        self.listbox = tk.Listbox(root, width=80, height=15)
        for f in self.arquivos: self.listbox.insert(tk.END, f)
        self.listbox.pack(pady=10,padx=20)

        frame = tk.Frame(root)
        frame.pack(pady=10)
        
        tk.Button(frame, text="🎬 OUVIR REF (TIKTOK)", command=self.play_ref, bg="orange", width=20).grid(row=0, column=0, padx=5)
        tk.Button(frame, text="🎵 OUVIR COMPLETA", command=self.play_full, bg="lightgreen", width=20).grid(row=0, column=1, padx=5)
        
        tk.Button(root, text="❌ ERRADA (Mover para 09_ERRADAS)", command=self.marcar_errada, bg="red", fg="white", font=("Arial", 10, "bold")).pack(pady=10)

    def play_ref(self):
        sel = self.listbox.curselection()
        if sel:
            # Tenta encontrar correspondente
            nome_mp3 = self.listbox.get(sel[0])
            nome_base = os.path.splitext(nome_mp3)[0]
            
            # Tenta achar .mp4 na referência
            ref_path = os.path.join(PASTAS['ref'], nome_base + ".mp4")
            
            if os.path.exists(ref_path):
                os.startfile(ref_path)
            else:
                # Tenta match parcial
                encontrado = False
                for f in os.listdir(PASTAS['ref']):
                    if f.startswith(nome_base) or nome_base in f:
                        os.startfile(os.path.join(PASTAS['ref'], f))
                        encontrado = True
                        break
                if not encontrado:
                    messagebox.showinfo("Aviso", "Referência exata não encontrada.")

    def play_full(self):
        sel = self.listbox.curselection()
        if sel: 
            path = os.path.join(PASTAS['completas'], self.listbox.get(sel[0]))
            if os.path.exists(path):
                os.startfile(path)

    def marcar_errada(self):
        sel = self.listbox.curselection()
        if sel:
            index = sel[0]
            nome = self.listbox.get(index)
            origem = os.path.join(PASTAS['completas'], nome)
            destino = os.path.join(PASTAS['erradas'], nome)
            try:
                shutil.move(origem, destino)
                self.listbox.delete(index)
                self.arquivos.remove(nome)
                print(f"Movido para erradas: {nome}")
            except Exception as e:
                messagebox.showerror("Erro", f"Erro ao mover: {e}\nFeche o player se estiver tocando.")

# --- FUNÇÃO PRINCIPAL ---
def main():
    # Verifica dependências básicas
    if not shutil.which("yt-dlp"):
         print("⚠️  AVISO: yt-dlp não está no PATH. A função de download pode falhar.")
         print("   Instale com: pip install yt-dlp")

    while True:
        print("\n" + "="*40)
        print("🚀 BEM-VINDO À FÁBRICA MUSICAL DO MAURO 2026")
        print("="*40)
        print("1. [Download] Processar Links e Baixar Completas (Demo)")
        print("2. [QA] Abrir Auditoria de Qualidade")
        print("3. Sair")
        opcao = input("\nEscolha uma opção: ")

        if opcao == "1":
            print("\nIniciando módulo de download...")
            # Exemplo: pega nomes da pasta de referência e tenta baixar versão completa
            if not os.path.exists(PASTAS['ref']):
                print("Pasta de referência não encontrada.")
                continue
                
            arquivos_ref = [f for f in os.listdir(PASTAS['ref']) if f.endswith('.mp4')]
            print(f"Encontradas {len(arquivos_ref)} referências para verificar completas.")
            
            count = 0
            for i, arq in enumerate(arquivos_ref):
                nome_limpo = os.path.splitext(arq)[0]
                # Limpa sufixos de download se houver, para melhor busca
                # Exemplo: "Nome Musica_12345" -> "Nome Musica"
                # A lógica de limpeza pode ser ajustada
                
                print(f"[{i+1}/{len(arquivos_ref)}] Processando: {nome_limpo}")
                if baixar_completa(nome_limpo):
                    count += 1
            print(f"\n✅ Concluído. {count} músicas verificadas/baixadas.")
        
        elif opcao == "2":
            print("\nAbrindo interface gráfica...")
            root = tk.Tk()
            AuditoriaUI(root)
            root.mainloop()
            print("Interface fechada.")
            
        elif opcao == "3":
            print("Saindo...")
            break
        else:
            print("Opção inválida.")

if __name__ == "__main__":
    main()
