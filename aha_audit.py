import os, asyncio, shutil
import sys

# Garante que playwright está instalado na importação ou avisa usuário
try:
    from playwright.async_api import async_playwright
except ImportError:
    print("❌ Erro: Biblioteca 'playwright' não encontrada.")
    print("Execute: pip install playwright && playwright install chromium")
    sys.exit(1)

# CONFIGURAÇÕES
# Pastas relativas ou absolutas - ajustando para ser robusto
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# Tenta usar a estrutura padrão, se não existir, usa o diretório do script
DIR_LIXO = os.path.join(SCRIPT_DIR, "06_LIXO_CONFIRMADO")
if not os.path.exists(DIR_LIXO):
    DIR_LIXO = r"C:\Users\99196\Documents\Diego-repositorio\06_LIXO_CONFIRMADO"

DIR_FINAL = os.path.join(SCRIPT_DIR, "04_IDENTIFICADOS_FINAL")
if not os.path.exists(DIR_FINAL):
    DIR_FINAL = r"C:\Users\99196\Documents\Diego-repositorio\04_IDENTIFICADOS_FINAL"

URL_AHA = "https://www.aha-music.com/identify-songs-music-recognition-online"

async def identificar_no_aha(browser_context, caminho_arquivo):
    page = await browser_context.new_page()
    try:
        # Aumentei o timeout de navegação para garantir carregamento em conexões lentas
        await page.goto(URL_AHA, timeout=90000)
        
        # Faz o upload do arquivo (o AHA aceita .mp4 e .mp3)
        # Procura pelo botão de upload - pode variar, então tento ser genérico mas preciso
        async with page.expect_file_chooser() as fc_info:
            # Tenta clicar no botão de upload pelo texto ou classe comum
            # Estratégia: procurar input type file injetado ou botão visível
            # O site AHA usa um botão com classe 'upload-btn' ou texto
            try:
                await page.click("button:has-text('Upload a file')", timeout=5000)
            except:
                # Fallback: clica no input file invisível se existir ou tenta outro seletor
                await page.click(".upload-area", timeout=5000)
                
        file_chooser = await fc_info.value
        await file_chooser.set_files(caminho_arquivo)

        print(f"⏳ Analisando no AHA: {os.path.basename(caminho_arquivo)}...")
        
        # Espera o resultado aparecer
        # O AHA costuma mostrar o resultado em .result-item ou .result-title
        # Ajustei o seletor para ser mais abrangente
        try:
             # Espera qualquer indicador de resultado (sucesso ou falha)
            resultado = await page.wait_for_selector(".result-item h5 a, .result-title, .alert-danger, .no-result", timeout=60000)
            texto = await resultado.inner_text()
            
            # Reconhecimento negativo
            if "No record found" in texto or "Not found" in texto or "Sorry" in texto:
                return None
            
            return texto.strip()
        except:
            return None
            
    except Exception as e:
        # print(f"Erro ao processar {caminho_arquivo}: {e}")
        return None
    finally:
        await page.close()

async def main():
    if not os.path.exists(DIR_LIXO):
        print(f"❌ Erro: Pasta de origem '{DIR_LIXO}' não encontrada.")
        return

    # Garante que destino existe
    os.makedirs(DIR_FINAL, exist_ok=True)

    arquivos = [f for f in os.listdir(DIR_LIXO) if f.lower().endswith(('.mp4', '.mp3', '.m4a', '.wav'))]
    
    if not arquivos:
        print(f"✅ Pasta '06_LIXO_CONFIRMADO' está vazia! Nada para auditar.")
        return

    print(f"🚀 Iniciando Auditoria AHA em {len(arquivos)} arquivos da lixeira...")
    print(f"📂 Origem: {DIR_LIXO}")
    print(f"📂 Destino (se salvar): {DIR_FINAL}")

    # Headless=False para você ver o robô trabalhando
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        
        for i, arq in enumerate(arquivos):
            caminho = os.path.join(DIR_LIXO, arq)
            print(f"[{i+1}/{len(arquivos)}] 🔍 Verificando: {arq}")
            
            res = await identificar_no_aha(context, caminho)
            
            if res:
                # Limpa o nome do arquivo resultante
                nome_clean = "".join(x for x in res if x.isalnum() or x in "._- ")[:80].strip()
                if not nome_clean: nome_clean = "Recovered_Song_" + str(i)
                
                novo_caminho = os.path.join(DIR_FINAL, f"{nome_clean}.mp4")
                
                # Evita sobrescrever se já existe
                if os.path.exists(novo_caminho):
                    novo_caminho = os.path.join(DIR_FINAL, f"{nome_clean}_{i}.mp4")
                
                try:
                    shutil.move(caminho, novo_caminho)
                    print(f"✅ AHA RESGATOU: {res} -> Movido para Final!")
                except Exception as e:
                    print(f"❌ Erro ao mover arquivo: {e}")
            else:
                print(f"🗑️ AHA Confirmou Lixo: {arq}")
                # Opcional: Poderíamos mover para uma pasta 'LIXO_DEFINITIVO' ou deixar aqui
                
        print("\n🏆 Auditoria Finalizada!")
        await browser.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Auditoria interrompida pelo usuário.")
