# taiwan-drone-caa-data

台灣民航局（CAA）無人機空域圖資的開源資料倉庫，自動從民航局 GIS 平台同步並透過 [GitHub Releases](../../releases) 發布歷史版本。

## 資料來源

- 入口網站：<https://drone.caa.gov.tw/>
- GIS 圖台：<https://dronegis.caa.gov.tw/portal/apps/webappviewer/index.html?id=807bd21438ba4208b4a7e28569fe41aa>
- API 類型：ArcGIS REST FeatureServer

本倉庫整理的是上述公開圖台背後使用的 ArcGIS REST 端點，並非官方正式文件化的 API。

## 收錄圖層

| 代號 | 名稱 | 說明 | 近期筆數 |
|---|---|---|---|
| `uav_restricted_airspace` | 主空域 / 禁限航區 | 全台各類禁飛、限飛、機場周邊範圍 | ~4,700 |
| `temporary_area` | 臨時空域 | 臨時公告區域 | ~5 |
| `national_park` | 國家公園 | 國家公園範圍 | ~65 |
| `commercial_port` | 商港區 | 商港相關範圍 | ~30 |
| `county` | 行政區 | 縣市行政區邊界 | ~22 |

## 如何下載資料

所有資料都放在 [GitHub Releases](../../releases)，每次同步有變動時自動發布。

每個 Release 包含以下檔案：

```
uav_restricted_airspace.geojson.gz    # 主空域 / 禁限航區
temporary_area.geojson.gz             # 臨時空域
national_park.geojson.gz              # 國家公園
commercial_port.geojson.gz            # 商港區
county.geojson.gz                     # 行政區
uav_restricted_airspace.metadata.json # 各圖層 metadata
temporary_area.metadata.json
national_park.metadata.json
commercial_port.metadata.json
county.metadata.json
manifest.json                         # 總表（含所有圖層資訊）
all-layers.zip                        # 全部圖層打包（含未壓縮 GeoJSON）
```

### 快速下載最新版

以下連結指向最新 Release 的附件，點擊即可下載：

- [all-layers.zip](https://github.com/TonyPepeBear/taiwan-drone-caa-data/releases/latest/download/all-layers.zip) — 全部圖層打包
- [uav_restricted_airspace.geojson.gz](https://github.com/TonyPepeBear/taiwan-drone-caa-data/releases/latest/download/uav_restricted_airspace.geojson.gz) — 主空域 / 禁限航區
- [temporary_area.geojson.gz](https://github.com/TonyPepeBear/taiwan-drone-caa-data/releases/latest/download/temporary_area.geojson.gz) — 臨時空域
- [national_park.geojson.gz](https://github.com/TonyPepeBear/taiwan-drone-caa-data/releases/latest/download/national_park.geojson.gz) — 國家公園
- [commercial_port.geojson.gz](https://github.com/TonyPepeBear/taiwan-drone-caa-data/releases/latest/download/commercial_port.geojson.gz) — 商港區
- [county.geojson.gz](https://github.com/TonyPepeBear/taiwan-drone-caa-data/releases/latest/download/county.geojson.gz) — 行政區
- [manifest.json](https://github.com/TonyPepeBear/taiwan-drone-caa-data/releases/latest/download/manifest.json) — 總表

解壓 `.geojson.gz`：

```bash
gunzip uav_restricted_airspace.geojson.gz
```

### 使用 manifest.json

每個 release 都附帶 `manifest.json`，記錄所有圖層的同步時間、筆數、objectid 清單：

```json
{
  "dataset": "taiwan-drone-caa-data",
  "generated_at": "2026-04-08T00:15:00+00:00",
  "tag": "v2026.04.08-0015",
  "layer_count": 5,
  "layers": [...]
}
```

## Release 說明

- **Tag 格式**：`vYYYY.MM.DD-HHMM`（UTC+8 時間）
- **自動偵測變動**：比對前後兩版的 objectid 集合，只有實際資料有變動才會建立新 release
- **Release body**：列出每個圖層的筆數變化、新增 / 移除的 objectid
- **保留策略**：所有 release 全部保留，可回溯任意時間點的資料快照

## 自動同步

GitHub Actions 會在以下時機自動執行同步：

- 每日 **UTC+8 00:00**（UTC 16:00）
- 推送到 `main` 分支時
- 手動觸發（`gh workflow run sync.yml`）

流程：同步 → 比對前版 → 有變動才建立 release → 附帶 changelog 說明。

## 本機執行

```bash
# 同步全部圖層到指定目錄
python3 scripts/sync_arcgis.py --output-dir ./data/latest

# 只同步單一圖層
python3 scripts/sync_arcgis.py --layer uav_restricted_airspace --output-dir ./data/latest

# 同步並與前一版比對
python3 scripts/sync_arcgis.py --output-dir ./data/latest --compare-manifest path/to/manifest.json
```

腳本零外部依賴，只需要 Python 3.10+。

## 倉庫結構

```
.
├── .github/workflows/sync.yml    # GitHub Actions 自動同步
├── data/sources/layers.json      # 圖層來源定義
├── scripts/
│   ├── sync_arcgis.py            # 同步腳本
│   └── release.sh                # CI 發布腳本
└── docs/repository-design.md     # 設計說明
```

Git repo 不追蹤任何資料檔案，所有資料只存在 GitHub Releases。

## 常見欄位

以 `uav_restricted_airspace` 圖層為例：

| 欄位 | 說明 |
|---|---|
| `objectid` | 圖徵唯一識別 |
| `空域名稱` | 空域名稱 |
| `空域類別名稱` | 空域分類 |
| `空域說明` | 空域描述 |
| `限制區` | 限制類型 |
| `主管機關名稱` | 主管機關 |
| `會商機關名稱` | 會商機關 |
| `聯絡方式` | 聯絡資訊 |
| `罰則` | 違規罰則 |
| `有效日期起` | 生效起始日 |
| `有效日期迄` | 生效截止日 |

## 免責聲明

- 本倉庫整理的是公開可查詢的 ArcGIS REST 端點，不代表官方正式文件化 API
- 圖層編號、欄位名稱、資料內容未來可能調整
- 民航局網站標示圖資僅供參考，實際飛行仍應以主管機關公告為準
- 本倉庫不對資料正確性與即時性做任何保證
