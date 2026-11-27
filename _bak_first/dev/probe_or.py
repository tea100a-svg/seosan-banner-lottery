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
    pg = b.new_context(viewport={'width':1400,'height':1000}).new_page()
    pg.goto(base+'admin-official-review.html', wait_until='load'); pg.wait_for_timeout(900)
    print(pg.evaluate("() => ({ role: window.SEOSAN_VERIFY.accessRole().role, on: Array.from(document.querySelectorAll('#adminSub a.on')).map(a=>a.getAttribute('data-adminsub')), vis: window.SEOSAN_VERIFY.visibleTabs() })"))
    print(pg.evaluate("() => ({ lock: !!document.querySelector('#permLockBox'), info: (document.querySelector('#offReviewInfo')||{}).textContent })"))
    b.close()
s.shutdown()
