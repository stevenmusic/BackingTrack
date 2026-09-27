/* ══ 組裝:bus 與母帶 ══════════════════════════════════════════════════════
   訊號流(跟 BackingTrack 一樣):
   每條 bus:輸入 → 高通 → EQ(鐘形)→ 串聯壓縮 → 並聯壓縮 → 飽和 → 高頻架子 → chorus → 寬度 →(母帶)
                                    └ 殘響送(post-EQ)→ 殘響(預延遲 18ms → 卷積 → 低通 → 高通)→ 母帶
   母帶:輸入 → 高通 24Hz → 中頻鐘形 → 高頻架子 → 三段壓縮 → 低頻單聲道 → 黏著壓縮 → 飽和
         → 響度對齊(LUFS)→ 輸出增益 → True Peak 限幅器(看前 5ms)→ 軟削波(保險)→ 喇叭 */
async function createWebMix(ctx, opts){
  opts = opts || {};
  const IN = opts.inGain || 0.75, OUT = opts.outGain || 2.35, CEIL = opts.ceiling || 0.85;
  const input = ctx.createGain(); input.gain.value = IN;
  const hp = ctx.createBiquadFilter(); hp.type = "highpass"; hp.frequency.value = 24; hp.Q.value = 0.5;
  const mid = ctx.createBiquadFilter(); mid.type = "peaking"; mid.Q.value = 0.6; mid.frequency.value = 400; mid.gain.value = 0;
  const air = shelf(ctx, "highshelf", 5000);
  const mb = mkMultiband(ctx, 200, 3000), mono = mkMonoLow(ctx);
  const glue = ctx.createDynamicsCompressor();
  glue.threshold.value = -16; glue.knee.value = 8; glue.ratio.value = 2; glue.attack.value = 0.03; glue.release.value = 0.25;
  const glueTrim = ctx.createGain(); glueTrim.gain.value = 1;
  const sat = ctx.createWaveShaper();
  sat.curve = (() => { const n = 4096, c = new Float32Array(n), drive = 1.25, norm = 1 / (1 - 1 / 3);
    for (let i = 0; i < n; i++) { let x = ((i / (n - 1)) * 2 - 1) * drive; if (x > 1) x = 1; else if (x < -1) x = -1;
      c[i] = (x - x * x * x / 3) * norm / drive; } return c; })();
  const out = ctx.createGain(); out.gain.value = OUT;
  const clip = ctx.createWaveShaper(); clip.curve = softCurve(0.9, 0.98);
  input.connect(hp); hp.connect(mid); mid.connect(air); air.connect(mb.input); mb.output.connect(mono.input);
  mono.output.connect(glue); glue.connect(glueTrim); glueTrim.connect(sat);
  clip.connect(opts.destination || ctx.destination);

  /* 殘響(共用一個空間:所有 bus 送同一顆,才像同一個房間) */
  const rev = ctx.createGain(), pre = ctx.createDelay(0.2), conv = ctx.createConvolver(), revLp = ctx.createBiquadFilter(), revHp = ctx.createBiquadFilter(), revWet = ctx.createGain();
  pre.delayTime.value = 0.018; conv.buffer = buildImpulseResponse(ctx, opts.reverbSeconds || 2.0, 2.4);
  revLp.type = "lowpass"; revLp.frequency.value = 20000; revLp.Q.value = 0.5;
  revHp.type = "highpass"; revHp.frequency.value = 10; revHp.Q.value = BUTTER_Q_DB; revWet.gain.value = 0.26;
  const revHpSw = mkSwitch(ctx); revHpSw.input.connect(revHp); revHp.connect(revHpSw.wet);
  rev.connect(pre); pre.connect(conv); conv.connect(revLp); revLp.connect(revHpSw.input); revHpSw.output.connect(revWet); revWet.connect(input);

  /* worklet(True Peak 限幅 + 響度對齊);載不到就退回內建壓縮器當限幅(沒有響度對齊) */
  let limiter = null, agc = null, agcDb = 0, grDb = 0;
  try {
    const url = URL.createObjectURL(new Blob([LIMITER_SRC], { type: "application/javascript" }));
    await ctx.audioWorklet.addModule(url); URL.revokeObjectURL(url);
    agc = new AudioWorkletNode(ctx, "loudness-norm", { outputChannelCount: [2] });
    limiter = new AudioWorkletNode(ctx, "lookahead-limiter", { outputChannelCount: [2],
      processorOptions: { lookahead: 0.005, ceiling: CEIL, release: 0.08 } });
    agc.port.onmessage = e => { agcDb = e.data; };
    limiter.port.onmessage = e => { grDb = 20 * Math.log10(e.data || 1); };   // 限幅器回報的是這半秒最小的增益(倍數)
    sat.connect(agc); agc.connect(out); out.connect(limiter); limiter.connect(clip);
  } catch (e) {
    try { sat.disconnect(); out.disconnect(); } catch (_) {}
    limiter = agc = null; console.warn("webmix: AudioWorklet 載不到,退回內建壓縮器當限幅(沒有響度對齊 / True Peak)", e);
    const lim = ctx.createDynamicsCompressor();
    lim.threshold.value = -1; lim.knee.value = 0; lim.ratio.value = 20; lim.attack.value = 0.001; lim.release.value = 0.1;
    sat.connect(out); out.connect(lim); lim.connect(clip);
  }

  const buses = {};
  function bus(name, b){
    const x = {};
    x.input = ctx.createGain();
    x.hp = ctx.createBiquadFilter(); x.hp.type = "highpass"; x.hp.Q.value = 0.7;
    x.eq = ctx.createBiquadFilter(); x.eq.type = "peaking";
    x.comp = mkComp(ctx, 6); x.par = mkParallel(ctx); x.sat = mkSat(ctx, 4);
    x.air = shelf(ctx, "highshelf", 6500); x.chorus = makeChorus(ctx); x.send = ctx.createGain();
    x.width = (() => { const sp = ctx.createChannelSplitter(2), mg = ctx.createChannelMerger(2), inp = ctx.createGain(), g = [0, 1, 2, 3].map(() => ctx.createGain());
      inp.channelCountMode = "explicit"; inp.channelCount = 2; inp.connect(sp);
      sp.connect(g[0], 0); g[0].connect(mg, 0, 0); sp.connect(g[1], 1); g[1].connect(mg, 0, 0);
      sp.connect(g[2], 1); g[2].connect(mg, 0, 1); sp.connect(g[3], 0); g[3].connect(mg, 0, 1);
      return { input: inp, output: mg, set(w){ g[0].gain.value = g[2].gain.value = (1 + w) / 2; g[1].gain.value = g[3].gain.value = (1 - w) / 2; } }; })();
    x.input.connect(x.hp); x.hp.connect(x.eq); x.eq.connect(x.comp.input); x.comp.output.connect(x.par.input);
    x.par.output.connect(x.sat.input); x.sat.output.connect(x.air); x.air.connect(x.chorus.input);
    x.chorus.output.connect(x.width.input); x.width.output.connect(input);
    x.eq.connect(x.send); x.send.connect(rev);
    /* 欄位(全部可省略 = 透明):
       level 倍數、hp Hz、eq [Hz, dB, Q]、comp [門檻, 比例, 起音, 放開, 補償倍數]、par [量, 門檻, 比例, 低通 Hz]、
       sat k(0.2–0.6 = 輕)、air [Hz, dB]、chorus 0–1、width 0(單聲道)–1(原樣)、send 殘響送 */
    x.set = (c) => { c = c || {};
      x.input.gain.value = c.level == null ? 1 : c.level;
      x.hp.frequency.value = c.hp || 20;
      const eq = c.eq || [1000, 0, 1]; x.eq.frequency.value = eq[0]; x.eq.gain.value = eq[1]; x.eq.Q.value = eq[2] || 1;
      const cp = c.comp || []; x.comp.set(cp[0], cp[1], cp[2], cp[3], cp[4]);
      const pr = c.par || [0]; x.par.set(pr[0], pr[1], pr[2], pr[3]);
      x.sat.set(c.sat || 0);
      const a = c.air || [6500, 0]; x.air.frequency.value = a[0]; x.air.gain.value = a[1];
      x.chorus.wet.gain.value = c.chorus || 0; x.width.set(c.width == null ? 1 : c.width);
      x.send.gain.value = c.send || 0; };
    x.set(b); buses[name] = x; return x;
  }

  /* 母帶欄位(全部可省略 = 透明 / 預設):
     midEq [Hz, dB]、airEq [Hz, dB]、multiband { lo, mid, hi: [門檻, 比例, 起音, 放開], makeup }、monoBelow Hz、
     lufs 目標(例:−14)、truePeak true/false、reverb { lp, hp, level } */
  function set(cfg){
    cfg = cfg || {}; const m = cfg.master || cfg;
    const me = m.midEq || [400, 0]; mid.frequency.value = me[0]; mid.gain.value = me[1];
    const ae = m.airEq || [5000, 0]; air.frequency.value = ae[0]; air.gain.value = ae[1];
    mb.set(m.multiband || null); mono.set(m.monoBelow || 0);
    const r = m.reverb || {}; revLp.frequency.value = r.lp || 20000; revHpSw.set(r.hp > 0); if (r.hp > 0) revHp.frequency.value = r.hp; revWet.gain.value = r.level == null ? 0.26 : r.level;
    if (limiter) limiter.parameters.get("tp").value = m.truePeak ? 1 : 0;
    if (agc) { const P = agc.parameters; P.get("on").value = m.lufs != null ? 1 : 0;
      if (m.lufs != null) P.get("target").value = m.lufs - 20 * Math.log10(out.gain.value); }
    if (cfg.buses) for (const k in cfg.buses) (buses[k] || bus(k)).set(cfg.buses[k]);
  }
  set(opts);
  return { input, reverb: rev, bus, buses, set,
    reset(startDb){ if (agc) agc.port.postMessage({ reset: true, gdb: startDb || 0 }); },
    meter(){ return { worklet: !!limiter, agcGainDb: agcDb, limiterReductionDb: grDb }; },
    COMP_LATENCY: compLatency(ctx) };
}

const WebMix = { createWebMix, mkComp, mkSat, mkParallel, mkMultiband, mkMonoLow, lr4, compAutoMakeupDb, compLatency, makeChorus, buildImpulseResponse, COMP_LATENCY, LIMITER_SRC };
if (typeof window !== "undefined") window.WebMix = WebMix;
export { createWebMix, mkComp, mkSat, mkParallel, mkMultiband, mkMonoLow, lr4, compAutoMakeupDb, compLatency, makeChorus, buildImpulseResponse, COMP_LATENCY, LIMITER_SRC };
export default WebMix;
