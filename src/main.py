import appuifw as ui
import globalui, uiext, e32, sysinfo, key_codes
from baseui import WindowStack, ListBoxWindow
import ui_icons 
import loc as lang
from mm import*
from simpleutils import PyDownloader, hsize, clean_filename, parseExceptionMsg, Config, ItemsCache
import traceback, os, time


USERCONFIG_FP = '\\System\\Apps\\MegaMaru\\conf'
DEFCONFIG_FP = '\\System\\Apps\\MegaMaru\\defconf'
LOG_FP = 'C:\\System\\MegaMaruClient.log'
LANG_DIR = '\\System\\Apps\MegaMaru\\lang'

setup_log(LOG_FP, disable=True) # MegaMaruClient logger

loc_loader = lang.Loader(LANG_DIR)
def U_STR(k):
    s = loc_loader.get(k)
    if isinstance(s, unicode): 
        return s
    else:
        return unicode(s, 'utf-8')

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
    def __init__(self, browser):
        self.browser = browser
        self.node = None
        self.paths = []
        self.file = None
        self.prefix = u'\\Data\\MEGA'
        ListBoxWindow.__init__(self, [], uiext.EDoubleListbox)
    
    def getUserPath(self):
        user_config = self.openConfig(USERCONFIG_FP)
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

        for drv in ['E:', 'F:', 'C:']:
            if os.path.exists(drv):
                return unicode(drv + self.prefix)
            
    def setDefaultPath(self, path):                    
        if path != self.getDefaultPath():
            user_config = self.openConfig(USERCONFIG_FP)
            q = ui.query(U_STR(lang.SET_AS_DEFAULT_PATH), 'query')
            if q and user_config:
                user_config.set('dl_path', path)
                self.setupPaths() # update the paths ...
                self.items[1] = U_STR(lang.DOWNLOAD), path # update the UI
                self.setItems(self.items, 1)

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

    def openFile(self, ask_user=False):
        if self.file and os.path.exists(self.file):
            if ask_user:
                if not ui.query(U_STR(lang.OPEN_THE_FILE_NOW), 'query'):
                    return
            try:
                ui.Content_handler().open(self.file)
            except Exception, e:
                msg = unicode(parseExceptionMsg(e))
                ui.note(msg, 'error')
 
    def downloadTo(self):
        i = ui.popup_menu(self.paths, U_STR(lang.SAVE_TO))
        if i != None:
            path = self.paths[i]
            self.setDefaultPath(path) # if needed
            self.startDownload(path) # also if needed ...
    
    def startDownload(self, path):
        if self.fileSavedIn(path):
            q = ui.query(U_STR(lang.FILE_ALREADY_EXISTS), 'query')
            if not q:
                return
        drv = unicode(os.path.splitdrive(path)[0])
        free_space = sysinfo.free_drivespace().get(drv)
        fsize = self.node['size'] * 2 # for the temp file
        no_free_space = (free_space - fsize) <= 1024*1024 # 1MB
        if no_free_space:
            msg = U_STR(lang.NO_FREE_SPACE_TO_DOWNLOAD_THE_FILE)
            uiext.MessageQueryDialog(U_STR(lang.NOTICE), msg)
            return

        self.browser.downloadFile(path, self.node)
            
    def handleItemClicks(self, idx):           
        if idx == 1:
            if (self.getUserPath() is None) and len(self.paths) > 1:
                self.downloadTo()
            else:
                self.startDownload(self.paths[0])

    def fileSaved(self, fp):
        self.file = fp
        ui.note(U_STR(lang.FILE_SAVED), 'conf')
        self.updateMenu((U_STR(lang.OPEN), self.openFile), 0)
        self.openFile(ask_user=True)

    
    def show(self, node):
        self.setupPaths()       
        self.node = node
        fn = node['name']
        size = hsize(node['size'])      
        path = self.getDefaultPath()
        self.items = [
            (unicode(fn), unicode(size)),
            (U_STR(lang.DOWNLOAD), path),
        ]

        if len(self.paths) > 1:
            self.setMenu([(U_STR(lang.DOWNLOAD_TO), self.downloadTo)])
        else:
            self.setMenu([])

        self.enableMarquee(True)
        self.setSoftKeyLabel(uiext.EAknSoftkeyOptions, U_STR(lang.MENU))
        self.setSoftKeyLabel(uiext.EAknSoftkeyBack, U_STR(lang.BACK))        
        ListBoxWindow.show(self, self.menu_items)    


