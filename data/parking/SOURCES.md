# 臺中市路外停車場資料

## 正式資料目前尚未下載

2026-11-03 以不含憑證的 GET 測試 TDX，回傳 HTTP 401。本次沒有取得使用者帳號或讀取 `.env`，也沒有改用其他來源充當 TDX。

`taichung_carparks.json` 是**等待憑證的空檔**，不是零間停車場的統計，也不是正式下載快照。其 `source.snapshot_date` 為 null、`status` 為 `awaiting_credentials`。正式 API 會說明尚未下載，供使用者自行輸入停車費，不會讀測試 fixture 當作行情。

| 項目 | 內容 |
| --- | --- |
| 發布／彙整機關 | 交通部 TDX；原始提供機關為臺中市停車資料主管機關 |
| API | <https://tdx.transportdata.tw/api/basic/v1/Parking/OffStreet/CarPark/City/Taichung?$format=JSON> |
| API 文件 | <https://tdx.transportdata.tw/api-service/swagger/basic/945f57da-f29d-4dfd-94ec-c35d9f62be7d> |
| 查詢條件 | 路外停車場（CarPark）、City=Taichung、JSON；非動態剩餘車位 |
| 授權 | [政府資料開放授權條款－第1版](https://data.gov.tw/license)，應註明交通部 TDX 與原提供機關 |
| 下載日期 | 尚未下載；成功後以 JSON 的 `source.snapshot_date` 記錄臺北日期 |
| 原始檔 | 成功下載後儲存於 `raw/taichung_carparks.json` |
| 轉換腳本 | `scripts/fetch_tdx_parking.py` |

## 使用者下載步驟

1. 到 <https://tdx.transportdata.tw/> 註冊，依平臺流程建立可用的 API 憑證，確認服務額度。
2. 只在本機程序環境設定 `TDX_CLIENT_ID`、`TDX_CLIENT_SECRET`；不要貼到聊天、寫進 repo 或提交憑證。
3. 執行 `python scripts/fetch_tdx_parking.py`。腳本先試匿名下載，遇到 401/403 才用上述環境變數取得短期權杖；不讀 `.env`，不輸出憑證或權杖。
4. 確認成功訊息與輸出 JSON 的來源／日期；檢查缺少 `TownName` 的筆數。腳本不從地址猜測行政區。
5. 重新啟動後端，重新載入快取，再確認所在地頁面的停車場清單。

已從 TDX 下載原始 JSON 時，也可執行 `python scripts/fetch_tdx_parking.py --from-file <原始檔>` 離線轉換。

## 輸出欄位與解析限制

- `id`：`CarParkID`（必要時 `CarParkUID`）；`name`：`CarParkName`。
- `district`：`TownName`，缺少時保留空字串，不推估。
- `address`：`Address`；`lat`／`lon`：`PositionLat`／`PositionLon`（亦接受 `CarParkPosition` 容器）。
- `fare_description`／`special_offer_description`：原始 `FareDescription`／`SpecialOfferDescription`。
- `monthly_rent_twd`／`monthly_rent_text`：明確月租字樣與金額的解析結果，以及未正規化的原文片段；無法確定就為 null。
- `source_updated_at`：原始更新時間，若原資料未提供就為 null。

解析先辨識「月租、月票、包月、定期票」，再取同一子句的金額；同一句中「日間、全日」等接續選項可沿用月租語意，跨句不沿用。優先全日，否則取最高金額。全形字元只用於比對，保留原文。排除明示的押金、保證金、工本費等附加費；計時、計次、年／季票或多月總價不會直接換成月租。這是參考值，可能漏掉不規則寫法，實際價格與適用資格仍以停車場公告為準。

測試用的合成 TDX 回應獨立放在 `tests/fixtures/parking/`；名稱、地址與來源均標示測試，不代表真實停車場，不列入正式統計。至少十種解析寫法目前來自合理範例，尚非真實快照抽樣。
