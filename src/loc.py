import re, os, codecs

ENGLISH=0x0
ENTER_MEGA_LINK=0x1
BOOKMARKS=0x2
HISTORY=0x3
ABOUT=0x4
MANAGE=0x5
ENTER_LINK=0x6
CONFIRM_EXIT=0x7
CLEANUP_ALL_CACHE=0x8
RETRY=0x9
INVALID_URL=0xa
FATAL_ERROR=0xb
CLEANED_UP=0xc
DELETE_ALL_ITEMS=0xd
REMOVE_ITEM=0xe
CLEAN=0xf
REMOVE=0x10
REMOVE_BOOKMARK=0x11
BOOKMARK_ALREADY_EXISTS=0x12
TITLE_HEAD=0x13
BOOKMARK_CONNOT_BE_EMPTY=0x14
TITLE=0x15
LINK=0x16
ADD=0x17
EDIT=0x18
RESTART_ENGINE=0x19
CACHE=0x1a
DOWNLOADS=0x1b
LOGGING=0x1c
ENABLED=0x1d
DISABLED=0x1e
NO_DOWNLOADS=0x1f
FILES=0x20
SEARCH=0x21
RELOAD=0x22
ADD_BOOKMARK=0x23
GO_TO=0x24
HOME=0x25
BOOKMARK_SAVED=0x26
LOADING_ITEMS=0x27
DECRYPTING=0x28
DOWNLOAD_FAILED=0x29
DOWNLOADING=0x2a
DOWNLOAD=0x2b
DOWNLOAD_TO=0x2c
NOTICE=0x2d
NO_FREE_SPACE_TO_DOWNLOAD_THE_FILE=0x2e
FILE_ALREADY_EXISTS=0x2f
SAVE_TO=0x30
OPEN_THE_FILE_NOW=0x31
SET_AS_DEFAULT_PATH=0x32
OPEN=0x33
FILE_SAVED=0x34
SELECT_LANGUAGE=0x35
CHANGE_LANGUAGE=0x36
PLEASE_WAIT=0x37
MENU=0x38
BACK=0x39
EXIT=0x3a
DOWNLOAD_ABORTED=0x3b

def load_file(fp):
    error = None
    entries = {}
    f = None
    content = ''
    try:
        f = codecs.open(fp, 'r', encoding='utf-8')
        content = f.read()
    except Exception, e:
        return str(e), entries
    finally:
        if f:f.close()

    matches = re.findall('(\d+)\s+"([^"]*)"', content)
    entry_count = 0
    for match in matches:
        # process key
        s_key = match[0]
        if not s_key.isdigit():
            error = 'Invalid key, number expected.'
            break

        key = int(s_key)
        if key > 0:
            entry_count +=1
            if key != entry_count:
                error = 'Invalid key, incorrect order.'
                break

        # process value
        value = match[1]
        if value == '':
            error = 'Value must not be empty.'
            break
        entries[key] = value

    if error:
        error += '\nentry: %s "%s"'%match

    elif entries == {}:
        error = 'No entry was found.'

    return error, entries


class Loader:
    def __init__(self, lang_dir):
        self.lang_dir = lang_dir
        self.lang_ext = '.txt'
        self.current_lang = {}
        err, self.default_lang = self.load('english', set_current=False)

    def available(self):
        lang_ids = []
        if os.path.exists(self.lang_dir):
            for f in os.listdir(self.lang_dir):
                if f.endswith(self.lang_ext):
                    lang_id = f.split(self.lang_ext, 1)[0]
                    lang_ids.append(unicode(lang_id, 'utf-8').capitalize())    
        return lang_ids
       
    def load(self, lang_id, set_current=True):
        fn = lang_id + self.lang_ext
        fp = os.path.join(self.lang_dir, fn.lower())
        error, entries = load_file(fp)
        if set_current:
            self.current_lang = entries
        return error, entries    

    def get(self, k):
        s = self.current_lang.get(k) or self.default_lang.get(k)
        return s

#print(load_file('../lang/english.txt'))