class BrowserCache(ItemsCache):
    def __init__(self, browser):
        ItemsCache.__init__(self, maxsize=30)
        self.browser = browser

    # make a unique key from node ids
    def _gen_key(self, node):
        folder_id = node['id']
        parent_id = node['parent_id']
        root_id = node['root_id']
        key = '#'.join((root_id, parent_id, folder_id))
        return key

    def updateItem(self, node, idx, val):
        k = self._gen_key(node)
        cached_items = self.get(k)
        if cached_items != None:          
            cached_items[idx]=val

    def cacheItems(self, node):
        k = self._gen_key(node)
        focused_item = self.browser.focused_item
        items = [
                self.browser.current_nodes,
                self.browser.items,
                focused_item
                ]
        self.put(k, items)
            
    def loadCachedItems(self, node):
         k = self._gen_key(node)
         cached_items = self.get(k)
         if cached_items != None:
             nodes , items, focused_item = cached_items
             self.browser.current_nodes = nodes
             self.browser.focused_item = focused_item
             self.browser.loadItems(items, focused_item)
             return True

         return False
   
class BrowserWindow(ListBoxWindow):
    def __init__(self, mainwindow):
        ListBoxWindow.__init__(self)
        self.event_dispatcher = AEventDispatcher(self.handleEvents, self.handleError)
        self.mmc = mainwindow.mmc
        self.mainwindow = mainwindow
        self.dlrwindow = DownloaderWindow(self)
        self.downloads = DownloadsWindow()       
        self.waitDialog = None
        self.progressDialog = None
        self.current_nodes = []
        self.node_history = []
        self.focused_item = 0
        self.cache = BrowserCache(self)


    def onCloseDialog(self, btn):
        if btn == -1: # canceled by user
            self.mmc.cancelOp()        

    def showWaitDialog(self, msg=None):
        if msg is None:
            msg = U_STR(lang.PLEASE_WAIT)
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
            self.showProgressDialog(U_STR(lang.DOWNLOADING), params['size'])


        elif state == PyDownloader.DOWNLOAD_ING:
            # read bytes, downloaded_bytes, total bytes
            r_bytes = params['rb']
            dl_bytes = params['db']
            total_bytes = params['tb']
            msg = u'%s %s/%s' %(U_STR(lang.DOWNLOADING), hsize(dl_bytes), hsize(total_bytes))
            self.updateProgressDialog(msg, dl_bytes)

        elif state == PyDownloader.DOWNLOAD_ABORTED:
            msg = params.get('msg')
            globalui.global_msg_query(unicode(msg), U_STR(lang.DOWNLOAD_ABORTED))
            

        elif state == PyDownloader.DOWNLOAD_DONE:
            self.closeProgressDialog()
            # ui.note(u'Download Done')

        elif state in [PyDownloader.DOWNLOAD_FAILED, PyDownloader.REQUEST_FAILED]:
            self.closeProgressDialog()
            msg = unicode(params['error'])
            globalui.global_msg_query(msg, U_STR(lang.DOWNLOAD_FAILED))
            
        elif state == None:
            self.closeWaitDialog()
            self.closeProgressDialog()
        

    def handleDecryptEvents(self, event):
        prog = event.get('dec_prog')
        if type(prog) == tuple:
            self.showProgressDialog(U_STR(lang.DECRYPTING), prog[1])

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

            self.setupTitle()         
            self.setupItems(nodes)
            self.focused_item = extra_args.get('focused_item', 0)
            self.loadItems(self.items, self.focused_item)
            self.cacheItems(previous_node)
           
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

        self.mainwindow.handleEvents(event)
 

    def handleError(self, event):
        self.closeWaitDialog()
        self.closeProgressDialog()
        cmd = event.get('cmd')
        err_msg = event.get('error')
        q_msg = u'%s\n%s' %(err_msg, U_STR(lang.RETRY))
        tb = event.get('tb')
        if tb:
            logger.error(tb)

        if cmd == CMD_FETCH:
            node = event.get('node')
            if node:
                if ui.query(q_msg, 'query'):
                    self.openNode(node)
        else:
            file_node = event.get('node')
            if file_node:      
                if ui.query(q_msg, 'query'):
                    self.downloadFile(event['path'], file_node)
             

    def handleItemClicks(self, idx):
        self.focused_item = idx
        if len(self.current_nodes) > 0:
            node = self.current_nodes[self.focused_item][1]
            self.updateCacheItem(2, self.focused_item)
            self.openNode(node)
            
    def updateCacheItem(self, idx, val):
        if len(self.node_history) == 0:
             return 

        node = self.node_history[0]        
        self.cache.updateItem(node, idx, val)

    def loadCachedItems(self, node):  
        if self.cache.loadCachedItems(node):
            if not node in self.node_history:
                self.node_history.insert(0, node)

            self.setupTitle()
            return True

        return False

    def cacheItems(self, node):
        self.cache.cacheItems(node)

    # called usually from this class ...       
    def openNode(self, node, focused_item=0):      
        node_type = node.get('t', 0)
        if node_type == 0: # show file info
            parent = None#self.node_history[0]
            self.dlrwindow.show(node)

        elif node_type == 1: # fetch folder nodes                    
            args = {'focused_item': focused_item}
            if not self.loadCachedItems(node):
                self.showWaitDialog()
                self.mmc.fetch(node=node, extra_args=args) # wait for new nodes which will be processed by handleFetchEvents > setupItems 

    # lazy load ...
    def loadItems(self, items, focused_item=0):
        count = len(items)
        if len(items) <= 50:
            self.setItems(items, focused_item)
            return

        n_items = 20
        i = 0
        self.clear()
        self.showWaitDialog(U_STR(lang.LOADING_ITEMS))
        while i < count:
            self.addItems(items[i:i+n_items])
            i += n_items
            e32.ao_yield()

        self.setFocusedItem(focused_item)    
        self.closeWaitDialog()


    def setupItems(self, nodes, cached=False):
        def mkItem(icon, node):
            ts = node.get('timestamp', 0)
            timestamp = ''
            if ts > 0:
                fmt = '%d.%m.%Y %H:%M'
                timestamp = time.strftime(fmt, time.localtime(ts))

            item = unicode(node['name']), unicode(timestamp), icon
            return item
        
        if not cached:
            parent = nodes.pop(0)
            self.current_nodes = []

        self.items = []
        # folders first ...
        for node in nodes:
            if node['t'] == 1:
                item = mkItem(ui_icons.folder_icon, node)
                n = item[0]
                self.items.append(item)
                if not cached:self.current_nodes.append((n, node))
                
        self.items.sort()
        if not cached:self.current_nodes.sort()
        files = []
        _nodes = []
        for node in nodes:
            if node['t'] == 0:
                n = node['name']
                icon = ui_icons.icon_for(n)
                item = mkItem(icon, node)
                # n = item[0]
                files.append(item)
                _nodes.append((n, node))

        files.sort()
        _nodes.sort()
        self.items += files
        if not cached:
            self.current_nodes += _nodes
        
    def addBM(self):
        if len(self.node_history) == 0:
             return

        bm = self.mainwindow.bookmarks
        node = self.node_history[0]        
        k = node['root_key']
        is_root = node['id'] == node['parent_id']
        if is_root:
            path = '/folder/%s#%s' %(node['root_id'], k)            
        else:
            path = '/folder/%s#%s/folder/%s' %(node['root_id'], k, node['id'])

        item = [node['name'], path]
        if bm.add(item, update_ui=False):
            ui.note(U_STR(lang.BOOKMARK_SAVED), 'conf')        
     
    def reload(self):
        if len(self.node_history):
            node = self.node_history[0]
            self.clearItems()      
            # refetch nodes ...
            self.showWaitDialog()
            self.mmc.fetch(node=node, nocache=1)


    def clearItems(self):
        self.focused_item = 0
        self.current_nodes = []
        self.node_history = []   
        self.clear()
        self.cache.reset()
        self.setupMenu()
    
    def setupTitle(self): 
        if len(self.node_history) > 0:
            root = self.node_history[0]
            node = root.get('parent_node') or root
            node_name = node.get('name')
            self.setTitle(node_name)
        else:
            self.setTitle(u'')


    def openWindow(self):
        def openBookmarks():
            bm = self.mainwindow.bookmarks
            bm.show()

        def openHome():
            self.mainwindow.reSetup(ignore_previous=True)

        windows = {
                U_STR(lang.HOME): openHome,
                U_STR(lang.BOOKMARKS): openBookmarks,
                U_STR(lang.DOWNLOADS): self.downloads.show 
                }
        items = windows.keys()
        i = ui.popup_menu(items)
        if i != None:
            cb = windows.get(items[i])
            if cb:
                cb()

    def setupMenu(self):
        if self.items:
            self.menu_items = [
                (U_STR(lang.RELOAD), self.reload),
                (U_STR(lang.ADD_BOOKMARK), self.addBM),
                (U_STR(lang.GO_TO), self.openWindow)          
            ]

            if not ui.touch_enabled():
                self.menu_items.insert(1, (U_STR(lang.SEARCH), self.showSearchDialog))

        else:
             self.menu_items = [
                (U_STR(lang.GO_TO), self.openWindow)                             
            ]
        self.mainwindow.setMenu(self.menu_items)     

    # called from baseclass or history/bookmarks windows
    def show(self, nodes=None):
        self.dialog = self.mainwindow.dialog        
        self.mmc.setEventHandler(self.event_dispatcher)
        new_items = (nodes != None)
        if new_items:
            self.cache.reset()
            self.node_history = []
            node = None
            if len(nodes):
                root = nodes[0]
                node = root.get('parent_node') or root
                self.node_history.insert(0, node) # store the root/parent node

            self.setupItems(nodes)
            if node:
                self.cacheItems(node)


        self.setupTitle()    
        self.setupMenu()
        self.loadItems(self.items)              
        self.mainwindow.setCurrentSection(self)

    def handleExit(self):
        if len(self.node_history) > 1:
            self.updateCacheItem(2, self.current()) # update focused item in cache
            current = self.node_history.pop(0)
            previous = self.node_history.pop(0)
            self.openNode(previous)

        else:
            mainwindow.reSetup() # show MainWindow         
        return False

