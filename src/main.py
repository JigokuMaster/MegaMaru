import appuifw as ui
import globalui, uiext, e32, sysinfo, key_codes
from baseui import BaseApp, BaseWindow, ListBoxWindow
import httplib, threading, traceback, os, sys, time
from mm import*
from simpleutils import PyDownloader, hsize, clean_filename, parseExceptionMsg, Config

USERCONFIG_FP = '\\System\\\Apps\MegaMaru\\conf'
DEFCONFIG_FP = '\\System\\\Apps\MegaMaru\\defconf'
LOG_FP = 'C:\\System\\MegaMaruClient.log'
UI_ICONS_FP = '\\Resource\\Apps\\MegaMaru_ui.mif'

def U_STR(s):
    if s is None:
        return s
    # return lang.trans(s)
    return unicode(s)


setup_log(LOG_FP, disable=True) # MegaMaruClient logger

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
                logger.error(tb)
                # self._showErr(tb)                

    def handleEvent(self, **event):
        self.cg(self.on_event, event)
 
    def handleError(self, **event):
        self.cg(self.on_error, event)

               

class DownloaderWindow(ListBoxWindow):
    def __init__(self, app, parent):
        self.node = None
        self.paths = []
        self.file = None
        self.prefix = u'\\Data\\MEGA'
        ListBoxWindow.__init__(self, app, parent)
    
    def getUserPath(self):
        user_config = self.getAppConfig(USERCONFIG_FP)
        if user_config:
            path = user_config.get('dl_path')
            if path:
                drv = os.path.splitdrive(path)[0]
                if os.path.exists(drv):
                    return path
       
    def getDefaultPath(self):
        user_path = self.getUserPath()
        if user_path:
            return user_path

        for drv in ['E:', 'C:']:
            if os.path.exists(drv):
                return unicode(drv + self.prefix)
            
    def setDefaultPath(self, path):                    
        if path != self.getDefaultPath():
            user_config = self.getAppConfig(USERCONFIG_FP)
            q = ui.query(U_STR('Set as default path?'), 'query')
            if q and user_config:
                user_config.set('dl_path', path)
                self.setupPaths() # update the paths ...
                self.items[2] = U_STR('Download'), path # update the UI
                self.setItems(self.items, 2)

    def setupPaths(self):
        default_path =  self.getDefaultPath()
        if default_path:
            self.paths = [default_path]
        else:
            self.paths = []

        for i in e32.drive_list():
            drv = str(i.upper()) 
            if drv in ['Z:', 'D:']:
                continue       
            if os.path.exists(drv + '\\'):
                path = drv + self.prefix
                if not path in self.paths:
                    self.paths.append(unicode(path))
    
    def showFileName(self):
        fn = self.items[0][0]
        globalui.global_msg_query(fn, U_STR('Full name:'))

    def fileSavedIn(self, path=None):
        if path is None:
            path = self.getDefaultPath()

        fn = clean_filename(self.node['name'])
        fsize = self.node['size']            
        fp = os.path.join(path, fn)
        if os.path.exists(fp):
            return os.path.getsize(fp) == fsize
        else:
            return False

    def removeFile(self):
        if self.file and os.path.exists(self.file):
            q = ui.query(U_STR('Remove file?'), 'query')

    def openFile(self, ask_user=False):
        if self.file and os.path.exists(self.file):
            if ask_user:
                if ui.query(U_STR('Open the file now?'), 'query'):
                    try:
                        ui.Content_handler().open(self.file)
                    except Exception, e:
                        msg = unicode(parseExceptionMsg(e))
                        ui.note(msg, 'error')
 
    def downloadTo(self):
        i = ui.popup_menu(self.paths, U_STR('Save to:'))
        if i != None:
            path = self.paths[i]
            self.setDefaultPath(path) # if needed
            self.startDownload(path) # also if needed ...
    
    def startDownload(self, path):
        if self.fileSavedIn(path):
            q = ui.query(U_STR('File already saved, want to download again?'), 'query')
            if not q:
                return
        drv = unicode(os.path.splitdrive(path)[0])
        free_space = sysinfo.free_drivespace().get(drv)
        fsize = self.node['size'] * 2 # for the temp file
        no_free_space = (free_space - fsize) <= 1024*1024 # 1MB
        if no_free_space:
            msg = U_STR('No free space to download the file.')
            uiext.MessageQueryDialog(U_STR('Notice:'), msg)
            return

        self.parent.downloadFile(path, self.node)
            
    def handleLBClicks(self):
        i = self.current()
        if i == 0:
            self.showFileName()
            
        elif i == 1:
            if (self.getUserPath() is None) and len(self.paths) > 1:
                self.downloadTo()
            else:
                self.startDownload(self.paths[0])

    def fileSaved(self, fp):
        self.file = fp
        ui.note(U_STR('File saved'), 'conf')
        self.updateMenu((U_STR('Open'), self.openFile), 0)
        self.updateMenu((U_STR('Remove'), self.removeFile), 1)
        self.openFile(ask_user=True)

    def setupUI(self):
        self.setupPaths()
        self.item_len = 2
        return ui.Listbox([(u'', u'')], self.handleLBClicks)
     
    def show(self, node, parent=None):
        self.setTop()        
        self.node = node
        fn = node['name']
        size = hsize(node['size'])
        path = self.getDefaultPath()
        self.items = [
            (unicode(fn), unicode(size)),
            (U_STR('Download'), path),
        ]
        self.setItems(self.items)
        if len(self.paths) > 1:
            self.setMenu([(U_STR('Download to'), self.downloadTo)])
        else:
            self.setMenu([])
        self.setUI(self.ui)



