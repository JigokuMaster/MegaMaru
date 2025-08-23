import sys, os, warnings, struct
import traceback
import logging as log

APP_DIR = '/System/Apps/MegaMaru' # can be C or E Drive
# setup libs path 
sys.path.insert(0, APP_DIR)
sys.path.insert(0, os.path.join(APP_DIR , 'lib.zip'))
# disable sre DeprecationWarning in simplejson
warnings.filterwarnings('ignore', category=DeprecationWarning)

LOG_FP = 'C:\\System\\MegaMaruServer.log'
STDERR_FP = 'C:\\System\\MegaMaruServer.errors'

def setup_stderr():
    f = open(STDERR_FP, 'w')
    sys.stdout = f
    sys.stderr = f

def setup_log():
    log.basicConfig(filename=LOG_FP, filemode='w', level=log.DEBUG)

setup_stderr()
setup_log()

from globalui import global_note
from threading import Event
from BaseHTTPServer import HTTPServer, BaseHTTPRequestHandler
from mm import MegaMaruEngine, SERVER_PORT, SERVER_ADDR
from simpleutils import parseExceptionMsg
import simplejson as json
import socket

class RequestHandler(BaseHTTPRequestHandler):
    def __init__(self, request, client_address, server):
        self.mme = server.mme
        self.mme.setEventHandler(self)  
        BaseHTTPRequestHandler.__init__(self, request, client_address, server)

    def handleEvent(self, **event):
        self.sendEvent(**event)
        
    def handleError(self, msg):
        self.sendError(msg)

    def handleAbort(self):
        return self.clientDisconnected()
        
    def sendEvent(self, **event):
        self._sendEvent(event)

    def sendError(self, msg):
        event = {'error': msg}
        self._sendEvent(event)

    def _sendEvent(self, event):
        try:
            data = json.dumps(event)
            event_len = struct.pack('<I', len(data))
            self.wfile.write(event_len)
            self.wfile.write(data)
        except:
            log.debug('Client disconnected')
        self.close()

    def sendOKMsg(self):
        try:
            self.send_response(200)
            self.send_header('Request-accepted', 1)
            self.end_headers()
        except:
            return False
        return True

    def clientDisconnected(self):
        try:
            ping = '\x00'*4
            self.wfile.write(ping)
        except:
            global_note(u'Client disconnected')
            return True
        return False

    def handleRequest(self, req, data=None):
        if not self.sendOKMsg():
            return
        req = 'do_' + req.lstrip('/').upper()
        params = {}
        if data != None:
            try:
                params = json.loads(data)
            except Exception, e:
                traceback.print_exc()
                self.sendError(parseExceptionMsg(e))
                return

        if hasattr(self, req):
            func = getattr(self, req)
            func(params)
        else:
            self.sendError('Request not supported')

    def readData(self):
        h = self.headers or {}
        l = int(h.get('Content-Length', 0))
        if l < 1:
            return None
        try:
            return self.rfile.read(l)
        except:
            pass

    def do_POST(self):
        req = self.path
        data = self.readData()
        log.debug('do_POST: %s', req)
        self.handleRequest(req, data)

    def do_GET(self):
        req = self.path 
        log.debug('do_GET: %s', req)
        self.handleRequest(req)

    def do_FETCH(self, params):
        log.debug('do_FETCH params=%s', params)   
        try:   
            link = params['link']
            node = params['node']
            nocache = params['nocache']
            if nocache and node:
                node_id = node['root_id']
                self.mme.removeCache(node_id)
        except Exception, e:
            traceback.print_exc()
            self.sendError(parseExceptionMsg(e))  
        else:
            self.mme.fetch(link, node)


    def do_EXIT(self, params):
        log.debug('do_EXIT')
        try:   
            self.mme.cancelOp()
        except:
            pass 
        self.sendEvent() # empty relpy           
        self.server.shutdown_event.set()
        #Thread(target=self.server.shutdown).start()
    
    def do_GETSTATUS(self, params):
        log.debug('do_GETSTATUS params=%s', params)
        hostname, port = self.server.server_address
        self.sendEvent(port=port, addr=hostname)

    def do_CLEANCACHE(self, params):
        try:   
            cache_size = self.mme.removeCache()
            self.sendEvent(size=cache_size)
        except Exception, e:
            traceback.print_exc()
            self.sendError(parseExceptionMsg(e)) 

    def do_CANCELOP(self, params):
        try:   
            self.mme.cancelOp()
        except:pass

    def close(self):
        self.request.close()
        BaseHTTPRequestHandler.finish(self)

    def finish(self):
        pass

    # disable default logging
    def log_message(self, format, *args):
        pass

class MegaMaruServer(HTTPServer):
    allow_reuse_address = False
    def __init__(self, addr):
        HTTPServer.__init__(self, addr, RequestHandler)
        self.savePort(addr[1])

    def close_request(self, request):
        pass

    def savePort(self, port):
        fp = os.path.join(APP_DIR, 'tmp/server_port')
        f = open(fp, 'w')
        f.write(str(port))
        f.close()
    
    def run(self):
        global_note(u'MegaMaruServer Started')
        self.mme = MegaMaruEngine(None)
        self.shutdown_event = Event()
        sa = self.socket.getsockname()
        address = '%s:%d' %(sa[0], sa[1])    
        log.debug("Server is up %s", address)
        while 1:
            if self.shutdown_event.isSet():
                break
            else:
                self.handle_request()

        log.debug('Server is down')


def main():
    argv = sys.argv
    log.debug('sys.argv: %s', argv)
    cwd = os.path.dirname(argv[0])
    log.debug('CWD: %s', cwd)
    os.chdir(cwd)
    if len(argv) > 1:
        if argv[1].isdigit():
            port = int(argv[1])
    else:
        port = SERVER_PORT

    port_checker = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    port_checker.settimeout(5)
    while True:
        try:
            port_checker.connect((SERVER_ADDR, port))
        except:
            break
        port += 1
    port_checker.close()
    try:
        MegaMaruServer((SERVER_ADDR, port)).run()
    except:
        traceback.print_exc()
    sys.exit(0)
        
if __name__ == '__main__':
    main()

