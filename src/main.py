import appuifw as ui
import globalui, uiext
import e32, httplib, threading, traceback, os, sys, time
import logging as log
from mega import MegaService
from megacrypto import a32_decode , make_chunk_decryptor, base64_url_decode
import simplejson as json
from simpleutils import PyDownloader, OpState, hsize, clean_filename, parseExceptionMsg

LOG_FP = 'C:\\System\\MegaMaruClient.log'
def setup_log():
    log.basicConfig(filename=LOG_FP, filemode='w', level=log.NOTSET)
    log.disable(100) # disable all levels

setup_log()

def U_STR(s):
    if s is None:
        return s
    # return lang.trans(s)
    return unicode(s)

SERVER_ADDR = '127.0.0.11'
SERVER_PORT = 8887
SERVER_URL = 'http://%s:%d' %(SERVER_ADDR, SERVER_PORT)
CMD_GETSTATUS = 'GETSTATUS'
CMD_FETCH = 'FETCH'
CMD_CANCELOP = 'CANCELOP'
CMD_EXIT = 'EXIT'

class MegaMaruClient:
    def __init__(self, server_url, event_handler):
        self.event_handler = event_handler
        self.thread = None
        self.server_addr = server_url
        self.op_state = OpState()
        self.ms = MegaService()
        self.dlr = None
        self.conn = None
        self._conn_lock = threading.Lock()

    def setEventHandler(self, h):
        self.event_handler = h
    

    def cancelOp(self, send_event=True):
        self.op_state.set(OpState.OP_ABORTED)
        self.ms.cancelOp()  
        self.cancelRequest()
        # self.cancelServerOp() 
        if self.dlr:
            self.dlr.abort()
        #if send_event:
            # self.event_handler.onEvent(op=OpState.OP_ABORTED)

    def _doSendRequest(self, req, data=None):
        proto =  'http://'
        if self.server_addr.startswith(proto):
            self.server_addr = self.server_addr[7:]
            
        log.debug('sendRequest %s/%s', self.server_addr, req)
        headers = {}
        jsdata = None
        if data != None:
            jsdata = json.dumps(data)
            headers['Content-Length'] = len(jsdata) 


        self.conn = httplib.HTTPConnection(self.server_addr)
        self.conn.request('POST', '/'+req, body=jsdata, headers=headers)
        resp = self.conn.getresponse()
        data = resp.read()
        self.conn.close()
        return data

    def sendRequest(self, req, data=None):
        self._conn_lock.acquire()
        try:
            return self._doSendRequest(req, data)
        finally:
            self._conn_lock.release()

    def cancelRequest(self):
        try:
            if self.conn:
                if self.conn.sock:
                    fd = self.conn.sock.fileno()
                    os.close(fd)
        except:pass
       
    def checkServerStatus(self):
        try:
            data = self.sendRequest(CMD_GETSTATUS)
            info = json.loads(data)
            return int(info.get('port'))
        except:
            return 0
   
    def startServer(self, use_thread=True):
        def run():
            fp = os.path.abspath('./server.py')
            port = self.checkServerStatus()
            tries = 5
            if port == 0:
                log.debug('starting server: %s', fp)
                try:
                    e32.start_exe('pyserver25.exe', fp)
                except:
                    tb = traceback.format_exc()
                    log.error(tb)
                else:
                    while tries:
                        port = self.checkServerStatus()
                        tries -= 1
                        if port:
                            break
                        time.sleep(3)

            if port:
                self.server_addr = '%s:%d' %(SERVER_ADDR, port)
                self.sendEvent(server_port=port)
            else:
                self.sendError(fatal_error='Engine not responding')
            
        if use_thread:
            thread = threading.Thread(target=run)    
            thread.start()
        else:
            run()

    def stopServer(self):
        def run():
            ret = False
            self.op_state.set(OpState.OP_RUNNING)           
            try:
                self.sendRequest(CMD_EXIT)
                ret = True
            except:pass
                # TO-DO: Kill the Process ?
            self.sendEvent(exit=ret)
            self.op_state.set(OpState.OP_FINISHED)

        thread = threading.Thread(target=run)    
        thread.start()

    def cancelServerOp(self):
        def run():          
            try:
                self.sendRequest(CMD_CANCELOP)
            except:pass

        thread = threading.Thread(target=run)    
        thread.start()

    def restartServer(self):
        def run():
            self.op_state.set(OpState.OP_RUNNING)           
            try:
                self.sendRequest(CMD_EXIT)
            except:
                # TO-DO: Kill the Process ?
                pass

            self.startServer(use_thread=False)
            self.op_state.set(OpState.OP_FINISHED)

        if self.thread and self.thread.isAlive():
            self.sendError(error='thread busy')
            return
 
        self.thread = threading.Thread(target=run)    
        self.thread.start()

   
    def sendError(self, **params):
        if not self.op_state.check(OpState.OP_ABORTED):
            self.event_handler.onError(**params)
            
    def sendEvent(self, **params):
        if not self.op_state.check(OpState.OP_ABORTED):
            self.event_handler.onEvent(**params)

 
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
            
        self.sendEvent(dec_prog=0) # progress finish
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
                tmp_fn = str(file_id) + '.tmp_file'
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
            self.cancelOp(False)
            params = {'link': link, 'node': node, 'nocache': nocache}
            self.op_state.set(OpState.OP_RUNNING)
            try:
                data = self.sendRequest(CMD_FETCH, params)  
            except Exception, e:
                tb = traceback.format_exc()
                # if self.op_state.check(OpState.OP_ABORTED):
                #    globalui.global_note(u'FETCH Canceled')
               
                # should be sent only if the request was not canceled
                self.sendError(error='Request Failed', link=link, tb=tb, exta_args=extra_args)
                
            else:
                try:
                    info = json.loads(data)
                    nodes = info.get('nodes')              
                    fileinfo = info.get('fileinfo')
                    error = info.get('error')
                    if error:
                        self.sendError(error=error, link=link, previous_node=node, extra_args=extra_args)
                    elif nodes: 
                        self.sendEvent(cmd=CMD_FETCH, nodes=nodes, link=link, previous_node=node, extra_args=extra_args)
                    elif fileinfo:
                        self.sendEvent(cmd=CMD_FETCH, fileinfo=fileinfo, link=link, previous_node=node, extra_args=extra_args)
                    else:
                        self.sendError(error='Invalid Data', link=link, previous_node=node, extra_args=extra_args)

                except Exception, e: #  json error ...
                    tb = traceback.format_exc()
                    log.error(tb)                   
                    self.sendError(error=parseExceptionMsg(e), tb=tb, link=link, previous_node=node, extra_args=extra_args)    
            self.op_state.set(OpState.OP_FINISHED)
        
        thread = threading.Thread(target=run)
        thread.start()

