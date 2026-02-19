import os, shutil

# CONFIGURAÇÕES DE ELITE
# Os arquivos já estão em 02_ORIGINAIS_REFERENCIA conforme verificado pelo comando list_dir
# Portanto origem e destino são o mesmo lugar, faremos um rename in-place
origem = "02_ORIGINAIS_REFERENCIA"
destino = "02_ORIGINAIS_REFERENCIA"

if not os.path.exists(origem):
    print(f"Pasta {origem} não encontrada! Verifique se você está no diretório certo.")
    exit()

arquivos = [f for f in os.listdir(origem) if f.lower().endswith(('.mp4', '.mp3'))]
print(f"📦 Encontrados {len(arquivos)} arquivos para limpar e renomear em {origem}...")

for i, nome in enumerate(arquivos):
    extensao = ".mp4" if nome.lower().endswith(".mp4") else ".mp3"
    novo_nome = f"track_{i+1}{extensao}"
    
    caminho_antigo = os.path.join(origem, nome)
    caminho_novo = os.path.join(destino, novo_nome)
    
    try:
        shutil.move(caminho_antigo, caminho_novo)
        print(f"✅ Renomeado: {nome[:30]}... -> {novo_nome}")
    except Exception as e:
        print(f"❌ Erro ao mover {nome[:30]}: {e}")

print("\n🚀 Tudo pronto! Agora a pasta 02_ORIGINAIS_REFERENCIA está abastecida com nomes seguros.")
