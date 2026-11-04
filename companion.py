"""Opt-in local native-game mailbox. Sample-only; no network listener or eval.

This is an implementation awaiting remote fixtures and actual native acceptance.
Installing writes only into the explicitly supplied game base directory. Nothing
is installed or started merely by importing this module.
"""
from __future__ import annotations
import argparse
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import signal
import threading
import time
from phonetics import Lexicon
from renderer import Renderer

VERSION='1'
VOICES=[*(f'Male{i}' for i in range(1,6)),*(f'Fem{i}' for i in range(1,6)),
        *(f'Derm{i}' for i in range(1,4)),'Bot1','Announcer','TrainingFemale','BriefingMale']
EMOTIONS={'neutral','angry','sad','excited','calm'}
MAX_TEXT=240
MAX_LOG=4194304
MAX_OUTPUT=134217728
MAILBOX='prefs/t2vl-live'

def owned(base,relative):
    base=Path(base).resolve();candidate=base/relative
    if candidate.is_symlink():raise ValueError('Symlink mailbox/output refused')
    path=candidate.resolve()
    if base not in path.parents:raise ValueError('Mailbox/output escapes game base')
    return path

def atomic(path,data):
    path=Path(path)
    if path.is_symlink():raise ValueError('Symlink destination refused')
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_name(path.name+'.'+secrets.token_hex(8)+'.part')
    try:
        fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'wb') as stream:
            stream.write(data);stream.flush();os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)

def save(path,data):atomic(path,json.dumps(data,indent=2).encode())

def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def install(base,bank,lexicon,overrides=None,audition_unverified=False,bank_pronunciations=False):
    base=Path(base).resolve()
    if not base.is_dir():raise ValueError('Supply an EXISTING native game base directory')
    mailbox=owned(base,MAILBOX)
    if mailbox.exists():raise ValueError('Mailbox already exists; refusing to replace identity, pending requests or evidence')
    client_script=owned(base,'scripts/t2vl_live_client.cs')
    if client_script.exists():raise ValueError('Client script already exists; refusing to overwrite it')
    index=Path(bank).resolve()/'index.json';inventory=json.loads(index.read_text())
    voices=sorted(set(inventory['speakers'])&set(VOICES))
    if not voices:raise ValueError('No supported voices in bank')
    config={'version':VERSION,'session':secrets.token_hex(8),'token':secrets.token_hex(32),
            'bank':str(Path(bank).resolve()),'bank_sha256':digest(index),
            'lexicon':str(Path(lexicon).resolve()),'lexicon_sha256':digest(lexicon),
            'overrides':str(Path(overrides).resolve()) if overrides else None,
            'overrides_sha256':digest(overrides) if overrides else None,'voices':voices,
            'audition_unverified':bool(audition_unverified),'bank_pronunciations':bool(bank_pronunciations)}
    mailbox.mkdir(parents=True,mode=0o700)
    owned(base,'audio/t2vl-live').mkdir(parents=True,exist_ok=True)
    atomic(mailbox/'requests.tsv',b'')
    atomic(mailbox/'response.tsv',b'')
    save(mailbox/'companion.json',config)
    save(mailbox/'state.json',{'session':config['session'],'offset':0,'last_seq':0,'pending':None})
    code='// PRIVATE local configuration. Never distribute the token.\n'
    for name,value in [('Version',VERSION),('Session',config['session']),('Token',config['token']),('Bank',config['bank_sha256'])]:
        code+=f'$T2VLLive::{name} = "{value}";\n'
    for voice in voices:code+=f'$T2VLLive::Voice["{voice}"] = true;\n'
    atomic(mailbox/'config.cs',code.encode())
    atomic(client_script,CLIENT.encode())
    # Does not execute/install on a server; explicit server loading remains separate.
    server=SERVER.replace('@BANK@',config['bank_sha256']).replace('@VOICES@',' '.join(voices))
    server+='\n'+CLIENT[CLIENT.index('function T2VLLiveTextOK'):]
    atomic(mailbox/'server.cs',server.encode())
    save(mailbox/'installation.json',{'version':VERSION,'bank_sha256':config['bank_sha256'],
         'candidate_audition_only':audition_unverified,'native_client_test':'NOT RUN',
         'production_license_clearance':'NOT ESTABLISHED'})
    return {'base':str(base),'version':VERSION,'bank_sha256':config['bank_sha256'],
            'candidate_audition_only':audition_unverified,'native_client_test':'NOT RUN'}

