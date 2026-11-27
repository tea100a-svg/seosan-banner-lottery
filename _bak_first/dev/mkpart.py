# -*- coding: utf-8 -*-
"""verify_multipage.py 분할 실행기 — 지정한 섹션 구간만 실행하는 임시 파일을 만든다.

    python3 mkpart.py "head('4." "head('10."   → verify_part.py (섹션 4~9)
"""
import io, os, sys

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'verify_multipage.py')
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'verify_part.py')

start_sub, end_sub = sys.argv[1], sys.argv[2]
lines = io.open(SRC, encoding='utf-8').read().split('\n')

def find(sub):
    for i, l in enumerate(lines):
        if sub in l:
            return i
    raise SystemExit('not found: ' + sub)

s = find(start_sub)
e = find(end_sub)
# 섹션 구분 주석(# ---) 이 앞에 있으면 함께 제외한다
if e >= 2 and lines[e - 1].strip().startswith('# ---') and lines[e - 2].strip().startswith('# ---'):
    e = e - 2
out = lines[:s] + lines[e:]
io.open(OUT, 'w', encoding='utf-8').write('\n'.join(out))
print('part: %s .. %s (lines %d-%d)' % (start_sub, end_sub, s + 1, e))
