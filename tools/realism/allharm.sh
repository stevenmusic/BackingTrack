cd /home/user/BackingTrack/tools/realism
# 段落庫全部的進行:照 index.html 的 SECTIONS 產生 /tmp/allprog.json([曲風, 進行, 拍號])
python3 -c "
import re, json
src = open('../../index.html').read()
body = src[src.index('const SECTIONS = ['):]
body = body[:body.index('\n];')]
out = [[m.group(2), m.group(1), m.group(3)] for m in re.finditer(r'text:\s*\"([^\"]+)\",\s*feel:\s*\"(\w+)\",\s*meter:\s*\"([^\"]+)\"', body)]
json.dump(out, open('/tmp/allprog.json', 'w'), ensure_ascii=False)
print(len(out), '組')"
python3 -c "
import json
S=['comp','drive','pad']
for i,(f,t,m) in enumerate(json.load(open('/tmp/allprog.json'))): print(f'{i}\t{f}\t{t}\t{m}\t{S[i%3]}')" > /tmp/allprog.tsv
rm -rf /tmp/harm; mkdir -p /tmp/harm
cat /tmp/allprog.tsv | xargs -P4 -d '\n' -I{} bash -c 'IFS=$'"'"'\t'"'"' read i f t m st <<< "{}"; timeout 900 node harmony.mjs "$f" "$t" 40 "$st" "$m" > /tmp/harm/$i.txt 2>&1; echo "$f | $t | $m | $st" >> /tmp/harm/$i.txt'
echo DONE > /tmp/harm/DONE
