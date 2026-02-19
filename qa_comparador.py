import os
import tkinter as tk
import webbrowser
import threading

# PASTA ONDE ESTÃO OS VÍDEOS ORIGINAIS RENOMEADOS
# Usando caminho relativo para robustez
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DIR_VIDEOS = os.path.join(SCRIPT_DIR, "04_IDENTIFICADOS_FINAL")

class QAApp:
    def __init__(self, root):
        self.root = root
        self.root.title("🔍 Validador de Referência - Diego vs Mauro")
        self.root.geometry("900x500")
        self.root.configure(bg="#2d2d2d")  # Dark mode suave

        # Verificação de segurança da pasta
        if not os.path.exists(DIR_VIDEOS):
            print(f"❌ Erro: Pasta '{DIR_VIDEOS}' não encontrada.")
            self.arquivos = []
        else:
            self.arquivos = [f for f in os.listdir(DIR_VIDEOS) if f.lower().endswith(('.mp4', '.mp3', '.m4a', '.wav'))]
            self.arquivos.sort()

        # UI
        top_frame = tk.Frame(root, bg="#2d2d2d")
        top_frame.pack(pady=10, fill=tk.X)
        
        tk.Label(top_frame, text="Vídeos Identificados (Clique para validar)", fg="#ffffff", bg="#2d2d2d", font=("Segoe UI", 12, "bold")).pack()
        
        # Lista com Scrollbar
        list_frame = tk.Frame(root, bg="#2d2d2d")
        list_frame.pack(pady=5, padx=20, fill=tk.BOTH, expand=True)

        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.listbox = tk.Listbox(list_frame, width=100, height=15, bg="#1e1e1e", fg="#e0e0e0", 
                                font=("Consolas", 10), selectbackground="#4a4a4a", 
                                yscrollcommand=scrollbar.set)
        
        for f in self.arquivos:
            self.listbox.insert(tk.END, f)
            
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.listbox.yview)

        # Ação de duplo clique
        self.listbox.bind('<Double-1>', lambda x: self.executar_ambos())

        # Botões
        btn_frame = tk.Frame(root, bg="#2d2d2d")
        btn_frame.pack(pady=20)

        tk.Button(btn_frame, text="📺 ABRIR PACK (Vídeo + Busca)", command=self.executar_ambos, 
                 bg="#4CAF50", fg="white", font=("Segoe UI", 10, "bold"), width=30, height=2).grid(row=0, column=0, padx=10)
        
        tk.Button(btn_frame, text="📂 ABRIR PASTA (Renomear)", command=self.abrir_pasta, 
                 bg="#FF9800", fg="black", font=("Segoe UI", 10), width=20, height=2).grid(row=0, column=1, padx=10)

    def executar_ambos(self):
        """Abre o vídeo local e a busca no YouTube simultaneamente"""
        selecao = self.listbox.curselection()
        if selecao:
            nome_arquivo = self.listbox.get(selecao[0])
            caminho_completo = os.path.join(DIR_VIDEOS, nome_arquivo)
            
            # Limpa o nome para a busca (remove extensão e caracteres especiais)
            # Remove sufixos comuns que atrapalham a busca
            nome_busca = os.path.splitext(nome_arquivo)[0]
            nome_busca = nome_busca.replace("_6720", "").replace("_", " ").replace("-", " ")
            
            # 1. Abre o arquivo local
            try:
                os.startfile(caminho_completo)
            except Exception as e:
                print(f"Erro ao abrir arquivo: {e}")

            # 2. Abre o navegador
            url = f"https://www.youtube.com/results?search_query={nome_busca}+official+audio"
            webbrowser.open(url)

    def abrir_pasta(self):
        """Abre o explorer na pasta para renomear manualmente se necessário"""
        os.startfile(DIR_VIDEOS)

if __name__ == "__main__":
    root = tk.Tk()
    app = QAApp(root)
    root.mainloop()