class BrowserWindow(ListBoxWindow):
    def __init__(self, app, parent):
        ListBoxWindow.__init__(self, app, parent)
        self.event_dispatcher = AEventDispatcher(self.handleEvents, self.handleError)
        self.mmc = self.parent.mmc
        self.dlrwindow = DownloaderWindow(app, self)
        self.downloads = DownloadsWindow(app)       
        self.waitDialog = None
        self.progressDialog = None
        self.current_nodes = []
        self.node_history = []
        self.last_focused_item = 0

    def onCloseDialog(self, btn):
        if btn == -1: # canceled by user
            self.mmc.cancelOp()        

    
    def showWaitDialog(self, msg=None):
        # self.waitDialog = uiext.WaitDialog(uiext.R_MODAL_WAITDIALOG, msg, self.onCloseWaitDialog)
        self.waitDialog = uiext.WaitDialog(uiext.R_WAITDIALOG_SOFTKEY_CANCEL, msg, self.onCloseDialog)
        self.waitDialog.show()

    def closeWaitDialog(self):
        if self.waitDialog:
            self.waitDialog.finish()

            
    def showProgressDialog(self, msg, max_val):
        self.progressDialog = uiext.ProgressDialog(uiext.R_PROGRESSDIALOG_SOFTKEY_CANCEL,msg, self.onCloseDialog)
        self.progressDialog.show(None, max_val)

    def closeProgressDialog(self):
        if self.progressDialog:
            self.progressDialog.finish()

    def showSearchDialog(self):
        items = []
        for label, timestamp, icon  in self.items:
            items.append(label)
        i = ui.selection_list(items, search_field=1)
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
                self.dlrwindow.fileSaved(event['fp'])

    def downloadFile(self, path, node):
        self.mmc.setEventHandler(self.event_dispatcher)        
        self.showWaitDialog()
        self.mmc.downloadFile(path, node)
       
    def handleFetchEvents(self, event):
        nodes = event.get('nodes')
        fileinfo = event.get('fileinfo')
        previous_node = event.get('node')
        extra_args = event.get('extra_args', {})
        if nodes != None:
            if previous_node != None:
                if not previous_node in self.node_history:
                    self.node_history.insert(0, previous_node)

            self.setTitle()         
            self.setupItems(nodes)
            focused_item = extra_args.get('focused_item', 0)
            self.setItems(self.items, focused_item)
            
        if fileinfo != None:
            self.dlrwindow.show(fileinfo)
 
      
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
        cmd = event.get('cmd')
        err_msg = event.get('error')
        tb = event.get('tb')
        if tb:
            logger.error(tb)

        if cmd == CMD_FETCH:
            node = event.get('node')
            if node:      
                if ui.query(U_STR('%s , Retry?'%err_msg), 'query'):
                    self.openNode(node)
        else:
            file_node = event.get('node')
            if file_node:      
                if ui.query(U_STR('%s , Retry?'%err_msg), 'query'):
                    self.downloadFile(event['path'], file_node)
             

    def handleLBClicks(self):
        focused_item = self.current()
        self.last_focused_item = focused_item
        if len(self.current_nodes) > 0:
            node = self.current_nodes[focused_item][1]
            self.openNode(node)
        
    # called usually from this class ...       
    def openNode(self, node, focused_item=0):      
        node_type = node.get('t', 0)
        if node_type == 0: # show file info
            parent = None#self.node_history[0]
            self.dlrwindow.show(node, parent)

        elif node_type == 1: # fetch folder nodes                    
            self.showWaitDialog()
            args = {'focused_item': focused_item}
            self.mmc.fetch(node=node, extra_args=args) # wait for new nodes which will be processed by handleFetchEvents > setupItems 


    def setupItems(self, nodes):
        def mkItem(icon, node):
            ts = node.get('timestamp', 0)
            timestamp = ''
            if ts > 0:
                fmt = '%d.%m.%Y %H:%M'
                timestamp = time.strftime(fmt, time.localtime(ts))

            item = unicode(node['name']), unicode(timestamp), icon
            return item

        parent = nodes.pop(0)
        self.current_nodes = []
        self.items = []
        # folders first ...
        for node in nodes:
            if node['t'] == 1:
                item = mkItem(self.folder_icon,node)
                n = item[0]
                self.items.append(item)
                self.current_nodes.append((n, node))
                
        self.items.sort()
        self.current_nodes.sort()
        files = []
        _nodes = []
        for node in nodes:
            if node['t'] == 0:
                icon = self.file_icon
                n = node['name']
                if n.endswith('.txt'):
                    icon = self.txtfile_icon

                item = mkItem(icon, node)
                # n = item[0]
                files.append(item)
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
        if bm.add(item, update_ui=False):
            ui.note(U_STR('Bookmark Saved'), 'conf')        
    
    
    def reload(self):
        if len(self.node_history):
            node = self.node_history[0]
            self.clearItems()      
            # refetch nodes ...
            self.showWaitDialog()
            self.mmc.fetch(node=node, nocache=1)


    def clearItems(self):
        self.last_focused_item = 0
        self.current_nodes = []
        self.node_history = []   
        self.clear()
        menu_items = [
            (U_STR('Downloads'), self.downloads.show),        
            (U_STR('Home'), self.parent.show),            
            (U_STR('Exit'), self.parent.exit)         
        ]
        self.setMenu(menu_items)
    
    def setTitle(self, t=None): 
        if len(self.node_history) > 0:
            root = self.node_history[0]
            node = root.get('parent_node') or root
            node_name = node.get('name')
            ListBoxWindow.setTitle(self, node_name)
        else:
            ListBoxWindow.setTitle(self, u'')

    def loadIcons(self):
        fp = unicode(UI_ICONS_FP)
        self.folder_icon = ui.Icon(fp, 16384, 16385)
        self.file_icon = ui.Icon(fp, 16386, 16387)
        self.txtfile_icon = ui.Icon(fp, 16388, 16389)

    def setupUI(self):
        self.loadIcons()
        self.empty_item = (u'', u'', self.folder_icon)
        return ui.Listbox([self.empty_item], self.handleLBClicks) 
    
    # called from baseclass or history/bookmarks windows
    def show(self, nodes=None):
        self.setTop()
        self.mmc.setEventHandler(self.event_dispatcher)
        new_items = (nodes != None)
        if new_items:
            self.node_history = []
            if len(nodes):
                root = nodes[0]
                node = root.get('parent_node') or root
                self.node_history.insert(0, node) # store the root/parent node

            self.setupItems(nodes)
            self.setItems(self.items) 

        
        if len(self.items):
            menu_items = [
                (U_STR('Reload'), self.reload),
                (U_STR('Search'), self.showSearchDialog),
                (U_STR('Add Bookmark'), self.addBM),
                (U_STR('Downloads'), self.downloads.show),                
                (U_STR('Home'), self.parent.show), 
                (U_STR('Exit'), self.parent.exit) # should stop the engine            
            ]
        else:
             menu_items = [
                (U_STR('Downloads'), self.downloads.show),             
                (U_STR('Home'), self.parent.show), 
                (U_STR('Exit'), self.parent.exit) # should stop the engine            
            ]

        self.setUI(self.ui)
        self.setTitle(self)
        self.setMenu(menu_items)
        self.setExitKeyHandler(self.close)
      

    def close(self):
        if len(self.node_history) > 1:          
            current = self.node_history.pop(0)
            previous = self.node_history.pop(0)
            self.openNode(previous, self.last_focused_item)

        else:
            ListBoxWindow.close(self)


