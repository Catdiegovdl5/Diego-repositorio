import os
import tkinter as tk
from tkinter import ttk, messagebox
import webbrowser
import subprocess

# CONFIGURAÇÕES
# Ajuste para ser relativo ao diretório do script, garantindo portabilidade
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DIR_MP3 = os.path.join(SCRIPT_DIR, "07_PENDRIVE_MAURO_MP3")
RELATORIO_VERIFICACAO = os.path.join(SCRIPT_DIR, "Verificacao_Final_Mauro.csv")

class AuditApp:
    def __init__(self, root):
        self.root = root
        self.root.title("💎 Estação de Auditoria - Projeto Mauro")
        self.root.geometry("800x600")
        
        self.musicas = []
        if os.path.exists(DIR_MP3):
            self.musicas = [f for f in os.listdir(DIR_MP3) if f.lower().endswith('.mp3')]
            self.musicas.sort()
        else:
            messagebox.showerror("Erro", f"Pasta não encontrada: {DIR_MP3}")
        
        # Interface
        label = tk.Label(root, text="Selecione a música para comparar (Local vs Oficial)", font=("Arial", 12, "bold"))
        label.pack(pady=10)

        # Frame da Lista com Scrollbar
        list_frame = tk.Frame(root)
        list_frame.pack(pady=10, padx=20, fill=tk.BOTH, expand=True)

        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.listbox = tk.Listbox(list_frame, width=80, height=20, font=("Arial", 10), yscrollcommand=scrollbar.set)
        for m in self.musicas:
            self.listbox.insert(tk.END, m)
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        scrollbar.config(command=self.listbox.yview)
        
        self.listbox.bind('<Double-1>', lambda x: self.verificar())

        # Botões
        btn_frame = tk.Frame(root)
        btn_frame.pack(pady=20)

        tk.Button(btn_frame, text="▶️ TOCAR E COMPARAR", command=self.verificar, bg="#2196F3", fg="white", width=20).grid(row=0, column=0, padx=5)
        tk.Button(btn_frame, text="✅ APROVAR", command=self.aprovar, bg="#4CAF50", fg="white", width=15).grid(row=0, column=1, padx=5)
        tk.Button(btn_frame, text="❌ REVISAR", command=self.revisar, bg="#F44336", fg="white", width=15).grid(row=0, column=2, padx=5)

        self.status = {} # Guarda o veredito

    def verificar(self):
        selecao = self.listbox.curselection()
        if not selecao: return
        
        nome_arquivo = self.listbox.get(selecao[0])
        caminho_local = os.path.join(DIR_MP3, nome_arquivo)
        
        # Limpa o nome para busca
        termo_busca = nome_arquivo.replace(".mp3", "").replace("_", " ")
        
        try:
            # 1. Toca o arquivo local (usa o player padrão do Windows)
            # aspas no caminho para evitar problemas com espaços
            os.startfile(caminho_local)
        except Exception as e:
            print(f"Erro ao tocar arquivo: {e}")
        
        # 2. Abre a busca no YouTube para comparação instantânea
        url_busca = f"https://www.youtube.com/results?search_query={termo_busca}+official+audio"
        webbrowser.open(url_busca)

    def aprovar(self):
        selecao = self.listbox.curselection()
        if selecao:
            idx = selecao[0]
            nome = self.listbox.get(idx)
            self.listbox.itemconfig(idx, {'bg': '#C8E6C9'}) # Verde claro
            self.status[nome] = "APROVADO"
            self.avancar_proximo(idx)

    def revisar(self):
        selecao = self.listbox.curselection()
        if selecao:
            idx = selecao[0]
            nome = self.listbox.get(idx)
            self.listbox.itemconfig(idx, {'bg': '#FFCDD2'}) # Vermelho claro
            self.status[nome] = "REVISAR"
            self.avancar_proximo(idx)
            
    def avancar_proximo(self, idx_atual):
        if idx_atual < len(self.musicas) - 1:
            self.listbox.selection_clear(0, tk.END)
            self.listbox.selection_set(idx_atual + 1)
            self.listbox.activate(idx_atual + 1)
            self.listbox.see(idx_atual + 1)

if __name__ == "__main__":
    root = tk.Tk()
    app = AuditApp(root)
    root.mainloop()
