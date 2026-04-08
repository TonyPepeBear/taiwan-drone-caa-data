# Contributing

## 開發流程

1. 修改 `data/sources/layers.json` 或 `scripts/sync_arcgis.py`
2. 本機測試：`python3 scripts/sync_arcgis.py --output-dir /tmp/test-sync`
3. 確認輸出格式正確
4. 提交變更

## 貢獻原則

- 保持腳本零外部依賴（純 Python stdlib）
- 不要在 repo 中追蹤資料檔案
- 若新增圖層，需同步更新 `data/sources/layers.json` 與 `README.md`
- 若上游欄位或 API 行為變更，請在 PR 描述中附上觀察結果

## 問題回報

Issue 建議附上：

- 圖層代號（slug）
- API 回應片段
- 預期結果與實際結果
- 若是地理圖徵問題，附上查詢座標

## 本機執行

```bash
# 同步全部圖層
python3 scripts/sync_arcgis.py --output-dir ./data/latest

# 只同步單一圖層
python3 scripts/sync_arcgis.py --layer uav_restricted_airspace --output-dir ./data/latest

# 同步並比對前一版
python3 scripts/sync_arcgis.py --output-dir ./data/latest --compare-manifest path/to/previous/manifest.json
```

## Release 流程

Release 由 GitHub Actions 自動管理，不需要手動操作。

如需手動觸發：

```bash
gh workflow run sync.yml
```

或在本機模擬（需要 `gh` 已登入）：

```bash
bash scripts/release.sh
```
