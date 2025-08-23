import e32, appuifw as ui
import uiext, os
from simpleutils import Config

class BaseApp:
    def __init__(self):
        self.windows = []
        self._lock = e32.Ao_lock()
        self.config = None
    
    def openConfig(self, fp):
        self.config = Config(fp)

    def putWin(self, win, index=0):
        if index <= len(self.windows):
            self.windows.insert(index, win)
            

    def removeWin(self, win, index=0):
        if win in self.windows:
            self.windows.remove(win)

    def setTopWin(self, win):
        ui.app.exit_key_handler = self.showNextWin        
        if win in self.windows:
            self.windows.remove(win)
        self.putWin(win)

    def showTopWin(self):
        ui.app.exit_key_handler = self.showNextWin        
        if len(self.windows) > 0:    
            win = self.windows[0]
            win.show()
        else:
            self.exit()

    def closeWin(self, win):
        if win in self.windows:
            self.windows.remove(win)

        self.showTopWin()    


    def showNextWin(self):     
        if len(self.windows) > 0:    
            top = self.windows[0]
            self.closeWin(top)
            self.showTopWin()
       
    def exit(self):
        self._lock.signal()

    def run(self):
        ui.app.exit_key_handler = self.showNextWin 
        self.showTopWin()
        self._lock.wait()    

class BaseWindow:
    def __init__(self,app_ctx, parent=None):
        self.app = app_ctx
        self.parent = parent

    def getAppConfig(self, fp=None):
        if fp:
            self.app.openConfig(fp)
        return self.app.config

    def setTitle(self, t):
        ui.app.title = unicode(t)

    def setMenu(self, items):
        if isinstance(items, tuple):
            ui.app.menu = [items]

        elif isinstance(items, list):
            ui.app.menu = items

    def updateMenu(self, item, idx):
        items = ui.app.menu
        items_l = len(items)
        if items_l and idx <= items_l:
            if item in items:
                items[idx] = item
        else:
            if not item in items:
                items.insert(idx, item)
        ui.app.menu = items

    def setSoftKeyLabel(self, label, id):
        try:
            uiext.setSoftKeyLabel(label, id)
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

    def setTop(self):
        if self.app:
            self.app.setTopWin(self)

    def setUI(self, ui_obj):
        ui.app.body = ui_obj

    def setExitKeyHandler(self, cb):
        ui.app.exit_key_handler = cb       

    def show(self):
        pass

    def close(self):
        if self.app:
            self.app.closeWin(self)


class ListBoxWindow(BaseWindow):
    def __init__(self,app, parent=None):      
        BaseWindow.__init__(self, app, parent=parent)
        self.items = []
        self.ui = self.setupUI()

    def setupUI(self):
        return None 

    def setItems(self, items=[], focused_item=0):
        if self.ui:
            self.items = items
            if len(items) == 0:
                self.clear(True)
            else:
                self.ui.set_list(items, focused_item)
    
    def isEmpty(self):
        if self.items != None:
            return len(self.items) == 0
        else:
            self.items = []
            return True

    def current(self):
        if self.ui:
            return self.ui.current()

    
    def getCurrentItem(self):
        if not self.isEmpty():
            return self.items[self.current()]

    def clear(self, empty=False):
        if self.ui:
            if empty:
                self.ui.set_list([u''])
            self.items = []    
            uiext.clearListBox(self.ui)
    




            

    
