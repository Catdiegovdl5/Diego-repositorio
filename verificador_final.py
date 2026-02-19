import os
import tkinter as tk

# Caminhos baseados nas suas pastas
# Ajuste se necessário, mas esses são os do exemplo
DIR_REFERENCIA = r"C:\Users\99196\Documents\Diego-repositorio\04_IDENTIFICADOS_FINAL"
DIR_COMPLETAS = r"C:\Users\99196\Documents\Diego-repositorio\08_MUSICAS_COMPLETAS_MAURO"

class Auditoria:
    def __init__(self, root):
        self.root = root
        self.root.title("Auditoria Diego - 100% Certeza")
        
        # Check if directories exist to avoid crash
        if not os.path.exists(DIR_COMPLETAS):
            print(f"Diretório não encontrado: {DIR_COMPLETAS}")
            self.arquivos = []
        else:
            self.arquivos = [f for f in os.listdir(DIR_COMPLETAS) if f.lower().endswith(('.webm', '.mp3', '.mp4', '.m4a'))]
        
        self.label = tk.Label(root, text=f"Músicas para conferir: {len(self.arquivos)}", font=("Arial", 12))
        self.label.pack(pady=10)

        self.listbox = tk.Listbox(root, width=80, height=20)
        for f in self.arquivos: self.listbox.insert(tk.END, f)
        self.listbox.pack(padx=20, pady=10)

        btn_frame = tk.Frame(root)
        btn_frame.pack(pady=10)

        tk.Button(btn_frame, text="🎬 OUVIR REFERÊNCIA (TikTok)", command=self.play_ref, bg="orange").grid(row=0, column=0, padx=5)
        tk.Button(btn_frame, text="🎵 OUVIR COMPLETA (Baixada)", command=self.play_full, bg="lightgreen").grid(row=0, column=1, padx=5)

    def play_ref(self):
        sel = self.listbox.curselection()
        if sel:
            arquivo_completo = self.listbox.get(sel[0])
            # A referência deve ter o mesmo nome base? 
            # O exemplo do usuário diz: nome = self.listbox.get(sel[0]).replace(".webm", ".mp4")
            # Mas se o arquivo completo for .mp3?
            # Vamos tentar inferir o nome da referência. 
            # Geralmente é o mesmo nome base.
            base_name = os.path.splitext(arquivo_completo)[0]
            # Assumindo que a referência é .mp4
            nome_ref = base_name + ".mp4"
            path_ref = os.path.join(DIR_REFERENCIA, nome_ref)
            if os.path.exists(path_ref):
                os.startfile(path_ref)
            else:
                print(f"Referência não encontrada: {path_ref}")

    def play_full(self):
        sel = self.listbox.curselection()
        if sel:
            path_full = os.path.join(DIR_COMPLETAS, self.listbox.get(sel[0]))
            if os.path.exists(path_full):
                os.startfile(path_full)
            else:
                print(f"Arquivo não encontrado: {path_full}")

if __name__ == "__main__":
    root = tk.Tk()
    Auditoria(root)
    root.mainloop()
