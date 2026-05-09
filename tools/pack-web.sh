#!/usr/bin/env bash
#
# Convenience wrapper: pack a single glTF for web with Draco + KTX2 via gltfpack.
# Used by export-all.sh but can also be invoked directly when you produce a
# prop glb outside the master scene.
#
# Usage: tools/pack-web.sh <input.glb> <output.glb>
set -euo pipefail

if [ "$#" -ne 2 ]; then
  echo "Usage: $0 <input.glb> <output.glb>" >&2
  exit 2
fi

if ! command -v gltfpack >/dev/null 2>&1; then
  echo "gltfpack not found. Install with: npm i -g gltfpack" >&2
  exit 3
fi

mkdir -p "$(dirname "$2")"
gltfpack -i "$1" -o "$2" -cc -tc
echo "Packed $1 -> $2"
ls -la "$2"
