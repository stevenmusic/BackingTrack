# BackingTrack 專案規則

## 和弦詞彙
- `QUALITY` 表是對著 HarmonyMap 的和弦資料庫生出來的：它的 80 種和弦類型、
  連同每種的別名寫法，共 134 種拼法。HarmonyMap 加了新和弦，這裡要跟著補，
  兩個工具看得懂的東西必須是同一套
- 兩個不收：「So What」有空白當不了 token；「♯5」跟 `C♯5` 撞在一起，一律當後者

## 音源
三軌都在 sfzinstruments 這個 org 底下（跟鋼琴同一家），要換之前先問：
- 鋼琴：Salamander Grand，跟 ScrollScore 指向同一組檔案
- 鼓：Virtuosity Drums（Versilian Studios × Karoryfer，KVRDC'21）。
  這是波士頓實錄的**爵士鼓組**（鼓手 Austin McMahon），不是管弦打擊樂。
  取 `Samples/mid/`（中距離麥克風）那一組
- 貝斯：Black And Blue Basses 的 `darkblack` 指彈電貝斯，mf 力度

VCSL 看起來像是鼓，其實是管弦打擊樂（定音鼓、大鑼、碰鈸），不要拿來當爵士鼓用。

每一份檔案都走 `fetchDecode()` 的多來源清單：jsDelivr →
raw.githubusercontent（鋼琴多一條 tonejs.github.io）。同一份檔案不同路由，
新增音源時照這個模式走，不要只寫一個網址。

## 兩個軸:感覺歸和弦,疏密歸使用者
不要再把「曲風」做成選單。一開始讓使用者直接挑 Bossa/Pop/Rock/Smooth Jazz,
結果是 8 組進行 × 4 種風格裡一堆說不通的組合(Dm9-G13-Cmaj9 套 Rock、
C-F-G-F 套 Bossa)。「要用哪種感覺」本來就是和弦決定的。

- **感覺**(`FEELS`,自動):`detectFeel()` 看和弦語彙——有九度以上延伸音 → swing、
  只有六度七度 → latin、只剩三和弦 → straight。決定 swing 比例、鼓的三件、
  貝斯走法、comping 位置。畫面上不顯示,使用者聽得出來就好,不要再加標籤
- **伴奏樣式**(`PATTERNS`,使用者選):pad / comp / drive,只管疏密與力度倍率
- 兩個在排程時交叉(`feel()` × `pat()`)。加新東西時想清楚它屬於哪一軸;
  九種組合每一種都要成立
- `drive` 會把貝斯往上推一級:straight → 八分推進、swing → 走動低音,
  latin 維持 bossa 的形狀(那個切分就是它的味道,改掉就不是 bossa)

## 鼓與貝斯永遠都在
沒有開關，不要再加回去。`lhGain()` 固定回 0.55（貝斯一直在，鋼琴左手要讓位）。

## 響度
拿來跟著彈的，音量不夠會被真鋼琴蓋過去。鏈路是
`masterGain ×1.9 → 限幅器(−10dB, 20:1) → outGain ×1.25`。
三段一起調，動其中一個就要重新量：目標 peak ≤0.85、RMS −12～−14 dBFS、零削波。
outGain 放到 2.4 會讓尖峰衝到 1.6 直接爆掉（實測過）。

## 版面
- 860px 以上分兩欄（左 `.col` 輸入、右 `.col` 播放），目標是整頁一個螢幕高。
  改版面時拿 `document.body.scrollHeight` 量一下，1280px 下不要超過 900
- 窄螢幕疊回一欄，兩欄的 DOM 順序必須跟單欄想要的順序一致
- 一排按鈕數量不固定時用 grid 不要用 flex：flex 會把最後一行剩下的幾顆撐滿整列，
  同一顆鈕在不同行寬度差一倍（音名列、開關列都踩過）

## 技術棧
- 單檔 HTML，CSS/JS 內嵌，CDN only，無 build，GitHub Pages 直接部署
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
- 正規化時不要動 `+`。寫 `/+/g` 是「Nothing to repeat」語法錯誤（整支 script 都不會跑），
  就算改成 `/[+]/g` 寫對了，`It+6` 也會被換成 `Itaug6`、`7+5` 變 `7aug5`，兩個都查不到。
  `+`、`7+5`、`It+6` 一律當字面 key 收在 QUALITY 表裡
- `/` 有兩個意思：`C/E` 是轉位低音，`6/9` 是和弦記號自己帶的斜線。只有斜線後面
  真的是音名時才當轉位，否則整串留著查表（用 lastIndexOf，`C6/9/E` 才切得對）
- 中文輸入法很容易打出 `Ｃ７` 這種全形字，正規化第一步就要把全形英數符號轉半形
- 六、七個音的和弦不要整組照彈。捨音順序：五音 → 根音（轉位時不能捨）→ 延伸音，
  上聲部最多四個音（見 `trimTones`）
- 和弦品質表的 key 大小寫有意義（`M7` 是大七、`m7` 是小七），不能整串 toLowerCase
- 每小節都要從所有轉位裡挑離前一小節最近的那個，不然 C→F→G 會整組跳上跳下，
  聽起來像機器在按琴鍵（見 `buildVoicing` 的 cost）
- Salamander 每個八度只錄 C / D# / F# / A 四個音，其餘用 playbackRate 補位。
  音域是 A0–C8，鋼琴全音域都蓋得到，低音區不需要另外處理
- 鼓是 FLAC，`decodeAudioData` 對 FLAC 的支援不如 mp3（舊的 iOS Safari 可能吃不下），
  所以每個鼓件都要留合成備援（見 `synthDrum`），不能假設取樣一定載得到
- 貝斯一律待在 E1–D#2（`bassMidiFor`）。移調只換音級、不跟著跑到別的音域，
  不然移幾度貝斯就飛到鋼琴中間、低音整個空掉
- 貝斯軌開著時鋼琴左手要降音量（`lhGain`），同一個根音疊兩層低頻會糊
- 三種伴奏樣式的左手低音都要留長（撐兩拍，墊底撐整小節），不要只響一個音就收掉
- 變化用 `hash01(絕對小節號, salt)`，不要改成 `Math.random()`：那樣連「這一拍到底
  加了沒」都無法重現，出問題沒辦法追
- `hash01` 一定要兩輪 murmur 收尾。第一版只混一輪，整體分布看起來沒問題
  （四分位都是 0.25），但把 salt 固定、小節號從 0 數上去會連出一串很小的值，
  實測貝斯前五小節全部選到同一條路。雪崩不夠就是會這樣，不要為了短而簡化它
- 過門的鼓件（htom / ltom / crash）加起來 2MB 出頭，要背景載、不要擋播放
  （見 `ensureDrums` 裡沒有 await 的那條）。還沒到位時 `synthDrum` 會頂著
- 一格的進行沒有「最後一格」可言，過門只在兩格以上才給
- 大段落搬移程式碼時，先確認 `hash01` / `chance` 這種被大家用到的小工具沒被一起搬走。
  整段換掉 `STYLE_FNS` 那次就把它們刪掉了，症狀是「取樣都載好了但按播放沒聲音」，
  而且 pageerror 抓不到（錯誤發生在 promise 的 .then 裡），要靠 window error 才看得到
- 過門不要佔滿最後兩拍、也不要寫成整串 tom 滾奏：從八分突然跳成十六分很突兀。
  預設只佔最後一拍，hi-hat 要繼續走不能斷，力度從很輕推上去
