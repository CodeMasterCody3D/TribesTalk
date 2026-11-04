"""Serial preparation job, run by the existing VM-kit job control plane."""
from pathlib import Path
import subprocess
import sys
root=Path(__file__).resolve().parent
for command in ([sys.executable,'-u','setup_remote.py','asr'],
                [str(root/'environments/asr/bin/python'),'-u','asr_entry.py','--asr','--skip-prep'],
                [sys.executable,'-u','setup_remote.py','breeze']):
    subprocess.run(command,cwd=root,check=True)
print('========== PREPARATION SEQUENCE DONE ==========',flush=True)
