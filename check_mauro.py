import os
import tkinter as tk
from tkinter import ttk
import webbrowser

# PASTA COM OS VÍDEOS QUE ERAM DO TIKTOK E AGORA TÊM NOME DE MÚSICA
# Usando caminho relativo para robustez
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DIR_REFERENCIA = os.path.join(SCRIPT_DIR, "04_IDENTIFICADOS_FINAL")

class CheckApp:
    def __init__(self, root):
        self.root = root
        self.root.title("🎯 Auditoria Final: Vídeo Original vs Música Oficial")
        self.root.geometry("900x600")
        self.root.configure(bg="#121212")

        # Verifica se diretório existe
        if not os.path.exists(DIR_REFERENCIA):
            tk.messagebox.showerror("Erro", f"Pasta não encontrada: {DIR_REFERENCIA}")
            self.arquivos = []
        else:
            self.arquivos = [f for f in os.listdir(DIR_REFERENCIA) if f.lower().endswith(('.mp4', '.mp3', '.m4a'))]
            self.arquivos.sort()

        # UI Header
        header_frame = tk.Frame(root, bg="#121212")
        header_frame.pack(pady=15)
        tk.Label(header_frame, text="LISTA DE MÚSICAS PARA VALIDAR", fg="#00e676", bg="#121212", font=("Segoe UI", 14, "bold")).pack()
        tk.Label(header_frame, text=f"Total: {len(self.arquivos)} arquivos", fg="#aaaaaa", bg="#121212", font=("Segoe UI", 10)).pack()
        
        # Lista com Scrollbar
        list_frame = tk.Frame(root, bg="#121212")
        list_frame.pack(pady=10, padx=20, fill=tk.BOTH, expand=True)

        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.listbox = tk.Listbox(list_frame, width=90, height=15, bg="#1e1e1e", fg="#e0e0e0", 
                                font=("Consolas", 11), selectbackground="#00e676", selectforeground="black",
                                yscrollcommand=scrollbar.set)
        
        for f in self.arquivos:
            self.listbox.insert(tk.END, f)
            
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.listbox.yview)

        # Bind duplo clique
        self.listbox.bind('<Double-1>', lambda x: self.ver_original())

        # Botões
        btn_frame = tk.Frame(root, bg="#121212")
        btn_frame.pack(pady=25)

        # Botão Laranja: Abre o vídeo que você baixou do TikTok
        btn_original = tk.Button(btn_frame, text="📺 VER VÍDEO LOCAL (TIKTOK)", command=self.ver_original, 
                                bg="#ff9800", fg="black", font=("Segoe UI", 11, "bold"), width=30, height=2, cursor="hand2")
        btn_original.grid(row=0, column=0, padx=15)
        
        # Botão Azul: Abre o YouTube para ouvir a música oficial
        btn_oficial = tk.Button(btn_frame, text="🎵 OUVIR MÚSICA OFICIAL (YT)", command=self.ouvir_oficial, 
                               bg="#2196f3", fg="white", font=("Segoe UI", 11, "bold"), width=30, height=2, cursor="hand2")
        btn_oficial.grid(row=0, column=1, padx=15)

        # Instruções
        instruct_label = tk.Label(root, text="Dica: Duplo clique na lista abre o vídeo local.", fg="#666666", bg="#121212", font=("Segoe UI", 9))
        instruct_label.pack(side=tk.BOTTOM, pady=10)

    def ver_original(self):
        selecao = self.listbox.curselection()
        if selecao:
            nome = self.listbox.get(selecao[0])
            caminho = os.path.join(DIR_REFERENCIA, nome)
            try:
                # Abre o vídeo original do TikTok usando o player do Windows
                os.startfile(caminho)
            except Exception as e:
                print(f"Erro ao abrir arquivo: {e}")

    def ouvir_oficial(self):
        selecao = self.listbox.curselection()
        if selecao:
            nome = self.listbox.get(selecao[0])
            # Remove extensão e limpa nome para busca
            termo_busca = os.path.splitext(nome)[0].replace("_6720", "").replace("_", " ").replace("-", " ")
            
            # Abre a busca oficial no YouTube para comparação
            url = f"https://www.youtube.com/results?search_query={termo_busca}+official+audio"
            webbrowser.open(url)

if __name__ == "__main__":
    root = tk.Tk()
    app = CheckApp(root)
    root.mainloop()
