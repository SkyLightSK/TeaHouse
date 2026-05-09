#!/usr/bin/env bash
#
# Rebuild every distribution target from source/.
# Idempotent — safe to run repeatedly.
#
# Skips steps gracefully when source files don't exist yet (e.g. no master
# Blender file, no captured splat) so this can be wired into CI from day one.
#
# Required tools (install on demand, not all at once):
#   - blender (sudo apt install blender / brew install --cask blender)
#   - gltfpack (npm i -g gltfpack)
#   - usdzconvert (Apple's Reality Converter, or pip install usd-core + script)
#   - node (already required by the rest of the repo)
#
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

MASTER_BLEND="source/rooms/teahouse.blend"
RAW_SPLAT="source/captures/raw-splats/teahouse.ply"

mkdir -p exports/master exports/web exports/web/props exports/unity exports/unreal exports/apple

step() {
  echo
  echo "==> $1"
}

# 1. Validate spec
step "Validating spec/teahouse.room.json"
pnpm exec tsx tools/validate-spec.ts spec/teahouse.room.json

# 2. Master glb (uncompressed reference) from Blender
if [ -f "$MASTER_BLEND" ] && command -v blender >/dev/null 2>&1; then
  step "Exporting master glb from $MASTER_BLEND"
  blender "$MASTER_BLEND" --background --python tools/blender-export.py -- \
    --out exports/master/teahouse.glb --format glb
else
  if [ ! -f "$MASTER_BLEND" ]; then
    step "SKIP master export — $MASTER_BLEND does not exist yet"
  else
    step "SKIP master export — blender not found in PATH"
  fi
fi

# 3. Web target (Draco + Meshopt + KTX2)
if [ -f "exports/master/teahouse.glb" ] && command -v gltfpack >/dev/null 2>&1; then
  step "Packing web glb (gltfpack -cc -tc)"
  gltfpack -i exports/master/teahouse.glb -o exports/web/teahouse.glb -cc -tc
elif [ -f "exports/master/teahouse.glb" ]; then
  step "gltfpack not found — copying master glb to exports/web/teahouse.glb (uncompressed)"
  cp exports/master/teahouse.glb exports/web/teahouse.glb
else
  step "SKIP web pack — no master glb yet"
fi

# 4. Splat compression (raw .ply -> .ksplat)
if [ -f "$RAW_SPLAT" ]; then
  step "Compressing splat: $RAW_SPLAT -> exports/web/teahouse.ksplat"
  if command -v node >/dev/null 2>&1 && [ -f "tools/pack-splat.mjs" ]; then
    node tools/pack-splat.mjs "$RAW_SPLAT" exports/web/teahouse.ksplat || \
      step "WARN splat packer failed, copying raw .ply"
  fi
  if [ ! -f "exports/web/teahouse.ksplat" ]; then
    cp "$RAW_SPLAT" exports/web/teahouse.ply
    step "Copied raw .ply to exports/web/teahouse.ply (web runtime can also load .ply directly)"
  fi
else
  step "SKIP splat pack — $RAW_SPLAT does not exist yet"
fi

# 5. Unity / Unreal: FBX with unpacked textures
if [ -f "$MASTER_BLEND" ] && command -v blender >/dev/null 2>&1; then
  step "Exporting Unity FBX"
  blender "$MASTER_BLEND" --background --python tools/blender-export.py -- \
    --out exports/unity/teahouse.fbx --format fbx --unpack-textures
  step "Exporting Unreal FBX"
  blender "$MASTER_BLEND" --background --python tools/blender-export.py -- \
    --out exports/unreal/teahouse.fbx --format fbx --unpack-textures
fi

# 6. Apple: USDZ
if [ -f "$MASTER_BLEND" ] && command -v blender >/dev/null 2>&1; then
  step "Exporting USD"
  blender "$MASTER_BLEND" --background --python tools/blender-export.py -- \
    --out exports/apple/teahouse.usd --format usd
  if command -v usdzconvert >/dev/null 2>&1; then
    step "Converting USD -> USDZ"
    usdzconvert exports/apple/teahouse.usd exports/apple/teahouse.usdz || \
      step "WARN usdzconvert failed; .usd is still usable on Omniverse"
  fi
fi

step "Done. Targets in exports/"
ls -la exports/web/ exports/unity/ exports/unreal/ exports/apple/ exports/master/ 2>/dev/null || true
