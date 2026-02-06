#!/bin/bash
pulseaudio -k && sudo alsa force-reload && systemctl --user restart pipewire wireplumber
