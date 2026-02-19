import os, shutil, time, hashlib, hmac, base64, requests, subprocess, tkinter as tk
import imageio_ffmpeg, re, uuid

# --- CONFIGURAÇÕES TÉCNICAS ---
CONFIG = {
    'access_key': "16c15aaefa0a10af964b085bd9a3cebc",
    'access_secret': "jdcfprIGFStvczF2BdTx7keSxb3yyJdqJwaKGRvI",
    'host': "identify-us-west-2.acrcloud.com",
    'ffmpeg': imageio_ffmpeg.get_ffmpeg_exe(),
    'repo': r"C:\Users\99196\Documents\Diego-repositorio",
    'whatsapp_file': "Conversa do WhatsApp com Mauro.txt"
}

PASTAS = {
    'referencia': os.path.join(CONFIG['repo'], "04_IDENTIFICADOS_FINAL"),
    'completas': os.path.join(CONFIG['repo'], "08_MUSICAS_COMPLETAS_MAURO"),
    'erradas': os.path.join(CONFIG['repo'], "09_MUSICAS_ERRADAS"),
    'temp': os.path.join(CONFIG['repo'], "TEMP_SAMPLES")
}

for p in PASTAS.values(): os.makedirs(p, exist_ok=True)

# --- FUNÇÕES DE PROCESSAMENTO ---
def extrair_links():
    print("📂 Lendo links do WhatsApp...")
    caminho_txt = os.path.join(CONFIG['repo'], CONFIG['whatsapp_file'])
    if not os.path.exists(caminho_txt):
        print(f"❌ Arquivo não encontrado: {caminho_txt}")
        return []
    
    with open(caminho_txt, "r", encoding="utf-8") as f:
        texto = f.read()
    links = re.findall(r'https://\S+tiktok\S+', texto)
    return list(set(links))

def identificar_acr(caminho):
    timestamp = str(int(time.time()))
    string_to_sign = f"POST\n/v1/identify\n{CONFIG['access_key']}\naudio\n1\n{timestamp}"
    sign = base64.b64encode(hmac.new(CONFIG['access_secret'].encode('ascii'), string_to_sign.encode('ascii'), digestmod=hashlib.sha1).digest()).decode('ascii')
    
    data = {
        'access_key': CONFIG['access_key'], 
        'sample_bytes': os.path.getsize(caminho), 
        'timestamp': timestamp, 
        'signature': sign, 
        'data_type': 'audio', 
        "signature_version": "1"
    }
    
    try:
        with open(caminho, 'rb') as f:
            files = {'sample': f}
            r = requests.post(f"http://{CONFIG['host']}/v1/identify", files=files, data=data, timeout=30)
            res = r.json()
            if res.get('status', {}).get('msg') == 'Success':
                if 'metadata' in res and 'music' in res['metadata'] and len(res['metadata']['music']) > 0:
                    m = res['metadata']['music'][0]
                    return f"{m.get('artists', [{}])[0].get('name')} - {m.get('title')}"
    except Exception as e:
        print(f"   ⚠️ Instabilidade na API (Timeout). Pulando...")
    return None

def processar_novos_links():
    links = extrair_links()
    if not links: return

    print(f"🎯 Encontrados {len(links)} links no total. Iniciando varredura...")
    print("-" * 50)
    
    for i, url in enumerate(links, 1):
        print(f"\n[{i}/{len(links)}] Processando: {url}")
        
        temp_file = os.path.join(PASTAS['temp'], f"check_{uuid.uuid4().hex[:6]}.mp4")
        
        # 1. Baixa o TikTok
        # Adicionado --force-overwrites e tratamento de erro
        cmd_tk = ["yt-dlp", "-o", temp_file, "--max-filesize", "15M", "--quiet", "--no-warnings", "--force-overwrites", url]
        
        try:
            res = subprocess.run(cmd_tk)
            if res.returncode != 0:
                print("   ❌ Erro ao tentar acessar o TikTok (Privado ou Apagado).")
                continue
        except FileNotFoundError:
             print("❌ yt-dlp não encontrado. Instale com 'pip install yt-dlp'")
             return

        # PROTEÇÃO CONTRA VÍDEOS FANTASMAS E CARROSSEIS
        if not os.path.exists(temp_file):
            print("   ❌ Download falhou (provavelmente um Carrossel de Fotos ou vídeo removido).")
            continue

        # 2. Identifica a música
        print("   🔍 Identificando áudio...")
        nome_musica = identificar_acr(temp_file)
        if not nome_musica:
            print("   ❌ Música não identificada ou não comercial.")
        else:
            nome_limpo = "".join(x for x in nome_musica if x.isalnum() or x in "._- ")[:100]
            print(f"   ✨ ENCONTRADA: {nome_limpo}")

            # 3. Salva a referência original
            ref_path = os.path.join(PASTAS['referencia'], f"{nome_limpo}.mp4")
            if not os.path.exists(ref_path):
                try:
                    shutil.copy(temp_file, ref_path)
                except Exception as e:
                    print(f"   ⚠️ Erro ao copiar referência: {e}")

            # 4. Baixa a MÚSICA COMPLETA em MP3
            saida_completa = os.path.join(PASTAS['completas'], f"{nome_limpo}.mp3")
            if not os.path.exists(saida_completa):
                print(f"   📥 Baixando VERSÃO COMPLETA oficial...")
                busca = f"ytsearch1:{nome_musica} official audio"
                cmd_yt = [
                    "yt-dlp", "--extract-audio", "--audio-format", "mp3", "--audio-quality", "192K",
                    "--ffmpeg-location", CONFIG['ffmpeg'], "--output", saida_completa, "--no-playlist", "--quiet", "--no-warnings", busca
                ]
                subprocess.run(cmd_yt)
                print("   ✅ MP3 Salvo com sucesso.")
            else:
                print("   ⏩ Música completa já existe no repositório.")

        # Limpeza segura
        try:
            if os.path.exists(temp_file):
                os.remove(temp_file)
        except Exception:
            pass