class AEventDispatcher:
    def __init__(self, on_event, on_error):
        self.on_event = on_event
        self.on_error = on_error
        self.cg = e32.ao_callgate(self.dispatch)
    
    def dispatch(self, func, event):
        if func:
            try:
                func(event)
            except Exception, e:
                tb = traceback.format_exc()
                log.error(tb)
                # self._showErr(tb)                

    def onEvent(self, **event):
        self.cg(self.on_event, event)
 
    def onError(self, **event):
        self.cg(self.on_error, event)


class Config:
    def __init__(self, fp):
        self.data = {}
        self.fp = fp
        self._load(fp)

    def _load(self, fp):
        if os.path.exists(fp):
            f = open(fp, 'r')
            try:
                self.data = json.load(f)
            except:pass
            f.close()

    def remove(self, k,  item):
        v = self.data.get(k)
        if v is None:
            return
            
        if not item in v:
            return
            
        if isinstance(v, list):
            v.remove(item) 

        if isinstance(v, dict):
            v.delete(item)
            
        self.commit()
        
    def set(self, k,  v):
        self.data[k] = v
        self.commit()

    def get(self, k):
        return self.data.get(k)

    def commit(self):
        f = open(self.fp, 'w')
        try:
            json.dump(self.data, f)
        except:pass
        f.close()
                

