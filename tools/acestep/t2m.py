import sys, time, os
sys.path.insert(0, '/tmp/ace15'); os.chdir('/tmp/ace15')
from acestep.handler import AceStepHandler
from acestep.inference import GenerationParams, GenerationConfig, generate_music
dit = AceStepHandler()
print(dit.initialize_service(project_root='/tmp/ace15', config_path='acestep-v15-turbo', device='cpu', quantization='int8_weight_only')[1], flush=True)
cap = ("1980s Japanese city pop instrumental, chord progression Fmaj7 - E7 - Am7 - C7 repeating, one chord per bar, "
       "live drums, fingerstyle electric bass, clean electric guitar cutting, Rhodes, brass stabs, studio recording")
lyr = "[Instrumental]\n" + "\n".join(["[Fmaj7] [E7] [Am7] [C7]"] * 3)
p = GenerationParams(task_type='text2music', caption=cap, lyrics=lyr, instrumental=True, bpm=110, keyscale='A minor',
                     timesignature='4', duration=20, seed=11, thinking=False, use_cot_metas=False, use_cot_caption=False)
t=time.time(); r = generate_music(dit, None, p, GenerationConfig(batch_size=1, audio_format='wav'), save_dir='/tmp/acet/t2m')
print('gen', round(time.time()-t), r.success, r.error if not r.success else [a['path'] for a in r.audios], flush=True)