class BookmarksWindow(ListBoxWindow):
    def __init__(self, app, onclick=None):
        ListBoxWindow.__init__(self, app)
        self.onclick_cb = onclick
        self.config = self.getAppConfig(USERCONFIG_FP)
        self._copyDefBM()
        self.bm_items = []

    # devilish method :), copy default bookmarks to userconfig 
    def _copyDefBM(self):
        defconfig = Config(DEFCONFIG_FP)
        if defconfig is None:
            return

        def_bm = defconfig.get('bm') or []
        if len(def_bm) == 0:
            return
        
        user_bm = self.config.get('bm') or []
        tmp = []
        tmp.extend(user_bm)
        for i in def_bm:
            if self._itemExists(i, tmp): # check if any element of the item exists
                if i in tmp: # check if the item exists
                    tmp.remove(i) 
                continue
            user_bm.append(i)
 
        defconfig.set('bm', [])
        self.config.set('bm', user_bm)

    def loadItems(self):
        bm = self.config.get('bm')
        if bm != None:
            self.bm_items = bm
            for i in bm:
                label = unicode(i[0])
                if label in self.items:
                    continue
                self.items.append(label)

    def _itemExists(self, item, bm=None):
        if bm is None:
            bm = self.config.get('bm')
        if bm != None:
            for label, link in bm:
                if (label == item[0]) or (link == item[1]):
                    return True
        return False            


    def reload(self, update_ui=True):             
        self.items = []
        self.bm_items = []
        self.loadItems()
        if update_ui:
            self.setupItems()   
    
    def setupItems(self):        
        empty_items = len(self.items) == 0
        self.setItems(self.items)
        if empty_items:    
            self.setMenu((U_STR('Add'), self.addNew))
        else:           
            self.setMenu([(U_STR('Add'), self.addNew),
                          (U_STR('Edit'), self.edit),
                          (U_STR('Remove'), self.remove),
                          (U_STR('Clean'), self.clean)])
    
       
    def openEditor(self, item=None):
        domain = 'https://mega.nz'
        if item is None:
            title, link = ('', '')
        else:
            title, link = item  
        if not link.startswith(domain):
            link = domain + link

        items = [(U_STR('Title'), 'text', unicode(title)),
                 (U_STR('Link'), 'text', unicode(link))]

        f = ui.Form(items, ui.FFormEditModeOnly|ui.FFormDoubleSpaced)
        f.execute()
        return f

    def addNew(self, item=None):
        res = self.openEditor(item)
        item = res[0][2], res[1][2]
        title, link = item
        if (not title) and (not link):
            return False
       
        if (not title) or (not link):
            q = ui.query(U_STR('Bookmark connot be empty, Edit again?'), 'query')
            if q:
                return self.addNew(item)
            else:
                return False
           
        if self._itemExists(item):
            q = ui.query(U_STR('Bookmark already exists, Edit again?'), 'query')
            if q:
                return self.addNew(item)
            else:
                return False

        bm = self.config.get('bm') or []
        bm.insert(0, item)
        self.config.set('bm', bm)
        self.reload()      
      
    def add(self, item, update_ui=True):
        title = ui.query(U_STR('Title:'), 'text', unicode(item[0]))
        if title is None:
            return False

        item[0] = title
        if self._itemExists(item):
            q = ui.query(U_STR('Bookmark already exists, Edit again?'), 'query')
            if q:
                return self.add(item, update_ui)
            else:
                return False
       
        bm = self.config.get('bm') or []
        bm.insert(0, item)
        self.config.set('bm', bm)
        self.reload(update_ui)
        return True


    def edit(self):
        if len(self.bm_items) == 0:return
        idx = self.current()
        item = self.bm_items[idx]
        res = self.openEditor(item)      
        title = res[0][2]
        link = res[1][2]
        bm = self.config.get('bm') or []
        if item in bm:
            idx = bm.index(item)
            new_item = [title, link] 
            if new_item != item:
                bm[idx] = new_item
                self.config.set('bm', bm)
                self.reload()

    def remove(self):
        if len(self.bm_items) == 0:return
        i = self.current()
        item = self.bm_items[i]
        if ui.query(U_STR('Remove bookmark?'), 'query'):
            self.config.remove('bm', item)
            self.reload()

    def clean(self):
        if ui.query(U_STR('Delete All items?'), 'query'):
            self.config.set('bm', [])
            self.reload()
            
    def count(self):
        self.loadItems()
        return len(self.items)

    def handleLBClicks(self):
        if len(self.bm_items) == 0:return
        i = self.current()
        item = self.bm_items[i]
        if self.onclick_cb:
            self.onclick_cb(item[1]) # link

    def setupUI(self):
        return ui.Listbox([self.empty_item], self.handleLBClicks)

    def show(self):
        self.setTop()  
        self.setupItems()    
        self.setUI(self.ui)
        self.setTitle('Bookmarks')
        self.setSoftKeysLabel(U_STR('Back'), None)
        self.ui.bind(key_codes.EKeyBackspace ,self.remove)
           

