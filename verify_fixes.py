
import asyncio
from shazamio import Shazam
from miner_app import CoreMiner

async def run_tests():
    print("="*50)
    print("🚀 Iniciando Verificação de Resiliência do JULES")
    print("="*50)
    
    # ---------------------------------------------------------
    # Teste 1: Falha no fetch_link_metadata (NoneType Crash)
    # ---------------------------------------------------------
    print("\n[Teste 1] Simulando falha de Metadata (Proteção de UI)...")
    miner = CoreMiner()
    
    # Passamos uma URL propositalmente quebrada para forçar o erro no yt-dlp
    print("-> Extraindo dados de URL inválida...")
    title, duration = miner.fetch_link_metadata("https://tiktok.com/link_falso_do_mauro_123")
    
    if title == "Unknown":
        print("✅ PASSOU: O sistema interceptou o erro e retornou 'Unknown'. Sua interface está segura!")
    else:
        print(f"❌ FALHOU: O sistema retornou '{title}' (Era esperado: 'Unknown').")

    # ---------------------------------------------------------
    # Teste 2: Disponibilidade da API do Shazamio
    # ---------------------------------------------------------
    print("\n[Teste 2] Verificando a assinatura da API do Shazamio...")
    shazam = Shazam()
    
    if hasattr(shazam, 'recognize_song'):
        print("✅ PASSOU: O método ativo no seu PC é o 'recognize_song()'.")
    elif hasattr(shazam, 'recognize'):
        print("✅ PASSOU: O método ativo no seu PC é o 'recognize()'.")
    else:
        print("❌ FALHOU: Nenhum método de reconhecimento compatível foi encontrado!")
        
    print("\n" + "="*50)
    print("🏁 Verificação Concluída. Pode iniciar o MinerApp!")

if __name__ == "__main__":
    asyncio.run(run_tests())
