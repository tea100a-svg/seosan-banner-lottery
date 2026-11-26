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
    errs=[]; pg.on('pageerror', lambda x: errs.append(str(x)))
    pg.goto(base+'first.html', wait_until='load'); pg.wait_for_timeout(800)
    pg.evaluate("() => window.SEOSAN_VERIFY.login('M-1001')")
    pg.evaluate("() => window.SEOSAN_VERIFY.renderAll()")
    pg.wait_for_timeout(300)
    print('mode', pg.evaluate("() => window.SEOSAN_VERIFY.fcMode ? window.SEOSAN_VERIFY.fcMode() : 'n/a'"))
    pg.evaluate("""() => window.SEOSAN_VERIFY.fcSet({ mode: 'live', advertiser: '테스트광고주', text: '검증 문구', file: true, agree: true, license: false, qty: 1, picks: 'auto' })""")
    pg.evaluate("() => window.SEOSAN_VERIFY.setFcLicSample()")
    pg.wait_for_timeout(200)
    print('lic', pg.evaluate("() => window.SEOSAN_VERIFY.fcLicState()"))
    print('v1', pg.evaluate("() => window.SEOSAN_VERIFY.fcValidate(1)"))
    pg.evaluate("() => window.SEOSAN_VERIFY.fcSetStep(4)")
    pg.wait_for_timeout(200)
    print('picks', pg.evaluate("() => window.SEOSAN_VERIFY.fcPicks()"), 'qty', pg.evaluate("() => document.querySelector('#fcQty') ? document.querySelector('#fcQty').value : ''"))
    print('v3', pg.evaluate("() => window.SEOSAN_VERIFY.fcValidate(3)"))
    r = pg.evaluate("() => window.SEOSAN_VERIFY.fcSubmit()")
    print('submit', r)
    print('apps', pg.evaluate("() => window.SEOSAN_VERIFY.apps().slice(-1).map(a => ({id:a.id, live:a.liveWeek, start:a.start}))"))
    print('errs', errs[:3])
    b.close()
s.shutdown()