class Companion:
    def __init__(self,base,renderer=None,clock=time.time):
        self.base=Path(base).resolve();self.folder=owned(self.base,MAILBOX);self.clock=clock
        self.config=json.loads(owned(self.base,MAILBOX+'/companion.json').read_text())
        self.state=json.loads(owned(self.base,MAILBOX+'/state.json').read_text())
        c=self.config
        if c['version']!=VERSION or self.state['session']!=c['session']:raise ValueError('Protocol/session mismatch')
        if not re.fullmatch(r'[0-9a-f]{16}',c['session']) or not re.fullmatch(r'[0-9a-f]{64}',c['token']):
            raise ValueError('Invalid local credential/session configuration')
        for path,expected in [(Path(c['bank'])/'index.json',c['bank_sha256']),
                              (c['lexicon'],c['lexicon_sha256'])]+([(c['overrides'],c['overrides_sha256'])] if c['overrides'] else []):
            if digest(path)!=expected:raise ValueError('Bank/dictionary configuration changed; do not reuse this session')
        self.renderer=renderer if renderer is not None else Renderer(c['bank'],Lexicon.load(c['lexicon'],c['overrides']),
            audition_unverified=c['audition_unverified'],bank_pronunciations=c['bank_pronunciations'])
    def persist(self):save(owned(self.base,MAILBOX+'/state.json'),self.state)
    def publish(self,seq,status,reason,milliseconds=0):
        row='\t'.join((VERSION,self.config['session'],str(seq),status,reason,str(milliseconds)))+'\n'
        atomic(owned(self.base,MAILBOX+'/response.tsv'),row.encode())
    def error(self,reason,detail=''):
        save(owned(self.base,MAILBOX+'/last-error.json'),{'reason':reason,'detail':str(detail)[:300],
             'at':self.clock(),'native_playback_verified':False})
        return reason
    def process_once(self):
        pending=self.state['pending']
        if pending and self.clock()>pending['deadline']:
            self.publish(pending['seq'],'ERROR','ack_timeout')
            self.state['pending']=None;self.persist();self.error('ack_timeout')
        path=owned(self.base,MAILBOX+'/requests.tsv');stat=path.stat()
        if stat.st_size>MAX_LOG:raise ValueError('Request-log budget exhausted; preserve/archive before resetting')
        if stat.st_size<self.state['offset']:raise ValueError('Request log truncated; refusing unsafe replay')
        identity=[stat.st_dev,stat.st_ino]
        if self.state.get('log_identity',identity)!=identity:raise ValueError('Request log replaced; refusing unsafe replay')
        self.state['log_identity']=identity
        with path.open('rb') as stream:
            stream.seek(self.state['offset']);line=stream.readline(2049)
            if not line:return 'idle'
            if len(line)>2048:raise ValueError('Oversized mailbox line; preserve log and inspect')
            if not line.endswith(b'\n'):return 'partial'
            self.state['offset']=stream.tell()
        # Offset is committed before acting: interruption may lose a request, never
        # silently replay speech. Recovery/timeout is explicit, not exactly-once audio.
        self.persist()
        try:fields=line.decode('utf-8').rstrip('\n').split('\t')
        except UnicodeDecodeError:return self.error('invalid_encoding')
        if len(fields)!=8:return self.error('invalid_fields')
        version,token,session,kind,seq,speaker,emotion,text=fields
        if (not re.fullmatch(r'[0-9a-f]{64}',token) or not re.fullmatch(r'[0-9a-f]{16}',session) or
                not hmac.compare_digest(token,self.config['token']) or not hmac.compare_digest(session,self.config['session'])):
            return self.error('authentication_failed')
        if not re.fullmatch(r'[1-9][0-9]{0,8}',seq):return self.error('invalid_sequence')
        seq=int(seq);pending=self.state['pending']
        if version!=VERSION:
            if not pending:self.publish(seq,'ERROR','protocol_mismatch')
            return self.error('protocol_mismatch')
        if kind=='A':
            if not pending or seq!=pending['seq']:return self.error('stale_ack')
            if text not in ('playback_timer_elapsed','engine_failed','cancelled'):return self.error('invalid_ack')
            self.publish(seq,'DONE',text);self.state['pending']=None;self.persist()
            return 'acknowledged'
        if kind!='S':return self.error('invalid_operation')
        if pending:return self.error('busy','One outstanding request; no response or speech was overwritten')
        if seq<=self.state['last_seq']:return self.error('duplicate_sequence')
        self.state['last_seq']=seq;self.persist()
        reason=None
        if speaker not in self.config['voices'] or emotion not in EMOTIONS:reason='unsupported_voice_style'
        elif not text.strip() or len(text)>MAX_TEXT or any(ord(c)<32 for c in text) or '[' in text or ']' in text:
            reason='invalid_text'
        if reason:
            self.publish(seq,'ERROR',reason);return self.error(reason)
        output=owned(self.base,f'audio/t2vl-live/{session}-{seq}.wav')
        temporary=output.with_suffix('.part.wav')
        if output.exists() or temporary.exists() or temporary.is_symlink():
            self.publish(seq,'ERROR','output_exists');return self.error('output_exists','Existing bytes preserved')
        used=sum(p.stat().st_size for p in output.parent.glob(session+'-*.wav') if p.is_file())
        try:
            if used>=MAX_OUTPUT:raise ValueError('Output budget exhausted; archive owned outputs explicitly')
            rendered=text if emotion=='neutral' else f'[{emotion}]{text}[/{emotion}]'
            result=self.renderer.render(speaker,rendered,temporary)
            milliseconds=round(result['audio_seconds']*1000)
            if not 1<=milliseconds<=30000 or used+temporary.stat().st_size>MAX_OUTPUT:
                raise ValueError('Rendered output exceeds duration/storage budget')
            temporary.replace(output)
            self.state['pending']={'seq':seq,'deadline':self.clock()+milliseconds/1000+30}
            self.persist();self.publish(seq,'READY','none',milliseconds)
            # Warnings retain missing/fallback/candidate provenance; no token/text.
            save(owned(self.base,MAILBOX+'/last-render.json'),{**result,'seq':seq,'text_stored':False,
                 'native_playback_verified':False})
            return 'ready'
        except ValueError as exc:
            self.publish(seq,'ERROR','render_refused');return self.error('render_refused',exc)
        finally:temporary.unlink(missing_ok=True)

