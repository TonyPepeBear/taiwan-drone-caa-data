# Repository Design

## 目標

這個倉庫將台灣民航局無人機空域圖資從 ArcGIS REST API 同步下來，透過 GitHub Releases 發布，讓任何人都可以下載最新與歷史版本的 GeoJSON 資料。

## 目錄結構

```text
.
├── .github/workflows/sync.yml    # GitHub Actions 自動同步流程
├── .gitignore
├── CONTRIBUTING.md
├── README.md
├── data/
│   └── sources/
│       └── layers.json            # 圖層來源定義（唯一設定來源）
├── docs/
│   └── repository-design.md
└── scripts/
    ├── sync_arcgis.py             # 同步腳本
    └── release.sh                 # CI 比對 + 發布腳本
```

Git repo **不追蹤**任何資料檔案（GeoJSON、壓縮檔、metadata），所有資料只存在 GitHub Releases。

## 資料格式

### Release 附件清單（共 12 個檔案）

| 檔案 | 說明 |
|---|---|
| `uav_restricted_airspace.geojson.gz` | 主空域 / 禁限航區 |
| `temporary_area.geojson.gz` | 臨時空域 |
| `national_park.geojson.gz` | 國家公園 |
| `commercial_port.geojson.gz` | 商港區 |
| `county.geojson.gz` | 行政區 |
| `uav_restricted_airspace.metadata.json` | 主空域 metadata |
| `temporary_area.metadata.json` | 臨時空域 metadata |
| `national_park.metadata.json` | 國家公園 metadata |
| `commercial_port.metadata.json` | 商港區 metadata |
| `county.metadata.json` | 行政區 metadata |
| `manifest.json` | 總表 |
| `all-layers.zip` | 全部圖層打包（含未壓縮 GeoJSON） |

### Release Tag 格式

`vYYYY.MM.DD-HHMM`（UTC+8 時間），例如 `v2026.04.08-0015`。

### manifest.json 結構

```json
{
  "dataset": "taiwan-drone-caa-data",
  "generated_at": "2026-04-08T00:15:00+00:00",
  "tag": "v2026.04.08-0015",
  "layer_count": 5,
  "layers": [
    {
      "slug": "uav_restricted_airspace",
      "title": "主空域 / 禁限航區",
      "service": "Hosted/UAV_fs/FeatureServer/3",
      "query_url": "...",
      "source_page": "...",
      "feature_count": 4744,
      "reported_count": 4744,
      "objectids": [1, 2, ...],
      "page_size": 1000,
      "page_count": 5,
      "fetched_at": "..."
    }
  ]
}
```

## 同步流程

### `sync_arcgis.py`

純 Python stdlib，無外部依賴。

- `--output-dir`：輸出目錄（預設 `data/latest`，CI 用 `/tmp/sync-output`）
- `--layer <slug>`：只同步單一圖層
- `--compare-manifest <path>`：傳入前一版 manifest，產出 `diff_report.json` 與 `changelog.md`

每個圖層輸出：
- `<slug>.geojson`（本地除錯用，不進 release）
- `<slug>.geojson.gz`（Release 用）
- `<slug>.metadata.json`

分頁策略：
- 小圖層：通常一頁完成
- 大圖層（如 UAV_fs）：以 `resultOffset + resultRecordCount` 分頁

### `release.sh`

CI 環境中執行的發布腳本：

1. 執行 `sync_arcgis.py` 同步資料
2. 下載最新 release 的 `manifest.json`
3. 比對新舊 manifest（objectid 集合差異）
4. 無變動 → 結束
5. 有變動 → 產生 changelog、打包 `all-layers.zip`、建立 release

### 差異比對邏輯

- 比較每個圖層的 objectid 集合
- 偵測新增 / 移除的 feature
- 產生人類可讀的 changelog

## GitHub Actions

- 觸發條件：
  - push 到 main
  - 手動 workflow_dispatch
  - 每日 UTC 16:00（= UTC+8 00:00）
- 權限：`contents: write`
- 不需要 commit 任何東西回 repo

## Release 保留策略

全部保留，不做清理。每個 release 都是一個時間點的完整快照。

## 後續可擴充項目

- 增加 TopoJSON 或 PMTiles 輸出
- 增加欄位字典與型別比對報告
- 增加 GitHub Pages 提供靜態 API
- 增加資料驗證（geometry 有效性檢查）