class HistoryWindow(ListBoxWindow):
    def __init__(self, app, onclick=None):
        ListBoxWindow.__init__(self, app)
        self.onclick_cb = onclick
        self.config = self.getAppConfig(USERCONFIG_FP)
        self.hist_items = []


    def loadItems(self):
        hist = self.config.get('hist')
        if hist != None:
            self.hist_items = hist
            for i in hist:
                label = unicode(i[0])
                if label in self.items:
                    continue
                self.items.append(label)

    def reload(self):             
        self.items = []
        self.hist_items = {}
        self.setupItems()

    def setupItems(self):
        self.loadItems()
        empty_items = len(self.items) == 0
        self.setItems(self.items)
        if empty_items:    
           self.setMenu([])       
        else:
            self.setMenu([(U_STR('Remove'), self.remove), (U_STR('Clean'), self.clean)])

        
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
        if len(self.hist_items) == 0:return
        i = self.current()
        item = self.hist_items[i]
        if ui.query(U_STR('Remove item?'), 'query'):
            self.config.remove('hist', item)
            self.reload()

    def clean(self):
        if ui.query(U_STR('Delete All Items? '), 'query'):
            self.config.set('hist', [])
            self.reload()

    def count(self):
        self.loadItems()
        return len(self.hist_items)

    def handleLBClicks(self):
        if len(self.hist_items) == 0:return
        i = self.current()
        item = self.hist_items[i]
        if self.onclick_cb:
            self.onclick_cb(item[1])

    def setupUI(self):
        return ui.Listbox([self.empty_item], self.handleLBClicks)

    def show(self):
        self.setTop()
        self.setTitle(U_STR('History'))
        self.setupItems()    
        self.setUI(self.ui)
        self.setSoftKeysLabel(U_STR('Back'), None)
        self.ui.bind(key_codes.EKeyBackspace ,self.remove)
           

