#!/bin/bash
if (( $EUID != 0)); then
    echo "Please run as root"
    exit
fi
wget -q https://ltdata1.informatik.uni-hamburg.de/bbb-live-subtitles/audio_fork.zip
unzip -q audio_fork.zip -d audio_fork
cd audio_fork
cp mod_audio_fork.*  /opt/freeswitch/lib/freeswitch/mod
cp libwebsockets* /usr/local/lib
ldconfig
cd ..