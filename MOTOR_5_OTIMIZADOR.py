import os, shutil, subprocess, re
import numpy as np
import imageio_ffmpeg

REPO = r"C:\Users\99196\Documents\Diego-repositorio"
PASTAS = {
    'ref': os.path.join(REPO, "04_IDENTIFICADOS_FINAL"),
    'mp3': os.path.join(REPO, "08_MUSICAS_COMPLETAS_MAURO"),
    'err': os.path.join(REPO, "09_MUSICAS_ERRADAS"),
    'ok':  os.path.join(REPO, "10_MUSICAS_APROVADAS")
}

for p in PASTAS.values(): os.makedirs(p, exist_ok=True)
ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()

print("======================================================")
print("🤖 MOTOR 5: JUÍZ INVISÍVEL E MÁQUINA DE LAVAR NOMES")
print("⚡ TURBO MÁXIMO: Leitura Restrita a 15 Segundos")
print("======================================================\n")

# --- 🧹 1. A MÁQUINA DE LAVAR NOMES ---
def limpar_nome_arquivo(nome):
    novo_nome = nome
    padroes_lixo = [
        r'\(.*?(official|video|audio|lyric|remastered|live|hd|hq|1080p|4k).*?\)',
        r'\[.*?(official|video|audio|lyric|remastered|live|hd|hq|1080p|4k).*?\]',
        r'(?i)official video', r'(?i)official audio', r'(?i)music video',
        r'(?i)lyric video', r'(?i)lyrics', r'(?i)remastered', r'(?i) hd ', r'(?i) hq '
    ]
    for padrao in padroes_lixo:
        novo_nome = re.sub(padrao, '', novo_nome, flags=re.IGNORECASE)
    
    novo_nome = re.sub(r'\s+', ' ', novo_nome).replace(' - .mp3', '.mp3').replace(' -.mp3', '.mp3').strip()
    if not novo_nome.endswith('.mp3'): novo_nome += '.mp3'
    return novo_nome

# --- 🧠 2. O CÉREBRO NEURAL COM NITRO E TESOURA 🚀 ---
def obter_dados_audio(caminho):
    # A TESOURA ESTÁ AQUI: '-t', '15' (Lê só 15 segundos e para!)
    cmd = [ffmpeg_path, '-i', caminho, '-t', '15', '-f', 's16le', '-acodec', 'pcm_s16le', '-ar', '4000', '-ac', '1', '-']
    pipe = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    out, _ = pipe.communicate()
    return np.frombuffer(out, dtype=np.int16)

def calcular_confianca(ref_path, comp_path):
    try:
        ref_data = obter_dados_audio(ref_path)
        comp_data = obter_dados_audio(comp_path)
        
        if len(comp_data) < len(ref_data) or len(ref_data) == 0: return 0.0
        
        # FFT Mágico
        n = len(comp_data) + len(ref_data) - 1
        N = 2 ** (int(np.log2(n)) + 1) 
        
        A = np.fft.fft(comp_data, N)
        B = np.fft.fft(ref_data[::-1], N) 
        res = np.real(np.fft.ifft(A * B))
        
        correlacao = res[len(ref_data)-1 : len(comp_data)]
        
        media = np.mean(correlacao)
        maximo = np.max(correlacao)
        return maximo / (media + 1e-10) 
    except: return 0.0

# --- 🚀 3. O PROCESSAMENTO EM LOTE ---
arquivos = [f for f in os.listdir(PASTAS['mp3']) if f.endswith('.mp3')]
total = len(arquivos)

aprovadas_auto = 0
reprovadas_auto = 0
duvidas = 0

for i, nome in enumerate(arquivos, 1):
    caminho_mp3 = os.path.join(PASTAS['mp3'], nome)
    caminho_ref = os.path.join(PASTAS['ref'], nome)
    
    print(f"[{i:03d}/{total}] Analisando: {nome[:30]:<30} ...", end="", flush=True)

    if not os.path.exists(caminho_mp3):
        print(" ⚠️ Sumiu!")
        continue

    if not os.path.exists(caminho_ref):
        print(" ⚠️ Sem Referência")
        duvidas += 1
        continue

    score = calcular_confianca(caminho_ref, caminho_mp3)
    
    try:
        if score > 15.0:
            nome_limpo = limpar_nome_arquivo(nome)
            destino = os.path.join(PASTAS['ok'], nome_limpo)
            if os.path.exists(destino): destino = destino.replace(".mp3", f"_{i}.mp3")
            shutil.move(caminho_mp3, destino)
            print(f" ✅ APROVADA! (Score: {score:.1f})")
            aprovadas_auto += 1
            
        elif score < 3.0:
            destino = os.path.join(PASTAS['err'], nome)
            if os.path.exists(destino): os.remove(destino)
            shutil.move(caminho_mp3, destino)
            print(f" ❌ REJEITADA! (Score: {score:.1f})")
            reprovadas_auto += 1
            
        else:
            print(f" 🤷‍♂️ DÚVIDA    (Score: {score:.1f})")
            duvidas += 1
            
    except Exception as e:
        print(f" ⚠️ Erro ao mover")
        duvidas += 1 

print("\n======================================================")
print("🏁 MOTOR 5 CONCLUÍDO COM SUCESSO!")
print(f"   ✅ Aprovadas sozinhas: {aprovadas_auto}")
print(f"   ❌ Rejeitadas sozinhas: {reprovadas_auto}")
print(f"   🎧 Restaram para o Jogo: {duvidas}")
print("======================================================")
