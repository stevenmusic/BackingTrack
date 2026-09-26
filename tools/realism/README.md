# 伴奏真實度評測(eval)

判斷「伴奏聽起來像不像真的錄音」,而且每次改程式都能重跑、比較。兩把尺:

| | 怎麼量 | 當什麼用 |
| --- | --- | --- |
| **你的盲聽分數** | [伴奏盲聽台](https://claude.ai/artifact/GxmtQqTjiCE1jTSrGYL8ek):一段 10 秒,1–5 分,勾出哪件樂器假 | **標準答案** |
| **VGGish 自動評分** | Google AudioSet 的音訊嵌入模型,算跟真實錄音的距離(FAD)與判別器機率 | 輔助,之後用你的分數去校正它 |

## 流程
```
1. 改 index.html
2. cases.json 加一組新版本  →  node render.mjs          # 錄片段,聲學特徵寫進 db/clips.jsonl
3. python realism.py score                                # VGGish:P(真)、最近距離、各組 FAD → db/scores.jsonl
4. 片段放上盲聽台:WAV 包成 base64 的 JSON(`{type, b64}`),**一定要當附屬檔發布**
   (publish 的 `files`:`clips/<id>.json`),db `clips/<id>` 寫 `url: "clips/<id>.json"`。
   **只上傳成 asset(`/_blob/<id>`)是不夠的**:第二批只做了這一步,使用者那邊整批 404、
   一題都打不了。第一批能聽是因為它走附屬檔(頁面會帶著網址參數去抓)。
   asset 留著當第一順位也沒關係,抓不到會自己往下試
   **不要用發佈時的附屬檔案**:使用者那邊 WAV 與 JSON 都是 403(本機測不出來);
   `<audio>` 也不要用,一律 fetch + Web Audio。頁面失敗時會把每一種讀法的錯誤列出來
5. 你打分 → 讀回 db/ratings.jsonl → python realism.py analyze   # 寫進 KNOWLEDGE.md
```

## 環境(雲端容器)
- **取樣**:CDN 被擋,從 GitHub blobless clone 到 `/tmp/smp/<repo>`,render.mjs 用 `page.route` 對到本機。
  需要的 repo:`sfzinstruments/{jlearman.jRhodes3c, virtuosity_drums, karoryfer.black-and-blue-basses, dsmolken.double-bass}`、
  `nbrosowsky/tonejs-instruments`、`Tonejs/audio`、`tidalcycles/Dirt-Samples`。
  缺的檔案會寫進 `/tmp/smp/missing.txt`,那一筆不收(錄到的會是合成備援)
- **原始 repo 本來就沒有的檔案**(正式環境也 404)照錄,列在 `db/prod404.txt`
- **VGGish 權重**(290MB,不進 repo):
  `curl -L -o /tmp/vgg/vggish.pth https://github.com/harritaylor/torchvggish/releases/download/v0.1/vggish-10086976.pth`
  pypi 的 torch 是 CUDA 版跑不起來,所以 `vggish_np.py` 是純 numpy 實作(`pip install numpy scipy soundfile`)
- **Audiobox Aesthetics**(`aes.py`):`python3 -m venv /tmp/abx`,`pip install torch==2.5.1 torchaudio==2.5.1 numpy audiobox_aesthetics requests huggingface_hub soundfile`
  (pytorch.org 的 CPU 版會轉到 `download-r2.pytorch.org` 被擋,pypi 那一版在 CPU 上也跑得起來),
  權重 `curl -L -o /tmp/abx_ckpt/checkpoint.pt https://dl.fbaipublicfiles.com/audiobox-aesthetics/checkpoint.pt`(415MB,不進 repo)。
  跑 `/tmp/abx/bin/python aes.py [額外音檔…]`,29 段約 30 秒
- **參考曲只存嵌入不存音檔**(`db/refs/*.npy`)。版權音檔不要進 repo

## 檔案
- `cases.json` 要錄哪些片段(版本 × 曲風 × 疏密)。**舊的不要刪**,分數才能跨版本比
- `db/clips.jsonl` 每段的 id、commit、曲風、聲學特徵(RMS、peak、波峰因數、L/R 相關、八度頻帶)
- `db/scores.jsonl` / `db/summary.json` VGGish 評分
- `db/ratings.jsonl` 盲聽分數(從盲聽台的 db 讀回來)
- `KNOWLEDGE.md` 知識庫:人工整理的結論 + `analyze` 自動產生的相關分析

## 風格尺(2026-09-26)
- `style.py [組…] [--reuse] [--merge-mix]`:真歌與 Suno 都當正確答案,找兩邊一致、我們不一樣的特徵(各樂器佔比、亮度、寬度、密度、小節起伏、
  殘響、和聲色彩兩套模板),附 bootstrap 95% 區間。分軌放 `/tmp/sty/sep_<組>/htdemucs_6s/`,結果 `db/style.json`、`db/style_report.json`
- `leak_melody.py`:人聲滲漏實驗,在我們的伴奏上混一條合成人聲旋律,再拆軌量一次
- `review_stats.py drums|leak|mix|sub|dup`:`docs/REVIEW.md` 裡數字的重現腳本(只讀;`dup` 要給原始 mp3 的資料夾)

## CLAP 耳朵(`clapfad.py`)
- 模型:`laion/larger_clap_music`(Hugging Face,**Apache-2.0**),只拿來評測、不進產品;權重只有 `.bin`,需要 torch ≥ 2.6
- 方法:Gui et al., "Adapting Frechet Audio Distance for Generative Music Evaluation", ICASSP 2024(微軟 fadtk)
