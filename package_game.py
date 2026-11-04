"""Build a PRIVATE preinstalled-phrase VL2, not a server-to-client WAV transfer.

Only reviewed rendered phrases may be packaged. Live arbitrary usernames are
not solved by this pack: they require new client content or a companion renderer.
"""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile
from bank import read_wav

def package(phrases,output):
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    entries=[]
    for phrase in phrases:
        if phrase.get('verified') is not True:
            raise ValueError('Refusing to package unreviewed phrase')
        p=Path(phrase['file']);rate,audio=read_wav(p)
        if not audio:raise ValueError('Empty phrase')
        digest=hashlib.sha256(p.read_bytes()).hexdigest()
        if phrase.get('sha256',phrase.get('output_sha256'))!=digest:
            raise ValueError('Phrase lacks a matching review checksum: '+str(p))
        entries.append({'id':digest[:24],'sha256':digest,'file':'audio/t2vl/'+digest[:24]+'.wav',
                        'duration':len(audio)/rate,'source':str(p),'text':phrase['text'],'speaker_id':phrase['speaker_id']})
    digest=hashlib.sha256(json.dumps(entries,sort_keys=True).encode()).hexdigest()
    client='// PRIVATE / research and noncommercial. Install on EVERY participating client.\n'
    client+='$T2VL::Manifest = "'+digest+'";\n'
    server='// Load on the server. This script transfers IDs, NOT audio bytes.\n'
    server+='$T2VL::Manifest = "'+digest+'";\n'
    for e in entries:
        client+='$T2VL::Path["'+e['id']+'"] = "'+e['file']+'";\n'
        server+='$T2VL::Allowed["'+e['id']+'"] = true;\n'
    client+='''
function clientCmdT2VLPlay(%id)
{
   %path = $T2VL::Path[%id];
   if (%path $= "" || !isFile(%path))
   {
      error("T2 Voice Lab: missing preinstalled phrase " @ %id);
      return;
   }
   if ($T2VL::Handle !$= "")
      alxStop($T2VL::Handle);
   $T2VL::Handle = alxCreateSource(AudioGui, %path);
   alxPlay($T2VL::Handle);
}
// After connecting, call T2VLReady(); a successful handshake proves only that
// this script loaded, NOT that an audio device played the WAV successfully.
function T2VLReady()
{
   commandToServer('T2VLReady', $T2VL::Manifest);
}
'''
    server+='''
function serverCmdT2VLReady(%client, %manifest)
{
   %client.t2vlReady = (%manifest $= $T2VL::Manifest);
}
function serverCmdT2VLAnnounce(%client, %id)
{
   if ((!%client.isAdmin && !%client.isSuperAdmin) || !$T2VL::Allowed[%id])
      return;
   if (%client.t2vlLast !$= "" && getSimTime() - %client.t2vlLast < 1000)
      return;
   %client.t2vlLast = getSimTime();
   for (%i = 0; %i < ClientGroup.getCount(); %i++)
   {
      %target = ClientGroup.getObject(%i);
      if (%target.t2vlReady)
         commandToClient(%target, 'T2VLPlay', %id);
      else
         messageClient(%target, '', "A custom voice announcement requires the matching client voice pack.");
   }
}
'''
    with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr('scripts/t2vl_client.cs',client)
        for e in entries:z.write(e['source'],e['file'])
        z.writestr('t2vl-manifest.json',json.dumps({'digest':digest,'phrases':entries,
            'live_client_test':'NOT RUN','license':'Private development; research/noncommercial.'},indent=2))
    output.with_suffix('.server.cs').write_text(server)
    output.with_suffix('.manifest.json').write_text(json.dumps({'digest':digest,'phrases':entries,'bytes':output.stat().st_size},indent=2))
    return entries

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--phrases',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();print(json.dumps(package(json.loads(a.phrases.read_text()),a.out),indent=2))
