# 臺灣行政區快照

- 發布機關：內政部國土測繪中心。
- 縣市來源：<https://api.nlsc.gov.tw/other/ListCounty>。
- 鄉鎮市區來源：<https://api.nlsc.gov.tw/other/ListTown1/{countycode}>；戶政清單，不是地政區。
- 官方資料集與授權說明：<https://data.gov.tw/dataset/102011>。
- 授權：[政府資料開放授權條款－第1版](https://data.gov.tw/license)，使用時應註明來源。
- 下載日期：2026-11-03（臺北時間）。
- 原始檔：`raw/counties.xml` 與 `raw/towns-*.xml`，保留下載內容。
- 轉換：`python scripts/fetch_tw_districts.py`；已有原始檔時可用 `--offline` 重建，不連網。
- 輸出：`tw_districts.json`，22 縣市、368 鄉鎮市區；臺中市 29 區。
- 欄位：`city` 來自 `countyname`，`districts` 來自各縣市的 `townname`，沿用官方「臺」字與順序。
- `/regions` 執行時只讀此 JSON，並於程式內快取；不連外部 API。
