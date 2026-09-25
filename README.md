# BackingTrack 跟著彈

輸入和弦進行,馬上生成一整個樂團的伴奏(鋼琴或電鋼琴、鼓、貝斯、吉他、鋪底…),讓你跟著彈、跟著唱、練即興。
免安裝,打開瀏覽器就能用,支援中文與英文介面。

**[直接開啟工具 →](https://stevenmusic.github.io/BackingTrack/)**

打一行 `C - Am - F - G`,按播放。

## 功能

- **和弦輸入**:用文字打(`C - Am - F - G`、`Dm7 G7 | Cmaj7`),或用畫面上的和弦鍵盤一格一格點。
  看得懂爵士譜上的寫法(`C∆7`、`C-7`、`Cø`、`C°7`)、轉位(`C/E`)、全形字
- **一小節多顆和弦、換在拍子中間**:用 `|` 分小節;`/` 多撐一拍、`.` 多撐半拍。
  也可以在小節編輯條上直接拖曳換和弦的位置
- **七種曲風**:Pop、City Pop、K-Pop、Bossa、Blues、Swing、Funk。預設「自動」會看和弦挑一個,也可以自己指定。
  每個曲風有自己的鼓的打法、貝斯走法、編制與音色
- **伴奏疏密**:墊底 / 打點 / 推進,或「混合」每一圈換一種
- **三種拍號**:4/4、3/4、6/8
- **速度與移調**:速度自由調;移調時畫面上顯示移調後、拼法正確的和弦
- **和弦變化**:第二圈起偶爾換成代理和弦,重複練習不會膩,但聽起來還是同一首
- **段落庫**:83 組常用和弦進行(依曲風分類,含主歌/導歌/副歌),一鍵「組一首」
- **練習用**:預備拍、循環播放、復原、存檔、複製連結(把同一題傳給學生)
- 可以「加到主畫面」,平板架在譜架上用

## 音源授權與出處

所有取樣都在播放時從公開的 GitHub 倉庫(經 jsDelivr)下載,只下載這次用得到的音。
完整授權原文、出處要求與「能不能放進付費 App」的判斷見 [`docs/LICENSES.md`](docs/LICENSES.md)。

| 用在 | 音源 | 作者 | 授權 |
| --- | --- | --- | --- |
| 鋼琴 | [Salamander Grand Piano](https://github.com/sfzinstruments/SalamanderGrandPiano)(經 [Tone.js audio](https://github.com/Tonejs/audio) 的 mp3) | Alexander Holm | CC BY 3.0 |
| 電鋼琴(Funk) | [jRhodes3c](https://github.com/sfzinstruments/jlearman.jRhodes3c) | Jeff Learman | 非商業 CC BY-NC(商用需另外授權) |
| 鼓 | [Virtuosity Drums](https://github.com/sfzinstruments/virtuosity_drums) | Versilian Studios × Karoryfer Samples | CC0 |
| 鼓(City Pop) | [SM Drums](https://github.com/sfzinstruments/SMDrums) | Scott McLean 等 | 作者聲明免費、免版稅、任何用途 |
| 鼓(K-Pop 808) | [Dirt-Samples](https://github.com/tidalcycles/Dirt-Samples) 的 TR-808 取樣 | TidalCycles 社群 | 倉庫未標示授權 |
| 電貝斯 | [Black And Blue Basses](https://github.com/sfzinstruments/karoryfer.black-and-blue-basses) | Karoryfer Samples | CC0 |
| 低音提琴 | [dsmolken.double-bass](https://github.com/sfzinstruments/dsmolken.double-bass) | D. Smolken | CC0 |
| 電吉他(City Pop) | [Black And Green Guitars](https://github.com/sfzinstruments/karoryfer.black-and-green-guitars) | Karoryfer Samples(Brian Wood 錄音) | CC0 |
| 木吉他、尼龍弦、電吉他 | [tonejs-instruments](https://github.com/nbrosowsky/tonejs-instruments) | Nicholaus P. Brosowsky 整理 | 程式 MIT、取樣標示 CC BY 3.0 |
| 鼓的節奏(City Pop) | [Groove MIDI Dataset](https://magenta.tensorflow.org/datasets/groove) | Google Magenta(Gillick, Roberts, Engel, Eck, Bamman) | CC BY 4.0 |
| 字型 | Noto Serif TC / Noto Sans TC(Google Fonts) | Google | SIL OFL 1.1 |

風琴、合成器鋪底、銅管、K-Pop 的合成器與 808 低音、打擊小物是程式即時合成的,沒有外部取樣。

## 開發

單一 `index.html`,沒有 build。開發規則見 [`CLAUDE.md`](CLAUDE.md),
過去的設計說明與量測紀錄見 [`docs/DEVLOG.md`](docs/DEVLOG.md) 與 [`docs/HISTORY.md`](docs/HISTORY.md),
聲音的評測工具在 [`tools/realism/`](tools/realism/)。
