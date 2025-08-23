import e32, os, threading, time, traceback, struct
from simpleutils import PyDownloader, OpState, clean_filename, parseExceptionMsg, kwArgs, read_file
import simplejson as json
import logging
from mega import MegaService
from megacrypto import a32_decode , make_chunk_decryptor, base64_url_decode
import httplib


logger = logging
def setup_log(fp, disable=True):
    logger.basicConfig(filename=fp, filemode='w', level=logging.NOTSET)
    if disable:
        logger.disable(100) # disable all levels

def get_appdir():
    return os.getcwd() or '/System/Apps/MegaMaru'

def get_cachedir():
    d = os.path.join(get_appdir(), 'tmp')
    return d
    
SERVER_ADDR = '127.0.0.11'
SERVER_PORT = 7389
SERVER_URL = 'http://%s:%d' %(SERVER_ADDR, SERVER_PORT)
CMD_GETSTATUS = 'GETSTATUS'
CMD_FETCH = 'FETCH'
CMD_CANCELOP = 'CANCELOP'
CMD_EXIT = 'EXIT'
CMD_CLEANCACHE = 'CLEANCACHE'


class MegaMaruEngine:
    def __init__(self, event_handler):
        self.event_handler = event_handler      
        self.ms = MegaService(cache_dir=get_cachedir())
        if self.event_handler:
            self.ms.abort_hook = self.event_handler.handleAbort
        self.op_state = OpState()

    def setEventHandler(self, h):
        self.event_handler = h
    
    def cancelOp(self):
        self.op_state.set(OpState.OP_ABORTED)
        self.ms.cancelOp()
        
    def removeCache(self, node_id=None):
        return self.ms.removeCachedData(node_id)

    def sendEvent(self, **event):
        if not self.op_state.check(OpState.OP_ABORTED):
            self.event_handler.handleEvent(**event)       

    def waitForFinish(self):
        while 1:
            s = self.op_state.get()
            if s in [-1, OpState.OP_FINISHED]:
                break
            time.sleep(1)

    def fetch(self, link, node):       
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

        self.op_state.set(OpState.OP_FINISHED)
 
