-- profiles 新增所在地與職業（只新增選填欄位，不影響既有資料）
-- 在 Supabase SQL Editor 執行一次。可以重複執行。

alter table public.profiles add column if not exists city text
  check (city is null or char_length(city) between 1 and 10);           -- 縣市，例如「臺中市」
alter table public.profiles add column if not exists district text
  check (district is null or char_length(district) between 1 and 10);   -- 行政區，例如「北屯區」
alter table public.profiles add column if not exists occupation text
  check (occupation is null or char_length(occupation) between 1 and 40); -- 職業代號，清單由前端與後端共用

-- 確認：應該列出 city、district、occupation 三個欄位
select column_name, data_type, is_nullable
from information_schema.columns
where table_schema = 'public' and table_name = 'profiles'
  and column_name in ('city', 'district', 'occupation');
