#!/bin/sh
# Rigenera icona e immagini dai sorgenti SVG (servono rsvg-convert e ImageMagick).
# Uso: sh assets/crea_icona.sh
set -e
cd "$(dirname "$0")"
T=$(mktemp -d)
for n in 16 24 32 48 64 128 256; do rsvg-convert -w $n -h $n rhino2sw_icona.svg -o "$T/i$n.png"; done
convert "$T/i16.png" "$T/i24.png" "$T/i32.png" "$T/i48.png" "$T/i64.png" "$T/i128.png" "$T/i256.png" rhino2sw.ico
rsvg-convert -w 256 rhino2sw_icona.svg -o rhino2sw.png
rsvg-convert -w 256 rhino2sw_logo.svg -o rhino2sw_logo.png
rm -r "$T"
echo "fatto: rhino2sw.ico, rhino2sw.png, rhino2sw_logo.png"
