import sys, os, json
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse

SERVE_DIR = sys.argv[1]
DB_DIR    = sys.argv[2]
PORT      = int(sys.argv[3])

os.chdir(SERVE_DIR)

class Handler(SimpleHTTPRequestHandler):

    def log_message(self, *a): pass  # silent logs

    def send_cors(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS, DELETE')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_cors()
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)

        # List all sessions
        if parsed.path == '/db/sessions':
            sessions = []
            if os.path.isdir(DB_DIR):
                for f in sorted(os.listdir(DB_DIR), reverse=True):
                    if f.endswith('.json') and f != 'context.json':
                        fpath = os.path.join(DB_DIR, f)
                        try:
                            with open(fpath, encoding='utf-8') as fp:
                                data = json.load(fp)
                            sessions.append({
                                'id':           data.get('id'),
                                'title':        data.get('title', 'Chat'),
                                'created':      data.get('created', 0),
                                'messageCount': len(data.get('messages', []))
                            })
                        except Exception:
                            pass
            self._json(sessions)

        # Get single session (full messages)
        elif parsed.path.startswith('/db/session/'):
            sid   = parsed.path.split('/')[-1]
            fpath = os.path.join(DB_DIR, f'{sid}.json')
            if os.path.exists(fpath):
                try:
                    with open(fpath, encoding='utf-8') as fp:
                        self._json(json.load(fp))
                except Exception as e:
                    self._json({'error': str(e)}, 500)
            else:
                self._json({}, 404)

        # Get context/persona
        elif parsed.path == '/db/context':
            fpath = os.path.join(DB_DIR, 'context.json')
            if os.path.exists(fpath):
                try:
                    with open(fpath, encoding='utf-8') as fp:
                        self._json(json.load(fp))
                except Exception:
                    self._json({})
            else:
                self._json({})

        else:
            super().do_GET()

    def do_POST(self):
        # Safely read the full body byte by byte based on Content-Length
        try:
            length = int(self.headers.get('Content-Length', 0))
            body = b''
            while len(body) < length:
                chunk = self.rfile.read(length - len(body))
                if not chunk:
                    break
                body += chunk
            data = json.loads(body.decode('utf-8'))
        except Exception as e:
            self._json({'error': f'bad json: {str(e)}'}, 400)
            return

        parsed = urlparse(self.path)

        # Save session — atomic write to prevent corruption
        if parsed.path == '/db/session':
            sid = data.get('id')
            if not sid:
                self._json({'error': 'no id'}, 400)
                return
            fpath = os.path.join(DB_DIR, f'{sid}.json')
            tmp   = fpath + '.tmp'
            try:
                with open(tmp, 'w', encoding='utf-8') as fp:
                    json.dump(data, fp, indent=2, ensure_ascii=False)
                os.replace(tmp, fpath)  # atomic rename
                self._json({'ok': True})
            except Exception as e:
                self._json({'error': str(e)}, 500)

        # Save context/persona — atomic write
        elif parsed.path == '/db/context':
            fpath = os.path.join(DB_DIR, 'context.json')
            tmp   = fpath + '.tmp'
            try:
                with open(tmp, 'w', encoding='utf-8') as fp:
                    json.dump(data, fp, indent=2, ensure_ascii=False)
                os.replace(tmp, fpath)
                self._json({'ok': True})
            except Exception as e:
                self._json({'error': str(e)}, 500)

        else:
            self._json({'error': 'not found'}, 404)

    def do_DELETE(self):
        parsed = urlparse(self.path)
        if parsed.path.startswith('/db/session/'):
            sid   = parsed.path.split('/')[-1]
            fpath = os.path.join(DB_DIR, f'{sid}.json')
            if os.path.exists(fpath):
                os.remove(fpath)
                self._json({'ok': True})
            else:
                self._json({'error': 'not found'}, 404)
        else:
            self._json({'error': 'not found'}, 404)

    def _json(self, data, code=200):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', len(body))
        self.send_cors()
        self.end_headers()
        self.wfile.write(body)

print(f'  Server ready on port {PORT}!')
HTTPServer(('', PORT), Handler).serve_forever()
