import hashlib,json,urllib.request
from pathlib import Path
from urllib.parse import quote
root=Path(__file__).resolve().parent
tree=json.loads((root/'source-tree.json').read_text())
rev=tree['sha']
names={'SinglePlayerGame.cs','spdialog.cs','clientDefaults.cs','clientTasks.cs','server.cs','OptionsDlg.cs','aiBotProfiles.cs'}
for x in tree['tree']:
    if Path(x['path']).name not in names and not (x['path'].endswith('.mis') and '/Training' in x['path']):
        continue
    p=root/'game_scripts'/x['path'];p.parent.mkdir(parents=True,exist_ok=True)
    with urllib.request.urlopen('https://raw.githubusercontent.com/exogen/t2-mapper/'+rev+'/'+quote(x['path'],safe='/'),timeout=30) as r:b=r.read()
    assert hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()==x['sha']
    p.write_bytes(b)
    print(x['path'])
