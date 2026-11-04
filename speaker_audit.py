"""Remote ONNX speaker comparisons, not automatic identity certification.

WeSpeaker ResNet34-LM (CC-BY-4.0), pinned HF revision. Matching scores are
uncalibrated cosine similarities, not probabilities or verified voice names.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parent
MODEL='Wespeaker/wespeaker-voxceleb-resnet34-LM'
REVISION='f0c48c298fd835726c27956a5d617bad7115627e'

def main():
    import kaldi_native_fbank as knf
    import numpy as np
    import onnxruntime as ort
    from huggingface_hub import hf_hub_download
    model=hf_hub_download(MODEL,'voxceleb_resnet34_LM.onnx',revision=REVISION)
    options=ort.SessionOptions();options.intra_op_num_threads=2;options.inter_op_num_threads=1
    sess=ort.InferenceSession(model,sess_options=options,providers=['CPUExecutionProvider'])
    print('ONNX',[(x.name,x.shape) for x in sess.get_inputs()],flush=True)
    rows=json.loads((ROOT/'artifacts/audio_inventory.json').read_text())
    manifest={r['path']:r for r in rows}
    out=ROOT/'artifacts/speaker-audit';out.mkdir(parents=True,exist_ok=True)
    cache=out/'embeddings';cache.mkdir(exist_ok=True)
    start=time.time()
    def embedding(name):
        file=ROOT/'artifacts/pcm24k'/name
        digest=hashlib.sha256(file.read_bytes()).hexdigest()
        cached=cache/(digest+'.npy')
        if cached.exists():return np.load(cached)
        raw=subprocess.check_output(['ffmpeg','-nostdin','-v','error','-i',str(file),'-ac','1','-ar','16000',
                                     '-f','s16le','-c:a','pcm_s16le','-'])
        wav=np.frombuffer(raw,dtype='<i2').astype(np.float32)
        # Whole recordings: no assumption of common speaker from folder. Long recordings
        # get separate windows; disagreement is retained for review, not silently averaged.
        opts=knf.FbankOptions();opts.frame_opts.samp_freq=16000;opts.frame_opts.dither=0
        opts.frame_opts.window_type='hamming';opts.mel_opts.num_bins=80
        extractor=knf.OnlineFbank(opts);extractor.accept_waveform(16000,wav.tolist());extractor.input_finished()
        features=np.stack([extractor.get_frame(i) for i in range(extractor.num_frames_ready)])
        embeddings=[]
        for pos in range(0,len(features),300):
            feat=features[pos:pos+300]
            if len(feat)<100 and embeddings:continue
            if len(feat)<25:raise ValueError('Too little audio for speaker embedding')
            feat=feat-feat.mean(axis=0,keepdims=True)
            e=np.asarray(sess.run(None,{sess.get_inputs()[0].name:feat[None].astype(np.float32)})[0]).reshape(-1)
            embeddings.append(e/max(float(np.linalg.norm(e)),0.00000001))
        values=np.stack(embeddings);np.save(cached,values)
        return values
    packs=[*(f'Male{i}' for i in range(1,6)),*(f'Fem{i}' for i in range(1,6)),*(f'Derm{i}' for i in range(1,4)),'Bot1']
    refs={}
    for pack in packs:
        possible=[r for r in rows if r['path'].startswith('voice/'+pack+'/') and 1.2<=r['seconds']<=8
                  and any(w in r['path'].casefold() for w in ('gbl.hi.','gbl.thanks.','def.base.','att.base.','slf.defend.'))]
        if not possible:
            possible=[r for r in rows if r['path'].startswith('voice/'+pack+'/') and 1.2<=r['seconds']<=8]
        if not possible:raise ValueError('No usable enrollment candidate for '+pack)
        names=[r['path'] for r in sorted(possible,key=lambda r:r['path'])[:3]]
        values=np.concatenate([embedding(n) for n in names])
        centroid=values.mean(axis=0);centroid/=np.linalg.norm(centroid)
        refs[pack]=(centroid,names)
    for label,names in {
        'Announcer_candidate':['voice/Announcer/ANN.60.WAV','voice/Announcer/ANN.gameover.WAV'],
        'TrainingFemale_candidate':['voice/Training/Mission1/T1_01.WAV'],
        'BriefingMale_candidate':['voice/Training/Briefings/T1.brief02.WAV'],
    }.items():
        values=np.concatenate([embedding(n) for n in names]);c=values.mean(axis=0);c/=np.linalg.norm(c)
        refs[label]=(c,names)
    results=[]
    for i,row in enumerate(rows):
        if not row['path'].startswith(('voice/Training/','voice/Announcer/')):continue
        if row['seconds']<1:
            results.append({'path':row['path'],'status':'too_short','speaker_verified':False});continue
        values=embedding(row['path'])
        scores=sorted(((label,float(values.mean(axis=0)@c)) for label,(c,_) in refs.items()),key=lambda x:-x[1])
        nearest=[max(refs,key=lambda k:float(e@refs[k][0])) for e in values]
        results.append({'path':row['path'],'top_matches':scores[:4],'margin':scores[0][1]-scores[1][1],
                        'window_nearest':nearest,'window_disagreement':len(set(nearest))>1,
                        'speaker_verified':False,'status':'candidate_only'})
        if (i+1)%50==0:print('speaker comparisons',i+1,flush=True)
    same=embedding('voice/Training/Mission1/T1_01.WAV')[0]
    pilot_comparisons=[]
    pilots=ROOT/'artifacts/pilot/pilot-jobs.json'
    if pilots.exists():
        for job in json.loads(pilots.read_text()):
            if job.get('kind')!='speech':continue
            label=job['speaker_id'] if job['speaker_id'] in refs else job['speaker_id']+'_candidate'
            if label not in refs:continue
            values=embedding(job['source'])
            pilot_comparisons.append({'id':job['id'],'reference_label':label,
                'window_cosines':[float(e@refs[label][0]) for e in values],
                'speaker_verified':False,'note':'Uncalibrated comparison, not a voice identity verdict.'})
    instrument={'positive_same_clip_cosine':float(same@same),
                'contrast_reference_cosine':float(same@refs['BriefingMale_candidate'][0]),
                'warning':'Contrast is not ground-truth different-speaker certification.'}
    receipt={'model':MODEL,'revision':REVISION,'license':'CC-BY-4.0; attribution WeSpeaker authors',
        'sha256':hashlib.sha256(Path(model).read_bytes()).hexdigest(),'seconds':time.time()-start,
        'enrollment':{k:v[1] for k,v in refs.items()},'instrument':instrument,
        'records':results,'pilot_comparisons':pilot_comparisons,
        'warning':'Uncalibrated scores; no automatic speaker or gender verification. Processed/robotic voices may confuse embeddings.'}
    (out/'speaker-comparisons.json').write_text(json.dumps(receipt,indent=2))
    print(json.dumps(instrument),flush=True)
    print('========== DONE ==========',flush=True)

if __name__=='__main__':main()
