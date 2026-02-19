import os, asyncio, shutil
import sys

# Garante playwright
try:
    from playwright.async_api import async_playwright
except ImportError:
    print("❌ Erro: Playwright não encontrado. pip install playwright")
    sys.exit(1)

# PASTAS DO SEU REPOSITÓRIO
# Usando caminho relativo para robustez
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DIR_LIXO = os.path.join(SCRIPT_DIR, "06_LIXO_CONFIRMADO")
if not os.path.exists(DIR_LIXO):
    DIR_LIXO = r"C:\Users\99196\Documents\Diego-repositorio\06_LIXO_CONFIRMADO"

DIR_FINAL = os.path.join(SCRIPT_DIR, "04_IDENTIFICADOS_FINAL")
if not os.path.exists(DIR_FINAL):
    DIR_FINAL = r"C:\Users\99196\Documents\Diego-repositorio\04_IDENTIFICADOS_FINAL"
    
URL_AHA = "https://www.aha-music.com/identify-songs-music-recognition-online"

async def verificar_no_aha(context, caminho_arquivo):
    page = await context.new_page()
    try:
        await page.goto(URL_AHA, timeout=60000)
        
        # Clica no botão 'Upload a file...' que vimos na imagem
        # Usando seletor robusto
        async with page.expect_file_chooser() as fc_info:
            try:
                await page.click("text=Upload a file...", timeout=5000) 
            except:
                # Tenta outra variante se falhar
                await page.click(".upload-btn, .btn-upload, button:has-text('Upload')", timeout=5000)
                
        file_chooser = await fc_info.value
        await file_chooser.set_files(caminho_arquivo)

        print(f"⏳ Analisando: {os.path.basename(caminho_arquivo)}...")
        
        # Espera o resultado (pode levar até 40s dependendo do arquivo)
        # O AHA mostra o nome da música em um link dentro de um h5
        # Adicionei seletores extras para garantir captura
        resultado_selector = "div.result-item h5 a, div.alert-danger, .result-title, h3:has-text('Result')"
        
        try:
            resultado = await page.wait_for_selector(resultado_selector, timeout=60000)
            texto = await resultado.inner_text()
            
            if "No record found" in texto or "not found" in texto.lower() or "Sorry" in texto:
                return None
            return texto.strip()
        except:
             # Timeout ou erro na seleção
            return None
            
    except Exception as e:
        # print(f"Erro processando {caminho_arquivo}: {e}")
        return None
    finally:
        await page.close()

async def main():
    if not os.path.exists(DIR_LIXO):
        print(f"❌ Erro: Pasta {DIR_LIXO} não encontrada")
        return

    os.makedirs(DIR_FINAL, exist_ok=True)

    async with async_playwright() as p:
        # Abrimos o navegador visível para você acompanhar e intervir se houver CAPTCHA
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        
        arquivos = [f for f in os.listdir(DIR_LIXO) if f.lower().endswith(('.mp4', '.mp3', '.m4a', '.wav'))]
        
        if not arquivos:
            print("✅ Pasta de lixo vazia! Tudo limpo ou verificado.")
            return

        print(f"🧐 Iniciando resgate AHA para {len(arquivos)} arquivos...")
        print(f"📂 Lendo de: {DIR_LIXO}")

        for i, arq in enumerate(arquivos):
            print(f"[{i+1}/{len(arquivos)}] 🔍 {arq}")
            caminho = os.path.join(DIR_LIXO, arq)
            
            res = await verificar_no_aha(context, caminho)
            
            if res:
                # Limpa o nome para salvar sem erro no Windows
                nome_limpo = "".join(x for x in res if x.isalnum() or x in " ._-")[:80].strip()
                if not nome_limpo: nome_limpo = "Resgate_AHA_" + str(i)
                
                novo_caminho = os.path.join(DIR_FINAL, f"{nome_limpo}.mp4")
                if os.path.exists(novo_caminho):
                    novo_caminho = os.path.join(DIR_FINAL, f"{nome_limpo}_{i}.mp4")

                try:
                    shutil.move(caminho, novo_caminho)
                    print(f"✅ RESGATADO: {res} -> Salvo como {os.path.basename(novo_caminho)}")
                except Exception as e:
                    print(f"❌ Erro ao mover: {e}")
            else:
                print(f"🗑️ Confirmado como Lixo: {arq}")
            
            await asyncio.sleep(2) # Pausa para evitar bloqueio por spam

        print("\n🏆 Verificação Completa!")
        await browser.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Parando verificação.")
