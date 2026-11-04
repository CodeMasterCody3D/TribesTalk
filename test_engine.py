"""Remote CPU regression/benchmark suite. Synthetic fixtures are NOT voice coverage."""
from array import array
import hashlib
import json
import math
from pathlib import Path
import tempfile
import time
import unittest
from bank import extract,write_wav,write_index,read_wav,safe_path
from phonetics import Lexicon,UnknownWords,number,normalize,coverage,select_gaps
from renderer import Renderer,MissingUnit,markup

class EngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        self.lex=Lexicon({'hello':[['HH','AH0','L','OW1']], 'world':[['W','ER1','L','D']]})
    def tearDown(self):self.tmp.cleanup()
    def make_bank(self,emotion='neutral'):
        src=self.root/'source.wav'; rate=16000
        write_wav(src,rate,array('h',(round(9000*math.sin(2*math.pi*180*i/rate)) for i in range(rate))))
        labels=['SIL','HH','AH0','L','OW1','SIL']
        alignment={'source':str(src),'speaker_id':'synthetic','emotion':emotion,
                   'speaker_verified':True,'transcript_verified':True,'alignment_verified':True,
                   'emotion_verified':True,'phones':[{'label':p,'start':i/6,'end':(i+1)/6} for i,p in enumerate(labels)]}
        bank=self.root/'bank'
        units=extract(alignment,bank)
        write_index(bank,units)
        return bank,units
    def test_numbers(self):
        self.assertEqual(number(2042),'two thousand forty two')
        self.assertEqual(normalize('/kick Cody_42 in 2.5 seconds'), 'kick cody forty two in two point five seconds')
    def test_username_override(self):
        self.assertEqual(normalize('CodeMasterCody3D',{'CodeMasterCody3D':'Cody'}),'cody')
    def test_cross_word(self):
        p=self.lex.pronounce('hello world')
        self.assertEqual(p['cross_word'],[('OW1','W')])
        self.assertEqual(p['phones'][0],'SIL'); self.assertEqual(p['phones'][-1],'SIL')
    def test_unknown_is_explicit(self):
        with self.assertRaises(UnknownWords) as cm:self.lex.pronounce('hello xzq')
        self.assertEqual(cm.exception.words,['xzq'])
    def test_unicode_username_is_not_silently_removed(self):
        with self.assertRaises(UnknownWords) as cm:self.lex.pronounce('hello 王')
        self.assertEqual(cm.exception.words,['王'])
    def test_dictionary_is_immutable(self):
        with self.assertRaises(TypeError):self.lex.entries['hello']=[['P']]
        with self.assertRaises(TypeError):self.lex.entries['hello'][0][0]='P'
        with self.assertRaises(AttributeError):self.lex.entries={}
    def path_renderer(self,lex,phones,**kwargs):
        bank=self.root/'paths';bank.mkdir(exist_ok=True)
        units=[{'speaker_id':'synthetic','emotion':'neutral','phones':list(pair),'verified':True}
               for pair in zip(phones,phones[1:])]
        (bank/'index.json').write_text(json.dumps({'units':units,'events':[]}))
        return Renderer(bank,lex,bank_pronunciations=True,**kwargs)
    def test_bank_dictionary_alternative_is_explicit(self):
        lex=Lexicon({'to':[['T','UW1'],['T','AH0']],'the':[['DH','AH0']]})
        phones=['SIL','T','AH0','DH','AH0','SIL']
        r=self.path_renderer(lex,phones)
        self.assertEqual(r.pronounce_for_bank('synthetic','neutral','to the')['phones'],phones)
        self.assertEqual(r.warnings[0]['pronunciation_choice'],'to')
        self.assertEqual(lex.pronounce('to the')['phones'][2],'UW1')
    def test_bank_paths_look_ahead_without_greedy_failure(self):
        lex=Lexicon({'a':[['AH0'],['AH1']],'word':[['W']]})
        r=self.path_renderer(lex,['SIL','AH1','W','SIL'])
        r.available[('synthetic','neutral')].add(('SIL','AH0'))
        self.assertEqual(r.pronounce_for_bank('synthetic','neutral','a word')['phones'],['SIL','AH1','W','SIL'])
    def test_bank_path_respects_explicit_override(self):
        lex=Lexicon({'to':[['T','UW1'],['T','AH0']]},{'to':['T','UW1']})
        r=self.path_renderer(lex,['SIL','T','AH0','SIL'])
        with self.assertRaises(MissingUnit):r.pronounce_for_bank('synthetic','neutral','to')
    def test_bank_path_comma_choice_reported(self):
        lex=Lexicon({'one':[['W','AH1','N']],'two':[['T','UW1']]})
        phones=['SIL','W','AH1','N','T','UW1','SIL']
        r=self.path_renderer(lex,phones)
        self.assertEqual(r.pronounce_for_bank('synthetic','neutral','one, two')['phones'],phones)
        self.assertTrue(any(x.get('pause_choice')=='comma_without_recorded_silence' for x in r.warnings))
        with self.assertRaises(MissingUnit):r.pronounce_for_bank('synthetic','neutral','one. two')
    def test_bank_path_recorded_word_pause(self):
        lex=Lexicon({'one':[['W','AH1','N']],'two':[['T','UW1']]})
        phones=['SIL','W','AH1','N','SIL','T','UW1','SIL']
        r=self.path_renderer(lex,phones)
        self.assertEqual(r.pronounce_for_bank('synthetic','neutral','one two')['phones'],phones)
        self.assertTrue(any(x.get('pause_choice')=='recorded_word_boundary' for x in r.warnings))
    def test_bank_paths_never_borrow_voice_style_or_review(self):
        lex=Lexicon({'one':[['W','AH1','N']]})
        r=self.path_renderer(lex,['SIL','W','AH1','N','SIL'])
        for speaker,emotion in (('other','neutral'),('synthetic','angry')):
            with self.assertRaises(MissingUnit):r.pronounce_for_bank(speaker,emotion,'one')
        data=json.loads((r.root/'index.json').read_text())
        for unit in data['units']:unit['verified']=False
        (r.root/'index.json').write_text(json.dumps(data))
        r=Renderer(r.root,lex,bank_pronunciations=True)
        with self.assertRaises(MissingUnit):r.pronounce_for_bank('synthetic','neutral','one')
    def test_bank_paths_unknown_and_missing_remain_errors(self):
        r=self.path_renderer(self.lex,['SIL','HH','AH0','L','OW1','SIL'])
        with self.assertRaises(UnknownWords):r.pronounce_for_bank('synthetic','neutral','hello xzq')
        with self.assertRaises(MissingUnit):r.pronounce_for_bank('synthetic','neutral','world')
    def test_bank_mode_cache_isolated_from_strict(self):
        bank,_=self.make_bank();out=self.root/'out.wav'
        strict=Renderer(bank,self.lex).render('synthetic','hello',out,self.root/'cache')
        bank_result=Renderer(bank,self.lex,bank_pronunciations=True).render('synthetic','hello',out,self.root/'cache')
        self.assertNotEqual(strict['cache_key'],bank_result['cache_key'])
        self.assertEqual(strict['output_sha256'],bank_result['output_sha256'])
    def test_context_selects_reviewed_variant(self):
        bank,units=self.make_bank()
        original=units[1]
        alternate={**original,'id':'alternate','variants':['reviewed_allophone','canonical'],
                   'context':{'previous':'K','next':'AH0'}}
        write_index(bank,[*units,alternate])
        selected=Renderer(bank,self.lex).select('synthetic','neutral',original['phones'],
            context={'previous':'K','next':'AH0'})
        self.assertEqual(selected['id'],'alternate')
    def test_markup(self):
        self.assertEqual(markup('[angry]hello[/angry] [grunt]'),[('speech','angry','hello'),('event','neutral','grunt')])
    def test_bad_markup(self):
        for text in ('[angry]hello','[angry][sad]hello[/sad][/angry]','[foo]','[/sad]'):
            with self.assertRaises(ValueError):markup(text)
    def test_missing_speaker(self):
        bank,_=self.make_bank()
        with self.assertRaises(MissingUnit):Renderer(bank,self.lex).render('other','hello',self.root/'out.wav')
    def test_missing_phone(self):
        bank,_=self.make_bank()
        with self.assertRaises(MissingUnit):Renderer(bank,self.lex).render('synthetic','world',self.root/'out.wav')
    def test_missing_event(self):
        bank,_=self.make_bank()
        with self.assertRaises(MissingUnit):Renderer(bank,self.lex).render('synthetic','[grunt]',self.root/'out.wav')
    def test_emotion_fallback_explicit(self):
        bank,_=self.make_bank()
        with self.assertRaises(MissingUnit):Renderer(bank,self.lex).render('synthetic','[angry]hello[/angry]',self.root/'out.wav')
        r=Renderer(bank,self.lex,emotion_fallback='neutral').render('synthetic','[angry]hello[/angry]',self.root/'out.wav')
        self.assertTrue(r['warnings'])
    def test_complementary_crossfade_duration(self):
        bank,units=self.make_bank()
        out=self.root/'out.wav'
        Renderer(bank,self.lex).render('synthetic','hello',out)
        rate,audio=read_wav(out)
        self.assertEqual(len(audio),sum(u['core_samples'] for u in units))
        # Same-source adjacent units reconstruct the original samples exactly.
        _,original=read_wav(self.root/'source.wav')
        a=round(units[0]['start_seconds']*rate)
        self.assertEqual(audio,original[a:a+len(audio)])
    def test_cache(self):
        bank,_=self.make_bank();r=Renderer(bank,self.lex); out=self.root/'out.wav'
        first=r.render('synthetic','hello',out,self.root/'cache')
        second=r.render('synthetic','hello',out,self.root/'cache')
        self.assertFalse(first['cache_hit']);self.assertTrue(second['cache_hit'])
        self.assertEqual(first['cache_key'],second['cache_key'])
        r.lexicon.aliases={'greeting':'hello'}
        self.assertNotEqual(r.render('synthetic','hello',out,self.root/'cache')['cache_key'],first['cache_key'])
    def test_corrupt_sample(self):
        bank,units=self.make_bank();p=bank/units[0]['file'];p.write_bytes(p.read_bytes()+b'x')
        with self.assertRaisesRegex(ValueError,'checksum'):Renderer(bank,self.lex).render('synthetic','hello',self.root/'out.wav')
    def test_unverified_refused(self):
        bank,units=self.make_bank();units[0]['verified']=False;write_index(bank,units)
        with self.assertRaises(MissingUnit):Renderer(bank,self.lex).render('synthetic','hello',self.root/'out.wav')
    def test_candidate_audition_is_explicit(self):
        bank,units=self.make_bank();units[0]['verified']=False;write_index(bank,units)
        result=Renderer(bank,self.lex,audition_unverified=True).render('synthetic','hello',self.root/'out.wav')
        self.assertTrue(any('unverified_audition_unit' in w for w in result['warnings']))
    def test_corrupt_cache_rebuilt(self):
        bank,_=self.make_bank();r=Renderer(bank,self.lex);out=self.root/'out.wav'
        result=r.render('synthetic','hello',out,self.root/'cache')
        cached=self.root/'cache'/(result['cache_key']+'.wav');cached.write_bytes(b'partial')
        rebuilt=r.render('synthetic','hello',out,self.root/'cache')
        self.assertFalse(rebuilt['cache_hit']);self.assertGreater(out.stat().st_size,44)
    def test_path_traversal(self):
        with self.assertRaises(ValueError):safe_path(self.root,'../../outside.wav')
    def test_predicted_not_verified(self):
        r=coverage([{'speaker_id':'synthetic','text':'hello'}],self.lex)['synthetic/neutral']
        self.assertTrue(r['predicted_transitions']);self.assertFalse(r['verified_usable_transitions'])
        self.assertEqual(r['unverified_transcript_rows'],1)
    def test_speaker_coverage_isolated(self):
        r=coverage([{'speaker_id':'one','text':'hello'},{'speaker_id':'two','text':'world'}],self.lex)
        self.assertNotEqual(r['one/neutral']['predicted_transitions'],r['two/neutral']['predicted_transitions'])
    def test_gap_selector(self):
        r=select_gaps(['hello world','hello','xzq'],self.lex,[('OW1','W'),('P','Z')])
        self.assertEqual(len(r['selected']),1); self.assertEqual(r['uncovered'],['P|Z']);self.assertEqual(len(r['rejected']),1)
    def test_bad_alignment(self):
        src=self.root/'source.wav';write_wav(src,16000,[0]*16000)
        with self.assertRaises(ValueError):extract({'source':str(src),'phones':[{'label':'AH0','start':0,'end':2}]},self.root/'bank')
    def test_stop_not_verified_without_release(self):
        src=self.root/'source.wav';write_wav(src,16000,[0]*16000)
        units=extract({'source':str(src),'speaker_id':'synthetic','speaker_verified':True,
            'transcript_verified':True,'alignment_verified':True,'emotion_verified':True,
            'phones':[{'label':'P','start':0,'end':0.5},{'label':'AH0','start':0.5,'end':1}]},self.root/'bank')
        self.assertFalse(units[0]['verified']);self.assertFalse(units[0]['release_safe'])
    def test_event_whole_sample(self):
        bank,units=self.make_bank();p=bank/'event.wav';write_wav(p,16000,[500]*8000)
        write_index(bank,units,[{'id':'event','speaker_id':'synthetic','emotion':'neutral','event':'grunt',
            'verified':True,'file':'event.wav','sha256':hashlib.sha256(p.read_bytes()).hexdigest()}])
        out=self.root/'out.wav';r=Renderer(bank,self.lex).render('synthetic','[grunt]',out)
        self.assertEqual(read_wav(out)[1],array('h',[500]*8000))

