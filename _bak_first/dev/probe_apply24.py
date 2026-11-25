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
    pg.goto(base+'apply.html', wait_until='load'); pg.wait_for_timeout(900)
    print(pg.evaluate("""() => { const s1=document.querySelector('#step1'); const n=document.querySelector('#stepNotes1');
      return { notesN: n? n.querySelectorAll('.callout').length : -1,
        first: s1? (s1.querySelector('.callout:not(.hidden)')||{}).outerHTML?.slice(0,160) : null,
        noteHTML: n? n.innerHTML.slice(0,200) : null }; }"""))
    b.close()
s.shutdown()
