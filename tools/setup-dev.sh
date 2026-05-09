#!/usr/bin/env bash
#
# One-command development setup for environments where the project lives on a
# filesystem that does not support symlinks (exFAT, FAT32, NTFS without admin).
#
# Mirrors the project to ~/TeaHouse-dev/ on the home filesystem (which supports
# symlinks), runs pnpm install there, and shows you how to develop with both
# locations in sync.
#
# Usage:
#   bash tools/setup-dev.sh
#
# After it's done:
#   - Edit code in either location (they're rsync'd both ways below)
#   - Run `pnpm dev` from ~/TeaHouse-dev/
#
# When you're ready to commit, sync back to the source-of-truth location.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
DEV_DIR="${TEAHOUSE_DEV_DIR:-$HOME/TeaHouse-dev}"

# Detect underlying filesystem
fs_type() {
  df -T "$1" 2>/dev/null | awk 'NR==2 {print $2}'
}

REPO_FS="$(fs_type "$REPO")"
HOME_FS="$(fs_type "$HOME")"

echo "Repo at        $REPO   (filesystem: $REPO_FS)"
echo "Home at        $HOME   (filesystem: $HOME_FS)"
echo "Dev mirror at  $DEV_DIR"
echo

if [[ "$REPO_FS" =~ ^(ext|btrfs|xfs|zfs)$ ]]; then
  echo "Your repo is on a Linux filesystem ($REPO_FS) — symlinks work natively."
  echo "You can just run 'pnpm install && pnpm dev' here."
  exit 0
fi

echo "Your repo is on $REPO_FS which does not support symlinks."
echo "Mirroring to $DEV_DIR for development..."
echo

mkdir -p "$DEV_DIR"
rsync -a --delete \
  --exclude node_modules \
  --exclude exports/ \
  --exclude '.git/' \
  "$REPO/" "$DEV_DIR/"

echo
echo "Mirror complete. Next steps:"
echo
echo "  cd $DEV_DIR"
echo "  pnpm install"
echo "  pnpm dev"
echo
echo "While developing, run this script again to push changes from the repo to"
echo "the mirror, or use the helper aliases below in your shell rc:"
echo
echo "  alias teahouse-push='rsync -a --delete --exclude node_modules --exclude exports/ \"$REPO/\" \"$DEV_DIR/\"'"
echo "  alias teahouse-pull='rsync -a --delete --exclude node_modules --exclude exports/ \"$DEV_DIR/\" \"$REPO/\"'"
echo
echo "Or use Cursor's 'open folder' on $DEV_DIR and treat THAT as the working"
echo "copy; rsync changes back to $REPO when ready to commit."