class DownloadsWindow(ListBoxWindow):
    PATHS_SECTION = 0
    FILES_SECTION = 1
    def __init__(self, app):  
        ListBoxWindow.__init__(self, app)
        self.section = self.PATHS_SECTION
        self.current_path = None


    def setupPaths(self):
        prefix = '\\Data\\MEGA'
        self.paths = []      
        for i in e32.drive_list():
            drv = str(i.upper()) 
            if drv in ['Z:', 'D:']:
                continue

            path = drv + prefix
            if os.path.exists(path):
                try:
                    files = os.listdir(path)
                    nfiles = len(files)
                    info = (unicode(path), u'%d files' %nfiles)
                    self.paths.append(info)
                except:
                    logger.error(traceback.format_exc())
                
    def removeFile(self):
        if (self.section == self.FILES_SECTION) and self.current_path:
            fn, fsize = self.items[self.current()]
            fp = os.path.join(self.current_path, fn)
            msg = U_STR('Remove "%s" ?' %fp)
            if ui.query(msg, 'query'):
                try:
                    os.remove(fp)
                    focused_item = self.current() - 1
                    self.openPath(self.current_path, focused_item) # reload
                except Exception, e:
                    msg = unicode(parseExceptionMsg(e))
                    ui.note(msg, 'error')

    def openFile(self):
        if self.current_path:
            fn, fsize = self.items[self.current()]
            fp = os.path.join(self.current_path, fn)
            try:
                ui.Content_handler().open(fp)
            except Exception, e:
                msg = unicode(parseExceptionMsg(e))
                ui.note(msg, 'error')
           

    def openPath(self, path=None, focused_item=0):
        if path is None:
            path, nfiles = self.getCurrentItem()
           
        if not os.path.exists(path):
            return

        self.current_path = path
        files = []
        for f in os.listdir(path):
            fp = os.path.join(path, f)
            if os.path.isfile(fp):
                fsize = hsize(os.path.getsize(fp))
                info = (unicode(f), unicode(fsize))
                files.append(info)

        if len(files) == 0:
            ui.note(U_STR('No Downloads'), 'info')
        else:
            self.section = self.FILES_SECTION
            self.setItems(files, focused_item)
            self.setTitle(self.current_path)


    def handleLBClicks(self):
        if self.section == self.PATHS_SECTION:
            if len(self.paths) > 0:
                self.openPath()

        elif self.section == self.FILES_SECTION:
             if not self.isEmpty():
                 self.openFile()
    
    def setupItems(self):
        self.setupPaths()
        if len(self.paths) == 0:
            ui.note(U_STR('No Downloads'), 'info')
            return False
        else:
            self.setMenu((U_STR('Remove'), self.removeFile))
            self.setItems(self.paths)
            return True    

    def setupUI(self):
        self.empty_item = (u'', u'')
        return ui.Listbox([self.empty_item], self.handleLBClicks)
        
    def show(self):
        if self.setupItems():
            self.setTop()
            self.setTitle(U_STR('Downloads'))
            self.setUI(self.ui)      
            self.setSoftKeysLabel(U_STR('Back'), None)
            self.setExitKeyHandler(self.doReturn)
            self.ui.bind(key_codes.EKeyBackspace ,self.removeFile)

    def doReturn(self):
        if self.section == self.PATHS_SECTION:
            self.close()
        else:
            self.section = self.PATHS_SECTION
            self.setupItems()

