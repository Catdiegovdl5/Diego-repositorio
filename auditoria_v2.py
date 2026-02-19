import os
import shutil
import tkinter as tk
import subprocess

# Caminhos das suas pastas
DIR_REFERENCIA = r"C:\Users\99196\Documents\Diego-repositorio\04_IDENTIFICADOS_FINAL"
DIR_COMPLETAS = r"C:\Users\99196\Documents\Diego-repositorio\08_MUSICAS_COMPLETAS_MAURO"
DIR_ERRADAS = r"C:\Users\99196\Documents\Diego-repositorio\09_MUSICAS_ERRADAS"

class AuditoriaMaster:
    def __init__(self, root):
        self.root = root
        self.root.title("Auditoria Diego - 100% Certeza")
        self.root.geometry("700x550")
        
        # Cria a pasta de erradas se não existir
        os.makedirs(DIR_ERRADAS, exist_ok=True)
        
        # Garante que as pastas base existam
        if not os.path.exists(DIR_COMPLETAS):
            os.makedirs(DIR_COMPLETAS)
        if not os.path.exists(DIR_REFERENCIA):
            print(f"Aviso: Pasta de referência não encontrada: {DIR_REFERENCIA}")

        self.arquivos = [f for f in os.listdir(DIR_COMPLETAS) if f.lower().endswith(('.webm', '.mp3', '.mp4', '.m4a', '.wav'))]
        self.arquivos.sort()
        
        self.label = tk.Label(root, text=f"Músicas para conferir: {len(self.arquivos)}", font=("Arial", 12, "bold"))
        self.label.pack(pady=10)

        self.listbox = tk.Listbox(root, width=80, height=18, font=("Consolas", 10))
        for f in self.arquivos: self.listbox.insert(tk.END, f)
        self.listbox.pack(padx=20, pady=10)

        btn_frame = tk.Frame(root)
        btn_frame.pack(pady=10)

        # Botões de controle
        # Usando lambda para passar argumentos se necessário, mas aqui são simples
        tk.Button(btn_frame, text="🎬 OUVIR REF (TikTok)", command=self.play_ref, bg="#f59e0b", width=20).grid(row=0, column=0, padx=5)
        tk.Button(btn_frame, text="🎵 OUVIR COMPLETA", command=self.play_full, bg="#10b981", width=20).grid(row=0, column=1, padx=5)
        
        # NOVO BOTÃO: Mandar para pasta de erradas
        tk.Button(btn_frame, text="❌ MARCAR COMO ERRADA", command=self.marcar_errada, bg="#ef4444", fg="white", width=25, font=("Arial", 9, "bold")).grid(row=1, column=0, columnspan=2, pady=15)

    def play_ref(self):
        sel = self.listbox.curselection()
        if sel:
            nome = self.listbox.get(sel[0])
            # Remove a extensão webm/mp3 e tenta achar o mp4 original
            base = os.path.splitext(nome)[0]
            # Tenta encontrar correspondente na referência
            # A referência pode ter o mesmo nome base + .mp4
            ref_path = os.path.join(DIR_REFERENCIA, base + ".mp4")
            
            if os.path.exists(ref_path): 
                os.startfile(ref_path)
            else:
                # Tente procurar algo similar se o nome exato não for encontrado
                print(f"Referência exata não encontrada: {ref_path}")
                # Fallback simples: tentar achar arquivo que comece com o mesmo nome
                for f in os.listdir(DIR_REFERENCIA):
                    if f.startswith(base):
                        os.startfile(os.path.join(DIR_REFERENCIA, f))
                        return
                print("Nenhuma referência encontrada.")

    def play_full(self):
        sel = self.listbox.curselection()
        if sel:
            path = os.path.join(DIR_COMPLETAS, self.listbox.get(sel[0]))
            if os.path.exists(path):
                os.startfile(path)
            else:
                print(f"Arquivo não encontrado: {path}")

    def marcar_errada(self):
        sel = self.listbox.curselection()
        if sel:
            index = sel[0]
            nome_arquivo = self.listbox.get(index)
            origem = os.path.join(DIR_COMPLETAS, nome_arquivo)
            destino = os.path.join(DIR_ERRADAS, nome_arquivo)
            
            try:
                # Se o arquivo estiver tocando, pode dar erro ao mover.
                # Não temos como parar o player padrão do sistema facilmente via os.startfile.
                # O usuário terá que fechar o player primeiro se der erro de permissão.
                shutil.move(origem, destino)
                self.listbox.delete(index)
                
                # Atualiza contagem
                self.arquivos.remove(nome_arquivo) # Remove da lista interna também
                self.label.config(text=f"Músicas para conferir: {len(self.arquivos)}")
                
                print(f"🚩 Movido para ERRADAS: {nome_arquivo}")
            except PermissionError:
                print(f"❌ Erro de permissão: Feche o player de música antes de mover!")
                tk.messagebox.showerror("Erro", "Feche o player de música/vídeo antes de mover o arquivo.")
            except Exception as e:
                print(f"❌ Erro ao mover: {e}")

if __name__ == "__main__":
    root = tk.Tk()
    app = AuditoriaMaster(root)
    root.mainloop()
