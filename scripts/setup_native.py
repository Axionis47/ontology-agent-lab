"""Explicit native dependency setup, with no model calls or task attempts."""
import os,subprocess,sys
from pathlib import Path
REPO=Path(__file__).resolve().parents[1]
UPSTREAM=REPO/'.vendor/appworld'
REVISION='42b5bcf3cd334fee33f0c37c02070a9f5807add5'
def run(args,cwd=None):subprocess.run(args,cwd=cwd,check=True)
def main():
    if UPSTREAM.exists():raise SystemExit('Native checkout already exists. Inspect it instead of resetting or overwriting it.')
    UPSTREAM.parent.mkdir(parents=True,exist_ok=True)
    run(['git','clone','--no-checkout','https://github.com/stonybrooknlp/appworld.git',str(UPSTREAM)])
    run(['git','lfs','install','--local'],UPSTREAM)
    run(['git','checkout','--detach',REVISION],UPSTREAM)
    run(['git','lfs','pull'],UPSTREAM)
    run(['git','apply',str(REPO/'third-party/appworld-injected-model.patch')],UPSTREAM)
    run([sys.executable,'-m','pip','install','-c',str(REPO/'constraints-native.txt'),'-e',str(UPSTREAM),'-e',str(UPSTREAM/'experiments')])
    run([sys.executable,'-m','appworld.cli','install','--repo'],UPSTREAM)
    print('Native source prepared. Download official task data separately. No task or model was run.')
if __name__=='__main__':main()
