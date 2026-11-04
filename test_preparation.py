"""Remote fixture tests for alignment staging, stop preservation and game packaging."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile
import pilot
from alignment import stage,convert
from bank import extract,write_wav,read_wav
from events import export_events
from phonetics import Lexicon
from package_game import package
from build_bank import merge_banks
from gap_jobs import plan_incremental,immutable_json

class PreparationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.wav=self.root/'test.wav';write_wav(self.wav,16000,[0]*16000)
    def tearDown(self):self.temp.cleanup()
    def test_staging_unknown_refused(self):
        with self.assertRaises(ValueError):stage([{'text':'unknown','source':str(self.wav),'speaker_id':'one'}],Lexicon({}),self.root/'corpus')
    def test_staging_preserves_speaker(self):
        lex=Lexicon({'one':[['W','AH1','N']]})
        data=stage([{'text':'one','source':str(self.wav),'speaker_id':x} for x in ('female_candidate','male_candidate')],lex,self.root/'corpus')
        self.assertEqual(len(data),2)
    def test_stop_release_remains_intact(self):
        samples=[0]*16000
        samples[5000:5100]=[25000]*100
        write_wav(self.wav,16000,samples)
        d={'source':str(self.wav),'speaker_id':'synthetic','emotion':'neutral',
           **{k:True for k in ('speaker_verified','transcript_verified','alignment_verified','emotion_verified')},
           'phones':[{'label':'SIL','start':0,'end':0.2},
                     {'label':'P','start':0.2,'end':0.4,'anchor':0.25,'closure_verified':True,'protected_release':[0.3,0.34]},
                     {'label':'AH1','start':0.4,'end':0.8},{'label':'SIL','start':0.8,'end':1}]}
        units=extract(d,self.root/'bank')
        self.assertTrue(all(u['verified'] for u in units))
        release=next(u for u in units if u['phones'][0]=='P')
        self.assertEqual(sum(x==25000 for x in read_wav(self.root/'bank'/release['file'])[1]),100)
    def test_mfa_textgrid_candidate(self):
        import textgrid
        tg=textgrid.TextGrid(minTime=0,maxTime=1)
        tier=textgrid.IntervalTier(name='phones',minTime=0,maxTime=1)
        tier.add(0,0.2,'');tier.add(0.2,0.8,'AH1');tier.add(0.8,1,'')
        tg.append(tier);p=self.root/'test.TextGrid';tg.write(str(p))
        data=convert(p,{'source':str(self.wav),'speaker_id':'candidate','emotion':'neutral','text':'a'})
        self.assertEqual([x['label'] for x in data['phones']],['SIL','AH1','SIL'])
        self.assertFalse(data['alignment_verified'])
    def test_event_carrier_refused(self):
        review={'source':str(self.wav),'speaker_id':'one','event':'laugh','start':0.1,'end':0.5,
                'speaker_verified':True,'event_verified':True,'boundaries_verified':True,'event_type':'wordless',
                'source_sha256':hashlib.sha256(self.wav.read_bytes()).hexdigest()}
        with self.assertRaises(ValueError):export_events([review],self.root/'bank')
        review['contains_carrier_speech']=False
        self.assertEqual(len(export_events([review],self.root/'bank')),1)
    def test_unverified_event_skipped(self):
        self.assertEqual(export_events([{'source':str(self.wav)}],self.root/'bank'),[])
    def test_unverified_pack_refused(self):
        with self.assertRaises(ValueError):package([{'file':str(self.wav),'verified':False}],self.root/'test.vl2')
    def test_pack_local_wav_and_allowlist(self):
        p=self.root/'test.vl2'
        entries=package([{'file':str(self.wav),'verified':True,'text':'synthetic fixture','speaker_id':'one',
                          'sha256':hashlib.sha256(self.wav.read_bytes()).hexdigest()}],p)
        with zipfile.ZipFile(p) as z:
            client=z.read('scripts/t2vl_client.cs').decode()
            self.assertIn('alxCreateSource(AudioGui, %path)',client)
            self.assertEqual(z.read(entries[0]['file']),self.wav.read_bytes())
            self.assertEqual(z.testzip(),None)
        self.assertIn('isSuperAdmin',p.with_suffix('.server.cs').read_text())
    def test_changed_reviewed_phrase_refused(self):
        with self.assertRaisesRegex(ValueError,'checksum'):
            package([{'file':str(self.wav),'verified':True,'sha256':'0'*64}],self.root/'test.vl2')
    def assert_permission_rejected_before_model_import(self,permission):
        if permission is not None:
            path=self.root/'artifacts/permissions/rights-attestation.json'
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text(json.dumps(permission))
        original_import=__import__
        def guarded_import(name,*args,**kwargs):
            if name.split('.')[0] in ('numpy','soundfile','torch','infer','breeze_infer','models'):
                self.fail('Model dependencies imported before permission rejection: '+name)
            return original_import(name,*args,**kwargs)
        with patch.object(pilot,'ROOT',self.root),patch('builtins.__import__',side_effect=guarded_import):
            with self.assertRaises(PermissionError):pilot.generate(['Announcer'],allow_provisional=True)
    def test_absent_permission_refused_before_model_import(self):
        self.assert_permission_rejected_before_model_import(None)
    def test_unconfirmed_permission_refused_before_model_import(self):
        self.assert_permission_rejected_before_model_import({
            'performer_consent_and_recording_rights_confirmed':False,'voice_ids':['Announcer']})
    def test_wrong_voice_permission_refused_before_model_import(self):
        self.assert_permission_rejected_before_model_import({
            'performer_consent_and_recording_rights_confirmed':True,'voice_ids':['Male1']})
    def test_merge_preserves_conflicting_old_alignment_ids(self):
        banks=[]
        for i in range(2):
            folder=self.root/f'bank{i}';folder.mkdir();write_wav(folder/'unit.wav',16000,[i]*100)
            unit={'id':'same-old-source-and-phone-index','file':'unit.wav','speaker_id':'one',
                  'emotion':'neutral','phones':['SIL','AH1'],'verified':False,
                  'sha256':hashlib.sha256((folder/'unit.wav').read_bytes()).hexdigest(),
                  'start_seconds':i/100,'end_seconds':0.1,'left_handle':5,'right_handle':5}
            (folder/'index.json').write_text(json.dumps({'units':[unit],'events':[]}));banks.append(folder)
        self.assertEqual(merge_banks(banks,self.root/'strict'),[])
        units=merge_banks([*banks,banks[0]],self.root/'merged',include_candidates=True)
        self.assertEqual(len(units),2)
        self.assertEqual(len({u['id'] for u in units}),2)
        self.assertTrue(all(u['verified'] is False for u in units))
        self.assertNotEqual((self.root/'merged'/units[0]['file']).read_bytes(),
                            (self.root/'merged'/units[1]['file']).read_bytes())
        (banks[0]/'unit.wav').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'checksum'):
            merge_banks(banks,self.root/'broken',include_candidates=True)
    def gap_fixture(self):
        import shutil
        folder=self.root/'artifacts/references-provisional';folder.mkdir(parents=True,exist_ok=True)
        for speaker in ('Male1','Male2'):
            ref=folder/(speaker+'.wav');shutil.copy2(self.wav,ref)
            ref.with_suffix('.txt').write_text('one')
            ref.with_suffix('.json').write_text(json.dumps({'sha256':hashlib.sha256(ref.read_bytes()).hexdigest(),
                                                          'reference_verified':False}))
        bank=self.root/'gap-bank';bank.mkdir(exist_ok=True)
        phones=['SIL','W','AH1','N','SIL']
        units=[{'id':str(i),'speaker_id':'Male1','emotion':'neutral','phones':list(pair),'verified':False}
               for i,pair in enumerate(zip(phones,phones[1:]))]
        (bank/'index.json').write_text(json.dumps({'units':units,'events':[]}))
        return bank,Lexicon({'one':[['W','AH1','N']],'two':[['T','UW1']]})
    def test_gap_candidate_coverage_is_explicit(self):
        bank,lex=self.gap_fixture()
        strict,report=plan_incremental(self.root,bank,lex,['Male1'],['neutral'],2,sentences=['one','two'])
        audition,private=plan_incremental(self.root,bank,lex,['Male1'],['neutral'],2,True,sentences=['one','two'])
        self.assertEqual(len(strict),2);self.assertEqual([x['text'] for x in audition],['two'])
        self.assertFalse(report['candidate_coverage']);self.assertTrue(private['candidate_coverage'])
        self.assertTrue(all(x['verified'] is False and x['reference_verified'] is False for x in audition))
    def test_gap_voice_style_separation(self):
        bank,lex=self.gap_fixture()
        jobs,report=plan_incremental(self.root,bank,lex,['Male1','Male2'],['neutral','angry'],2,True,sentences=['one','two'])
        self.assertEqual(report['groups']['Male1/neutral']['supported_phone_paths'],1)
        for key in ('Male2/neutral','Male1/angry','Male2/angry'):
            self.assertEqual(report['groups'][key]['supported_phone_paths'],0)
            self.assertEqual(report['groups'][key]['selected_sentences'],2)
        self.assertEqual(len({x['id'] for x in jobs}),len(jobs))
        self.assertTrue(all(x['instruction'] for x in jobs if x['emotion']=='angry'))
    def test_gap_job_identity_and_source_are_stable(self):
        bank,lex=self.gap_fixture()
        args=(self.root,bank,lex,['Male1'],['neutral'],2,True)
        first,_=plan_incremental(*args,sentences=['one','two'])
        second,_=plan_incremental(*args,sentences=['one','two'])
        self.assertEqual(first,second)
        self.assertEqual(Path(first[0]['source']).name,first[0]['id']+'.wav')
    def test_gap_previous_intact_attempt_is_not_repeated(self):
        bank,lex=self.gap_fixture();folder=self.root/'artifacts/pilot';folder.mkdir()
        old={'id':'previous','kind':'speech','speaker_id':'Male1','emotion':'neutral','text':'two',
             'source':str(self.wav),'sha256':hashlib.sha256(self.wav.read_bytes()).hexdigest()}
        (folder/'pilot-jobs.json').write_text(json.dumps([old]))
        jobs,report=plan_incremental(self.root,bank,lex,['Male1'],['neutral'],2,True,sentences=['one','two'])
        self.assertEqual(jobs,[])
        self.assertEqual(report['groups']['Male1/neutral']['existing_attempts_excluded'],1)
        self.assertTrue(report['groups']['Male1/neutral']['predicted_uncovered_after'])
    def test_gap_changed_reference_is_refused(self):
        bank,lex=self.gap_fixture();ref=self.root/'artifacts/references-provisional/Male1.wav'
        ref.write_bytes(ref.read_bytes()+b'changed')
        with self.assertRaisesRegex(ValueError,'Reference checksum'):
            plan_incremental(self.root,bank,lex,['Male1'],['neutral'],sentences=['two'])
    def test_gap_unknown_workload_is_reported(self):
        bank,lex=self.gap_fixture()
        jobs,report=plan_incremental(self.root,bank,lex,['Male1'],['neutral'],sentences=['xzq'])
        self.assertEqual(jobs,[]);self.assertEqual(report['unknown_workload_items'][0]['unknown'],['xzq'])
    def test_gap_plan_changed_bytes_are_not_overwritten(self):
        path=self.root/'plan.json';immutable_json(path,[{'id':'one'}]);before=path.read_bytes()
        immutable_json(path,[{'id':'one'}])
        with self.assertRaisesRegex(ValueError,'overwrite'):immutable_json(path,[{'id':'two'}])
        self.assertEqual(path.read_bytes(),before)

if __name__=='__main__':
    if not str(Path(__file__).resolve()).startswith('/kaggle/'):
        raise RuntimeError('Run tests on assigned remote compute')
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(PreparationTests)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    Path('test-preparation-results.json').write_text(json.dumps({'tests':result.testsRun,
        'failures':len(result.failures),'errors':len(result.errors)},indent=2))
    raise SystemExit(0 if result.wasSuccessful() else 1)
