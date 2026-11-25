#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SYNC_OUTPUT="/tmp/sync-output"
PREV_DIR="/tmp/previous-release"

rm -rf "$SYNC_OUTPUT" "$PREV_DIR"
mkdir -p "$SYNC_OUTPUT" "$PREV_DIR"

PREV_MANIFEST=""
LATEST_TAG=""

echo "=== Checking for existing releases ==="
LATEST_TAG=$(gh release list --limit 1 --json tagName --jq '.[0].tagName // ""')
if [ -n "$LATEST_TAG" ]; then
    echo "Latest release: $LATEST_TAG"
    echo "Downloading previous manifest and GeoJSON..."
    gh release download "$LATEST_TAG" \
        --pattern "manifest.json" \
        --pattern "*.geojson.gz" \
        --dir "$PREV_DIR" \
        --clobber

    if [ -f "$PREV_DIR/manifest.json" ]; then
        PREV_MANIFEST="$PREV_DIR/manifest.json"
        echo "Previous manifest found, running comparison..."
        bash "$REPO_ROOT/scripts/run_sync.sh" \
            --output-dir "$SYNC_OUTPUT" \
            --compare-manifest "$PREV_MANIFEST" \
            --require-previous-geojson
    else
        echo "Previous manifest missing from release $LATEST_TAG" >&2
        exit 1
    fi
else
    echo "No existing releases, creating initial release..."
    bash "$REPO_ROOT/scripts/run_sync.sh" \
        --output-dir "$SYNC_OUTPUT" \
        --compare-manifest "/nonexistent"
fi

if [ -f "$SYNC_OUTPUT/diff_report.json" ]; then
    HAS_CHANGES=$(python3 -c "
import json, sys
d = json.load(open('$SYNC_OUTPUT/diff_report.json'))
print('true' if d.get('has_changes') else 'false')
")
else
    HAS_CHANGES="true"
fi

if [ "$HAS_CHANGES" = "false" ]; then
    echo "=== No changes detected, skipping release ==="
    exit 0
fi

echo "=== Changes detected, creating release ==="

TAG=$(python3 -c "
import json
m = json.load(open('$SYNC_OUTPUT/manifest.json'))
print(m['tag'])
")

DISPLAY_DATE=$(python3 -c "
from datetime import datetime, timezone, timedelta
tz = timezone(timedelta(hours=8))
now = datetime.now(tz)
print(now.strftime('%Y-%m-%d %H:%M'))
")

echo "Tag: $TAG"
echo "Title: 台灣空拍機空域資料 $DISPLAY_DATE"

CHANGELOG_FILE="$SYNC_OUTPUT/changelog.md"
if [ ! -f "$CHANGELOG_FILE" ]; then
    cat > "$CHANGELOG_FILE" << EOF
## 初始發布

首次同步民航局無人機空域圖資資料。
EOF
fi

echo "=== Creating all-layers.zip ==="
cd "$SYNC_OUTPUT"
ZIP_DIR="/tmp/all-layers-staging"
rm -rf "$ZIP_DIR"
mkdir -p "$ZIP_DIR"
cp *.geojson "$ZIP_DIR/"
cp *.metadata.json "$ZIP_DIR/"
cp manifest.json "$ZIP_DIR/"
cd "$ZIP_DIR"
zip -j "$SYNC_OUTPUT/all-layers.zip" ./*.geojson ./*.metadata.json ./manifest.json
cd "$REPO_ROOT"
rm -rf "$ZIP_DIR"

NOTES_FILE="$CHANGELOG_FILE"
# Large change lists are still available in the complete attachment.
if [ "$(wc -c < "$CHANGELOG_FILE")" -gt 60000 ]; then
    NOTES_FILE="$SYNC_OUTPUT/release-notes.md"
    {
        echo "## 變動摘要"
        echo
        grep -E '^### |^本次同步共 ' "$CHANGELOG_FILE"
        echo
        echo '完整新增、移除與更新名稱請見下方附件 `changelog.md`。'
    } > "$NOTES_FILE"
fi

echo "=== Creating release ==="
ASSETS=()
for f in "$SYNC_OUTPUT"/*.geojson.gz "$SYNC_OUTPUT"/*.metadata.json "$SYNC_OUTPUT"/manifest.json "$SYNC_OUTPUT"/all-layers.zip; do
    ASSETS+=("$f")
done
ASSETS+=("$CHANGELOG_FILE")

gh release create "$TAG" \
    "${ASSETS[@]}" \
    --title "台灣空拍機空域資料 $DISPLAY_DATE" \
    --notes-file "$NOTES_FILE"

echo "=== Release $TAG created successfully ==="
