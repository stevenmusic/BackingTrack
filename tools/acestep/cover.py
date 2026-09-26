import sys, time, os
sys.path.insert(0, '/tmp/ace15')
os.chdir('/tmp/ace15')
from acestep.handler import AceStepHandler
from acestep.inference import GenerationParams, GenerationConfig, generate_music
src, strength, tag = sys.argv[1], float(sys.argv[2]), sys.argv[3]
t0 = time.time()
dit = AceStepHandler()
print(dit.initialize_service(project_root='/tmp/ace15', config_path='acestep-v15-turbo', device='cpu', quantization=os.environ.get('Q') or None), flush=True)
print('init', round(time.time() - t0), 's', flush=True)
cap = ("1980s Japanese city pop instrumental backing track, studio session band, tight live drums, "
       "funky fingerstyle electric bass, clean single-coil guitar sixteenth-note cutting, Rhodes and grand piano comping, "
       "brass stabs, warm analog mix, high fidelity, no vocals")
p = GenerationParams(task_type='cover', src_audio=src, caption=cap, lyrics='[Instrumental]', instrumental=True,
                     audio_cover_strength=strength, bpm=110, duration=int(os.environ.get('DUR','20')), seed=42)
c = GenerationConfig(batch_size=1, audio_format='wav')
t1 = time.time()
r = generate_music(dit, None, p, c, save_dir=f'/tmp/acet/{tag}')
print('gen', round(time.time() - t1), 's', r.success, r.error if not r.success else [a['path'] for a in r.audios], flush=True)
