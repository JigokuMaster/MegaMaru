import e32, appuifw as ui
import uiext, os
from simpleutils import Config


class WindowStack:
    def __init__(self, top=None):
        self.stack = []
        if top != None:
            self.setTop(top)

    def top(self):
       if len(self.stack) > 0:
            return self.stack[0]

    def previous(self):
       if len(self.stack) > 1:
            return self.stack[1]

    def remove(self, i):
        if i in self.stack:
            self.stack.remove(i)

    def setTop(self, i):
        self.remove(i) # if already exists
        self.stack.insert(0, i)

       

class BaseWindow:
    def __init__(self):
        self.config = None
        self.menu_items = []
  
    def openConfig(self, fp):
        self.config = Config(fp)
        return self.config

    def handleExit(self):
        return True

    def handleKeyEvents(self, keycode):
        pass

    def setTitle(self, t):
        if t is None:
            return
        ui.app.title = unicode(t)

    def setMenu(self, items):
        if isinstance(items, tuple):
            self.menu_items = [items]
        elif isinstance(items, list):
            self.menu_items = items
       
        ui.app.title = self.menu_items

    def updateMenu(self, item, idx):
        items = self.menu_items
        items_l = len(items)
        if items_l and idx <= items_l:
            if item in items:
                items[idx] = item
        else:
            if not item in items:
                items.insert(idx, item)
        self.setMenu(items)

    def show(self):
        pass

    def close(self):
        pass

class ListBoxWindow(BaseWindow):
    def __init__(self, items=[], style=-1):
        BaseWindow.__init__(self)
        self.dialog = None
        self.items = items
        self.menu_items = []
        self.style = style
        self.dialog = None
        self.title = None
        self.closed = True
        self.marquee_enabled = False
        self.softkeys = {}
  
    def __onClose(self):
        self.closed = self.handleExit()
        if self.closed:
            self.dialog = None
        return self.closed

    def handleMenuEvents(self, idx):
        if idx <= len(self.menu_items):
            label, cb = self.menu_items[idx]
            if cb != None:
                cb()

    def setTitle(self, t):
        if t is None:
            return
        self.title = unicode(t)
        if self.dialog:
            self.dialog.setTitle(self.title)

    def addItem(self, item):
        if self.dialog:
            self.dialog.addItems([item])

    def removeItem(self, idx):
        if self.dialog:
            self.dialog.removeItem(idx)
 
    def clear(self):
        self.items = []
        if self.dialog:
            self.dialog.clearItems()

    def current(self):
        return self.dialog.current()

    def setFocusedItem(self, idx):
        if self.dialog:
            self.dialog.setFocusedItem(idx)

    def getCurrentItem(self):
        if not self.isEmpty():
            return self.items[self.current()]

    def setItems(self, items=[], focused_item=0):
        self.items = items
        if self.dialog:
            self.dialog.setItems(self.items, focused_item)

    def addItems(self, items):
        self.items += items
        if self.dialog:
            self.dialog.addItems(items)

    def isEmpty(self):
        if self.items != None:
            return len(self.items) == 0
        else:
            self.items = []
            return True

    def setMenu(self, items):
        if isinstance(items, tuple):
            self.menu_items = [items]
        elif isinstance(items, list):
            self.menu_items = items
       
        if self.dialog:
            self.setSoftKeyVisible(uiext.EAknSoftkeyOptions, len(self.menu_items)>0) 
            self.dialog.setMenuItems(self.menu_items)

    def enableMarquee(self, enable):
        self.marquee_enabled = enable 
        if self.dialog:
            self.dialog.enableMarquee(enabled)

    def setSoftKeyVisible(self, btn_id, visible):
        self.softkeys[btn_id] = visible
        if self.dialog:
            self.dialog.setSoftKeyVisible(btn_id, visible)

    def setupSoftKeys(self):
        if self.dialog:
            for btn_id, visible in self.softkeys.items():
                self.dialog.setSoftKeyVisible(btn_id, visible)

    def show(self, menu_items=[]):
        self.menu_items = menu_items
        no_menu = False#len(self.menu_items) == 0
        self.dialog = uiext.ListBoxDialog(self.items, self.style, self.handleItemClicks, no_menu)
        if self.title:
            self.dialog.setTitle(self.title)
      
        if self.marquee_enabled:
            self.dialog.enableMarquee(self.marquee_enabled)
        
        if len(self.menu_items):
            self.dialog.setMenuItems(self.menu_items)
        else:
            self.setSoftKeyVisible(uiext.EAknSoftkeyOptions, False) 
            
        self.dialog.setMenuCallbacks(self.handleMenuEvents)
        self.setupSoftKeys()
        self.dialog.setKeyEventsCallback(self.handleKeyEvents)
        self.dialog.setExitCallback(self.__onClose)
        self.closed = False
        return self.dialog.show()

    def close(self):
        if self.dialog:
            self.dialog.finish()
   

