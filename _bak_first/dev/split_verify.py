# -*- coding: utf-8 -*-
"""verify_multipage.py 부분 실행 파일 생성기

    python3 split_verify.py 20 22   → dev/part_20_21.py (20~21 구간만)
"""
import io, os, re, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
SRC = os.path.join(ROOT, 'verify_multipage.py')

a, b = int(sys.argv[1]), int(sys.argv[2])
lines = io.open(SRC, encoding='utf-8').read().split('\n')

heads = []
for i, l in enumerate(lines):
    m = re.match(r"\s*head\('(\d+)[.\s]", l)
    if m:
        heads.append((int(m.group(1)), i))

main_i = next(i for i, l in enumerate(lines) if l.startswith('def main(argv):'))
first_head_i = heads[0][1]
start = next(i for n, i in heads if n == a)
end = next((i for n, i in heads if n == b), None)
if end is None:
    end = next(i for i, l in enumerate(lines) if l.strip().startswith('except _StopRun:'))
tail_i = next(i for i, l in enumerate(lines) if l.strip().startswith('except _StopRun:'))

head_lines = lines[:first_head_i]
# 헤더 끝의 주석/공백 줄을 지운다 — 다음 블록 들여쓰기와 어긋나지 않게
while head_lines and (not head_lines[-1].strip() or head_lines[-1].strip().startswith('#')):
    head_lines.pop()
body_lines = lines[start:end]
# 구간이 더 깊게 들여쓰여 있으면(중첩 블록) 8칸 기준으로 되돌린다
_first = next((l for l in body_lines if l.strip()), '')
ind = len(_first) - len(_first.lstrip())
if ind > 8:
    _cut = ind - 12
    if _cut >= 0:
        body_lines = [((l[_cut:] if len(l) >= _cut else l.lstrip()) if l.strip() else l) for l in body_lines]
        body_lines = ['        if not skip_file:'] + body_lines
out = head_lines + body_lines + lines[tail_i:]
dst = os.path.join(ROOT, 'part_%d_%d.py' % (a, b - 1))
txt = '\n'.join(out)
import os as _os
sl = _os.environ.get('PART_SLICE')
if sl:
    txt = txt.replace('def main(argv):', 'PAGES = PAGES[%s]\n\n\ndef main(argv):' % sl, 1)
io.open(dst, 'w', encoding='utf-8').write(txt)
print(dst)
