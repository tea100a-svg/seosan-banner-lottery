import functools, http.server, os, socketserver, threading
from playwright.sync_api import sync_playwright
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
h = functools.partial(Q, directory=ROOT)
s = socketserver.ThreadingTCPServer(('127.0.0.1', 0), h); s.daemon_threads = True
threading.Thread(target=s.serve_forever, daemon=True).start()
base = 'http://127.0.0.1:%d/' % s.server_address[1]
exe = '/workspace/.preview-run/chrome-headless-shell'
with sync_playwright() as p:
    e = dict(os.environ); e['LD_LIBRARY_PATH'] = ':'.join(os.path.join(os.path.dirname(exe), d) for d in ('syslibs','libs','shim'))
    b = p.chromium.launch(executable_path=exe, env=e, args=['--no-sandbox','--disable-dev-shm-usage'])
    pg = b.new_context(viewport={'width':1280,'height':1000}).new_page()
    pg.goto(base+'apply.html', wait_until='load'); pg.wait_for_timeout(800)
    pg.evaluate("() => window.SEOSAN_VERIFY.guestAccept()")
    pg.evaluate("""() => window.SEOSAN_VERIFY.setApply({ company: '서산튼튼병원', owner: '김의사', phone: '010-2222-3333', advertiser: '서산튼튼병원', advertiserBiz: '330-11-22334', text: '정형외과 도수치료 안내', qty: 1, agree: true })""")
    pg.wait_for_timeout(350)
    print('after hospital', pg.evaluate("() => { const e=document.querySelector('#medicalAdNote'); return e? !e.classList.contains('hidden') : null }"))
    pg.evaluate("""() => window.SEOSAN_VERIFY.setApply({ advertiser: '햇살농원', text: '가을 사과 직판 안내' })""")
    pg.wait_for_timeout(350)
    print('after normal', pg.evaluate("() => { const e=document.querySelector('#medicalAdNote'); return e? {hidden:e.classList.contains('hidden'), txt:e.textContent.slice(0,80)} : null }"))
    b.close()
s.shutdown()
