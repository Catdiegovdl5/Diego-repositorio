import os
import tkinter as tk
import webbrowser
from tkinter import ttk

# CONFIGURAÇÕES DE CAMINHO
# Usando paths robustos baseados na localização do script
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DIR_VIDEOS = os.path.join(SCRIPT_DIR, "04_IDENTIFICADOS_FINAL")
if not os.path.exists(DIR_VIDEOS):
    DIR_VIDEOS = r"C:\Users\99196\Documents\Diego-repositorio\04_IDENTIFICADOS_FINAL"

DIR_MP3 = os.path.join(SCRIPT_DIR, "07_PENDRIVE_MAURO_MP3")
if not os.path.exists(DIR_MP3):
    DIR_MP3 = r"C:\Users\99196\Documents\Diego-repositorio\07_PENDRIVE_MAURO_MP3"

class QAMaster:
    def __init__(self, root):
        self.root = root
        self.root.title("🔍 Verificador de Elite - Diego vs Mauro")
        self.root.geometry("1000x600")
        self.root.configure(bg="#0f172a")

        # Carrega arquivos
        if os.path.exists(DIR_VIDEOS):
            self.arquivos = [f for f in os.listdir(DIR_VIDEOS) if f.lower().endswith(('.mp4', '.m4a', '.mp3'))]
            self.arquivos.sort()
        else:
            self.arquivos = []
            print(f"Erro: Pasta {DIR_VIDEOS} não encontrada.")

        # UI - Título
        top_frame = tk.Frame(root, bg="#0f172a")
        top_frame.pack(pady=15)
        
        tk.Label(top_frame, text=f"Auditoria de {len(self.arquivos)} músicas resgatadas", 
                 fg="#38bdf8", bg="#0f172a", font=("Segoe UI", 16, "bold")).pack()
        tk.Label(top_frame, text="Verifique se o vídeo original corresponde ao MP3 final.", 
                 fg="#94a3b8", bg="#0f172a", font=("Segoe UI", 10)).pack()
        
        # Lista com Scrollbar
        list_frame = tk.Frame(root, bg="#0f172a")
        list_frame.pack(pady=10, padx=20, fill=tk.BOTH, expand=True)

        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.listbox = tk.Listbox(list_frame, width=110, height=18, bg="#1e293b", fg="#f8fafc", 
                                  font=("Consolas", 11), selectbackground="#38bdf8", selectforeground="#0f172a",
                                  border=0, highlightthickness=0, yscrollcommand=scrollbar.set)
        
        for f in self.arquivos:
            self.listbox.insert(tk.END, f)
            
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.listbox.yview)

        # Botões
        btn_frame = tk.Frame(root, bg="#0f172a")
        btn_frame.pack(pady=25)

        # Estilo dos botões
        btn_font = ("Segoe UI", 10, "bold")

        # Botão 1: Abre o vídeo original que o Mauro mandou (A Referência)
        self.btn_video = tk.Button(btn_frame, text="🎬 1. VER VÍDEO LOCAL (Origem)", command=self.ver_video, 
                  bg="#f59e0b", fg="black", font=btn_font, width=28, height=2, cursor="hand2")
        self.btn_video.grid(row=0, column=0, padx=10)
        
        # Botão 2: Toca o MP3 que vai para o Pendrive
        self.btn_mp3 = tk.Button(btn_frame, text="🎵 2. OUVIR MP3 (Final)", command=self.ouvir_mp3, 
                  bg="#10b981", fg="white", font=btn_font, width=28, height=2, cursor="hand2")
        self.btn_mp3.grid(row=0, column=1, padx=10)

        # Botão 3: Tira-teima no YouTube
        self.btn_yt = tk.Button(btn_frame, text="🌐 3. TIRA-TEIMA (YouTube)", command=self.buscar_yt, 
                  bg="#ef4444", fg="white", font=btn_font, width=28, height=2, cursor="hand2")
        self.btn_yt.grid(row=0, column=2, padx=10)

        # Atalho de teclado
        self.listbox.bind('<Double-1>', lambda x: self.ver_video())
        self.listbox.bind('<Return>', lambda x: self.ouvir_mp3())

    def ver_video(self):
        sel = self.listbox.curselection()
        if sel:
            nome = self.listbox.get(sel[0])
            caminho = os.path.join(DIR_VIDEOS, nome)
            try:
                os.startfile(caminho)
            except Exception as e:
                print(f"Erro ao abrir vídeo: {e}")

    def ouvir_mp3(self):
        sel = self.listbox.curselection()
        if sel:
            nome_original = self.listbox.get(sel[0])
            # Tenta encontrar o MP3 correspondente (pode ter sido limpo)
            nome_base = os.path.splitext(nome_original)[0]
            # Remove sufixos comuns que o conversor remove
            nome_limpo = nome_base.replace("_6720", "").replace("_original", "").strip()
            
            caminho_mp3 = os.path.join(DIR_MP3, f"{nome_limpo}.mp3")
            
            if os.path.exists(caminho_mp3):
                try:
                    os.startfile(caminho_mp3)
                except Exception as e:
                    print(f"Erro ao abrir MP3: {e}")
            else:
                tk.messagebox.showwarning("Aviso", f"MP3 não encontrado:\n{caminho_mp3}\n\nRode o 'smart_convert.py' se ainda não converteu.")

    def buscar_yt(self):
        sel = self.listbox.curselection()
        if sel:
            nome = self.listbox.get(sel[0])
            termo = os.path.splitext(nome)[0].replace("_6720", "").replace("-", " ").replace("_", " ")
            webbrowser.open(f"https://www.youtube.com/results?search_query={termo}+official+audio")

if __name__ == "__main__":
    root = tk.Tk()
    app = QAMaster(root)
    root.mainloop()
