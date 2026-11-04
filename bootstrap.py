"""Preserve attachment and extract its literal embedded files without executing cells."""
import ast
import hashlib
import json
import shutil
from pathlib import Path

root = Path(__file__).resolve().parent
source = Path('/home/cody/Downloads/tribes2_voice_lab.ipynb')
data = source.read_bytes()
digest = hashlib.sha256(data).hexdigest()
vault = root / 'code_vault'
vault.mkdir(exist_ok=True)
backup = vault / f'tribes2_voice_lab.{digest[:16]}.ipynb'
if not backup.exists():
    shutil.copy2(source, backup)
assert hashlib.sha256(backup.read_bytes()).hexdigest() == digest
nb = json.loads(data)
found = []
for cell in nb['cells']:
    if cell['cell_type'] != 'code':
        continue
    code = cell['source']
    if isinstance(code, list):
        code = ''.join(code)
    for node in ast.parse(code).body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'EMBEDDED_FILES' for t in node.targets):
            for name, content in ast.literal_eval(node.value).items():
                p = Path(name)
                assert not p.is_absolute() and '..' not in p.parts
                dest = root / 'prep' / p
                dest.parent.mkdir(parents=True, exist_ok=True)
                if dest.exists() and dest.read_text() != content:
                    raise RuntimeError(f'Refusing to overwrite existing helper: {dest}')
                dest.write_text(content)
                found.append(name)
(root / 'source-receipt.json').write_text(json.dumps({
    'source': str(source), 'sha256': digest, 'backup': str(backup),
    'upstream_pull': 'HTTP 403', 'extracted': found,
}, indent=2))
print(json.dumps({'backup_sha256': digest, 'files': found}, indent=2))
