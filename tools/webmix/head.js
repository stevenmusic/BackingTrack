/* webmix.js — 瀏覽器裡的完整混音 + 母帶鏈(Web Audio API,無相依、單檔)
   來源:BackingTrack(index.html)實際在用、量過的那一套。用法、每一站做什麼、數字怎麼挑:docs/WEB_MIXING.md

   用法:
     import { createWebMix } from "./webmix.js";      // ES module(<script type="module">);import 之後也掛在 window.WebMix
     const ctx = new AudioContext();
     const mix = await createWebMix(ctx, { lufs: -14, truePeak: true, monoBelow: 120 });
     const drums = mix.bus("drums", { hp: 45, comp: [-18, 3, 0.01, 0.12], par: [1, -30, 8], sat: 0.35, send: 0.05 });
     someSource.connect(drums.input);
     mix.set({ master: { multiband: { lo: [-18, 2, 0.03, 0.2], mid: [-20, 1.5, 0.02, 0.15], hi: [-24, 2, 0.005, 0.1] } } });
     mix.reset();                                       // 換歌 / 重新播放時:響度重新量

   **沒寫的欄位 = 透明**(那一站被繞過或是 0dB),所以可以一站一站開。
   注意:DynamicsCompressor 自帶 6ms 延遲——開了串聯壓縮的 bus 會晚 6ms(要對齊就把那一軌提早排 `COMP_LATENCY`)。 */
"use strict";
