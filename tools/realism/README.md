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
4. 片段放上盲聽台:WAV 包成 base64 的 JSON(`{type, b64}`),**用 Artifact 的 asset 上傳**
   (一個 JSON 一次呼叫),回來的 `/_blob/<id>` 寫進 db `clips/<id>.asset`。
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
