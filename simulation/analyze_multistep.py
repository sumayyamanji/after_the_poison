import argparse
from qpoison.multistep_analysis import analyze

if __name__ == '__main__':
    p=argparse.ArgumentParser(description='Create multi-state Markdown report, PNGs, CSVs and upload zip')
    p.add_argument('--input',required=True)
    p.add_argument('--out',required=True)
    p.add_argument('--zoom',type=int,default=200)
    a=p.parse_args();analyze(a.input,a.out,a.zoom)
