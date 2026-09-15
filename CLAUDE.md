# PitchMaster 專案規則

## 技術棧
- 單檔 HTML，CSS/JS 內嵌，CDN only，無 build，GitHub Pages 直接部署
- @soundtouchjs/audio-worklet 0.2.1（版本釘死）做時間伸縮與移調
- 配色/字體/元件樣式跟 ScrollScore、LoudMaster 共用同一套變數，不要自己發明新的

## 絕不能做的事
- 不要把單檔拆成多檔案，除非我明確要求
- 不要動 SoundTouch 版本號，除非先確認該版本的 dist/soundtouch-worklet.js 還是
  一支自帶相依、可以直接丟給 addModule() 的檔案（2.x 改成 ESM + bare specifier，不能直接用）
- 不要拿掉 10 分鐘長度上限；那是為了 iPad 不要當掉

## 已知踩過的坑
- worklet 的 tempo/rate 參數不能用來變速：processor 是即時的，進 128 格就要吐 128 格，
  tempo != 1 會欠料破音。變速一律走 playbackRate，再用 pitch = 1/速度 把音高補回來
- addModule() 會被 CDN 的 Content-Type 擋掉，一定要留 fetch → Blob URL 的備援
- SVGElement 沒有 hidden 這個 IDL 屬性，el.hidden = true 不會生效；而且瀏覽器內建的
  [hidden]{display:none} 綁在 HTML 命名空間上，對 <svg> 無效，要自己寫一條 CSS
- 播放位置不能用 ctx.currentTime 直接減，速度改變時要重新錨定（見 positionNow）
