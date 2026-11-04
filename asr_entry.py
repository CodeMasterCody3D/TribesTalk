"""Expose pip CUDA libraries to CTranslate2 before process startup."""
import os
from pathlib import Path
import runpy
import sys

if not os.environ.get('T2_ASR_LIBS_READY'):
    dirs=[str(p) for path in sys.path for p in Path(path).glob('nvidia/*/lib') if Path(path).is_dir()]
    env=dict(os.environ,T2_ASR_LIBS_READY='1')
    env['LD_LIBRARY_PATH']=':'.join(dirs+[env.get('LD_LIBRARY_PATH','')])
    os.execve(sys.executable,[sys.executable,__file__,*sys.argv[1:]],env)
sys.argv=[str(Path(__file__).with_name('remote_prepare.py')),*sys.argv[1:]]
runpy.run_path(sys.argv[0],run_name='__main__')