class MegaMaruClient:
    def __init__(self, server_addr, event_handler):
        self.event_handler = event_handler
        self.thread = None
        self.server_addr = server_addr or SERVER_URL
        self.op_state = OpState()
        self.ms = MegaService(cache_dir=get_cachedir())
        self.dlr = None
        self.conn = None
        self._conn_fd = -1
        self._conn_lock = threading.Lock()

    def setEventHandler(self, h):
        self.event_handler = h
    
    def cancelOp(self, send_event=True):
        self.cancelRequest()        
        self.op_state.set(OpState.OP_ABORTED)       
        self.ms.cancelOp()  
        if self.dlr:
            self.dlr.abort()
        #if send_event:
            # self.event_handler.onEvent(op=OpState.OP_ABORTED)

    def _doSendRequest(self, req, data=None, timeout=0):
        proto =  'http://'
        if self.server_addr.startswith(proto):
            self.server_addr = self.server_addr[7:]
        logger.debug('sendRequest %s/%s', self.server_addr, req)
        headers = {}
        jsdata = None
        if data != None:
            jsdata = json.dumps(data)
            headers['Content-Length'] = len(jsdata) 

        self.conn = httplib.HTTPConnection(self.server_addr)
        self.conn.request('POST', '/'+req, body=jsdata, headers=headers)
        if timeout > 0:
            self.conn.sock.settimeout(timeout)
        self._conn_fd = self.conn.sock.fileno() 
        resp = self.conn.getresponse()
        while 1:
            if self.op_state.check(OpState.OP_ABORTED):
                raise EOFError('Connection closed')
            b = resp.read(4)
            if len(b) < 4:
                raise EOFError('Connection closed')
            msg_len = struct.unpack('<I', b)[0] # 4 bytes
            if msg_len > 0:
                return resp.read(msg_len)

    def sendRequest(self, req, data=None, timeout=0):
        self._conn_lock.acquire()
        try:
            return self._doSendRequest(req, data, timeout)
        finally:
            self._conn_lock.release()
            

    def cancelRequest(self):
        try:
            if self._conn_fd > -1:
                os.close(self._conn_fd)               
        except:pass
       
    def checkServerStatus(self, log_error=False):
        try:
            data = self.sendRequest(CMD_GETSTATUS, timeout=10)
            info = json.loads(data)
            return int(info.get('port'))
        except:
            if log_error:
                logger.error(traceback.format_exc())
            return 0

    def startServer(self, use_thread=True):
        def run():
            port = self.checkServerStatus()
            if port == 0:
                fp = os.path.join(get_appdir(), 'server.py')
                logger.debug('starting server: %s', fp)
                try:
                    e32.start_exe('pyserver25.exe', fp)
                    fp = os.path.join(get_cachedir(), 'server_port')
                    port = read_file(fp, int, tries=10)
                    os.remove(fp)
                except:
                    tb = traceback.format_exc()
                    logger.error(tb)

            if port:
                self.server_addr = '%s:%d' %(SERVER_ADDR, port)
                self.sendEvent(server_addr=self.server_addr)
            else:
                self.sendError(fatal_error='Engine not responding')
            
        if use_thread:
            thread = threading.Thread(target=run)    
            thread.start()
        else:
            run()

    def stopServer(self, use_thread=True):
        def run():
            ret = False
            self.op_state.set(OpState.OP_RUNNING)           
            try:
                self.sendRequest(CMD_EXIT, timeout=25)
                ret = True
            except:
                self.sendError(fatal_error='Engine not responding')
                # TO-DO: Kill the Process ?
            else:
                self.sendEvent(cmd=CMD_EXIT, exit=ret)
            self.op_state.set(OpState.OP_FINISHED)
            return ret

        if use_thread:
            thread = threading.Thread(target=run)    
            thread.start()
        else:
            return run()

    def restartServer(self):
        def run():
            self.op_state.set(OpState.OP_RUNNING)
            try:
                self.sendRequest(CMD_EXIT, timeout=25)
            except:
                self.sendError(fatal_error='Engine not responding')           
            else:
                self.startServer(use_thread=False)

            self.op_state.set(OpState.OP_FINISHED)

        if self.thread and self.thread.isAlive():
            self.sendError(error='thread busy')
            return
 
        self.thread = threading.Thread(target=run)    
        self.thread.start()



    def cleanServerCache(self):
        def run():
            self.op_state.set(OpState.OP_RUNNING)           
            try:
                cmd = CMD_CLEANCACHE
                res = self.sendRequest(cmd)
                info = json.loads(res)
                error = info.get('error')
                size = info.get('size', 0)
                if error:
                    self.sendError(cmd=cmd, error=error)
                else:
                    self.sendEvent(cmd=cmd, cache_size=size)
            except Exception, e:
                self.sendError(cmd=cmd, error=parseExceptionMsg(e))

            self.op_state.set(OpState.OP_FINISHED)

        thread = threading.Thread(target=run)    
        thread.start()
   
    def sendError(self, **params):
        if not self.op_state.check(OpState.OP_ABORTED):
            self.event_handler.handleError(**params)
            
    def sendEvent(self, **params):
        if not self.op_state.check(OpState.OP_ABORTED):
            self.event_handler.handleEvent(**params)

 
    def decryptFile(self, path, fn, node):      
        fi_fp = os.path.join(path, fn) # path of the encrypted file
        if not os.path.exists(fi_fp):
            return False

        file_name = node['name']        
        fo_fp = os.path.join(path, clean_filename(file_name)) # path of the decrypted/output file
        fi = open(fi_fp, 'rb')
        fo = open(fo_fp, 'wb')
        file_size = node['size']
        file_key = a32_decode(node['key'])
        iv = a32_decode(node['iv'])
        meta_mac = a32_decode(node['meta_mac'])
        chunk_decryptor = make_chunk_decryptor(file_key, iv, meta_mac)
        chunk_size = 0x20000
        bytes_read = 0
        self.sendEvent(dec_prog=(bytes_read, file_size)) # progress start
        while True:
            chunk = fi.read(chunk_size)
            if self.op_state.check(OpState.OP_ABORTED) or (not chunk):
                break
            bytes_read += len(chunk)
            self.sendEvent(dec_prog=bytes_read)    
            chunk = chunk_decryptor.decrypt(chunk)
            fo.write(chunk)
            
        self.sendEvent(dec_prog=0, fp=fo_fp) # progress finish
        fi.close()
        fo.close()
        # remove the encrypted file
        os.remove(fi_fp)
        return True

    def downloadFile(self, path, node):
        def dl_required(path, fn, size):
            fp = os.path.join(path, fn)
            if os.path.isfile(fp) and os.path.exists(fp):
                return os.path.getsize(fp) != size                
            return True
            
        def dlr_cb(state, params):
            self.sendEvent(dl_state=state, params=params)
            
        def run(path, node):
            self.op_state.set(OpState.OP_RUNNING)
            try:
                if not os.path.exists(path):
                    os.makedirs(path)
                
                file_size = node['size']
                file_id = node['id']
                file_key = a32_decode(node['key'])
                tmp_fn = str(file_id) + '.tmp'
                if dl_required(path, tmp_fn, file_size):
                    link = node.get('dllink')
                    if link is None:
                        parent_id = node['parent_id']
                        root_id = node['root_id']
                        info = self.ms.getNodeFileInfo(file_id, file_key, parent_id, root_id)
                        link = info['dllink']

                    # if isinstance(link, list): # MEGA API V2 dl link
                    #   link = info['dllink'][0]

                    self.dlr = PyDownloader(path, bufsize=1024**2, state_listener=dlr_cb)
                    done = self.dlr.download_file(link , tmp_fn, 0, file_size, overwrite=True) 
                    self.sendEvent(dl_done=done)
                    if done:
                        self.decryptFile(path, tmp_fn, node)

                else:                   
                    self.sendEvent(dl_done=1)
                    self.decryptFile(path, tmp_fn, node)


            except Exception, e:
                tb = traceback.format_exc()
                # if self.op_state.check(OpState.OP_ABORTED):
                #    globalui.global_note(u'Download Canceled')
                self.sendError(error=parseExceptionMsg(e), tb=tb, path=path, node=node)
                
            self.op_state.set(OpState.OP_FINISHED)    

        if self.thread and self.thread.isAlive():
            self.cancelOp(False)          
            self.op_state.reset()
            self.sendError(error='thread busy')
            return
                        
        else:
            self.thread = threading.Thread(target=run, args=(path, node) )    
            self.thread.start()

    def fetch(self, link=None, node=None, nocache=0, extra_args={}):
        def run():
            """"
            wait = 1
            while wait:
                s = self.op_state.get()
                if s in [-1, OpState.OP_FINISHED, OpState.OP_ABORTED]:
                    globalui.global_note(u'previous FETCH Canceled')    
                    break
            """

            params = {'link': link, 'node': node, 'nocache': nocache}
            event = kwArgs(cmd=CMD_FETCH, link=link, node=node, extra_args=extra_args)
            self.op_state.set(OpState.OP_RUNNING)
            try:
                data = self.sendRequest(CMD_FETCH, params)  
            except Exception, e:
                tb = traceback.format_exc()
                logger.error(tb)
                # should be sent only if the request was not canceled
                event['error'] = 'Request Failed'
                self.sendError(**event)
                
            else:
                try:
                    info = json.loads(data)
                    nodes = info.get('nodes')              
                    fileinfo = info.get('fileinfo')
                    error = info.get('error')
                    if error:
                        event['error'] = error
                        self.sendError(**event)
                    elif nodes:
                        event['nodes'] = nodes
                        self.sendEvent(**event)
                    elif fileinfo:
                        event['fileinfo'] = fileinfo
                        self.sendEvent(**event)
                    else:
                        event['error'] = 'Invalid Data'
                        self.sendError(**event)
                except Exception, e: #  json error ...
                    tb = traceback.format_exc()
                    logger.error(tb)
                    # event['tb'] = tb
                    event['error'] = parseExceptionMsg(e)
                    self.sendError(**event)
           
            self.op_state.set(OpState.OP_FINISHED)
            
        self.thread = threading.Thread(target=run)
        self.thread.start()


