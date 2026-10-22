"""Comparison specimen of the three treatments for the design sample characters."""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from common import *
from render import *

SAMPLE = 'H O A S B R M N n o a e g m s i j 0 1 8'
def main():
    rows = []
    for key, name in [('exact', '1 exact pixel'), ('rounded', '2 softened pixel'), ('smooth', '3 smooth')]:
        for px in (64, 32):
            im, _ = render_line(SAMPLE, key, px)
            rows.append(label(im, f'{name} @{px}px'))
    out = stack(rows)
    out.save(os.path.join(BUILD, 'comparisons', 'treatments_sample.png'))
    # difficult letters large
    rows = []
    for key, name in [('exact', '1'), ('rounded', '2'), ('smooth', '3')]:
        im, _ = render_line('KMNWX kvwxyz ×&?@$%', key, 96)
        rows.append(label(im, name, 30))
    stack(rows).save(os.path.join(BUILD, 'comparisons', 'treatments_difficult.png'))
    print(out.size)

if __name__ == '__main__':
    main()