class DownloadsWindow(ListBoxWindow):
    PATHS_SECTION = 0
    FILES_SECTION = 1
    def __init__(self):
        ListBoxWindow.__init__(self, [], uiext.EDoubleGraphicListbox)
        self.current_path = None
        self.section_stack = WindowStack(self.PATHS_SECTION)

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
                    item = (unicode(path), u'%d %s' %(nfiles, U_STR(lang.FILES)), ui_icons.folder_icon)
                    self.paths.append(item)
                except:
                    logger.error(traceback.format_exc())
                
    def removeFile(self):
        current_section = self.section_stack.top()
        if self.isEmpty() or current_section != self.FILES_SECTION:
            return

        if self.current_path:
            fn = self.items[self.current()][0]
            fp = os.path.join(self.current_path, fn)
            msg = u'%s\n"%s"' %(U_STR(lang.REMOVE), fp)
            if ui.query(msg, 'query'):
                try:
                    os.remove(fp)
                    focused_item = self.current() -1
                    self.openPath(self.current_path, focused_item) # reload
                except Exception, e:
                    msg = unicode(parseExceptionMsg(e))
                    ui.note(msg, 'error')

    def openFile(self):
        if self.current_path:
            fn = self.items[self.current()][0]
            fp = os.path.join(self.current_path, fn)
            try:
                ui.Content_handler().open(fp)
            except Exception, e:
                msg = unicode(parseExceptionMsg(e))
                ui.note(msg, 'error')
           

    def openPath(self, path=None, focused_item=0):         
        if not os.path.exists(path):
            return

        self.current_path = path
        files = []
        for f in os.listdir(path):
            fp = os.path.join(path, f)
            if os.path.isfile(fp):
                fsize = hsize(os.path.getsize(fp))
                item = (unicode(f), unicode(fsize), ui_icons.icon_for(f))
                files.append(item)
        
            
        if len(files) == 0:
            current_section = self.section_stack.top()
            if current_section == self.FILES_SECTION:
                self.showPaths()
            else:
                ui.note(U_STR(lang.NO_DOWNLOADS), 'info')

        else:
            self.section_stack.setTop(self.FILES_SECTION)
            self.setMenu((U_STR(lang.REMOVE), self.removeFile))
            self.setItems(files, focused_item)
            self.setTitle(self.current_path)


    def handleItemClicks(self, idx):
        current_section = self.section_stack.top()
        if current_section == self.PATHS_SECTION:
            if len(self.paths) > 0:
                self.openPath(self.paths[idx][0])

        elif current_section == self.FILES_SECTION:
             if not self.isEmpty():
                 self.openFile()

    def handleKeyEvents(self, keycode):
        if keycode == key_codes.EKeyBackspace:
            self.removeFile()

    def setupItems(self):
        self.setupPaths()
        if len(self.paths) == 0:
            ui.note(U_STR(lang.NO_DOWNLOADS), 'info')
            return False
        else:
            return True    

    def showPaths(self):
        self.setupPaths()
        self.section_stack.setTop(self.PATHS_SECTION)
        self.setTitle(U_STR(lang.DOWNLOADS))
        self.setMenu([])
        self.setItems(self.paths)

    def show(self):
        if self.setupItems():
            self.items = self.paths
            self.setTitle(U_STR(lang.DOWNLOADS))
            self.enableMarquee(True)
            self.setSoftKeyLabel(uiext.EAknSoftkeyOptions, U_STR(lang.MENU))
            self.setSoftKeyLabel(uiext.EAknSoftkeyBack, U_STR(lang.BACK))            
            ListBoxWindow.show(self)
    

    def handleExit(self):
        current_section = self.section_stack.top()
        if current_section == self.PATHS_SECTION:            
            return True
        else:
            self.showPaths()
           
        return False    