class BaseWindow:
    def __init__(self, parent=None):
        self.parent = parent
    
    def setTitle(self, t):
        ui.app.title = U_STR(t)

    def setMenu(self, items):
        if isinstance(items, tuple):
            ui.app.menu = [items]

        elif isinstance(items, list):
            ui.app.menu = items

    def updateMenu(self, item, idx):
        items = ui.app.menu
        if idx <= len(items):
            items[idx] = item
            ui.app.menu = items

    def setSoftKeyLabel(self, label, id):
        try:
            uiext.setSoftKeyLabel(U_STR(label), id)
        except:pass


    def setSoftKeysLabel(self, right, left, after=0):
        if after > 0:
            try:
                cb = lambda: self.setSoftKeysLabel(right, left)
                self._t = e32.Ao_timer()
                self._t.after(after, cb)
            except:pass    

        else:
            if right:
                self.setSoftKeyLabel(right, uiext.EAknSoftkeyExit)                
            if left:
                self.setSoftKeyLabel(left, uiext.EAknSoftkeyOptions)

    def setSoftKeys(self, res_id):
        uiext.setSoftKey(res_id)

    def show(self):
        pass
        
    def close(self):
        if self.parent:
            self.parent.show()


class DownloadsWindow(BaseWindow):
    def __init__(self, parent):
        BaseWindow.__init__(self, parent)
        self.lb = None
        self.lb_items = []
        self.node = None
        self.paths = []
    
    def setupPaths(self, fp):
        prefix = '\\Data\\MEGA'
        res  = []
        for i in e32.drive_list():
            drv = str(i.upper()) 
            if drv in ['Z:', 'D:']:
                continue       
            if os.path.exists(drv + '\\'):
                # path = os.path.join(drv + prefix, fp)
                path = drv + prefix
                res.append(unicode(path))
        self.paths = res
    
    def showFileName(self):
        fn = self.lb_items[0][1]
        globalui.global_msg_query(fn, U_STR('Full name:'))

    def handleLBClicks(self):
        i = self.lb.current()
        if i == 0:
            self.showFileName()
            
        elif i == 2:
            i = ui.popup_menu(self.paths, U_STR('Save to:'))
            if i != None:
                self.parent.downloadFile(self.paths[i], self.node)

        
    def show(self, node, parent=None):
        self.node = node
        fn = node['name']
        size = hsize(node['size'])
        """
        if parent:
            pn = clean_filename(parent['name']) # folder name
            fp = os.path.join(pn, fn) # folder_name + file_name
            self.setupPaths(fp)
        else:
            self.setupPaths('')
        """
        self.setupPaths('')
        self.lb_items = [
            (U_STR('File name'), unicode(fn)),
            (U_STR('File size'), unicode(size)),
            (U_STR('Download'), self.paths[0]),
        ]       
        self.setMenu([])
        self.lb = ui.Listbox(self.lb_items, self.handleLBClicks)
        #self.lb.bind(EKeyLeftSoftkey, self.startDownload)
        ui.app.body = self.lb
        ui.app.exit_key_handler = self.close


    