class ManagementWindow(ListBoxWindow):
    def __init__(self, app, parent):  
        ListBoxWindow.__init__(self, app, parent)

    def switchLogging(self, change_state=True):
        enabled = logger.root.isEnabledFor(logger.DEBUG)
        state_values = U_STR('Enabled'), U_STR('Disabled')
        if enabled:
            lvl = 100 # higher than all levels           
            if change_state:
                logger.disable(lvl)
                self.items[3] = (U_STR('Logging'), state_values[1])
                self.setItems(self.items, 3)
            else:
                self.items[3] = (U_STR('Logging'), state_values[0])


        else:
            if change_state:
                logger.disable(logger.NOTSET)
                self.items[3] = (U_STR('Logging'), state_values[0])
                self.setItems(self.items, 3)
            else:
                self.items[3] = (U_STR('Logging'), state_values[1])


    def handleLBClicks(self):
        index = self.current()
        if index == 0:
            self.parent.restartEngine()

        elif index == 1:
            self.parent.cleanEngineCache()

        elif index == 2:
            self.downloads.show()
    
        elif index == 3:
            self.switchLogging()

    def setupUI(self):
        self.downloads = DownloadsWindow(self.app)
        self.empty_item = (u'', u'')
        self.items = [
                    (U_STR('Restart Engine'), u''),
                    (U_STR('Cache'), u''),                  
                    (U_STR('Downloads'), u''),
                    (u'', u'')] 
        self.switchLogging(False)
        return ui.Listbox(self.items, self.handleLBClicks)

    def show(self):
        self.setTop()
        self.setTitle(U_STR('Manage'))
        self.setMenu([])        
        self.setUI(self.ui)
        self.setSoftKeysLabel(U_STR('Back'), None)
       

