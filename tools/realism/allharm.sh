cd /home/user/BackingTrack/tools/realism
python3 -c "
import json
S=['comp','drive','pad']
for i,(f,t,m) in enumerate(json.load(open('/tmp/allprog.json'))): print(f'{i}\t{f}\t{t}\t{m}\t{S[i%3]}')" > /tmp/allprog.tsv
rm -rf /tmp/harm; mkdir -p /tmp/harm
cat /tmp/allprog.tsv | xargs -P4 -d '\n' -I{} bash -c 'IFS=$'"'"'\t'"'"' read i f t m st <<< "{}"; timeout 900 node harmony.mjs "$f" "$t" 40 "$st" "$m" > /tmp/harm/$i.txt 2>&1; echo "$f | $t | $m | $st" >> /tmp/harm/$i.txt'
echo DONE > /tmp/harm/DONE