class BrowserWindow(BaseWindow):
    def __init__(self, parent):
        BaseWindow.__init__(self, parent)
        self.event_dispatcher = AEventDispatcher(self.handleEvents, self.handleError)
        self.mmc = self.parent.mmc
        self.downloads = DownloadsWindow(self)
        self.waitDialog = None
        self.progressDialog = None
        self.lb = None
        self.items = []
        self.focused_item = 0
        self.current_nodes = {}
        self.node_history = []
        self.config = parent.config
        
    def onCloseDialog(self, btn):
        if btn == -1: # canceled by user
            self.mmc.cancelOp()        
        # self.setSoftKeysLabel('Back', None, after=2)
    
    def showWaitDialog(self, msg=None):
        # self.waitDialog = uiext.WaitDialog(uiext.R_MODAL_WAITDIALOG, msg, self.onCloseWaitDialog)
        self.waitDialog = uiext.WaitDialog(uiext.R_WAITDIALOG_SOFTKEY_CANCEL, msg, self.onCloseDialog)
        self.waitDialog.show()

    def closeWaitDialog(self):
        if self.waitDialog:
            self.waitDialog.finish()
            # self.waitDialog = None
            
    def showProgressDialog(self, msg, max_val):
        self.progressDialog = uiext.ProgressDialog(uiext.R_PROGRESSDIALOG_SOFTKEY_CANCEL,msg, self.onCloseDialog)
        self.progressDialog.show(None, max_val)

    def closeProgressDialog(self):
        if self.progressDialog:
            self.progressDialog.finish()

    def showSearchDialog(self):
        i = ui.selection_list(self.items, search_field=1)
        if (i >= 0) and len(self.current_nodes):
            node = self.current_nodes[i][1]
            self.openNode(node)
 

    def updateProgressDialog(self, msg,  val):
        if self.progressDialog:
            inc_val = 0
            self.progressDialog.update(inc_val, msg, val)

    def handleDownloadEvents(self, event):
        state = event.get('dl_state')
        params = event.get('params', {})
        error = params.get('error')
        if state == PyDownloader.DOWNLOAD_STARTED:
            self.closeWaitDialog()
            self.showProgressDialog(u'Downloading ...', params['size'])


        elif state == PyDownloader.DOWNLOAD_ING:
            # read bytes, downloaded_bytes, total bytes
            r_bytes = params['rb']
            dl_bytes = params['db']
            total_bytes = params['tb']
            msg = U_STR('Downloading ... %s/%s' %(hsize(dl_bytes), hsize(total_bytes)))
            self.updateProgressDialog(msg, dl_bytes)

        elif state == PyDownloader.DOWNLOAD_ABORTED:
            msg = params.get('msg')
            globalui.global_msg_query(unicode(msg), U_STR('Download Aborted'))
            

        elif state == PyDownloader.DOWNLOAD_DONE:
            self.closeProgressDialog()
            # ui.note(u'Download Done')

        elif state in [PyDownloader.DOWNLOAD_FAILED, PyDownloader.REQUEST_FAILED]:
            self.closeProgressDialog()
            msg = unicode(params['error'])
            globalui.global_msg_query(msg, U_STR('Download Failed'))
            
        elif state == None:
            self.closeWaitDialog()
            self.closeProgressDialog()
        

    def handleDecryptEvents(self, event):
        prog = event.get('dec_prog')
        if type(prog) == tuple:
            self.showProgressDialog(U_STR('Decrypting ...'), prog[1])

        elif type(prog) == int:
            if prog > 0:
                self.updateProgressDialog(None, prog)
            else:
                self.closeProgressDialog()
                ui.note(U_STR('File saved'), 'conf')

    def downloadFile(self, path, node):
        self.mmc.setEventHandler(self.event_dispatcher)        
        self.showWaitDialog()
        self.mmc.downloadFile(path, node)
       
    def handleFetchEvents(self, event):
        nodes = event.get('nodes')
        fileinfo = event.get('fileinfo')
        previous_node = event.get('previous_node')
        extra_args = event.get('extra_args', {})
        if nodes != None:
            if previous_node != None:
                if not previous_node in self.node_history:
                    self.node_history.insert(0, previous_node)

            self.setTitle(previous_node['name'])         
            self.setupItems(nodes)
            if len(self.items) == 0:
                uiext.clearListBox(self.lb)
            else:
                focused_item = extra_args.get('focused_item', self.focused_item or 0)
                self.lb.set_list(self.items, focused_item)
            
        if fileinfo != None:
            self.downloads.show(fileinfo)
 
      
    def handleEvents(self, event):
        cmd = event.get('cmd')      
        if cmd == CMD_FETCH:
            self.closeWaitDialog()
            self.handleFetchEvents(event)
            return
        else:
            if ('dl_done' in event) or ('dl_state' in event):
                self.handleDownloadEvents(event)
                return

            elif 'dec_prog' in event:
                self.handleDecryptEvents(event)
                return
        self.parent.handleEvents(event)
 

    def handleError(self, event):
        self.closeWaitDialog()
        self.closeProgressDialog() 
        err_msg = event.get('error')
        tb = event.get('tb')
        node = event.get('previous_node')
        file_node = event.get('node') 
        if tb:
            log.error(tb)
        if node:      
            if ui.query(U_STR('%s , Retry?'%err_msg), 'query'):
                self.openLink(node)

        if file_node:      
            if ui.query(U_STR('%s , Retry?'%err_msg), 'query'):
                self.downloadFile(event['path'], file_node)
        else:
            globalui.global_msg_query(u'', U_STR(err_msg))
              

    def handleLBClicks(self):
        self.focused_item = self.lb.current()
        if len(self.current_nodes):
            node = self.current_nodes[self.focused_item][1]
            self.openNode(node)
        
            
    def openNode(self, node, focused_item=0):      
        node_type = node.get('t', 0)
        if node_type == 0: # show file info
            parent = None#self.node_history[0]
            self.downloads.show(node, parent)

        elif node_type == 1: # fetch folder nodes                    
            self.showWaitDialog()
            args = {'focused_item': focused_item}
            self.mmc.fetch(node=node, extra_args=args)



    def setupItems(self, nodes):
        parent = nodes.pop(0)
        self.current_nodes = []
        self.items = []
        # folders first ...
        for node in nodes:
            if node['t'] == 1:
                n = unicode(node['name'])
                self.items.append(n)
                self.current_nodes.append((n, node))
                
        self.items.sort()
        self.current_nodes.sort()
        files = []
        _nodes = []
        for node in nodes:
            if node['t'] == 0:
                n = unicode(node['name'])
                files.append(n)
                _nodes.append((n, node))

        files.sort()
        _nodes.sort()
        self.items += files
        self.current_nodes += _nodes

    def addBM(self):
        if len(self.node_history) == 0:
             return

        bm = self.parent.bookmarks
        node = self.node_history[0]        
        k = node['root_key']
        is_root = node['id'] == node['parent_id']
        if is_root:
            path = '/folder/%s#%s' %(node['root_id'], k)            
        else:
            path = '/folder/%s#%s/folder/%s' %(node['root_id'], k, node['id'])

        item = [node['name'], path]
        if bm.add(item, reload_ui=False):
            ui.note(U_STR('Bookmark Saved'), 'conf')        
    
    
    def reload(self):
        if len(self.node_history):
            node = self.node_history[0]
            self.clearItems()      
            # refetch nodes ...
            self.showWaitDialog()
            self.mmc.fetch(node=node, nocache=1)


    def clearItems(self):
        self.current_nodes = []
        self.node_history = []
        self.items = []
        if self.lb is None:
            self.lb = ui.Listbox([u''], self.handleLBClicks)
        
        else:
            self.lb.set_list([u''])
            
        uiext.clearListBox(self.lb)
        menu_items = [           
            (U_STR('Home'), self.parent.show),            
            (U_STR('Exit'), self.parent.exit) # should stop the engine           
        ]
        self.setMenu(menu_items)

    
    def show(self, nodes=None):
        self.focused_item = 0
        self.mmc.setEventHandler(self.event_dispatcher)
        new_items = (nodes != None)
        if new_items:
            self.current_nodes = []
            self.node_history = []
            if len(nodes):
                root = nodes[0]
                node = root.get('parent_node') or root
                node_name = node.get('name')
                self.setTitle(node_name)        
                if not node in self.node_history:
                    self.node_history.insert(0, node)

            self.setupItems(nodes)

        empty_items = len(self.items) == 0
        if empty_items:
            self.items = [u'']
        
        if self.lb is None:
            self.lb = ui.Listbox(self.items, self.handleLBClicks)
        
        else:
            # pos = self.lb.current()
            if new_items:
                self.lb.set_list(self.items, 0)                

        if empty_items:
            self.items = []
            uiext.clearListBox(self.lb)

        ui.app.body = self.lb
        if len(self.items):
            menu_items = [
                (U_STR('Reload'), self.reload),
                (U_STR('Search'), self.showSearchDialog),
                (U_STR('Add Bookmark'), self.addBM),
                (U_STR('Home'), self.parent.show), 
                (U_STR('Exit'), self.parent.exit) # should stop the engine            
            ]
        else:
             menu_items = [
                (U_STR('Home'), self.parent.show), 
                (U_STR('Exit'), self.parent.exit) # should stop the engine            
            ]
           
        self.setMenu(menu_items)
        ui.app.exit_key_handler = self.close

    def close(self):
        if len(self.node_history) > 1:          
            current = self.node_history.pop(0)
            previous = self.node_history.pop(0)
            self.openNode(previous, self.focused_item)

        else:
            BaseWindow.close(self)


