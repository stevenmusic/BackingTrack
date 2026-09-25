/* 和弦變化會不會亂換情緒:段落庫全部 × 59 圈,數「大三/大七 ↔ 小三/小七」的翻轉。
   流行系的主和弦不可以被換成小調、一圈不可以換兩次。node tools/realism/mood_check.mjs */
import { chromium } from 'playwright';
const b = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium' });
const pg = await b.newPage(); await pg.route(/^https:/, r => r.abort());
pg.on('pageerror', e => console.log('ERR', e.message));
await pg.goto('file:///home/user/BackingTrack/index.html');
const r = await pg.evaluate(() => {
  const res = { byFeel: {}, bad: [], ex: {} };
  for (const ex of SECTIONS) {
    document.getElementById('chordInput').value = ex.text; reparse(); feelNow = ex.feel;
    const orig = flatChords(parsed.bars); const key = keyOf(parsed.bars);
    for (let lap = 1; lap < 60; lap++) {
      const bars = barsForLap(lap);
      const nowAll = []; bars.forEach(bb => bb.chords.forEach(c => nowAll.push(c)));
      const F = res.byFeel[ex.feel] ||= { laps: 0, split: 0, mood: 0, tonicMood: 0 };
      F.laps++;
      let moods = 0, oi = 0;
      for (let j = 0; j < nowAll.length; j++) { const c = nowAll[j];
        if (c.added) { F.split++; const s = c.text + ' ' + nowAll[j+1].text; (res.ex[ex.feel] ||= {})[s] = 1; continue; }
        const o = orig[oi++]; if (!o || !o.chord || !c.chord) continue;
        const flip = (qualOf(o.chord) === 'min') !== (qualOf(c.chord) === 'min') && o.chord.rootPc !== c.chord.rootPc;
        if (flip) { moods++; F.mood++;
          const d = ((o.chord.rootPc - key) % 12 + 12) % 12;
          if (d === 0 || d === 9) { F.tonicMood++; if (!['latin','swing'].includes(ex.feel)) res.bad.push(ex.feel + ' ' + ex.text + ' : ' + o.text + '→' + c.text); } }
      }
      if (moods > 1) res.bad.push('兩次換情緒 ' + ex.text + ' lap ' + lap);
    }
  }
  for (const k in res.ex) res.ex[k] = Object.keys(res.ex[k]).slice(0, 10);
  return res;
});
console.log(JSON.stringify(r.byFeel)); console.log('問題', r.bad.length, [...new Set(r.bad)].slice(0, 12)); console.log(JSON.stringify(r.ex, null, 0));
await b.close();