def benchmark():
    t=EngineTests();t.setUp()
    try:
        bank,units=t.make_bank();r=Renderer(bank,t.lex);out=t.root/'bench.wav'
        uncached=[];cached=[]
        for i in range(30):
            uncached.append(r.render('synthetic','hello',out)['wall_seconds'])
        r.render('synthetic','hello',out,t.root/'cache')
        for i in range(30):
            cached.append(r.render('synthetic','hello',out,t.root/'cache')['wall_seconds'])
        return {'fixture':'synthetic same-source sine wave, not speech quality evidence','host':'assigned Kaggle CPU',
            'unit_count':len(units),'bank_bytes':sum(p.stat().st_size for p in bank.rglob('*') if p.is_file()),
            'audio_seconds':read_wav(out)[1].__len__()/16000,'uncached_mean_seconds':sum(uncached)/30,
            'cached_mean_seconds':sum(cached)/30,'runs_per_condition':30}
    finally:t.tearDown()

if __name__=='__main__':
    if not str(Path(__file__).resolve()).startswith('/kaggle/'):
        raise RuntimeError('Run tests on remote compute')
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(EngineTests)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    Path('test-results.json').write_text(json.dumps({'tests':result.testsRun,'failures':len(result.failures),
        'errors':len(result.errors),'benchmark':benchmark() if result.wasSuccessful() else None},indent=2))
    raise SystemExit(0 if result.wasSuccessful() else 1)