class BookmarksWindow(BaseWindow):
    def __init__(self, parent):
        BaseWindow.__init__(self, parent)
        self.config = parent.config
        self.lb = None
        self.lb_items = []
        self.bm_items = []

    def loadItems(self):
        bm = self.config.get('bm')
        if bm != None:
            self.bm_items = bm
            for i in bm:
                label = unicode(i[0])
                if label in self.lb_items:
                    continue
                self.lb_items.append(label)

    def reload(self, reload_ui=True):             
        self.lb_items = []
        self.bm_items = []
        if reload_ui:
            self.setupItems()
        else:    
            self.loadItems()
    
    def setupItems(self):
        if self.lb_items == []:
            self.loadItems()
        
        empty_items = len(self.lb_items) == 0
        if empty_items:
           if self.lb is None:
                self.lb = ui.Listbox([u''], self.handleLBClicks)
           
           uiext.clearListBox(self.lb)     
           self.setMenu([])
           
        else:
            if self.lb:
                self.lb.set_list(self.lb_items, 0)                
            else:
                self.lb = ui.Listbox(self.lb_items, self.handleLBClicks)
            
            self.setMenu([(U_STR('remove'), self.remove), (U_STR('clean'), self.clean)])
        
    def add(self, item, reload_ui=True):
        bm = self.config.get('bm') or []
        if not item in bm:
            bm.insert(0, item)
            self.config.set('bm', bm)
            self.reload(reload_ui)
            return True

        else:
            return False

        
    def remove(self):
        i = self.lb.current()
        item = self.bm_items[i]
        self.config.remove('bm', item)
        self.reload()


    def clean(self):
        if ui.query(U_STR('Delete All items?'), 'query'):
            self.config.set('bm', [])
            self.lb_items = []
            self.bm_items = []
            uiext.clearListBox(self.lb)
            self.setMenu([])


    def count(self):
        self.loadItems()
        return len(self.lb_items)

    def handleLBClicks(self):
        i = self.lb.current()
        item = self.bm_items[i] # link
        self.parent.openLink(item[1])
        
    def show(self):
        self.setupItems()    
        ui.app.body = self.lb
        self.setTitle('Bookmarks')
        self.setSoftKeysLabel('Back', None)
        ui.app.exit_key_handler = self.close
            

