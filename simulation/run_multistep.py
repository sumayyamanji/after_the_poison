"""Run the fixed-horizon, paired multi-state protocol."""
import argparse
from qpoison.multistep import run_suite

if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',default='configs/multistep_smoke.json')
    p.add_argument('--out',default='results/multistep_smoke')
    p.add_argument('--resume',action='store_true')
    p.add_argument('--limit',type=int)
    p.add_argument('--dry-run',action='store_true')
    a=p.parse_args()
    run_suite(a.config,a.out,a.resume,a.limit,a.dry_run)