class ManagementWindow(ListBoxWindow):
    def __init__(self, mainwindow):
        self.mainwindow = mainwindow
        self.downloads = DownloadsWindow()
        self.setupItems()
        ListBoxWindow.__init__(self, self.items, uiext.EDoubleListbox)

    def switchLogging(self, change_state=True):
        enabled = logger.root.isEnabledFor(logger.DEBUG)
        state_values = U_STR(lang.ENABLED), U_STR(lang.DISABLED)
        if enabled:
            lvl = 100 # higher than all levels           
            if change_state:
                logger.disable(lvl)
                self.items[-1] = (U_STR(lang.LOGGING), state_values[1])
                self.setItems(self.items, 4)
            else:
                self.items[-1] = (U_STR(lang.LOGGING), state_values[0])

        else:
            if change_state:
                logger.disable(logger.NOTSET)
                self.items[-1] = (U_STR(lang.LOGGING), state_values[0])
                self.setItems(self.items, 4)
            else:
                self.items[-1] = (U_STR(lang.LOGGING), state_values[1])

    def handleItemClicks(self, index):
        if index == 0:
            self.mainwindow.restartEngine()

        elif index == 1:
            self.mainwindow.cleanEngineCache()

        elif index == 2:
            lang_id = self.mainwindow.setupLang()
            if lang_id:
                self.mainwindow.reSetup(ignore_previous=True)
                self.reSetup()

        elif index == 3:
            self.downloads.show()

        elif index == 4:
            self.switchLogging()
    

    def setupItems(self):
        config = self.mainwindow.config
        current_lang = unicode(config.get('lang'))
        if current_lang:
            current_lang = current_lang.capitalize()
        self.items = [
                    (U_STR(lang.RESTART_ENGINE), u''),
                    (U_STR(lang.CACHE), u''),
                    (U_STR(lang.CHANGE_LANGUAGE), current_lang),                    
                    (U_STR(lang.DOWNLOADS), u''),
                    (u'', u'')]

        self.switchLogging(False)

    def reSetup(self):
        self.setup()
        self.setupItems()
        self.setItems(self.items)

    def setup(self):
        self.setTitle(U_STR(lang.MANAGE))
        self.setSoftKeyLabel(uiext.EAknSoftkeyBack, U_STR(lang.BACK))
       
    def show(self):
        self.setup()
        ListBoxWindow.show(self)

