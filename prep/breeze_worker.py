"""Kaggle-only batch driver using Breeze's documented inference modules.
Model loaded once; jobs rendered sequentially to limit peak GPU memory.
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--model',type=Path,required=True)
    p.add_argument('--jobs',type=Path,required=True)
    args=p.parse_args()
    sys.path.insert(0,str(args.source.resolve()))
    import torch
    import soundfile as sf
    from breeze_infer.runtime import load_runtime, resolve_device, set_all_seeds, update_generation_config_for_breeze
    from breeze_infer.templates import get_template, prepare_inputs, select_template_name
    from models.fast_streaming import FastBreezeStreamingRuntime, FastStreamingConfig
    if not torch.cuda.is_available():
        raise RuntimeError('Enable a Kaggle CUDA GPU before generating expression variants.')
    tokenizer, model, codec = load_runtime(args.model, device=resolve_device(), attn_implementation='eager')
    update_generation_config_for_breeze(model)
    config=FastStreamingConfig(max_new_tokens=1500,max_seq_len=2048,fast_all=False,
        fast_text_encoder=False,fast_backbone_prefill=False,fast_backbone_decode=False,
        fast_depth_decoder=False,fast_codec=False,repetition_penalty=1.1)
    runtime=FastBreezeStreamingRuntime(model,codec,config,tokenizer=tokenizer)
    jobs=json.loads(args.jobs.read_text())
    for i,job in enumerate(jobs,1):
        output=Path(job['output'])
        output.parent.mkdir(parents=True,exist_ok=True)
        request={'id':job['id'],'speaker':'S0','text':job['text'],
                 'ref_audio_path':job['ref_audio_path'],'ref_text':job['ref_text']}
        instruction=job.get('instruction')
        if instruction:
            request['instruction']=instruction
        scale=4.0 if instruction else 1.0
        seed=int(job.get('seed',42))
        set_all_seeds(seed)
        inputs=prepare_inputs(tokenizer,codec,model,[request],get_template(select_template_name(request)),
                              guidance_scale=scale,guidance_scale_ref=None,guidance_scale_ins=None)
        temporary=output.with_name(output.stem+'.part.wav')
        with sf.SoundFile(temporary,mode='w',samplerate=runtime.sample_rate,channels=1,subtype='PCM_16') as w:
            for chunk in runtime.iter_audio_chunks(inputs,request_id=job['id'],seed=seed):
                w.write(chunk.audio)
        temporary.replace(output)
        output.with_suffix('.json').write_text(json.dumps(job,indent=2))
        print(f'{i}/{len(jobs)}: {output}',flush=True)
        del inputs
    print('Done. Listen and mark candidates before using them in a runtime voice bank.')

if __name__=='__main__':
    main()
