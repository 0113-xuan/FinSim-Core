# Codex 任務：更新車款價格，並把車款擴充到 30 款以上

日期：2026-11-04。完成後由 Claude 審查。

## 背景

- 購車事件會從車款清單自動帶入車價、排氣量和燃料種類，購車分析、車貸、稅費、保險參考都以這些數字計算。
- 目前有兩個問題：
  1. **價格過期**：清單是 2026-10 的快照，有些已經和車廠官網不同。例如 Toyota 官方試算頁顯示 Corolla Cross 汽油版約 88.9 萬，但清單寫 809,000。口試時如果評審打開官網對照，價格對不上會很難解釋。
  2. **車款太少**：計畫頁的車款清單只有 5 款，而且只有 Toyota 和 Honda。
- 使用者決定（2026-11-04）：
  - 總數擴充到 **30 款以上**。
  - 涵蓋四類：台灣熱銷大眾品牌、電動車、入門小車、進口豪華品牌。
- **分兩個 commit**：
  1. 先核對既有車款的價格（任務 A、B）。
  2. 再新增車款（任務 C、D）。

  方便分開審查。

## 工作規則

- 在現在的分支 `feat/frontend-upgrade` 上繼續做（HEAD `c00a46f`）。**不要 push**，不要建立新分支。
- 不讀 `.env`，不輸出任何 key。只 `git add` 你建立或修改的檔案，不要用 `git add .`。`docs/` 底下未追蹤的檔案與根目錄的 `futurewallet-flow.html` 不要動。
- 每個 commit 前執行 `python -m pytest -q` 和 `node --test tests/*.js`，全部通過才 commit。commit 結尾加上 `Co-Authored-By: Codex <noreply@openai.com>`。
- `index.html`、`vehicle.html`、`car-needs.html` 以及它們的 JS、CSS（包含 `static/vehicle-catalog.js`、`static/vehicle-costs.js`）不要修改。
- **既有車款的 `id` 一律不可以改，也不可以刪除**。使用者存在 Supabase 的購車事件會記錄 `vehicle_catalog_id`，改了或刪了，舊計畫就找不到車款。

## 資料來源規則（所有任務共用）

- **價格**：只用車廠**台灣官網**的建議售價，例如價格表、規格表、官方購車試算或官方訂購頁。
  - 不用經銷商、汽車新聞、比價網站的價格。
  - 不用限時優惠價、促銷價或含選配的價格。
- **排氣量、燃料種類**：用官網規格表。
- **油耗**：用官網規格表，或經濟部能源署「車輛油耗指南」的測試值。單位 km/L。
- **讀不到就不寫**：頁面需要 JavaScript 或被擋下、讀不到數字時，不可以用搜尋結果摘要、記憶或推測的數字當作已核對。
  - 既有車款：維持原值，寫進回報。
  - 新車款：不加進清單，寫進回報。

---

## 第一個 commit：核對既有車款

### 任務 A：核對官方價格

**範圍：兩份清單**

| 檔案 | 用途 | 筆數 |
| --- | --- | ---: |
| `app/vehicle_catalog.py` | 計畫頁購車事件、`vehicle.html` 的購車決策 | 5 |
| `app/recommendation_catalog.py` | `car-needs.html` 的推薦車款 | 7 |

對每一筆車款：

- **官網找到同等級的價格**：更新 `price_twd`。
- **官網找不到這個等級**（停售或改名）：價格不要改，在回報裡寫出你看到的官網現行等級名稱。不要自己改 `trim`，也不要換成別的等級。
- **排氣量、油耗、座位數**這次不改。如果官方數字和清單不同，寫進回報就好。

### 任務 B：每一筆車款自己記錄規格與查核日期

**`app/vehicle_catalog.py`**
- **排氣量和燃料種類**：現在 `catalog_list()` 用品牌寫死，例如 `1798 if item['brand']=='Toyota' else 1498`。改成每一筆車款自己的欄位：
  - `displacement_cc`
  - `fuel_type`：`gasoline`、`hybrid`、`diesel` 或 `ev`
  - `spec_source`
- **查核日期**：現在 `catalog_list()` 和 `get_vehicle()` 把 `checked_on` 寫死成 `'2026-10-11'`。改成每一筆車款自己的 `checked_on`，兩個函式回傳的值要一致。
- **有核對到新價格的車款**：
  - `checked_on` 改成實際查核日期。
  - `source_period` 同步更新。
  - `source_url` 指向實際讀到價格的官方頁面。
