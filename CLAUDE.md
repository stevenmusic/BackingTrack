# BackingTrack 專案規則

## 技術棧
- 單檔 HTML，CSS/JS 內嵌，CDN only，無 build，GitHub Pages 直接部署
- 取樣鋼琴用 Salamander Grand（`https://tonejs.github.io/audio/salamander/`），
  跟 ScrollScore 指向同一組檔案，不要自己另外找一套音源
- 配色/字體/元件樣式跟 ScrollScore、SightScore、LoudMaster 共用同一套變數，不要自己發明新的
- 拍號固定 4/4，一個和弦一小節

## 絕不能做的事
- 不要把單檔拆成多檔案，除非我明確要求
- 不要改用 setTimeout 排音符。排程一律走 `AudioContext.currentTime` 提前排，
  setInterval 只負責「每隔一陣子來看一下」，不決定任何一個音的實際時間點
- 不要把取樣改成一次載完整組；iPad 第一次開會等很久。只抓這次進行真的會用到的音
- 不要拿掉解析失敗時擋住播放的那一段。看不懂的和弦要明講是哪一個 token，
  不要自作聰明猜成別的和弦

## 已知踩過的坑
- SVGElement 沒有 hidden 這個 IDL 屬性，`el.hidden = true` 只會掛上一個沒人看的 JS 屬性，
  內容屬性不會變。播放/停止圖示一定要走 setAttribute / removeAttribute（見 `hideSvg`）；
  而且瀏覽器內建的 `[hidden]{display:none}` 綁在 HTML 命名空間上，對 `<svg>` 無效，
  要自己寫一條 `svg[hidden]{display:none}`
- 速度改變時不能直接拿舊的 anchorTime 來減，要重新錨定：讓「下一個還沒排的拍」維持原本
  該響的時間，新速度從那一拍之後才生效，已經排進去的音不會被改到一半（見 `reanchorTempo`）
- 正規化和弦記號時，`+` → aug 那條 replace 的 regex 要寫成 `/[+]/g`。
  直接寫 `/+/g` 是「Nothing to repeat」語法錯誤，整支 script 都不會跑
- 和弦品質表的 key 大小寫有意義（`M7` 是大七、`m7` 是小七），不能整串 toLowerCase
- 每小節都要從所有轉位裡挑離前一小節最近的那個，不然 C→F→G 會整組跳上跳下，
  聽起來像機器在按琴鍵（見 `buildVoicing` 的 cost）
- Salamander 每個八度只錄 C / D# / F# / A 四個音，其餘用 playbackRate 補位。
  音域是 A0–C8，鋼琴全音域都蓋得到，低音區不需要另外處理