# --- INTERFACE DE AUDITORIA ---
class AuditoriaUI:
    def __init__(self, root):
        self.root = root
        self.root.title("✅ Auditoria de Elite - Diego vs Mauro")
        self.root.geometry("800x600")
        self.root.configure(bg="#0f172a")
        
        self.atualizar_lista()

        tk.Label(root, text=f"Músicas prontas para o Pendrive: {len(self.arquivos)}", font=("Arial", 14, "bold"), bg="#0f172a", fg="#38bdf8").pack(pady=15)
        self.listbox = tk.Listbox(root, width=95, height=20, font=("Consolas", 10), bg="#1e293b", fg="white", selectbackground="#3b82f6")
        for f in self.arquivos: self.listbox.insert(tk.END, f)
        self.listbox.pack(pady=10)

        f_btn = tk.Frame(root, bg="#0f172a")
        f_btn.pack(pady=10)
        tk.Button(f_btn, text="🎬 OUVIR REF (TikTok)", command=self.play_ref, bg="#f59e0b", font=("Arial", 10, "bold"), width=22).grid(row=0, column=0, padx=10)
        tk.Button(f_btn, text="🎵 OUVIR COMPLETA", command=self.play_full, bg="#10b981", fg="white", font=("Arial", 10, "bold"), width=22).grid(row=0, column=1, padx=10)
        tk.Button(f_btn, text="❌ MARCAR ERRADA", command=self.errada, bg="#ef4444", fg="white", font=("Arial", 10, "bold"), width=22).grid(row=1, column=0, columnspan=2, pady=15)
        
        tk.Button(root, text="🔄 Atualizar Lista", command=self.refresh, bg="#334155", fg="white").pack()

    def atualizar_lista(self):
        self.arquivos = [f for f in os.listdir(PASTAS['completas']) if f.endswith('.mp3')]
        self.arquivos.sort()

    def refresh(self):
        self.listbox.delete(0, tk.END)
        self.atualizar_lista()
        for f in self.arquivos: self.listbox.insert(tk.END, f)

    def play_ref(self):
        sel = self.listbox.curselection()
        if sel:
            nome = self.listbox.get(sel[0])
            base = os.path.splitext(nome)[0]
            # Tenta encontrar referencia
            p = os.path.join(PASTAS['referencia'], base + ".mp4")
            if os.path.exists(p): 
                os.startfile(p)
            else:
                 # Match parcial
                for f in os.listdir(PASTAS['referencia']):
                    if base in f:
                        os.startfile(os.path.join(PASTAS['referencia'], f))
                        return

    def play_full(self):
        sel = self.listbox.curselection()
        if sel: os.startfile(os.path.join(PASTAS['completas'], self.listbox.get(sel[0])))

    def errada(self):
        sel = self.listbox.curselection()
        if sel:
            nome = self.listbox.get(sel[0])
            try:
                shutil.move(os.path.join(PASTAS['completas'], nome), os.path.join(PASTAS['erradas'], nome))
                print(f"🚩 Movido para ERRADAS: {nome}")
                self.listbox.delete(sel[0])
            except: pass

# --- MAIN ---
if __name__ == "__main__":
    print("\n" + "="*50)
    print("🚀 MAURO ULTIMATE ENGINE - PAINEL DE CONTROLE")
    print("="*50)
    print("1 - Processar TUDO (Ler WhatsApp -> ID -> Download Completo)")
    print("2 - Abrir Painel de Auditoria (QA Final)")
    print("3 - Sair")
    
    escolha = input("\nEscolha: ")
    if escolha == "1": processar_novos_links()
    elif escolha == "2":
        root = tk.Tk()
        AuditoriaUI(root)
        root.mainloop()
