# PitchMaster

把音檔放慢到跟得上的速度，**音高完全不變**；或是整首移調 ±12 半音，換成唱得上去的調。
不用安裝任何東西，直接在瀏覽器裡用。

**[直接開啟工具 →](https://stevenmusic.github.io/PitchMaster/)**

拖進音檔（或點一下選檔），拉速度、拉移調，按播放。檔案不會上傳到任何伺服器，
全程在瀏覽器裡處理。

---

## v1 有什麼

- 拖放或點選載入音檔（MP3 / WAV / M4A / AAC / FLAC 等瀏覽器解得開的格式）
- **速度 50–150%**，5% 一格，100% 有吸附
- **移調 −12 ～ +12 半音**，變速與移調互不影響
- 播放／暫停（也吃空白鍵）、進度條可拖曳
- 快捷：×0.75、×1、重設
- 中英文切換、深淺色主題，跟其他工具共用同一份偏好

## v1 刻意沒有

AB 循環、count-in、設定記憶、匯出檔案、YouTube 連結、波形圖、音質預設。
這些要真的用一陣子才知道缺不缺，先把 v1 用順再說。

## 怎麼運作

單檔 HTML，CSS/JS 全部內嵌，沒有 build，GitHub Pages 直接上。
變速引擎是 [@soundtouchjs/audio-worklet](https://github.com/cutterbl/SoundTouchJS)
（版本釘死在 `0.2.1`），跑在 AudioWorklet 裡，不佔主執行緒。

```
File → decodeAudioData → AudioBufferSourceNode → SoundTouchNode → GainNode → destination
```

變速不是交給 worklet 的 `tempo` 參數，而是這樣分工：

| 要做的事 | 誰負責 |
| --- | --- |
| 速度 | `AudioBufferSourceNode.playbackRate`（音高會跟著跑掉） |
| 把音高補回來 | SoundTouch 的 `pitch` = `1 / 速度` |
| 移調 | SoundTouch 的 `pitchSemitones` |

原因是這顆 processor 是**即時**的：每個 render quantum 進 128 格就得吐出 128 格。
如果改用它自己的 `tempo`，進出格數就不相等（`tempo=2` 只吐得出 64 格），缺的部分
會變成破音，反過來則是愈拖愈長的延遲。改成「playbackRate 變速、pitch 補回音高」之後，
SoundTouch 內部是 `rate = pitch`、`tempo = 1/pitch`，進出剛好 1:1，不會欠料。

## 三個踩過的坑

1. **AudioWorklet 的 `addModule()` 會被 CDN 的 Content-Type / CORS 擋掉**。
   Worklet 規範要求 `text/javascript`，有些 CDN 回 `text/plain` 就直接失敗。
   備援是自己 `fetch` 回來、包成 Blob URL 再 `addModule()`——Blob 的 type 是我們自己
   指定的，一定過。兩個 CDN（jsDelivr、unpkg）各試一次直接載入與 Blob 備援。
2. **AudioContext 一定要在使用者手勢之後 `resume()`**，不然畫面上看起來在播、
   實際上一點聲音都沒有。選檔/拖放本身就是手勢，在那裡先叫醒一次，每次播放前再確認一次
   （從背景切回來被系統暫停的情況也一起救回來）。
3. **10 分鐘立體聲解碼後大約 200MB**，iPad 會直接當掉。所以先用 `<audio>` 的
   metadata 問長度（只讀檔頭，幾乎不花記憶體），超過 10 分鐘就在解碼前擋下來並說明原因；
   檔頭沒寫時長的容器則退回解碼後再檢查。

## 授權與出處

時間伸縮演算法來自 [SoundTouchJS](https://github.com/cutterbl/SoundTouchJS)
（Olli Parviainen 的 SoundTouch 移植版）。