CLIENT=r'''// PRIVATE, opt-in local companion. Not native-tested. Never eval chat text.
function T2VLLiveDigits(%value)
{
   if (strlen(%value) < 1 || strlen(%value) > 9) return false;
   for (%i=0; %i<strlen(%value); %i++)
      if (strstr("0123456789", getSubStr(%value,%i,1)) == -1) return false;
   return (%value > 0);
}
function T2VLLiveAppend(%kind,%seq,%speaker,%emotion,%text)
{
   %file = new FileObject();
   %ok = %file.openForAppend("prefs/t2vl-live/requests.tsv");
   if (%ok) {
      %file.writeLine($T2VLLive::Version TAB $T2VLLive::Token TAB $T2VLLive::Session TAB
                      %kind TAB %seq TAB %speaker TAB %emotion TAB %text);
      %file.close();
   }
   %file.delete();
   return %ok;
}
function T2VLLiveStart()
{
   if ($T2VLLive::Enabled) {
      if (isObject(ServerConnection) && ServerConnection.getId()==$T2VLLive::Connection) return;
      T2VLLiveStop();
   }
   if (!isObject(ServerConnection)) { error("Join the intended server before enabling the companion."); return; }
   exec("prefs/t2vl-live/config.cs"); // Locally generated config, NEVER server text.
   if ($T2VLLive::Version !$= "1" || strlen($T2VLLive::Session)!=16 || strlen($T2VLLive::Token)!=64) return;
   $T2VLLive::Sequence=0;
   %file=new FileObject();
   if (%file.openForRead("prefs/t2vl-live/requests.tsv")) {
      while (!%file.isEOF()) {
         %line=%file.readLine(); %seq=getField(%line,4);
         if (getField(%line,2) $= $T2VLLive::Session && T2VLLiveDigits(%seq) && %seq>$T2VLLive::Sequence)
            $T2VLLive::Sequence=%seq;
      }
      %file.close();
   }
   %file.delete();
   $T2VLLive::Enabled=true;
   $T2VLLive::Connection=ServerConnection.getId();
   commandToServer('T2VLLiveReady',"1",$T2VLLive::Bank);
}
function clientCmdT2VLLiveSpeak(%version,%speaker,%emotion,%text)
{
   if (!$T2VLLive::Enabled || %version !$= "1") return;
   if (!isObject(ServerConnection) || ServerConnection.getId()!=$T2VLLive::Connection) { T2VLLiveStop(); return; }
   if ($T2VLLive::Pending !$= "") { error("T2 voice companion busy; announcement refused."); return; }
   if (!$T2VLLive::Voice[%speaker] || !T2VLLiveTextOK(%emotion,%text)) return;
   $T2VLLive::Sequence++;
   if (!T2VLLiveDigits($T2VLLive::Sequence)) { error("T2 voice sequence exhausted."); return; }
   if (T2VLLiveAppend("S",$T2VLLive::Sequence,%speaker,%emotion,%text)) {
      $T2VLLive::Pending=$T2VLLive::Sequence;
      $T2VLLive::Deadline=getRealTime()+60000;
      T2VLLivePoll();
   }
}
function T2VLLivePoll()
{
   if (!$T2VLLive::Enabled || $T2VLLive::Pending $= "") return;
   if (!isObject(ServerConnection) || ServerConnection.getId()!=$T2VLLive::Connection) { T2VLLiveStop(); return; }
   if ($T2VLLive::Playing) {
      if (getRealTime()>=$T2VLLive::Ends) T2VLLiveComplete($T2VLLive::Pending,"playback_timer_elapsed");
      else $T2VLLive::Timer=schedule(200,0,"T2VLLivePoll");
      return;
   }
   %file=new FileObject(); %line="";
   if (%file.openForRead("prefs/t2vl-live/response.tsv")) { %line=%file.readLine(); %file.close(); }
   %file.delete();
   %seq=getField(%line,2); %status=getField(%line,3); %duration=getField(%line,5);
   if (getField(%line,0) $= "1" && getField(%line,1) $= $T2VLLive::Session && %seq $= $T2VLLive::Pending) {
      if (%status $= "ERROR") { error("T2 voice refusal: " @ getField(%line,4)); $T2VLLive::Pending=""; return; }
      if (%status $= "READY" && T2VLLiveDigits(%duration) && %duration<=30000) {
         %path="audio/t2vl-live/" @ $T2VLLive::Session @ "-" @ %seq @ ".wav";
         if (!isFile(%path)) { T2VLLiveComplete(%seq,"engine_failed"); return; }
         $T2VLLive::Handle=alxCreateSource(AudioGui,%path);
         if (!$T2VLLive::Handle) { T2VLLiveComplete(%seq,"engine_failed"); return; }
         alxPlay($T2VLLive::Handle);
         $T2VLLive::Playing=true;
         $T2VLLive::Ends=getRealTime()+%duration+50;
         $T2VLLive::Timer=schedule(200,0,"T2VLLivePoll");
         return;
      }
   }
   if (getRealTime()>$T2VLLive::Deadline) { T2VLLiveComplete($T2VLLive::Pending,"cancelled"); return; }
   $T2VLLive::Timer=schedule(200,0,"T2VLLivePoll");
}
function T2VLLiveComplete(%seq,%result)
{
   if (%seq !$= $T2VLLive::Pending) return;
   T2VLLiveAppend("A",%seq,"-","-",%result);
   $T2VLLive::Playing=false;
   $T2VLLive::Pending="";
}
function T2VLLiveStop()
{
   cancel($T2VLLive::Timer);
   if ($T2VLLive::Handle !$= "") alxStop($T2VLLive::Handle);
   if ($T2VLLive::Pending !$= "") T2VLLiveComplete($T2VLLive::Pending,"cancelled");
   $T2VLLive::Enabled=false;
}
function T2VLLiveTextOK(%emotion,%text)
{
   if (%emotion !$= "neutral" && %emotion !$= "angry" && %emotion !$= "sad" && %emotion !$= "excited" && %emotion !$= "calm") return false;
   if (strlen(%text)<1 || strlen(%text)>240) return false;
   return strstr(%text,"\t")==-1 && strstr(%text,"\n")==-1 && strstr(%text,"\r")==-1 && strstr(%text,"[")==-1 && strstr(%text,"]")==-1;
}
'''

