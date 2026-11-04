"""Dictionary-only runtime frontend. No model, network, or GPU dependencies.

CMUdict JSON is produced during preparation. ARPAbet stress is retained in
variant keys; base coverage can separately collapse vowel stress.
"""
from __future__ import annotations
import json
import hashlib
import re
from collections import Counter
from pathlib import Path
from types import MappingProxyType

SIL = 'SIL'
ONES = 'zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen'.split()
TENS = 'zero ten twenty thirty forty fifty sixty seventy eighty ninety'.split()
ABBREVIATIONS = {'tts':'tee tee ess', 'afk':'ay eff kay', 'gg':'good game',
                 'ctf':'see tee eff', 'fps':'eff pee ess', 'admin':'administrator',
                 'vs':'versus', 'hp':'aitch pee', 'id':'eye dee'}

class UnknownWords(ValueError):
    def __init__(self, words):
        self.words = sorted(set(words))
        super().__init__('Unknown words (add pronunciation overrides): ' + ', '.join(self.words))

def number(n):
    n = int(n)
    if n < 0:
        return 'minus ' + number(-n)
    if n < 20:
        return ONES[n]
    if n < 100:
        return TENS[n//10] + (' '+ONES[n%10] if n%10 else '')
    if n < 1000:
        return ONES[n//100]+' hundred'+(' '+number(n%100) if n%100 else '')
    if n < 1000000:
        return number(n//1000)+' thousand'+(' '+number(n%1000) if n%1000 else '')
    return ' '.join(ONES[int(c)] for c in str(n))

def normalize(text, aliases=None):
    aliases = {k.casefold():v for k,v in (aliases or {}).items()}
    # A whole username alias wins before punctuation, digits, and camel-case splitting.
    for key in sorted(aliases, key=len, reverse=True):
        text = re.sub(r'(?<!\w)'+re.escape(key)+r'(?!\w)', lambda _: aliases[key], text, flags=re.I)
    text = re.sub(r'(?<=[a-z])(?=[A-Z])',' ',text)
    text = re.sub(r'(?<=\d)(?=[A-Za-z])|(?<=[A-Za-z])(?=\d)', ' ', text)
    text = text.replace('_',' ').replace('/',' ').replace('&',' and ')
    text = re.sub(r'\b(-?\d+)\.(\d+)\b',lambda m:number(m[1])+' point '+' '.join(ONES[int(c)] for c in m[2]),text)
    text = re.sub(r'(?<!\w)-?\d+', lambda m:number(m[0]),text)
    # Remove command prefix only; never silently discard an unknown command word.
    words = re.findall(r"[^\W\d_]+(?:'[^\W\d_]+)?|[.!?;,:]",text.casefold())
    return ' '.join(ABBREVIATIONS.get(w,w) for w in words)

def base(phone):
    return re.sub(r'[012]$','',phone)

def transitions(phones, collapse_stress=False):
    ps = [base(p) for p in phones] if collapse_stress else phones
    return Counter(zip(ps,ps[1:]))

class Lexicon:
    def __init__(self, entries, overrides=None, aliases=None):
        frozen={k.casefold():(tuple(tuple(p) for p in v) if v and isinstance(v[0],(list,tuple)) else tuple(v))
                for k,v in entries.items()}
        self._entries=MappingProxyType(frozen)
        self._dictionary_digest=hashlib.sha256(json.dumps(frozen,sort_keys=True).encode()).hexdigest()
        self.overrides = {k.casefold():v for k,v in (overrides or {}).items()}
        self.aliases = aliases or {}
    @property
    def entries(self):
        return self._entries
    @property
    def dictionary_digest(self):
        return self._dictionary_digest
    @classmethod
    def load(cls, path, overrides=None):
        d = json.loads(Path(path).read_text())
        o = json.loads(Path(overrides).read_text()) if overrides else {}
        return cls(d,o.get('phones'),o.get('aliases'))
    def pronunciation_tokens(self,text):
        """Retain attested dictionary alternatives; explicit overrides replace them."""
        normalized=normalize(text,self.aliases)
        tokens=[];unknown=[]
        for word in normalized.split():
            if word in '.!?;,:':
                tokens.append({'punctuation':word});continue
            prons=self.overrides.get(word) or self.entries.get(word)
            if not prons:
                unknown.append(word);continue
            if not isinstance(prons[0],(list,tuple)):prons=[prons]
            tokens.append({'word':word,'pronunciations':[list(p) for p in prons]})
        if unknown:raise UnknownWords(unknown)
        return normalized,tokens
    def pronounce(self,text):
        normalized = normalize(text,self.aliases)
        phones, unknown, words = [SIL], [], []
        boundaries = []
        for w in normalized.split():
            if w in '.!?;,:':
                if phones[-1] != SIL:
                    phones.append(SIL)
                continue
            prons = self.overrides.get(w) or self.entries.get(w)
            if not prons:
                unknown.append(w)
                continue
            pron = prons[0] if isinstance(prons[0],(list,tuple)) else prons
            if words and phones[-1] != SIL:
                boundaries.append((phones[-1],pron[0]))
            phones.extend(pron)
            words.append(w)
        if unknown:
            raise UnknownWords(unknown)
        if phones[-1] != SIL:
            phones.append(SIL)
        return {'normalized':normalized,'phones':phones,'words':words,'cross_word':boundaries}

def coverage(rows, lexicon, verified_units=()):
    """Rows are never pooled across speaker or emotion. Unassigned rows stay explicit."""
    reports = {}
    for row in rows:
        key = (row.get('speaker_id') or 'UNASSIGNED')+'/'+row.get('emotion','neutral')
        r = reports.setdefault(key, {'predicted':Counter(),'cross_word':Counter(),'unknown':[],
                                     'rows':0,'unverified_transcript_rows':0,'usable':set()})
        r['rows'] += 1
        if str(row.get('transcript_verified','false')).lower() != 'true':
            r['unverified_transcript_rows'] += 1
        try:
            p = lexicon.pronounce(row.get('text',''))
        except UnknownWords as e:
            r['unknown'].extend(e.words)
            continue
        r['predicted'].update(transitions(p['phones']))
        r['cross_word'].update(p['cross_word'])
    for u in verified_units:
        if u.get('verified') is True:
            key = u['speaker_id']+'/'+u['emotion']
            reports.setdefault(key, {'predicted':Counter(),'cross_word':Counter(),'unknown':[],
                                      'rows':0,'unverified_transcript_rows':0,'usable':set()})['usable'].add(tuple(u['phones']))
    return {k:{**{n:v for n,v in r.items() if n not in ('predicted','cross_word','usable','unknown')},
               'predicted_transitions':{'|'.join(p):n for p,n in sorted(r['predicted'].items())},
               'cross_word_transitions':{'|'.join(p):n for p,n in sorted(r['cross_word'].items())},
               'verified_usable_transitions':['|'.join(p) for p in sorted(r['usable'])],
               'unknown_words':sorted(set(r['unknown']))} for k,r in reports.items()}

def select_gaps(sentences, lexicon, target_pairs, existing=(), max_sentences=60):
    """Greedy set cover of a defined target, not a claim of all English coverage."""
    missing = set(map(tuple,target_pairs))-set(map(tuple,existing))
    candidates, rejected, chosen = [], [], []
    for s in sentences:
        try:
            p = lexicon.pronounce(s)
            candidates.append((s,p,set(transitions(p['phones']))))
        except UnknownWords as e:
            rejected.append({'text':s,'unknown':e.words})
    while missing and candidates and len(chosen) < max_sentences:
        best = max(candidates,key=lambda x:len(x[2]&missing)/max(1,len(x[1]['phones'])))
        gain = best[2]&missing
        if not gain:
            break
        chosen.append({'text':best[0],'phones':best[1]['phones'],'new_pairs':['|'.join(p) for p in sorted(gain)],
                       'pronunciation_verified':False,'audio_verified':False})
        missing -= gain
        candidates.remove(best)
    return {'selected':chosen,'uncovered':['|'.join(p) for p in sorted(missing)],'rejected':rejected,
            'scope':'Only the declared target transitions; predicted pronunciation pending audio validation.'}
