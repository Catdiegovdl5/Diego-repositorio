#!/bin/bash
echo "🚀 Jules iniciando reparo de áudio..."

# Mata processos travados
killall -9 pipewire wireplumber pipewire-pulse pulseaudio 2>/dev/null

# Limpa o socket de áudio que está bloqueando a conexão
rm -f /run/user/1000/pulse/native

# Reinicia os serviços em segundo plano
pipewire &
sleep 2
wireplumber &
sleep 2
pipewire-pulse &

echo "✅ Som reiniciado! Tente rodar o auditor agora."
