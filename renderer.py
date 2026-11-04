"""Sample-only, standard-library runtime. Missing speech or events raise by default."""
from __future__ import annotations
import argparse
from array import array
import hashlib
import json
from pathlib import Path
import re
import time
from bank import read_wav,write_wav,safe_path
from phonetics import Lexicon,transitions,base

EMOTIONS={'neutral','angry','sad','excited','calm'}
EVENTS={'laugh','sigh','grunt','cheer','cough','clear_throat','pain','death_cry'}

class MissingUnit(ValueError):
    pass

def markup(text):
    emotion='neutral'; opened=None; out=[]
    for part in re.split(r'(\[[^\]]+\])',text):
        if not part:
            continue
        if not part.startswith('['):
            if part.strip():
                out.append(('speech',emotion,part))
            continue
        tag=part[1:-1]
        if tag in EMOTIONS:
            if opened:
                raise ValueError('Nested emotion tags are not supported')
            emotion=opened=tag
        elif tag.startswith('/') and tag[1:] in EMOTIONS:
            if opened != tag[1:]:
                raise ValueError('Mismatched emotion tag')
            emotion='neutral'; opened=None
        elif tag in EVENTS:
            out.append(('event',emotion,tag))
        else:
            raise ValueError('Unknown expression tag: '+tag)
    if opened:
        raise ValueError('Unclosed emotion tag')
    return out

