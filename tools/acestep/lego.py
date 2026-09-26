import sys, time, os
sys.path.insert(0, '/tmp/ace15'); os.chdir('/tmp/ace15')
from acestep.handler import AceStepHandler
from acestep.inference import GenerationParams, GenerationConfig, generate_music
src, task, track, tag = sys.argv[1:5]
dit = AceStepHandler()
t0 = time.time()
print(dit.initialize_service(project_root='/tmp/ace15', config_path='acestep-v15-base', device='cpu', quantization='int8_weight_only')[1], 'init', round(time.time()-t0), flush=True)
cap = {"guitar": "clean single-coil electric guitar, 1980s Japanese city pop sixteenth-note cutting, funky, tight, studio recording",
       "keyboard": "Fender Rhodes electric piano comping, 1980s Japanese city pop, warm, studio recording",
       "drums": "tight live studio drum kit, 1980s Japanese city pop groove, crisp snare, sixteenth hi-hat",
       "all": "1980s Japanese city pop instrumental band, live drums, slap-free fingerstyle bass, clean electric guitar cutting, Rhodes, brass stabs, studio recording"}[track]
ins = (f"Generate the {track} track based on the audio context:" if task == 'lego'
       else "Complete the input track with drums, bass, guitar, keyboard, brass:")
p = GenerationParams(task_type=task, src_audio=src, instruction=ins, caption=cap, lyrics='[Instrumental]', instrumental=True,
                     bpm=110, keyscale='A minor', duration=20, seed=7, repainting_start=0.0, repainting_end=-1)
t1 = time.time()
r = generate_music(dit, None, p, GenerationConfig(batch_size=1, audio_format='wav'), save_dir=f'/tmp/acet/{tag}')
print('gen', round(time.time()-t1), 's', r.success, r.error if not r.success else [a['path'] for a in r.audios], flush=True)
