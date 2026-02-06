import os
import shutil
import subprocess
import asyncio
import threading
import customtkinter as ctk
from shazamio import Shazam

# --- CONFIGURAÇÃO ---
PASTA_FONTE = "FILTRADO_MAX_3"
PASTA_CERTO = "CERTO"
PASTA_LIXO = "LIXO"
# --------------------

for d in [PASTA_CERTO, PASTA_LIXO]:
    os.makedirs(d, exist_ok=True)

class SuperAuditorSync(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("AUDITOR PRO v3.0 - Jules Audio Fix")
        self.geometry("1000x700")
        ctk.set_appearance_mode("Dark")

        self.player_process = None
        self.ref_file = None
        self.mast_file = None
        self.shazam = Shazam()
        self.lista_completa = []

        if os.path.exists(PASTA_FONTE):
            subpastas = [f for f in os.listdir(PASTA_FONTE) if os.path.isdir(os.path.join(PASTA_FONTE, f))]
            self.lista_completa = sorted(subpastas)

        self.current_idx = 0
        self.total = len(self.lista_completa)

        if self.total == 0:
            print(f"⚠️ A pasta {PASTA_FONTE} está vazia!")
            self.destroy()
            return

        self.setup_ui()
        self.load_current()

        # Atalhos de Teclado
        self.bind("<space>", lambda e: self.play_ref())
        self.bind("<Return>", lambda e: self.play_master())
        self.bind("t", lambda e: self.sync_and_play())
        self.bind("s", lambda e: self.approve())
        self.bind("n", lambda e: self.reject())

    def setup_ui(self):
        self.lbl_prog = ctk.CTkLabel(self, text="0 / 0", font=("Arial", 18))
        self.lbl_prog.pack(pady=10)
        self.lbl_name = ctk.CTkLabel(self, text="...", font=("Arial", 22, "bold"), text_color="#3498DB", wraplength=850)
        self.lbl_name.pack(pady=10)
        frame = ctk.CTkFrame(self); frame.pack(expand=True, fill="both", padx=30, pady=20)
        btn_f1 = ctk.CTkFrame(frame, fg_color="transparent"); btn_f1.pack(pady=10)
        ctk.CTkButton(btn_f1, text="▶ VÍDEO (Espaço)", command=self.play_ref, fg_color="#E67E22", width=250).pack(side="left", padx=10)
        ctk.CTkButton(btn_f1, text="▶ MÚSICA (Enter)", command=self.play_master, fg_color="#9B59B6", width=250).pack(side="left", padx=10)
        self.btn_sync = ctk.CTkButton(frame, text="⚡ SINCRONIZAR BEAT (T)", command=self.sync_and_play, fg_color="#F1C40F", text_color="black", height=50, font=("Arial", 16, "bold")).pack(pady=20, padx=100, fill="x")
        ctk.CTkFrame(frame, height=2, fg_color="gray").pack(fill="x", padx=50, pady=20)
        btn_f2 = ctk.CTkFrame(frame, fg_color="transparent"); btn_f2.pack(pady=10)
        ctk.CTkButton(btn_f2, text="❌ LIXO (N)", command=self.reject, fg_color="#C0392B", width=200, height=60).pack(side="left", padx=20)
        ctk.CTkButton(btn_f2, text="✅ CERTO (S)", command=self.approve, fg_color="#27AE60", width=200, height=60).pack(side="left", padx=20)

    def stop_player(self):
        if self.player_process:
            try: self.player_process.terminate()
            except: pass
            self.player_process = None

    def load_current(self):
        if self.current_idx >= len(self.lista_completa):
            self.lbl_name.configure(text="🎉 REVISÃO CONCLUÍDA!")
            return
        folder = self.lista_completa[self.current_idx]
        self.curr_path = os.path.join(PASTA_FONTE, folder)
        self.lbl_prog.configure(text=f"Item {self.current_idx + 1} de {self.total}")
        self.lbl_name.configure(text=folder)
        self.ref_file = self._find(self.curr_path, [".mp4", ".mkv", ".webm"])
        self.mast_file = self._find(self.curr_path, [".mp3", ".wav"])

    def _find(self, p, exts):
        if not os.path.exists(p): return None
        for f in os.listdir(p):
            if any(f.lower().endswith(e) for e in exts): return os.path.join(p, f)
        return None

    def play_ref(self):
        self.stop_player()
        if self.ref_file:
            # FIX: Força Pulse ou ALSA para evitar erro de Host is Down
            self.player_process = subprocess.Popen(["mpv", "--ao=pulse,alsa", "--geometry=50%x50%", self.ref_file])

    def play_master(self, start_at=0):
        self.stop_player()
        if self.mast_file:
            # FIX: Força Pulse ou ALSA aqui também
            cmd = ["mpv", "--ao=pulse,alsa", "--force-window", "--geometry=450x250", f"--start={start_at}", self.mast_file]
            self.player_process = subprocess.Popen(cmd)

    def sync_and_play(self):
        if not self.ref_file: return
        def run_sync():
            try:
                loop = asyncio.new_event_loop(); asyncio.set_event_loop(loop)
                out = loop.run_until_complete(self.shazam.recognize(self.ref_file))
                offset = out.get('matches', [{}])[0].get('offset', 0)
                self.after(0, lambda: self.play_master(start_at=offset))
            except: self.after(0, lambda: self.play_master())
        threading.Thread(target=run_sync).start()

    def approve(self): self.stop_player(); self._move(PASTA_CERTO)
    def reject(self): self.stop_player(); self._move(PASTA_LIXO)

    def _move(self, dest):
        folder = self.lista_completa[self.current_idx]
        try:
            shutil.move(os.path.join(PASTA_FONTE, folder), os.path.join(dest, folder))
            del self.lista_completa[self.current_idx]
            self.total = len(self.lista_completa)
            self.load_current()
        except: pass

if __name__ == "__main__":
    app = SuperAuditorSync()
    app.mainloop()
