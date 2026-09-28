import argparse
from qpoison.persistence_analysis import analyze

if __name__ == '__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--input',default='results/persistence_smoke')
    p.add_argument('--bootstrap',type=int,default=1000)
    p.add_argument('--max-plots',type=int,default=12,help='Max condition figures; 0 skips all plotting')
    a=p.parse_args()
    if a.bootstrap<1 or a.max_plots<0:p.error('Invalid bootstrap or plot count')
    analyze(a.input,a.bootstrap,a.max_plots)
