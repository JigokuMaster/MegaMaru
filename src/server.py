import sys, os, warnings
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
    # sys.stdout = f
    sys.stderr = f

def setup_log():
    log.basicConfig(filename=LOG_FP, filemode='w', level=log.DEBUG)

setup_stderr()
setup_log()

from globalui import global_note
from threading import Thread, Event, Lock
import socket, traceback, time
from BaseHTTPServer import HTTPServer, BaseHTTPRequestHandler
from mega import MegaService
from megacrypto import a32_decode , make_chunk_decryptor, base64_url_decode
from simpleutils import OpState, parseExceptionMsg
import simplejson as json

SERVER_ADDRESS = '127.0.0.11'
SERVER_PORT = 8887

class MegaMaruEngine:
    def __init__(self, event_handler):
        self.ms = MegaService()
        self.op_state = OpState()
        self.event_handler = event_handler

    def setEventHandler(self, h):
        self.event_handler = h
    
    def cancelOp(self):
        self.op_state.set(OpState.OP_ABORTED)
        self.ms.cancelOp()
        
    def removeCache(self, node_id):
        try:
            self.ms.removeCachedData(node_id)
        except:
            return False
        return True    

    def sendEvent(self, **event):
        # self.event_handler.onEvent(event)
        if not self.op_state.check(OpState.OP_ABORTED):
            self.event_handler.onEvent(event)       

    def waitForFinish(self):
        while 1:
            s = self.op_state.get()
            if s in [-1, OpState.OP_FINISHED]:
                break
            time.sleep(1)

    def fetch(self, link, node):
        try:
            if self.op_state.check(OpState.OP_RUNNING):
                self.cancelOp()
                self.waitForFinish()
        except:pass
        self.op_state.set(OpState.OP_RUNNING)        
        try:
            if link:
                url_info = self.ms.parseUrl(link)
                file_info = url_info.get('file')
                folder_info = url_info.get('folder')
                sub_info = url_info.get('sub')
                if folder_info:
                    root_id, root_key = folder_info
                    if sub_info:
                        sub_folder = sub_info.get('folder')
                        sub_file = sub_info.get('file')
                        if sub_file:
                            # file key is root key
                            info = self.ms.getNodeFileInfo(sub_file, root_key, root_id, root_key)
                            self.sendEvent(fileinfo=info)
                            return

                        elif sub_folder:
                            info = self.ms.getNodeFolderInfo(sub_folder, root_id, root_key)
                            self.sendEvent(nodes=info)

                    else:
                        info = self.ms.getFolderInfo(link)
                        self.sendEvent(nodes=info)
 
                elif file_info:
                    info = self.ms.getFileInfo(link)
                    self.sendEvent(fileinfo=info)
 
            else:
                n = node['name']
                id = node['id']
                parent_id = node['parent_id']
                root_id = node['root_id']
                # root_key = a32_decode(node['root_key'])
                root_key = node['root_key']
                if node['t'] == 0:
                    key = a32_decode(node['key'])
                    info = self.ms.getNodeFileInfo(id, key, parent_id, root_id)
                    self.sendEvent(fileinfo=info)

                elif node['t'] == 1:
                    info = self.ms.getNodeFolderInfo(id, root_id, root_key)
                    self.sendEvent(nodes=info)
                  

        except Exception, e:           
            tb = traceback.format_exc()
            self.sendEvent(error=parseExceptionMsg(e), tb=tb, link=link, node=node)

        if self.op_state.check(OpState.OP_ABORTED):
            log.debug('FETCH OP_ABORTED')
           
        self.op_state.set(OpState.OP_FINISHED)
              
        
class RequestHandler(BaseHTTPRequestHandler):
    def __init__(self, request, client_address, server):
        self.mme = server.mme
        self.mme.setEventHandler(self)  
        BaseHTTPRequestHandler.__init__(self, request, client_address, server)

    def do_POST(self):
        req = self.path
        data = self.readData()
        log.debug('do_POST: %s', req)
        self.handleRequest(req, data)

    def do_GET(self):
        req = self.path 
        log.debug('do_GET: %s', req)
        self.handleRequest(req)

    def readData(self):
        h = self.headers or {}
        l = int(h.get('Content-Length', 0))
        if l < 1:
            return None
        try:
            return self.rfile.read(l)
        except:
            pass

    def sendError(self, msg):
        event = {'error': msg}
        self.onEvent(event)

    def sendEvent(self, **event):
        self.onEvent(event)

    def handleRequest(self, req, data=None):
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
            Thread(target=self.mme.fetch, args=(link, node)).start()


    def do_EXIT(self, params):
        log.debug('do_EXIT')
        try:   
            self.mme.cancelOp()
        except:
            pass
                   
        self.send_response(200)
        self.server.shutdown_event.set()
        #Thread(target=self.server.shutdown).start()
    
    def do_GETSTATUS(self, params):
        log.debug('do_GETSTATUS params=%s', params)
        host, port = self.server.server_address
        self.sendEvent(port=port, addr=host)

    def do_CANCELOP(self, params):
        log.debug('do_CANCELOP params=%s', params)
        try:   
            self.mme.cancelOp()
        except:pass
        self.send_response(200)

    def onEvent(self, event):
        try:
            data = json.dumps(event)
            self.send_response(200)
            self.send_header('Content-Length', len(data))
            self.end_headers()
            self.wfile.write(data)
        except Exception, e:
            traceback.print_exc()
        self.close()


    def close(self):
        self.request.close()
        BaseHTTPRequestHandler.finish(self)

    def finish(self):
        pass

    # disable default logging
    def log_message(self, format, *args):
        pass

class MegaMaruServer(HTTPServer):
    def __init__(self, addr):
        HTTPServer.__init__(self, addr, RequestHandler)

    def close_request(self, request):
        pass


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
    MegaMaruServer((SERVER_ADDRESS, port)).run()
    sys.exit(0)

main()
