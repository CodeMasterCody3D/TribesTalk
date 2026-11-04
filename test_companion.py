"""Remote mailbox fixtures. Fake render bytes are NOT acoustic/native evidence."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from companion import Companion,install,MAILBOX,MAX_TEXT

class FakeRenderer:
    def __init__(self):self.calls=[];self.fail=False
    def render(self,speaker,text,output):
        self.calls.append((speaker,text))
        if self.fail:raise ValueError('Unknown words (add pronunciation overrides): fixture')
        # Transport fixture only: deliberately not an actual playable waveform.
        Path(output).write_bytes(b'transport fixture, not native audio')
        return {'audio_seconds':0.1,'warnings':[],
                'output_sha256':hashlib.sha256(Path(output).read_bytes()).hexdigest()}

class CompanionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.base=self.root/'base';self.base.mkdir()
        self.bank=self.root/'bank';self.bank.mkdir()
        (self.bank/'index.json').write_text(json.dumps({'speakers':['Announcer'],'units':[],'events':[]}))
        self.lexicon=self.root/'lexicon.json';self.lexicon.write_text(json.dumps({'hello':[['HH','EH1','L','OW0']]}))
        install(self.base,self.bank,self.lexicon)
        self.folder=self.base/MAILBOX;self.config=json.loads((self.folder/'companion.json').read_text())
        self.fake=FakeRenderer();self.now=100.0
        self.service=Companion(self.base,renderer=self.fake,clock=lambda:self.now)
    def tearDown(self):self.temp.cleanup()
    def send(self,seq=1,kind='S',speaker='Announcer',emotion='neutral',text='hello',**changes):
        fields={'version':'1','token':self.config['token'],'session':self.config['session'],
                'kind':kind,'seq':str(seq),'speaker':speaker,'emotion':emotion,'text':text}
        fields.update(changes)
        with (self.folder/'requests.tsv').open('a') as stream:stream.write('\t'.join(fields.values())+'\n')
        return self.service.process_once()
    def response(self):return (self.folder/'response.tsv').read_text().strip().split('\t')
    def ack(self,seq=1):return self.send(seq=seq,kind='A',speaker='-',emotion='-',text='playback_timer_elapsed')
    def test_speech_then_ack_does_not_claim_audible_playback(self):
        self.assertEqual(self.send(),'ready');self.assertEqual(self.response()[3],'READY')
        self.assertEqual(self.fake.calls,[('Announcer','hello')])
        self.assertFalse(json.loads((self.folder/'last-render.json').read_text())['native_playback_verified'])
        self.assertEqual(self.ack(),'acknowledged');self.assertIsNone(self.service.state['pending'])
    def test_bad_and_non_ascii_tokens_rejected_before_renderer(self):
        self.assertEqual(self.send(token='0'*64),'authentication_failed')
        self.assertEqual(self.send(token='王'*64),'authentication_failed')
        self.assertEqual(self.fake.calls,[])
        self.assertNotIn(self.config['token'],(self.folder/'last-error.json').read_text())
    def test_protocol_mismatch_explicit(self):
        self.assertEqual(self.send(version='2'),'protocol_mismatch')
        self.assertEqual(self.response()[4],'protocol_mismatch');self.assertEqual(self.fake.calls,[])
    def test_path_and_unsupported_voice_style_rejected(self):
        self.assertEqual(self.send(speaker='../../outside'),'unsupported_voice_style')
        self.assertEqual(self.send(seq=2,emotion='unknown'),'unsupported_voice_style')
        self.assertEqual(self.fake.calls,[])
    def test_markup_long_and_control_text_refused(self):
        for seq,text in enumerate(('[grunt]','a'*(MAX_TEXT+1),'hello\x00world'),1):
            self.assertEqual(self.send(seq=seq,text=text),'invalid_text')
        self.assertEqual(self.fake.calls,[])
    def test_busy_does_not_overwrite_unacknowledged_output(self):
        self.send();before=(self.folder/'response.tsv').read_bytes()
        self.assertEqual(self.send(seq=2),'busy')
        self.assertEqual((self.folder/'response.tsv').read_bytes(),before)
        self.assertEqual(len(self.fake.calls),1)
    def test_duplicate_request_never_rerenders(self):
        self.send();self.ack()
        self.assertEqual(self.send(),'duplicate_sequence');self.assertEqual(len(self.fake.calls),1)
    def test_restart_preserves_pending_and_offset(self):
        self.send()
        self.service=Companion(self.base,renderer=self.fake,clock=lambda:self.now)
        self.assertEqual(self.service.process_once(),'idle')
        self.assertEqual(self.ack(),'acknowledged');self.assertEqual(len(self.fake.calls),1)
    def test_partial_line_waits_without_consuming(self):
        row='\t'.join(('1',self.config['token'],self.config['session'],'S','1','Announcer','neutral','hello'))
        (self.folder/'requests.tsv').write_text(row)
        self.assertEqual(self.service.process_once(),'partial');self.assertEqual(self.service.state['offset'],0)
        with (self.folder/'requests.tsv').open('a') as stream:stream.write('\n')
        self.assertEqual(self.service.process_once(),'ready')
    def test_truncation_is_not_silent_replay(self):
        self.send();(self.folder/'requests.tsv').write_bytes(b'')
        with self.assertRaisesRegex(ValueError,'truncated'):self.service.process_once()
    def test_ack_timeout_is_explicit(self):
        self.send();self.now+=32
        self.assertEqual(self.service.process_once(),'idle')
        self.assertEqual(self.response()[4],'ack_timeout');self.assertIsNone(self.service.state['pending'])
    def test_changed_dictionary_blocks_startup(self):
        self.lexicon.write_text('{}')
        with self.assertRaisesRegex(ValueError,'configuration changed'):Companion(self.base,renderer=self.fake)
    def test_existing_output_is_preserved(self):
        output=self.base/'audio/t2vl-live'/f'{self.config["session"]}-1.wav';output.write_bytes(b'keep')
        self.assertEqual(self.send(),'output_exists');self.assertEqual(output.read_bytes(),b'keep')
    def test_renderer_refusal_preserves_detail(self):
        self.fake.fail=True
        self.assertEqual(self.send(),'render_refused')
        self.assertIn('Unknown words',(self.folder/'last-error.json').read_text())
    def test_install_refuses_existing_configuration_or_client_script(self):
        with self.assertRaisesRegex(ValueError,'already exists'):install(self.base,self.bank,self.lexicon)
        other=self.root/'other';(other/'scripts').mkdir(parents=True)
        script=other/'scripts/t2vl_live_client.cs';script.write_text('human script')
        with self.assertRaisesRegex(ValueError,'overwrite'):install(other,self.bank,self.lexicon)
        self.assertEqual(script.read_text(),'human script');self.assertFalse((other/MAILBOX).exists())
    def test_installed_server_bound_to_bank_and_has_validation(self):
        server=(self.folder/'server.cs').read_text();client=(self.base/'scripts/t2vl_live_client.cs').read_text()
        self.assertIn(self.config['bank_sha256'],server)
        self.assertNotIn('@BANK@',server);self.assertNotIn('@VOICES@',server)
        self.assertIn('function T2VLLiveTextOK',server)
        self.assertIn('isSuperAdmin',server)
        self.assertNotIn('eval(',server+client)
    def test_symlink_mailbox_escape_refused(self):
        other=self.root/'symlink-base';other.mkdir()
        outside=self.root/'outside';outside.mkdir()
        (other/'prefs').symlink_to(outside,target_is_directory=True)
        with self.assertRaisesRegex(ValueError,'escapes'):install(other,self.bank,self.lexicon)

if __name__=='__main__':
    if not str(Path(__file__).resolve()).startswith('/kaggle/'):
        raise RuntimeError('Run transport fixtures on the authorized remote fixture lane, not the laptop')
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(CompanionTests)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    Path('test-companion-results.json').write_text(json.dumps({'tests':result.testsRun,
         'failures':len(result.failures),'errors':len(result.errors),
         'scope':'Fake-render transport fixtures, NOT native/audio acceptance'},indent=2))
    raise SystemExit(0 if result.wasSuccessful() else 1)