class HistoryWindow(BaseWindow):
    def __init__(self, parent):
        BaseWindow.__init__(self, parent)
        self.config = parent.config
        self.lb = None
        self.lb_items = []
        self.hist_items = []


    def loadItems(self):
        hist = self.config.get('hist')
        if hist != None:
            self.hist_items = hist
            for i in hist:
                label = unicode(i[0])
                if label in self.lb_items:
                    continue
                self.lb_items.append(label)

    def reload(self):             
        self.lb_items = []
        self.hist_items = {}
        self.setupItems()

    def setupItems(self):
        if self.lb_items == []:
            self.loadItems()
        
        empty_items = len(self.lb_items) == 0
        if empty_items:
           if self.lb is None:
                self.lb = ui.Listbox([u''], self.handleLBClicks)
           
           uiext.clearListBox(self.lb)     
           self.setMenu([])
           
        else:
            if self.lb:
                self.lb.set_list(self.lb_items, 0)                
            else:
                self.lb = ui.Listbox(self.lb_items, self.handleLBClicks)
            
            self.setMenu([(U_STR('remove'), self.remove), (U_STR('clean'), self.clean)])

        
    def add(self, item):
        label, link = item
        hist = self.config.get('hist') or []
        item_exists = item in hist
        for i in hist:
            if i[0] == label:
                item_exists = True
                item = i
                break

        if item_exists:    
            hist.remove(item)
            
        hist.insert(0, item)
        self.config.set('hist', hist)
        self.reload()
            
    def remove(self):
        i = self.lb.current()
        item = self.hist_items[i]
        self.config.remove('hist', item)
        self.reload()

    def clean(self):
        if ui.query(U_STR('Delete All Items? '), 'query'):
            self.config.set('hist', [])
            self.lb_items = []
            self.hist_items = []
            uiext.clearListBox(self.lb)
            self.setMenu([])

    def count(self):
        self.loadItems()
        return len(self.hist_items)

    def handleLBClicks(self):
        i = self.lb.current()
        item = self.hist_items[i]
        self.parent.openLink(item[1])
        
    def show(self):
        self.setupItems()    
        ui.app.body = self.lb
        self.setTitle('History')
        self.setSoftKeysLabel('Back', None)
        ui.app.exit_key_handler = self.close
            

