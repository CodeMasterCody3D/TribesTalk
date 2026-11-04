"""Fetch only small pinned game scripts, not the full game repository."""
import json
import urllib.request
from pathlib import Path
from urllib.parse import quote

root = Path(__file__).resolve().parent
manifest = json.loads((root/'prep/assets.json').read_text())
rev = manifest['revision']
url = f'https://api.github.com/repos/exogen/t2-mapper/git/trees/{rev}?recursive=1'
with urllib.request.urlopen(url, timeout=60) as r:
    tree = json.load(r)
assert not tree.get('truncated'), 'Incomplete GitHub tree'
(root/'source-tree.json').write_text(json.dumps(tree))
scripts = [x for x in tree['tree'] if x['path'].endswith('.cs')]
needles = ('audioprofile', 'audio.cs', 'message.cs', 'messaging.cs', 'chat.cs',
           'cannedchat', 'voice', 'training', 'briefing', 'player.cs', 'client.cs')
selected = [x for x in scripts if any(n in x['path'].lower() for n in needles)]
for x in selected:
    dest = root/'game_scripts'/x['path']
    dest.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen('https://raw.githubusercontent.com/exogen/t2-mapper/'+rev+'/'+quote(x['path'],safe='/'), timeout=30) as r:
        b = r.read()
    import hashlib
    assert hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest() == x['sha']
    dest.write_bytes(b)
print(json.dumps({'revision':rev,'scripts':len(selected),'paths':[x['path'] for x in selected]},indent=2))