class MainWindow(BaseWindow):
    def __init__(self, app):
        BaseWindow.__init__(self, app)
        self.config = self.getAppConfig(USERCONFIG_FP)
        self.lb = None
        self.waitDialog = None

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

    def showAboutDialog(self):
        try:
            f = open('about.txt', 'rU')
            about = unicode(f.read(), 'utf-8')
            f.close()
        except:
            logger.error(traceback.format_exc())
        else:
            uiext.MessageQueryDialog(U_STR('About'), about)


    def handleEvents(self, event):
        cmd = event.get('cmd')
        self.closeWaitDialog()
        if cmd == CMD_FETCH:
            nodes = event.get('nodes')
            if nodes != None:
                root = nodes[0]
                node = root.get('parent_node') or root
                node_name = node.get('name')
                link = event.get('link')
                if node_name and link:
                    self.history.add([node_name, link])
                self.browser.show(nodes)
                
        elif cmd == CMD_CLEANCACHE:
            size = hsize(event.get('cache_size'))
            ui.note(U_STR('%s was cleaned up' %size))
           
        else:
            fileinfo = event.get('fileinfo')
            exit_event = event.get('exit')
            server_addr = event.get('server_addr') 
            if fileinfo != None:
                self.browser.openNode(fileinfo)
            elif exit_event != None:
                self.app.exit()
            elif server_addr != None:
                conf = Config(USERCONFIG_FP)
                conf.set('server_addr', server_addr)

    def handleError(self, event):       
        self.closeWaitDialog()
        fatal_error = event.get('fatal_error')      
        err_msg = event.get('error')
        tb = event.get('tb')
        if tb:
            logger.error(tb)

        if fatal_error:
            globalui.global_msg_query(U_STR(fatal_error), U_STR('FatalError'))
            self.app.exit()

        else:
            link = event.get('link')
            if err_msg == 'Invalid URL':
                link = None # ask user to input another link
            if ui.query(U_STR('%s , Retry ?'%err_msg), 'query'):
                self.openLink(link)

        self.setSoftKeysLabel(U_STR('Exit'), None) 
    
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
            self.setSoftKeysLabel(U_STR('Back'), None)            
            self.showWaitDialog()
            self.mmc.setEventHandler(self.event_dispatcher)           
            self.mmc.fetch(link=link)
        
   
    def startEngine(self):
        self.showWaitDialog()
        self.mmc.startServer()
        
    def restartEngine(self):
        self.showWaitDialog()
        self.mmc.restartServer()

    def stopEngine(self):
        self.showWaitDialog()
        self.mmc.stopServer()

    def cleanEngineCache(self):
        if ui.query(U_STR('Cleanup all cache?'), 'query'):
            self.showWaitDialog()
            self.mmc.cleanServerCache()

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

        self.setUI(self.lb)
 
    def setupWindows(self):
        self.browser = BrowserWindow(self.app, parent=self)
        self.bookmarks = BookmarksWindow(self.app, onclick=self.openLink)
        self.history = HistoryWindow(self.app, onclick=self.openLink)
        self.management = ManagementWindow(self.app, parent=self)
        self.setTop()

    def show(self):
        self.setTop()
        self.initListbox()
        self.setTitle('MegaMaru')
        self.setExitKeyHandler(self.exit)
        self.setSoftKeys(uiext.R_AVKON_SOFTKEYS_OPTIONS_EXIT)
        self.setMenu(
                [(U_STR('Manage'), self.management.show),
                (U_STR('About'), self.showAboutDialog),             
                (U_STR('Exit'), self.exit)]
        )
        self.mmc.setEventHandler(self.event_dispatcher)
       
      
    def setup(self):
        server_addr = self.config.get('server_addr')
        self.event_dispatcher = AEventDispatcher(self.handleEvents, self.handleError)
        self.mmc = MegaMaruClient(server_addr, self.event_dispatcher)
        self.startEngine()
        self.setupWindows()

    def exit(self):
        self.stopEngine()

app = BaseApp()
MainWindow(app).setup()
app.run()
