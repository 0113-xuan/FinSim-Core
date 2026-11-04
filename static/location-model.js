(function(root) {
  'use strict';
  const schemaWarning='資料庫尚未新增所在地與職業欄位，請管理者執行 04_profiles_location_occupation.sql。';
  function districtsForCity(regions,city){return [...(regions.find(region=>region.city===city)?.districts||[])];}
  function locationValues(regions,city,district){
    if(!city)return {city:null,district:null};
    const districts=districtsForCity(regions,city);
    if(!districts.length)throw new Error('請選擇清單中的縣市');
    if(district&&!districts.includes(district))throw new Error('請選擇該縣市的行政區');
    return {city,district:district||null};
  }
  function missingLocationColumns(error){
    return ['PGRST204','42703'].includes(error?.code)&&/\b(city|district|occupation)\b/i.test(error.message||'')&&/column|schema cache/i.test(error.message||'');
  }
  function withoutLocation(values){const result={...values};for(const key of ['city','district','occupation'])delete result[key];return result;}
  const money=value=>`NT$${Number(value).toLocaleString('zh-TW',{maximumFractionDigits:2})}`;
  function sortParkingLots(lots){
    return [...lots].sort((a,b)=>Number(a.monthly_rent_twd==null)-Number(b.monthly_rent_twd==null)||(a.name<b.name?-1:a.name>b.name?1:0));
  }
  function parkingLotText(lot){
    const fee=lot.monthly_rent_twd==null?Array.from(lot.fare_description||lot.special_offer_description||'未提供收費說明').slice(0,40).join(''): `${money(lot.monthly_rent_twd)}／月`;
    return `${lot.name}｜${lot.address||'未提供地址'}｜${fee}`;
  }
  function parkingSummary(district,stats){
    return `${district}有月租價的停車場 ${stats.count} 間，${stats.median==null?'不足 3 間，不提供中間價':`中間價 ${money(stats.median)}（一半的停車場比這便宜）`}`;
  }
  function parkingPresentation(district,data){
    return {message:data.message||'',summary:data.supported&&data.data_available&&data.lots.length?parkingSummary(district,data.monthly_rent_stats):'',
      coverage:data.coverage?`本縣市 ${data.coverage.total} 間停車場中，${data.coverage.with_monthly_rent} 間有月租價`:''};
  }
  const api={schemaWarning,districtsForCity,locationValues,missingLocationColumns,withoutLocation,sortParkingLots,parkingLotText,parkingSummary,parkingPresentation};
  if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.LocationModel=api;
})(globalThis);