- **沒核對到的車款**：`checked_on` 和 `source_period` 維持原本的值，不要改成今天。
- **Honda HR-V**：目前的來源是 2025-06-17 的新聞稿。如果官網有現行的價格頁，改用官網頁面。

**`app/recommendation_catalog.py`**
- **有核對到的車款**：
  - 更新 `price_twd`。
  - `sources.price` 指向實際讀到價格的頁面。
  - `verification.price` 設為 `verified`。
- **查核日期**：`CHECKED_ON` 目前是全清單共用的日期。如果只核對到部分車款，改成每一筆自己的查核日期，不要讓沒核對的車款看起來像是今天查過。
- **Tesla**：目前是 `indexed_only`。
  - 能在官方訂購頁讀到售價：改成 `verified`，並更新說明。
  - 讀不到：維持原狀。

**兩份清單的同一個車款**（例如 Corolla Cross 汽油豪華），更新後的價格必須一致。

**這個 commit 不新增任何車款。**

---

## 第二個 commit：新增車款

### 任務 C：在 `app/vehicle_catalog.py` 新增車款

**目標**
- 加上原本的 5 款，總數**至少 30 款**。
- 每一款都必須符合上面的「資料來源規則」。

**怎麼挑**
- 每個車型最多 2 個等級。優先選最便宜的等級，有油電版的話再加油電版。
- 不收插電式油電（PHEV），因為稅費的燃料分類對不上。
- 四類都要有。下表是**建議的候選車款**，實際以官網能核對的結果為準。某款查不到或已停售，就換同一類的其他車款，並在回報裡說明。

| 類別 | 建議至少 | 候選車款（參考） |
| --- | ---: | --- |
| 台灣熱銷大眾品牌 | 12 | Toyota Yaris Cross、RAV4、Corolla Altis；Honda CR-V；Nissan Kicks、Sentra；Mazda CX-5、Mazda3；Ford Kuga、Focus；Hyundai Tucson L；Kia Sportage；Mitsubishi Outlander（非 PHEV 版） |
| 入門小車 | 5 | Toyota Yaris、Vios；Suzuki Swift；Honda FIT；Mitsubishi Colt Plus；Kia Picanto |
| 電動車 | 5 | Tesla Model 3、Model Y；Hyundai IONIQ 5；Toyota bZ4X；Volvo EX30；Kia EV6 |
| 進口豪華品牌 | 5 | Lexus UX、NX、ES；BMW 320i、X1；Mercedes-Benz C 200、GLA；Volvo XC40 |

**每一款的欄位**：和既有車款一樣，包含任務 B 新增的欄位。
- **`id`**：英文小寫加連字號，例如 `toyota-yaris-cross-gas`。不可以和既有 `id` 重複。
- **`efficiency_km_l`**：
  - 汽油、油電、柴油車必填。
  - 電動車填 `null`，這次不處理電耗。
- **電動車**：`displacement_cc` 為 `0`，`fuel_type` 為 `ev`。

`app/recommendation_catalog.py` 這次**不新增**車款，只做任務 A、B 的價格核對。

### 任務 D：讓舊頁面和計畫頁都能用

**1. `vehicle.html` 不能壞**
- `vehicle.html`（受保護，不能改）的 `static/vehicle-catalog.js` 會顯示 `vehicle.efficiency_km_l`，並用它試算每月油費。電動車沒有這個值。
- **`GET /decisions/vehicle/catalog`**：
  - 預設**只回傳 `efficiency_km_l` 不是 `null` 的車款**，`vehicle.html` 的行為不變。
  - 新增查詢參數 `include_ev=true`，回傳全部車款，包含電動車。
- **`vehicle_preset()`**：遇到電動車時回傳 422，訊息為「電動車沒有官方油耗，請自行填寫每月充電費用。」。不可以用 0 或其他數字代替油耗。

**2. 計畫頁 `static/plan-page.js`**
- 改呼叫 `/decisions/vehicle/catalog?include_ev=true`。
- **車款下拉選單**改用 `<optgroup>` 依品牌分組：
  - 品牌照中文排序或字母排序，選一種，前後一致。
  - 同品牌內依價格由低到高。
  - 選項文字為「車型 等級 · NT$xxx,xxx」。
  - 「自訂車款」維持在最後，而且是預設值。
- **已存的事件**：如果事件的 `vehicle_catalog_id` 是既有的 5 款，修改事件時要能正確選回。