SERVER=r'''// PRIVATE server opt-in. Client companion and actual native acceptance required.
$T2VLLiveServer::ExpectedBank="@BANK@";
function serverCmdT2VLLiveReady(%client,%version,%bank)
{
   %client.t2vlLiveReady=(%version $= "1" && %bank $= $T2VLLiveServer::ExpectedBank);
}
function serverCmdT2VLLiveAnnounce(%client,%speaker,%emotion,%text)
{
   if ((!%client.isAdmin && !%client.isSuperAdmin) || !T2VLLiveServerVoice(%speaker) || !T2VLLiveTextOK(%emotion,%text)) return;
   if (%client.t2vlLiveLast !$= "" && getSimTime()-%client.t2vlLiveLast<1000) return;
   %client.t2vlLiveLast=getSimTime();
   for (%i=0;%i<ClientGroup.getCount();%i++) {
      %target=ClientGroup.getObject(%i);
      if (%target.t2vlLiveReady) commandToClient(%target,'T2VLLiveSpeak',"1",%speaker,%emotion,%text);
      else messageClient(%target,'',"Custom voice needs the matching opt-in local companion.");
   }
}
function T2VLLiveServerVoice(%voice)
{
   %voices="@VOICES@";
   for (%i=0;%i<getWordCount(%voices);%i++)
      if (%voice $= getWord(%voices,%i)) return true;
   return false;
}
'''