class BookmarksWindow(ListBoxWindow):
    def __init__(self, mainwindow):
        ListBoxWindow.__init__(self, [])
        self.mainwindow = mainwindow
        self.config = self.openConfig(USERCONFIG_FP)
        self.bm_items = []
        self.item_icon = ui_icons.bookmarkitem_icon
        self._copyDefBM()


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
                item = (label, u'', self.item_icon)
                if item in self.items:
                    continue         
                self.items.append(item)

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
            self.setMenu((U_STR(lang.ADD), self.addNew))
        else:
            self.setMenu([(U_STR(lang.ADD), self.addNew),
                          (U_STR(lang.EDIT), self.edit),
                          (U_STR(lang.REMOVE), self.remove),
                          (U_STR(lang.CLEAN), self.clean)])
    
       
    def openEditor(self, item=None):
        domain = 'https://mega.nz'
        if item is None:
            title, link = ('', '')
        else:
            title, link = item  
        if not link.startswith(domain):
            link = domain + link

        items = [(U_STR(lang.TITLE), 'text', unicode(title)),
                 (U_STR(lang.LINK), 'text', unicode(link))]

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
            q = ui.query(U_STR(lang.BOOKMARK_CONNOT_BE_EMPTY), 'query')
            if q:
                return self.addNew(item)
            else:
                return False
           
        if self._itemExists(item):
            q = ui.query(U_STR(lang.BOOKMARK_ALREADY_EXISTS), 'query')
            if q:
                return self.addNew(item)
            else:
                return False

        bm = self.config.get('bm') or []
        bm.insert(0, item)
        self.config.set('bm', bm)
        self.reload()      
      
    def add(self, item, update_ui=True):
        title = ui.query(U_STR(lang.TITLE_HEAD), 'text', unicode(item[0]))
        if title is None:
            return False

        item[0] = title
        if self._itemExists(item):
            q = ui.query(U_STR(lang.BOOKMARK_ALREADY_EXISTS), 'query')
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
        if ui.query(U_STR(lang.REMOVE_BOOKMARK), 'query'):
            self.config.remove('bm', item)
            self.reload()

    def clean(self):
        if ui.query(U_STR(lang.DELETE_ALL_ITEMS), 'query'):
            self.config.set('bm', [])
            self.reload()
            
    def count(self):
        self.loadItems()
        return len(self.items)

    def handleItemClicks(self, idx):
        if len(self.bm_items) == 0:return
        link = self.bm_items[idx][1]
        self.mainwindow.openBookmarkLink(link) # link

    def handleKeyEvents(self, keycode):
        if keycode == key_codes.EKeyBackspace:
            self.remove()

    def handleExit(self):
        mainwindow.reSetup()
        return False
    
    def show(self):
        self.dialog = self.mainwindow.dialog
        self.setTitle(U_STR(lang.BOOKMARKS))    
        self.setupItems()
        self.mainwindow.setMenu(self.menu_items)       
        self.mainwindow.setCurrentSection(self)

