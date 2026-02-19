import os, shutil

# Caminhos ajustados para o ambiente e robustez
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DIR_FINAL = os.path.join(SCRIPT_DIR, "04_IDENTIFICADOS_FINAL")
if not os.path.exists(DIR_FINAL):
    DIR_FINAL = r"C:\Users\99196\Documents\Diego-repositorio\04_IDENTIFICADOS_FINAL"

# O arquivo de lista será salvo na raiz do repositório
LISTA_TXT = os.path.join(SCRIPT_DIR, "Músicas_do_Mauro_LISTA_FINAL.txt")

def finalizar():
    if not os.path.exists(DIR_FINAL):
        print(f"❌ Pasta {DIR_FINAL} não encontrada.")
        return

    # 1. Corrigir nomes com erro de acentuação (UTF-8)
    print("🔧 Corrigindo acentuação nos nomes...")
    arquivos = os.listdir(DIR_FINAL)
    for arq in arquivos:
        try:
            # Tenta corrigir Mojibake comum (UTF-8 interpretado como CP1252)
            # Ex: "GraÃ§a" -> "Graça"
            # Se já estiver correto, o encode/decode pode falhar ou não mudar nada
            novo_nome_bytes = arq.encode('cp1252')
            novo_nome = novo_nome_bytes.decode('utf-8')
            
            if novo_nome != arq:
                origem = os.path.join(DIR_FINAL, arq)
                destino = os.path.join(DIR_FINAL, novo_nome)
                
                # Evita sobrescrever se já existe
                if not os.path.exists(destino):
                    os.rename(origem, destino)
                    print(f"✨ Corrigido: {arq} -> {novo_nome}")
        except Exception as e:
            # print(f"Pulo: {arq} ({e})")
            pass

    # 2. Gerar a Lista de Ouro para o Mauro
    print("📝 Gerando índice oficial...")
    # Relista após correções
    musicas = [f for f in os.listdir(DIR_FINAL) if f.lower().endswith(('.mp4', '.mp3', '.m4a', '.wav'))]
    
    # Remove extensões para a lista bonita
    nomes_bonitos = []
    for m in musicas:
        base = os.path.splitext(m)[0]
        # Remove sufixos técnicos
        base = base.replace("_6720", "").replace("_original", "")
        nomes_bonitos.append(base)
        
    nomes_bonitos.sort()
    
    with open(LISTA_TXT, "w", encoding="utf-8") as f:
        f.write(f"📊 ACERVO DO MAURO - 2026\n")
        f.write(f"🎵 TOTAL DE MÚSICAS: {len(nomes_bonitos)}\n")
        f.write("="*40 + "\n\n")
        for i, m in enumerate(nomes_bonitos, 1):
            f.write(f"{i:03d}. {m}\n")

    print(f"✅ Lista salva em: {LISTA_TXT}")
    print(f"📦 Agora, execute o 'smart_convert.py' para sincronizar o pendrive.")

if __name__ == "__main__":
    finalizar()
