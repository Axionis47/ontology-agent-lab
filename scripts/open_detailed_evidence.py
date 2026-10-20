"""Explicit local decryption of sanitized evidence, never a model call."""
import argparse,sys
from pathlib import Path
REPO=Path(__file__).resolve().parents[1]
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=REPO/'private-evidence')
    args=parser.parse_args()
    from appworld.common.crypto import unpack_bundle
    from appworld.common.constants import PASSWORD,SALT
    if args.output.exists():raise SystemExit('Choose a new output folder; existing evidence is never overwritten.')
    args.output.mkdir(parents=True)
    unpack_bundle(str(REPO/'evidence/sanitized-traces.bundle'),str(args.output),password=PASSWORD,salt=SALT)
    print(args.output.resolve()/'detailed/evidence.html')
if __name__=='__main__':main()
