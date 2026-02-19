import os, shutil

# Determine the directory of the script
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DIR_FINAL = os.path.join(SCRIPT_DIR, "04_IDENTIFICADOS_FINAL")
RELATORIO = os.path.join(SCRIPT_DIR, "Músicas_do_Mauro_Prontas.txt")

def lapidar():
    print(f"💎 Iniciando lapidação final em {DIR_FINAL}...")
    if not os.path.exists(DIR_FINAL):
        print(f"❌ Erro: Diretório '{DIR_FINAL}' não encontrado.")
        return

    musicas = os.listdir(DIR_FINAL)
    vistas = set()
    duplicatas = 0
    lista_mauro = []

    # 1. Limpeza de Duplicatas
    for arq in musicas:
        nome_base = arq.lower().strip()
        if nome_base in vistas:
            file_path = os.path.join(DIR_FINAL, arq)
            try:
                os.remove(file_path)
                duplicatas += 1
                print(f"Removed duplicate: {arq}")
            except Exception as e:
                print(f"Error removing {arq}: {e}")
        else:
            vistas.add(nome_base)
            lista_mauro.append(arq.replace(".mp4", "").replace(".mp3", ""))

    # 2. Gerar Relatório
    lista_mauro.sort()
    with open(RELATORIO, "w", encoding="utf-8") as f:
        f.write(f"📊 TOTAL DE MÚSICAS ENCONTRADAS: {len(lista_mauro)}\n")
        f.write("-" * 30 + "\n")
        for m in lista_mauro:
            f.write(f"🎵 {m}\n")

    print(f"✅ Sucesso! {duplicatas} duplicatas removidas.")
    print(f"📝 Relatório '{RELATORIO}' gerado com {len(lista_mauro)} músicas.")
    print(f"📂 Pasta '04_IDENTIFICADOS_FINAL' está pronta para ser copiada para o Pen-drive!")

if __name__ == "__main__":
    lapidar()