class HistoryWindow(ListBoxWindow):
    def __init__(self, mainwindow):
        ListBoxWindow.__init__(self, []) 
        self.mainwindow = mainwindow
        self.config = self.openConfig(USERCONFIG_FP)
        self.hist_items = []
        self.item_icon = ui_icons.historyitem_icon

    def loadItems(self):
        hist = self.config.get('hist')
        if hist != None:
            self.hist_items = hist
            for i in hist:
                label = unicode(i[0])
                item = (label, u'', self.item_icon)
                if item in self.items:
                    continue         
                self.items.append(item)

    def reload(self):             
        self.items = []
        self.hist_items = {}
        self.setupItems()

    def setupItems(self):
        self.loadItems()
        self.setItems(self.items)
        if self.isEmpty():    
           self.setMenu([])       
        else:
            self.setMenu([(U_STR(lang.REMOVE), self.remove), (U_STR(lang.CLEAN), self.clean)])

        
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
        logger.debug('items: %s', self.hist_items)      
        item = self.hist_items[i]
        if ui.query(U_STR(lang.REMOVE_ITEM), 'query'):
            self.config.remove('hist', item)
            self.reload()

    def clean(self):
        if ui.query(U_STR(lang.DELETE_ALL_ITEMS), 'query'):
            self.config.set('hist', [])
            self.reload()

    def count(self):
        self.loadItems()
        return len(self.hist_items)

    def handleItemClicks(self, idx):
        if len(self.hist_items) == 0:
            return

        link = self.hist_items[idx][1]
        self.mainwindow.openHistoryLink(link)

    def handleKeyEvents(self, keycode):
        if keycode == key_codes.EKeyBackspace:
            self.remove()

    def handleExit(self):
        self.mainwindow.reSetup()
        return False
    
    def show(self):
        self.dialog = self.mainwindow.dialog      
        self.setTitle(U_STR(lang.HISTORY))
        self.setupItems()
        self.mainwindow.setMenu(self.menu_items)       
        self.mainwindow.setCurrentSection(self)


