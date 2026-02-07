#!/bin/bash
killall -9 pipewire wireplumber pipewire-pulse pulseaudio 2>/dev/null; rm -f /run/user/1000/pulse/native; pipewire & sleep 2; wireplumber & sleep 2; pipewire-pulse & echo -e "\n✅ JULES: Sistema de som reiniciado manualmente!\n"