class Renderer:
    def __init__(self,bank_path,lexicon,crossfade_ms=10,emotion_fallback='error',stress_fallback=False,audition_unverified=False,bank_pronunciations=False):
        self.root=Path(bank_path); self.lexicon=lexicon
        self.index=json.loads((self.root/'index.json').read_text())
        if not 5 <= crossfade_ms <= 10:
            raise ValueError('Crossfade must be 5–10 ms')
        if emotion_fallback not in ('error','neutral'):
            raise ValueError('Invalid emotion fallback')
        self.crossfade_ms=crossfade_ms; self.fallback=emotion_fallback
        self.stress_fallback=stress_fallback; self.warnings=[]; self.rate=None
        self.audition_unverified=audition_unverified
        self.bank_pronunciations=bank_pronunciations
        self.available={}
        for unit in self.index['units']:
            if unit.get('verified') is True or audition_unverified:
                key=(unit['speaker_id'],unit['emotion'])
                self.available.setdefault(key,set()).add(tuple(unit['phones']))
        self.digest=hashlib.sha256((self.root/'index.json').read_bytes()).hexdigest()
    def has_pair(self,speaker,emotion,pair):
        emotions=[emotion,'neutral'] if self.fallback=='neutral' and emotion!='neutral' else [emotion]
        for emo in emotions:
            available=self.available.get((speaker,emo),set())
            if tuple(pair) in available:return True
            if self.stress_fallback and any(tuple(map(base,p))==tuple(map(base,pair)) for p in available):return True
        return False
    def pronounce_for_bank(self,speaker,emotion,text):
        """Shortest supported dictionary/pause path; never invent or relabel audio.

        Strong punctuation keeps a silence boundary. A comma may have no recorded
        pause. Word boundaries may take existing silence transitions. Every departure
        from the dictionary-first, punctuation-literal path is reported explicitly.
        """
        normalized,tokens=self.lexicon.pronunciation_tokens(text)
        # Future feasibility depends only on the last phone, not the path history.
        states={'SIL':(0,['SIL'],[])}
        for position,token in enumerate(tokens):
            next_states={}
            for last,(cost,phones,choices) in states.items():
                options=[]
                if 'punctuation' in token:
                    mark=token['punctuation']
                    options.append(([] if last=='SIL' else ['SIL'],0,[]))
                    if mark==',' and last!='SIL':
                        options.append(([],1,[{'pause_choice':'comma_without_recorded_silence','token':position}]))
                else:
                    for index,pron in enumerate(token['pronunciations']):
                        change=[] if index==0 else [{'pronunciation_choice':token['word'],'phones':pron,'token':position}]
                        options.append((pron,index,change))
                        if last!='SIL':
                            options.append((['SIL']+pron,index+2,change+[
                                {'pause_choice':'recorded_word_boundary','before':token['word'],'token':position}]))
                for tail,extra,changes in options:
                    path=[last]+tail
                    if not all(self.has_pair(speaker,emotion,pair) for pair in zip(path,path[1:])):continue
                    end=path[-1];candidate=(cost+extra,phones+tail,choices+changes)
                    if end not in next_states or candidate[0]<next_states[end][0]:next_states[end]=candidate
            if not next_states:
                label=token.get('word',token.get('punctuation'))
                raise MissingUnit(f'{speaker}/{emotion}: no supported dictionary/pause path at {label!r}')
            states=next_states
        finished=[state for last,state in states.items() if last=='SIL' or self.has_pair(speaker,emotion,(last,'SIL'))]
        if not finished:raise MissingUnit(f'{speaker}/{emotion}: missing final silence transition')
        _,phones,choices=min(finished,key=lambda state:state[0])
        if phones[-1]!='SIL':phones=phones+['SIL']
        self.warnings.extend(choices)
        return {'normalized':normalized,'phones':phones}
    def select(self,speaker,emotion,pair,context=None):
        for emo in ([emotion,'neutral'] if self.fallback=='neutral' and emotion!='neutral' else [emotion]):
            candidates=[u for u in self.index['units'] if u['speaker_id']==speaker and u['emotion']==emo
                        and (u.get('verified') is True or self.audition_unverified) and tuple(u['phones'])==tuple(pair)]
            if not candidates and self.stress_fallback:
                candidates=[u for u in self.index['units'] if u['speaker_id']==speaker and u['emotion']==emo
                    and (u.get('verified') is True or self.audition_unverified) and tuple(map(base,u['phones']))==tuple(map(base,pair))]
                if candidates:
                    self.warnings.append({'stress_fallback':pair})
            if candidates:
                if emo!=emotion:
                    self.warnings.append({'emotion_fallback':emotion,'to':'neutral','pair':pair})
                # Acoustic allophones remain reviewed annotations. Prefer the
                # same neighboring-phone context rather than blindly pooling them.
                def context_penalty(u):
                    if not context:return 0
                    actual=u.get('context',{})
                    return sum(actual.get(k)!=value for k,value in context.items())
                chosen=min(candidates,key=lambda u:(u['quality'].get('clipped_fraction',1),context_penalty(u),u['id']))
                if not chosen.get('verified'):
                    self.warnings.append({'unverified_audition_unit':chosen['id'],'pair':pair})
                return chosen
        raise MissingUnit(f'{speaker}/{emotion}: missing {pair[0]}|{pair[1]}')
    def load(self,u):
        p=safe_path(self.root,u['file'])
        if hashlib.sha256(p.read_bytes()).hexdigest()!=u['sha256']:
            raise ValueError('Sample checksum mismatch: '+u['file'])
        rate,audio=read_wav(p)
        if self.rate is not None and rate!=self.rate:
            raise ValueError('Mixed sample rates in bank')
        self.rate=rate
        return audio
    def speech(self,speaker,emotion,text):
        p=self.pronounce_for_bank(speaker,emotion,text) if self.bank_pronunciations else self.lexicon.pronounce(text)
        phones=p['phones']
        units=[self.select(speaker,emotion,pair,{'previous':phones[i-1] if i else 'SIL',
                    'next':phones[i+2] if i+2<len(phones) else 'SIL'})
               for i,pair in enumerate(zip(phones,phones[1:]))]
        if not units:
            return array('h')
        result=array('h'); prev=None
        for u in units:
            audio=self.load(u)
            h=round(self.rate*self.crossfade_ms/2000)
            if u['left_handle']<h or u['right_handle']<h:
                raise ValueError('Unit lacks requested overlap handles')
            # Read symmetric handles: the 2*h crossfade spans a shared phone anchor.
            audio=audio[u['left_handle']-h:len(audio)-u['right_handle']+h]
            if prev is None:
                result.extend(audio[h:])
            else:
                n=2*h
                if len(result)<n or len(audio)<n:
                    raise ValueError('Unit too short for complementary crossfade')
                for j in range(n):
                    alpha=j/(n-1) if n>1 else 1
                    result[-n+j]=round(result[-n+j]*(1-alpha)+audio[j]*alpha)
                result.extend(audio[n:])
            prev=u
        return result[:-h]
    def event(self,speaker,emotion,name):
        for emo in ([emotion,'neutral'] if self.fallback=='neutral' and emotion!='neutral' else [emotion]):
            candidates=[u for u in self.index['events'] if u['speaker_id']==speaker and
                        u['emotion']==emo and u['event']==name and u.get('verified') is True]
            if candidates:
                if emo!=emotion:
                    self.warnings.append({'event_emotion_fallback':name,'from':emotion,'to':emo})
                return self.load(candidates[0])
        raise MissingUnit(f'{speaker}/{emotion}: missing whole-sample event {name}')
    def render(self,speaker,text,output,cache=None):
        self.warnings=[]
        t0=time.perf_counter()
        # Lexicon and aliases participate in cache identity, not just text and bank.
        config={'bank':self.digest,'speaker':speaker,'text':text,'crossfade':self.crossfade_ms,
            'fallback':self.fallback,'stress':self.stress_fallback,'audition_unverified':self.audition_unverified,
             'dictionary':self.lexicon.dictionary_digest,
             'bank_pronunciations':self.bank_pronunciations,
            'overrides':self.lexicon.overrides,'aliases':self.lexicon.aliases}
        key=hashlib.sha256(json.dumps(config,sort_keys=True).encode()).hexdigest()
        cached=Path(cache)/(key+'.wav') if cache else None
        if cached and cached.exists() and cached.with_suffix('.json').exists():
            metadata=json.loads(cached.with_suffix('.json').read_text())
            cached_bytes=cached.read_bytes()
            if metadata.get('output_sha256')==hashlib.sha256(cached_bytes).hexdigest():
                Path(output).parent.mkdir(parents=True,exist_ok=True)
                Path(output).write_bytes(cached_bytes)
                return {**metadata,'cache_hit':True,'wall_seconds':time.perf_counter()-t0}
        result=array('h')
        for kind,emotion,value in markup(text):
            piece=self.speech(speaker,emotion,value) if kind=='speech' else self.event(speaker,emotion,value)
            result.extend(piece)
        if not result or not self.rate:
            raise ValueError('Empty synthesis request')
        write_wav(output,self.rate,result)
        metadata={'cache_hit':False,'wall_seconds':time.perf_counter()-t0,'audio_seconds':len(result)/self.rate,
                  'bytes':Path(output).stat().st_size,'warnings':self.warnings,'speaker':speaker,'cache_key':key,
                  'output_sha256':hashlib.sha256(Path(output).read_bytes()).hexdigest()}
        if cached:
            cached.parent.mkdir(parents=True,exist_ok=True)
            tmp=cached.with_suffix('.wav.part')
            tmp.write_bytes(Path(output).read_bytes());tmp.replace(cached)
            meta_tmp=cached.with_suffix('.json.part')
            meta_tmp.write_text(json.dumps(metadata,indent=2));meta_tmp.replace(cached.with_suffix('.json'))
        return metadata

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bank',required=True);p.add_argument('--lexicon',required=True)
    p.add_argument('--overrides');p.add_argument('--speaker',required=True)
    p.add_argument('--text',required=True);p.add_argument('--output',required=True)
    p.add_argument('--cache');p.add_argument('--emotion-fallback',choices=['error','neutral'],default='error')
    p.add_argument('--stress-fallback',action='store_true')
    p.add_argument('--audition-unverified',action='store_true',help='Audition candidates only; never certifies a bank')
    p.add_argument('--bank-pronunciations',action='store_true',help='Use supported dictionary variants/recorded pauses and report every non-default choice')
    a=p.parse_args()
    r=Renderer(a.bank,Lexicon.load(a.lexicon,a.overrides),emotion_fallback=a.emotion_fallback,stress_fallback=a.stress_fallback,
               audition_unverified=a.audition_unverified,bank_pronunciations=a.bank_pronunciations)
    print(json.dumps(r.render(a.speaker,a.text,a.output,a.cache),indent=2))

if __name__=='__main__':main()