class MainWindow(ListBoxWindow):
    def __init__(self): 
        self.waitDialog = None 
        self._lock = e32.Ao_lock()
        ListBoxWindow.__init__(self, [], uiext.EDoubleGraphicListbox)
        self.config = self.openConfig(USERCONFIG_FP)
        self.section_stack = WindowStack(self)        
        self.default_menu_items = []

    def setCurrentSection(self, current, previous=None):
        self.section_stack.setTop(current)       
  
    def _unLock(self):
        try:
            self._lock.signal()
        except:pass        

    def _Lock(self):
        try:
            self._lock.wait()
        except:pass

    def onCloseWaitDialog(self, btn):
        # cancel button
        if btn == -1:
            self.mmc.cancelOp()
            
        
    def showWaitDialog(self, res_id=uiext.R_WAITDIALOG_SOFTKEY_CANCEL):
        msg = U_STR(lang.PLEASE_WAIT)
        self.waitDialog = uiext.WaitDialog(res_id, msg, self.onCloseWaitDialog)      
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
            uiext.MessageQueryDialog(U_STR(lang.ABOUT), about)


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
            ui.note(u'%s %s' %(U_STR(lang.CLEANED_UP),size))
           
        else:
            fileinfo = event.get('fileinfo')
            exit_event = event.get('exit')
            server_addr = event.get('server_addr') 
            if fileinfo != None:
                self.browser.openNode(fileinfo)

            elif exit_event != None:
                self._unLock()

            elif server_addr != None: # engine started
                conf = Config(USERCONFIG_FP)
                conf.set('server_addr', server_addr)
                self._unLock()

    def handleError(self, event):       
        self.closeWaitDialog()
        fatal_error = event.get('fatal_error')      
        err_msg = event.get('error')
        tb = event.get('tb')
        if tb:
            logger.error(tb)

        if fatal_error:
            globalui.uiext.MessageQueryDialog(U_STR(lang.FATAL_ERROR), unicode(fatal_error)) 
            self._unLock()

        else:
            link = event.get('link')
            if err_msg == 'Invalid URL':
                link = None # ask user to input another link
                err_msg = U_STR(lang.INVALID_URL)

            if ui.query(u'%s\n%s'%(err_msg, U_STR(lang.RETRY)), 'query'):
                self.openLink(link)
    
    def handleItemClicks(self, idx):
        current_section = self.section_stack.top() 
        if current_section != self:
            return current_section.handleItemClicks(idx)
       
        if idx == 0:
            self.openLink()
        elif idx == 1:
            self.bookmarks.show()
        elif idx == 2:        
            self.history.show()

    def handleKeyEvents(self, keycode):
        current_section = self.section_stack.top() 
        if current_section != self:
            return current_section.handleKeyEvents(keycode)
           
    def openLink(self, link=None):
        if link is None:
            link = uiext.TextQueryDialog(U_STR(lang.ENTER_LINK))
        if link:           
            self.showWaitDialog()
            self.mmc.setEventHandler(self.event_dispatcher)           
            self.mmc.fetch(link=link)
        
    def openHistoryLink(self, link):
         self.openLink(link)

    def openBookmarkLink(self, link):
         self.openLink(link)


    def startEngine(self):
        self.showWaitDialog()
        self.mmc.setEventHandler(self.event_dispatcher)
        self.mmc.startServer()
     
    def restartEngine(self):
        self.showWaitDialog()      
        self.mmc.setEventHandler(self.event_dispatcher)
        self.mmc.restartServer()
        self._Lock()

    def stopEngine(self):
        self.showWaitDialog(uiext.R_WAITDIALOG)        
        self.mmc.setEventHandler(self.event_dispatcher)
        self.mmc.stopServer()
        self._Lock()
        #self.close()


    def cleanEngineCache(self):
        if ui.query(U_STR(lang.CLEANUP_ALL_CACHE), 'query'):
            self.showWaitDialog()
            self.mmc.cleanServerCache()

    def setupLang(self, lang_id=None):
        if lang_id is None:
            lang_list = loc_loader.available()
            idx = ui.popup_menu(lang_list, U_STR(lang.SELECT_LANGUAGE))
            if idx != None:
                lang_id = lang_list[idx]
            else:
                return

        err, _ = loc_loader.load(lang_id)
        if err:
            err_msg = unicode('Error while loading language file.\n\n%s'%err)
            uiext.MessageQueryDialog(U_STR(lang.FATAL_ERROR), err_msg)
        else:
            self.config.set('lang', lang_id)
            return lang_id

    def setupWindows(self):
        self.browser = BrowserWindow(self)
        self.bookmarks = BookmarksWindow(self)
        self.history = HistoryWindow(self)
        self.management = ManagementWindow(self)

    def setupItems(self):
        bm_count = self.bookmarks.count()
        hist_count = self.history.count()
        self.items = [
                (U_STR(lang.ENTER_MEGA_LINK), u'', ui_icons.url_icon),
                (U_STR(lang.BOOKMARKS), unicode(bm_count), ui_icons.bookmarks_icon),
                (U_STR(lang.HISTORY), unicode(hist_count), ui_icons.history_icon)
            ]

        self.default_menu_items = [
                (U_STR(lang.MANAGE), self.management.show),
                (U_STR(lang.ABOUT), self.showAboutDialog),             
                # (U_STR('Exit'), self.exit) # this dialog cannot be closed ...
            ]
 
    def reSetup(self, ignore_previous=False):
        if not ignore_previous:
            current_section = self.section_stack.top()            
            previous_section = self.section_stack.previous() 
            if previous_section != self:
                self.section_stack.remove(current_section)
                previous_section.show()
                return

        self.setCurrentSection(self)           
        self.setTitle('MegaMaru')
        self.setupItems()
        self.setItems(self.items)
        self.setMenu(self.default_menu_items)
        self.setSoftKeyLabel(uiext.EAknSoftkeyOptions, U_STR(lang.MENU))
        self.setSoftKeyLabel(uiext.EAknSoftkeyBack, U_STR(lang.BACK)) 

    def setup(self):
        server_addr = self.config.get('server_addr')
        self.event_dispatcher = AEventDispatcher(self.handleEvents, self.handleError)
        self.mmc = MegaMaruClient(server_addr, self.event_dispatcher)
        self.setupLang(self.config.get('lang'))
        self.setupWindows()
        self.setupItems()
        # soft keys of the app body
        uiext.setSoftKeyLabel(U_STR(lang.MENU), uiext.EAknSoftkeyOptions)
        uiext.setSoftKeyLabel(U_STR(lang.EXIT), uiext.EAknSoftkeyExit)
        # soft keys of the dialog
        self.setSoftKeyLabel(uiext.EAknSoftkeyOptions, U_STR(lang.MENU))
        self.setSoftKeyLabel(uiext.EAknSoftkeyBack, U_STR(lang.BACK))        
        self.startEngine()
        self._Lock()

    def show(self):
        self.setTitle('MegaMaru')
        self.mmc.setEventHandler(self.event_dispatcher)      
        self.enableMarquee(True)       
        ListBoxWindow.show(self, self.default_menu_items)
    
    def handleExit(self):
        current_section = self.section_stack.top()
        if current_section != self:
           return current_section.handleExit()
       
        if ui.query(U_STR(lang.CONFIRM_EXIT), 'query'):
            self.exit()
            return True

        return False

    def exit(self):
        self.stopEngine()

mainwindow = MainWindow()
mainwindow.setup()
e32.ao_sleep(2)
mainwindow.show()

