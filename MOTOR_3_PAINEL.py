import os, shutil, time, tkinter as tk, subprocess
from tkinter import ttk
import pygame
import numpy as np
import imageio_ffmpeg
from difflib import SequenceMatcher
import threading

REPO = r"C:\Users\99196\Documents\Diego-repositorio"
PASTAS = {
    'ref': os.path.join(REPO, "04_IDENTIFICADOS_FINAL"),
    'mp3': os.path.join(REPO, "08_MUSICAS_COMPLETAS_MAURO"),
    'err': os.path.join(REPO, "09_MUSICAS_ERRADAS"),
    'ok':  os.path.join(REPO, "10_MUSICAS_APROVADAS")
}

for p in PASTAS.values(): os.makedirs(p, exist_ok=True)

class DJArcadeGame:
    def __init__(self, root):
        self.root = root
        self.root.title("\U0001f916 DJ DIEGO ARCADE V16 - MODO DEUS (Piloto Automatico)")
        self.root.geometry("900x750")
        self.root.configure(bg="#09090b")

        pygame.mixer.init()
        self.ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
        self.offset_calculado = 20.0
        self.confianca_ia = 0.0  # O NIVEL DE CERTEZA DA IA
        self.start_offset = 20.0
        self.total_length = 0.0
        self.is_dragging = False
        self.tocando_ref = False
        self.calculando = False
        self.first_play = True

        self.auto_pilot = False  # COMECA DESLIGADO

        self.score = 0
        self.combo = 1
        self.last_action_time = time.time()

        self.arquivos = [f for f in os.listdir(PASTAS['mp3']) if f.endswith('.mp3')]
        self.arquivos.sort()
        self.total_inicial = len(self.arquivos)
        self.current_idx = 0

        # --- CABECALHO ---
        f_top = tk.Frame(root, bg="#09090b")
        f_top.pack(fill=tk.X, pady=10, padx=20)

        # Botao do Piloto Automatico
        self.btn_autopilot = tk.Button(f_top, text="\U0001f916 AUTO-PILOTO: OFF (P)", command=self.toggle_autopilot, bg="#475569", fg="white", font=("Arial", 12, "bold"))
        self.btn_autopilot.pack(side=tk.LEFT)

        self.lbl_combo = tk.Label(f_top, text="COMBO: x1 \U0001f525", font=("Consolas", 20, "bold"), bg="#09090b", fg="#f97316")
        self.lbl_combo.pack(side=tk.RIGHT)
        self.lbl_score = tk.Label(f_top, text="SCORE: 0", font=("Consolas", 24, "bold"), bg="#09090b", fg="#eab308")
        self.lbl_score.pack(side=tk.RIGHT, padx=20)

        style = ttk.Style()
        style.theme_use('default')
        style.configure("TProgressbar", thickness=15, background='#10b981', troughcolor='#1e293b')
        self.progress = ttk.Progressbar(root, orient=tk.HORIZONTAL, length=800, mode='determinate', style="TProgressbar")
        self.progress.pack(pady=5)

        # --- CARTA DA MUSICA ---
        self.f_card = tk.Frame(root, bg="#1e293b", bd=5, relief=tk.RIDGE)
        self.f_card.pack(pady=15, padx=40, fill=tk.BOTH, expand=True)

        self.lbl_restantes = tk.Label(self.f_card, text=f"Restantes: {len(self.arquivos)}", font=("Arial", 12), bg="#1e293b", fg="#94a3b8")
        self.lbl_restantes.pack(pady=5)
        self.lbl_musica = tk.Label(self.f_card, text="Carregando...", font=("Arial", 20, "bold"), bg="#1e293b", fg="#38bdf8", wraplength=700)
        self.lbl_musica.pack(expand=True)
        self.lbl_status = tk.Label(self.f_card, text="\U0001f4e1 CALCULANDO SINCRONIA...", font=("Arial", 14, "bold"), bg="#1e293b", fg="#f59e0b")
        self.lbl_status.pack(pady=5)

        # --- RADAR DE TEMPO ---
        f_time = tk.Frame(self.f_card, bg="#1e293b")
        f_time.pack(fill=tk.X, padx=50, pady=10)
        self.lbl_time = tk.Label(f_time, text="00:00 / 00:00", font=("Consolas", 18, "bold"), bg="#1e293b", fg="#fbbf24")
        self.lbl_time.pack(pady=5)

        self.slider = ttk.Scale(f_time, from_=0, to=100, orient="horizontal", command=self.on_slider_move)
        self.slider.pack(fill=tk.X)
        self.slider.bind("<ButtonRelease-1>", self.on_slider_release)
        self.slider.bind("<ButtonPress-1>", self.on_slider_press)

        # --- BOTOES E ATALHOS ---
        f_btn = tk.Frame(root, bg="#09090b")
        f_btn.pack(pady=10)

        tk.Button(f_btn, text="\U0001f4f1 TIKTOK (Espaco)", command=self.play_ref, bg="#f59e0b", fg="black", font=("Arial", 14, "bold"), width=18, height=2).grid(row=0, column=0, padx=10, pady=5)
        tk.Button(f_btn, text="\U0001f3b5 YOUTUBE (C)", command=self.play_completa, bg="#3b82f6", fg="white", font=("Arial", 14, "bold"), width=18, height=2).grid(row=0, column=1, padx=10, pady=5)
        tk.Button(f_btn, text="\u274c LIXO (Delete)", command=lambda: self.processar(PASTAS['err']), bg="#ef4444", fg="white", font=("Arial", 16, "bold"), width=18, height=2).grid(row=1, column=0, padx=10, pady=10)
        tk.Button(f_btn, text="\u2705 SUCESSO (Enter)", command=lambda: self.processar(PASTAS['ok']), bg="#10b981", fg="white", font=("Arial", 16, "bold"), width=18, height=2).grid(row=1, column=1, padx=10, pady=10)

        self.root.bind('<Return>', lambda e: self.processar(PASTAS['ok']))
        self.root.bind('<Delete>', lambda e: self.processar(PASTAS['err']))
        self.root.bind('<space>', lambda e: self.play_ref())
        self.root.bind('<c>', lambda e: self.play_completa())
        self.root.bind('<Right>', lambda e: self.pular(10))
        self.root.bind('<Left>', lambda e: self.pular(-10))
        self.root.bind('<p>', lambda e: self.toggle_autopilot())  # Novo atalho

        self.carregar_musica()
        self.update_clock()

    def toggle_autopilot(self):
        self.auto_pilot = not self.auto_pilot
        if self.auto_pilot:
            self.btn_autopilot.config(text="\U0001f916 AUTO-PILOTO: ON (P)", bg="#10b981")
            self.lbl_status.config(text="\U0001f916 IA ASSUMIU O CONTROLE!", fg="#10b981")
        else:
            self.btn_autopilot.config(text="\U0001f916 AUTO-PILOTO: OFF (P)", bg="#475569")

    # --- O CEREBRO DE DECISAO DA IA ---
    def obter_dados_audio(self, caminho):
        cmd = [self.ffmpeg_path, '-i', caminho, '-f', 's16le', '-acodec', 'pcm_s16le', '-ar', '4000', '-ac', '1', '-']
        pipe = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        return np.frombuffer(pipe.communicate()[0], dtype=np.int16)

    def calcular_sync(self, ref_path, comp_path):
        try:
            ref_data = self.obter_dados_audio(ref_path)[::2]
            comp_data = self.obter_dados_audio(comp_path)[::2]
            if len(comp_data) < len(ref_data): return 20.0, 0.0

            correlacao = np.correlate(comp_data, ref_data, mode='valid')
            max_idx = np.argmax(correlacao)

            # CALCULO DE CONFIANCA (Signal-to-Noise Ratio da Onda)
            media = np.mean(correlacao)
            maximo = correlacao[max_idx]
            score = maximo / (media + 1e-10)  # Se o pico for muito maior que a media, e a mesma musica!

            return (max_idx * 2) / 4000.0, score
        except: return 20.0, 0.0

    def _thread_sync(self, caminho_ref, caminho_mp3):
        offset, score = self.calcular_sync(caminho_ref, caminho_mp3) if os.path.exists(caminho_ref) else (20.0, 0.0)
        self.root.after(0, lambda: self._finalizar_carregamento(offset, score))

    def _finalizar_carregamento(self, offset, score):
        self.offset_calculado = offset
        self.confianca_ia = score
        self.calculando = False
        self.last_action_time = time.time()
        self.first_play = True

        # DECISAO DO AUTO-PILOTO (Se a confianca for alta > 15, aprova sozinho!)
        if self.auto_pilot and self.confianca_ia > 15.0:
            self.lbl_status.config(text=f"\U0001f916 IA APROVOU! (Certeza: {self.confianca_ia:.1f})", fg="#10b981")
            self.f_card.config(bg="#166534")  # Fica verde escuro
            self.root.update()
            time.sleep(0.5)  # Da meio segundo pra voce ver que ele aprovou
            self.processar(PASTAS['ok'])  # APERTA O ENTER SOZINHO!
        else:
            self.play_completa()

    def format_time(self, seconds): return f"{int(seconds // 60):02d}:{int(seconds % 60):02d}"
    def get_length(self, path):
        try: return pygame.mixer.Sound(path).get_length()
        except: return 0.0

    def play_completa(self, event=None):
        if self.current_idx >= len(self.arquivos) or self.calculando: return
        if not self.tocando_ref and not self.first_play: return

        if self.tocando_ref and pygame.mixer.music.get_busy():
            self.start_offset = self.offset_calculado + (self.start_offset + (pygame.mixer.music.get_pos() / 1000.0))
        elif self.first_play:
            self.start_offset = self.offset_calculado
            self.first_play = False

        self.tocando_ref = False
        self.lbl_status.config(text=f"\u25b6\ufe0f YOUTUBE (Score IA: {self.confianca_ia:.1f})", fg="#a855f7")
        nome = self.arquivos[self.current_idx]
        caminho_mp3 = os.path.join(PASTAS['mp3'], nome)
        self.total_length = self.get_length(caminho_mp3)
        self.slider.config(to=self.total_length)

        try:
            pygame.mixer.music.load(caminho_mp3)
            pygame.mixer.music.play(start=self.start_offset)
        except: pass

    def play_ref(self, event=None):
        if self.current_idx >= len(self.arquivos) or self.calculando: return
        if self.tocando_ref: return

        if not self.tocando_ref and pygame.mixer.music.get_busy() and not self.first_play:
            nova_pos = (self.start_offset + (pygame.mixer.music.get_pos() / 1000.0)) - self.offset_calculado
            self.start_offset = max(0.0, nova_pos)

        self.tocando_ref = True
        self.lbl_status.config(text="\U0001f4f1 TIKTOK (Referencia)", fg="#f59e0b")
        nome = self.arquivos[self.current_idx]
        caminho_ref = os.path.join(PASTAS['ref'], nome)
        self.total_length = self.get_length(caminho_ref)
        self.slider.config(to=self.total_length)

        try:
            if os.path.exists(caminho_ref):
                pygame.mixer.music.load(caminho_ref)
                pygame.mixer.music.play(start=self.start_offset)
        except: pass

    def on_slider_press(self, event): self.is_dragging = True
    def on_slider_move(self, val):
        if self.is_dragging: self.lbl_time.config(text=f"{self.format_time(float(val))} / {self.format_time(self.total_length)}")
    def on_slider_release(self, event):
        self.is_dragging = False
        self.start_offset = self.slider.get()
        if not self.calculando:
            try: pygame.mixer.music.play(start=self.start_offset)
            except: pass

    def pular(self, segundos):
        if pygame.mixer.music.get_busy() and not self.calculando:
            self.start_offset = max(0, min(self.total_length - 1, self.start_offset + (pygame.mixer.music.get_pos() / 1000.0) + segundos))
            try: pygame.mixer.music.play(start=self.start_offset)
            except: pass

    def update_clock(self):
        if pygame.mixer.music.get_busy() and not self.is_dragging and not self.calculando:
            current = min(self.total_length, self.start_offset + (pygame.mixer.music.get_pos() / 1000.0))
            self.lbl_time.config(text=f"{self.format_time(current)} / {self.format_time(self.total_length)}")
            self.slider.set(current)
        self.root.after(100, self.update_clock)

    def sao_parecidos(self, nome1, nome2):
        n1, n2 = nome1.lower().replace(".mp3", "").strip(), nome2.lower().replace(".mp3", "").strip()
        if n1 in n2 or n2 in n1: return True
        return SequenceMatcher(None, n1, n2).ratio() > 0.85

    def carregar_musica(self):
        if self.current_idx < len(self.arquivos):
            self.calculando = True
            nome = self.arquivos[self.current_idx]
            self.lbl_musica.config(text=nome.replace(".mp3", ""))
            self.lbl_restantes.config(text=f"Restantes: {len(self.arquivos) - self.current_idx}")
            if self.total_inicial > 0:
                self.progress['value'] = ((self.total_inicial - (len(self.arquivos) - self.current_idx)) / self.total_inicial) * 100

            self.lbl_status.config(text="\U0001f4e1 ALINHANDO BATIDAS...", fg="#f59e0b")
            caminho_mp3, caminho_ref = os.path.join(PASTAS['mp3'], nome), os.path.join(PASTAS['ref'], nome)
            threading.Thread(target=self._thread_sync, args=(caminho_ref, caminho_mp3), daemon=True).start()
        else:
            self.lbl_musica.config(text="\U0001f3c6 GAME OVER! VOCE VENCEU! \U0001f3c6", fg="#10b981", font=("Arial", 30, "bold"))
            self.lbl_status.config(text="Pen-drive do Mauro 100% Finalizado!", fg="#10b981")
            self.lbl_time.config(text="00:00 / 00:00")
            self.slider.set(0)
            self.progress['value'] = 100
            try: pygame.mixer.music.stop()
            except: pass

    def processar(self, pasta_destino):
        if self.current_idx >= len(self.arquivos) or self.calculando: return

        tempo_gasto = time.time() - self.last_action_time
        if tempo_gasto < 8.0:
            self.combo += 1
            self.f_card.config(bg="#4d7c0f")
        else:
            self.combo = 1
            self.f_card.config(bg="#7f1d1d")

        nome_atual = self.arquivos[self.current_idx]
        origem, destino = os.path.join(PASTAS['mp3'], nome_atual), os.path.join(pasta_destino, nome_atual)

        try: pygame.mixer.music.stop()
        except: pass
        pygame.mixer.quit()
        time.sleep(0.1)

        try:
            if os.path.exists(origem):
                if os.path.exists(destino): os.remove(destino)
                shutil.move(origem, destino)
        except: pass

        # MULTI-KILL
        arquivos_para_manter = []
        removidos_extras = 0
        for i in range(self.current_idx + 1, len(self.arquivos)):
            f_futuro = self.arquivos[i]
            if self.sao_parecidos(nome_atual, f_futuro):
                origem_futura, destino_futura = os.path.join(PASTAS['mp3'], f_futuro), os.path.join(pasta_destino, f_futuro)
                try:
                    if os.path.exists(origem_futura):
                        if os.path.exists(destino_futura): os.remove(destino_futura)
                        shutil.move(origem_futura, destino_futura)
                        removidos_extras += 1
                except: pass
            else: arquivos_para_manter.append(f_futuro)

        self.arquivos = self.arquivos[:self.current_idx + 1] + arquivos_para_manter

        if removidos_extras > 0:
            bonus = 150 * removidos_extras
            self.score += bonus
            self.root.after(200, lambda: self.lbl_status.config(text=f"\U0001f525 MULTI-KILL! {removidos_extras} movidas juntas!", fg="#f59e0b"))

        self.score += 100 * self.combo
        self.lbl_score.config(text=f"SCORE: {self.score}")
        self.lbl_combo.config(text=f"COMBO: x{self.combo} \U0001f525" if self.combo > 1 else "COMBO: x1")

        pygame.mixer.init()
        self.root.after(150, lambda: self.f_card.config(bg="#1e293b"))
        self.current_idx += 1
        self.carregar_musica()

if __name__ == "__main__":
    root = tk.Tk()
    DJArcadeGame(root)
    root.focus_force()
    root.mainloop()