**3. 其他會用到 `get_vehicle()` 的地方**
- 購車分析和計畫頁的事件驗證，都要能接受新車款（含電動車）的 `id`。

---

## 任務 E：測試

**價格與資料完整性**
- **兩份清單一致**：同品牌、車型、等級的車款，價格必須相同。
- **每一筆車款**：
  - `id` 不重複。
  - `price_twd` 為正整數。
  - `source_url`、`spec_source` 以 `https://` 開頭。
  - `checked_on` 是合法日期。
  - `fuel_type` 是四種之一。
  - 非電動車的 `displacement_cc > 0`，`efficiency_km_l > 0`。
  - 電動車的 `displacement_cc == 0`，`efficiency_km_l is None`。
- **總數與分類**：總數至少 30。電動車至少 3 款。進口豪華品牌（Lexus、BMW、Mercedes-Benz、Volvo 等）至少 3 款。
- **既有車款仍然存在**：既有 5 個 `id` 仍在清單裡。

**API**
- **`/decisions/vehicle/catalog`**：
  - 預設不含電動車。
  - `include_ev=true` 包含電動車。
  - 兩者的非電動車部分完全相同。
- **`/decisions/vehicle/preset`**：電動車回 422，訊息正確。
- **電動車的計畫事件**：用電動車 `id` 建立購車事件，送 `/planner/simulate` 和購車分析都成功，牌照稅為 0。

**既有測試怎麼改**
- **寫死清單價格的地方**，例如 `tests/test_vehicle_catalog.py` 的 `assert result['purchase_price'] == 809000`：改成從清單讀取，例如 `catalog_list()[0]['price_twd']`，不要改成另一個寫死的新數字。
- **寫死清單數量的地方**，例如 `len(items) == 5`：改成和清單長度比對。
- **測試自己指定的車價**（例如 `purchase_price=849000` 這類測試輸入資料）**不要改**。那些是測試計算邏輯用的數字，和清單無關。
- **`tests/fixtures/p0/vehicle_api_snapshots.json`**（`tests/test_vehicle_p0_regression.py` 使用）：
  - 回應裡直接帶出的車款資料可以更新，包括 `price_twd`、`checked_on`、`source_url`、`source_period`，以及 catalog 清單本身。
  - **任何計算結果**（月付、總成本、現金流、淨資產等）如果因此改變，**先停下來回報**。回報要列出是哪個 snapshot、哪個欄位、舊值和新值，不要直接更新 fixture。
  - 不可以為了讓測試通過而放寬或刪除 regression 測試。

**瀏覽器**
- **計畫頁**：
  1. 新增購車事件，車款選單有品牌分組、30 款以上。
  2. 選一款電動車，牌照稅顯示 0。
  3. 儲存後執行模擬和購車分析，都要成功。
  4. 修改一個用舊車款建立的事件，車款能正確選回。
- **`vehicle.html`**：車款清單正常載入、沒有電動車，選車後「帶入」油電費用照常運作。
- **畫面**：桌面和手機各截一張計畫頁車款選單的圖，console 沒有錯誤。

## 不在本任務範圍

- 電動車電耗與充電費用試算。
- 擴充 `app/recommendation_catalog.py` 的車款，或修改推薦邏輯。
- 修改保險、稅費、持有成本的計算或預設值。
- 修改 `index.html`、`vehicle.html`、`car-needs.html` 以及它們的 JS、CSS。

發現相關問題時寫進回報，不要修改。

## 完成後的回報

1. **Commit**：每個 commit 的 hash 和一句話說明。
2. **既有車款價格對照表**：12 筆，每筆一列，欄位為：
   - 清單
   - `id`
   - 車型與等級
   - 舊價格
   - 新價格
   - 官方頁面網址
   - 查核日期
   - 狀態：已核對，或沒核對到加原因
3. **新增車款表**：每筆一列，欄位為：
   - 類別
   - `id`
   - 車型與等級
   - 價格
   - 排氣量
   - 燃料
   - 油耗
   - 價格來源網址
   - 規格來源網址
4. **沒加入的候選車款**：哪些車款沒加入，以及原因（停售、讀不到價格等）。
5. **其他差異**：官網和既有清單不同的排氣量、油耗、等級名稱，只列出，不修改。
6. **Fixture 變更**：改了哪些欄位，並確認沒有任何計算結果改變。
7. **測試**：指令和結果，包含通過和失敗的數量。
8. **截圖**：檔案位置。
9. **其他**：沒有完成或刻意保留的部分，以及原因。

回報完就停下來。
