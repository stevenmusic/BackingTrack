# BackingTrack 跟著彈

輸入和弦進行，程式就生成鋼琴伴奏，讓學生跟著彈。
不用安裝任何東西，直接在瀏覽器裡用。

**[直接開啟工具 →](https://stevenmusic.github.io/BackingTrack/)**

打一行 `C - Am - F - G`，選伴奏樣式、拉速度，按播放。

---

## v1 有什麼

- **和弦輸入**：文字列 `C - Am - F - G`，用空白、`-` 或 `|` 分隔，一個和弦一小節，4/4 拍
- **看得懂的和弦**：大三、小三、七和弦（`G7` `Cmaj7` `Dm7`）、`sus2` / `sus4`、
  `dim` / `aug` / `m7b5` / `dim7`、六和弦、九和弦、`add9`，以及轉位 `C/E`
- **三種伴奏樣式**：全音符墊底、四分打、八分分解
- **速度**：BPM 直接輸入（40–240），另有 70 / 100 / 120 快捷
- **移調**：−12 ～ +12 半音，改的是取樣選擇，不是拉速度，所以沒有音質損失
- **count-in 兩小節**與**循環播放**，都可以關掉
- 進行與設定存在 localStorage；按「存這組」可以留下多組具名的進行
- 中英文切換、深淺色主題，跟其他工具共用同一份偏好

## v1 刻意沒有

鼓、貝斯、其他音色、複雜拍號、匯出檔案、譜面顯示。
這些留到 v2 再說，先把「輸入和弦就有伴奏」這件事做順。

## 怎麼運作

單檔 HTML，CSS/JS 全部內嵌，沒有 build，GitHub Pages 直接上。

鋼琴音色是 [Salamander Grand Piano](https://github.com/sfzinstruments/SalamanderGrandPiano)
的取樣，跟 ScrollScore 指向同一組檔案（Tone.js 官方託管的完整版）。
這套每個八度只錄 `C` / `D#` / `F#` / `A` 四個音，其餘的音用 `playbackRate` 變調補位——
最遠只差 1.5 個半音，聽不出失真。音域是 A0–C8，鋼琴全音域都蓋得到，低音區不必另外處理。

```
和弦文字 → 解析 → 配置(voicing) → 依樣式排成音符 → Salamander 取樣 → 殘響 → 限幅器
```

### 排程

每個音的時間點都是 `AudioContext.currentTime` 算出來、提前排進去的。
`setInterval` 每 25ms 醒來一次，只負責「把未來 0.15 秒內的音排一排」，
它自己的抖動不會變成拍子飄——`setTimeout` 直接拿來排音符才會。

速度改變時不能拿舊的錨點直接減。作法是讓「下一個還沒排的拍」維持原本該響的時間，
新速度從那一拍之後才生效，已經排進去的音維持原樣，不會被改到一半。

### 配置與聲部連接

每一小節都從所有轉位裡挑一個離前一小節最近的。不這樣做的話，`C → F → G`
會整組跳上跳下，聽起來像機器在按琴鍵，而不是有人在伴奏。

低音擺在 C2–B2 那個八度，上方和弦音疊在中央 C 附近；轉位（`C/E`）只改最低音，
不動上面的和弦音。

## 四個踩過的坑

1. **`SVGElement` 沒有 `hidden` 這個 IDL 屬性**。`el.hidden = true` 只會掛上一個
   沒人看的 JS 屬性，內容屬性不會變，CSS 自然比對不到。播放/停止圖示要走
   `setAttribute` / `removeAttribute`。而且瀏覽器內建的 `[hidden]{display:none}`
   綁在 HTML 命名空間上，對 `<svg>` 無效，得自己補一條 `svg[hidden]{display:none}`。
2. **`+` → `aug` 那條 replace 的 regex 要寫成 `/[+]/g`**。直接寫 `/+/g` 是
   「Nothing to repeat」語法錯誤，整支 script 都不會跑，頁面看起來像沒載入。
3. **和弦品質表的 key 大小寫有意義**：`M7` 是大七和弦、`m7` 是小七和弦。
   解析時不能整串 `toLowerCase`，不然這兩個會合併成同一個。
4. **AudioContext 一定要在使用者手勢之後 `resume()`**，不然畫面上看起來在播、
   實際上一點聲音都沒有。從背景切回來被系統暫停的情況也一起救回來。

## 之後想加的

鼓與貝斯軌。取樣庫可以看 Versilian VCSL（CC0，含打擊樂與貝斯）、
Freesound 上的 CC0 打擊樂。

## 授權與出處

鋼琴取樣來自 [Salamander Grand Piano](https://github.com/sfzinstruments/SalamanderGrandPiano)
（Alexander Holm，CC-BY 3.0）。