def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='action',required=True)
    i=sub.add_parser('install');i.add_argument('--base',type=Path,required=True)
    i.add_argument('--bank',type=Path,required=True);i.add_argument('--lexicon',type=Path,required=True)
    i.add_argument('--overrides',type=Path);i.add_argument('--audition-unverified',action='store_true')
    i.add_argument('--bank-pronunciations',action='store_true')
    s=sub.add_parser('serve');s.add_argument('--base',type=Path,required=True);s.add_argument('--once',action='store_true')
    a=p.parse_args()
    if a.action=='install':
        print(json.dumps(install(a.base,a.bank,a.lexicon,a.overrides,a.audition_unverified,a.bank_pronunciations),indent=2));return
    service=Companion(a.base)
    if a.once:print(service.process_once());return
    stop=threading.Event()
    for signum in (signal.SIGINT,signal.SIGTERM):signal.signal(signum,lambda *_:stop.set())
    print('Local sample-only companion ready. Native audible playback is NOT certified.',flush=True)
    while not stop.is_set():
        result=service.process_once()
        if result not in ('idle','partial'):
            if result in ('ready','acknowledged'):print(result,flush=True)
            else:print((service.folder/'last-error.json').read_text(),flush=True)
        stop.wait(0.2)

if __name__=='__main__':main()
