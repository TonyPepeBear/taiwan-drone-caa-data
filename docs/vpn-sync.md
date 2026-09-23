# 隔離 VPN 同步

GitHub Actions 使用臨時 Docker 容器透過 WireGuard 抓取民航局資料。
僅民航局解析出的 IPv4 /32 路由走 VPN；主機路由不變，GitHub Release 在容器外發布。
容器不接收 GitHub Token。設定透過標準輸入傳入，暫存於 tmpfs，套用後即刪除。

## Repository Secret

設定 `WIREGUARD_CONFIG`，內容為 `wg setconf` 格式：

```ini
[Interface]
PrivateKey = <client-private-key>
[Peer]
PublicKey = <server-public-key>
AllowedIPs = 0.0.0.0/0
Endpoint = <vpn-host>:51820
PersistentKeepalive = 25
```

不得將真實設定、金鑰或端點提交到 repository。不要放入 `Address`、`DNS` 等
`wg-quick` 專用欄位。目前容器介面位址為 `10.14.0.2/32`；更換配置時需一併確認。

設定缺失、VPN 連線或同步失敗會使工作失敗，不自動改成直連發布。
工作上限為 30 分鐘。Workflow 支援手動觸發及既有每日排程。

未設定 `SYNC_USE_VPN=true` 時，`scripts/run_sync.sh` 保留本機直接同步行為。
發佈流程先取得上一版 manifest，再抓取及比較一次，避免重複下載所有圖層。

驗證：`python3 -m unittest discover -s tests -v`。
