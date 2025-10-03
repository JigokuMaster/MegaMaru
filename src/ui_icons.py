from appuifw import Icon

ICONS_FP = u'\\Resource\\Apps\\MegaMaru_ui.mif'

def icon(_id):
    return Icon(ICONS_FP, _id, _id+1) # +1 for the mask

# returns an icon based on the file extention
def icon_for(fn):
    ext = fn.split('.')[-1]
    icon = file_icon
    if ext:
        attr = globals().get(ext + '_icon')
        if attr != None:
            icon = attr         
    return icon    


opa_icon = icon(16384)
opo_icon = icon(16386)
sis_icon = icon(16388)
sisx_icon = icon(16390)
file_icon = icon(16392)
folder_icon = icon(16394)
txt_icon = icon(16396)
jar_icon = icon(16398)
wgz_icon = icon(16400)
url_icon = icon(16402)
bookmarks_icon = icon(16404)
history_icon = icon(16406)
bookmarkitem_icon = icon(16408)
historyitem_icon = icon(16410)