class MainWindow(BaseWindow):
    def __init__(self):
        BaseWindow.__init__(self, None)
        self.config = Config('conf')
        self.lb = None
        self.waitDialog = None
        self.event_dispatcher = AEventDispatcher(self.handleEvents, self.handleError)

    def onCloseWaitDialog(self, btn):
        # cancel button
        if btn == -1:
            self.mmc.cancelOp()
            
        
    def showWaitDialog(self, wait=False):
        if wait:
            self.waitDialog = uiext.WaitDialog(uiext.R_MODAL_WAITDIALOG, None, self.onCloseWaitDialog)
        else:
            self.waitDialog = uiext.WaitDialog(uiext.R_WAITDIALOG_SOFTKEY_CANCEL, None, self.onCloseWaitDialog)      
        self.waitDialog.show()

    def closeWaitDialog(self):
        if self.waitDialog:
            self.waitDialog.finish()
        
    def handleEvents(self, event):
        nodes = event.get('nodes')
        fileinfo = event.get('fileinfo')
        exit_event = event.get('exit') 
        self.closeWaitDialog()
        if nodes != None:
            root = nodes[0]
            node = root.get('parent_node') or root
            node_name = node.get('name')
            link = event.get('link')
            if node_name and link:
                self.history.add([node_name, link])
            self.browser.show(nodes)
            
        elif fileinfo != None:
            self.browser.openNode(fileinfo)

        elif exit_event != None:
            self.close()


    def handleError(self, event):
        self.closeWaitDialog()
        fatal_error = event.get('fatal_error')      
        err_msg = event.get('error')
        tb = event.get('tb')
        if tb:
            log.error(tb)

        if fatal_error:
            globalui.global_msg_query(U_STR(fatal_error), U_STR('FatalError'))

        else:
            link = event.get('link')
            if err_msg == 'Invalid URL':
                link = None # ask user to input another link
            if ui.query(U_STR('%s , Retry ?'%err_msg), 'query'):
                self.openLink(link)

        # self.setSoftKeysLabel('Exit', None, after=2)
    
    def handleLBClicks(self):
        i = self.lb.current()
        if i == 0:
            self.openLink()
        elif i == 1:
            self.bookmarks.show()
        elif i == 2:
            self.history.show()
            
    def openLink(self, link=None):
        if link is None:
            link = uiext.TextQueryDialog(U_STR('Enter Link:'))
        if link:
            self.showWaitDialog()
            self.mmc.fetch(link=link)
        
   
    def startEngine(self):
        self.showWaitDialog()
        self.mmc.startServer()

    def stopEngine(self):
        self.showWaitDialog()
        self.mmc.stopServer()

    def restartEngine(self):
        self.showWaitDialog()
        self.mmc.restartServer()

    def switchLogging(self):
        enabled = log.root.isEnabledFor(log.DEBUG)
        if enabled:
            lvl = 100 # higher than all levels
            log.disable(lvl)
            self.updateMenu((U_STR('Enable Logging'), self.switchLogging), 1)
            ui.note(U_STR('Logging disabled'), 'conf')


        else:
            log.disable(log.NOTSET)
            self.updateMenu((U_STR('Disable Logging'), self.switchLogging), 1)
            ui.note(U_STR('Logging enabled'), 'conf')

                        

    def initListbox(self):
        bm_count = self.bookmarks.count()
        hist_count = self.history.count()
        items = [
                (U_STR('Enter MEGA Link'), u''),
                (U_STR('Bookmarks'), U_STR(bm_count)),
                (U_STR('History'), U_STR(hist_count))
            ]
            
        if self.lb:
            self.lb.set_list(items)
        else:
            self.lb = ui.Listbox(items, self.handleLBClicks)
        return self.lb
 
    def setupWindows(self):
        self.browser = BrowserWindow(self)
        self.bookmarks = BookmarksWindow(self)
        self.history = HistoryWindow(self)

    def show(self):
        ui.app.body = self.initListbox()
        self.mmc.setEventHandler(self.event_dispatcher)
        self.setTitle('MegaMaru')
        self.setMenu(
                [(U_STR('Restart Engine'), self.restartEngine),
                (U_STR('Enable Logging'), self.switchLogging), 
                (U_STR('Exit'), self.exit)]
        )
        self.setSoftKeys(uiext.R_AVKON_SOFTKEYS_OPTIONS_EXIT)
        ui.app.exit_key_handler = self.close

      
    def run(self):
        server_url = self.config.get('server_url') or SERVER_URL
        self.mmc = MegaMaruClient(server_url, self.event_dispatcher)
        self.startEngine()
        self.app_lock = e32.Ao_lock()
        self.setupWindows()
        self.show()
        self.app_lock.wait()
        self.app_lock = None

    def exit(self):
        self.stopEngine()

    def close(self):
        self.app_lock.signal()
        #ui.app.set_exit()

MainWindow().run()

