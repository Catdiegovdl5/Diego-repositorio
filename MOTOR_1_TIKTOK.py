import os, re, subprocess, uuid

# --- CONFIGURAÇÕES ---
REPO = r"C:\Users\99196\Documents\Diego-repositorio"
ARQUIVO_LINKS = os.path.join(REPO, "novos_links.txt")  # 🆕 Ficheiro limpo só com links novos
FILA = os.path.join(REPO, "00_FILA_TIKTOK")

os.makedirs(FILA, exist_ok=True)

def extrair_links():
    if not os.path.exists(ARQUIVO_LINKS):
        print(f"❌ Arquivo não encontrado: {ARQUIVO_LINKS}")
        return []
    with open(ARQUIVO_LINKS, "r", encoding="utf-8") as f:
        return list(set(re.findall(r'https://\S+tiktok\S+', f.read())))

def iniciar_coleta():
    links = extrair_links()
    if not links:
        print("❌ Nenhum link encontrado.")
        return

    # ============================================================
    # 🔴 Mude este número para pular links já processados!
    # ============================================================
    LINKS_PARA_PULAR = 0

    total = len(links)
    print("\n" + "=" * 60)
    print("🚜 MOTOR 1 LIGADO: Coletor de TikToks")
    print("=" * 60)
    print(f"📂 Fila de saída: {FILA}")
    print(f"🎯 Total de links: {total}")
    if LINKS_PARA_PULAR > 0:
        print(f"⏩ Pulando os primeiros {LINKS_PARA_PULAR} (já processados)")
    print("-" * 60)

    baixados = 0
    erros = 0

    for i, url in enumerate(links, 1):
        if i <= LINKS_PARA_PULAR:
            continue

        print(f"\n[{i}/{total}] 📥 Baixando: {url}")

        nome_unico = uuid.uuid4().hex[:6]
        caminho_video = os.path.join(FILA, f"vid_{nome_unico}.mp4")
        caminho_txt = os.path.join(FILA, f"vid_{nome_unico}.txt")

        # Guarda a URL original para o Motor 2 usar nos metadados
        with open(caminho_txt, "w") as f:
            f.write(url)

        # Baixa o TikTok (yt-dlp usa .part enquanto baixa, só vira .mp4 no fim)
        cmd_tk = [
            "yt-dlp", "-o", caminho_video,
            "--max-filesize", "15M",
            "--quiet", "--no-warnings",
            "--force-overwrites",
            url
        ]

        try:
            result = subprocess.run(cmd_tk, timeout=60)
            if result.returncode == 0 and os.path.exists(caminho_video):
                tamanho_mb = os.path.getsize(caminho_video) / (1024 * 1024)
                print(f"   ✅ Na fila! ({tamanho_mb:.1f} MB)")
                baixados += 1
            else:
                print("   ❌ Falhou (Privado/Apagado/Carrossel)")
                erros += 1
                # Remove o .txt órfão se o vídeo não baixou
                try:
                    if os.path.exists(caminho_txt):
                        os.remove(caminho_txt)
                except:
                    pass
        except subprocess.TimeoutExpired:
            print("   ❌ Timeout (60s). Pulando...")
            erros += 1
            try:
                if os.path.exists(caminho_txt):
                    os.remove(caminho_txt)
            except:
                pass
        except FileNotFoundError:
            print("❌ yt-dlp não encontrado! Instale com: pip install yt-dlp")
            return

    # RELATÓRIO
    print("\n" + "=" * 60)
    print("📊 MOTOR 1 - RELATÓRIO FINAL")
    print("=" * 60)
    print(f"   ✅ Vídeos na fila:  {baixados}")
    print(f"   ❌ Erros/Privados:  {erros}")
    print(f"   📁 Pasta da fila:   {FILA}")
    print("=" * 60)
    print("\n🏁 MOTOR 1 TERMINOU! O Motor 2 vai processar a fila.")

if __name__ == "__main__":
    iniciar_coleta()
