import argparse
from qpoison.persistence import run_suite

if __name__ == '__main__':
    p=argparse.ArgumentParser(description='Resumable one-update FAA persistence experiments')
    p.add_argument('--config', default='configs/persistence_smoke.json')
    p.add_argument('--out', default='results/persistence_smoke')
    p.add_argument('--resume', action='store_true')
    p.add_argument('--limit', type=int, help='Stop after this many new paired jobs')
    p.add_argument('--dry-run', action='store_true')
    a=p.parse_args()
    if a.limit is not None and a.limit<1: p.error('--limit must be positive')
    run_suite(a.config,a.out,a.resume,a.limit,a.dry_run)
