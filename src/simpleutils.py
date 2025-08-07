import os, httpslib, urllib, time, sys, re
from urlparse import urlparse
from threading import Lock
import logging as log

SIZE_UNITS = ['B', 'KB', 'MB', 'GB', 'TB']
def hsize(size):
    for unit in SIZE_UNITS:
        if size < 1024.0:
            return "%3.1f %s" % (size, unit)
        size /= 1024.0

def clean_filename(fn):
    fn = re.sub(r'[<>:"/\\|?*]', '', fn).strip()
    if len(fn) == 0:
        return '_'
    return fn

def parseExceptionMsg(e, r=True):
    def findMsg(args, r=True):
        for arg in args:
            if isinstance(arg, str):
                return arg

            elif isinstance(arg, tuple):
                if r:
                    return findMsg(arg, False)
                
            elif isinstance(arg, BaseException) or hasattr(arg, 'args'):
                if r:
                    return parseExceptionMsg(arg, False)


    no_msg = 'Unknown Error Message'
    args = e.args or []
    if hasattr(e, 'message'):
        msg = e.message
        if isinstance(msg, tuple):
            args = msg
        elif isinstance(msg, str):
            if msg:return msg

    msg = findMsg(args) or no_msg
    return msg            
    
class OpState:
    OP_FINISHED = 0
    OP_RUNNING = 1
    OP_ABORTED = 2

    def __init__(self):
        self._lock = Lock()
        self._state = -1

    def get(self):
        self._lock.acquire()
        try:
            return self._state
        finally:
            self._lock.release()


    def set(self, v):
        self._lock.acquire()
        try:
            self._state = v
        finally:
            self._lock.release()

    def reset(self):
        self.set(-1)

    def check(self, v):
        return self.get() == v



ERRMSG_EMPTY_FILE_FOUND = 'remote file is empty'
ERRMSG_LOCAL_FILE_FOUND = 'file is already downloaded'
ERRMSG_ACCEPTRANGES_NOT_SUPPORTED = 'accept-ranges not supported'
ERRMSG_INVALID_FILETYPE = 'filetype not allowed'
class PyDownloader:
    DOWNLOAD_STARTED = 0 
    DOWNLOAD_FAILED = 1
    DOWNLOAD_ABORTED = 2
    DOWNLOAD_ING = 3
    DOWNLOAD_DONE = 4
    REQUESTING_FILEINFO = 5
    REQUEST_FAILED = 6
    DOWNLOAD_ABORTED_BY_USER = 7
    
    def __init__(self, path=None, bufsize=None, state_listener=None):
        self.state = -1
        self.dl_path = path
        self.chunk_size = bufsize or 8192
        self.state_listener = state_listener
        self.conn = None
        
    def abort(self):
        self.state = self.DOWNLOAD_ABORTED_BY_USER 
        if self.conn:
            # close TCP socket
            self.conn.shutdown()
  
    def _stateChanged(self,state, **params):
        self.state = state
        if self.state_listener:
            if self.state != self.DOWNLOAD_ABORTED_BY_USER:
                self.state_listener(self.state, params)


    def doRequest(self, method, host, path, headers={}, follow_redirect=True):
        try:
            parts = host.split(':')
            port = None
            if len(parts) == 2:
                host = parts[0]
                port = int(parts[1])
            self.conn = httpslib.HTTPSConnection(host, port)
            self.conn.request(method, path, headers=headers)
            resp = self.conn.getresponse()
            info = resp.msg
            if resp.status == 302:
                self.conn.shutdown()
                ref = 'https://%s%s' %(host, path)
                loc = info.get('location')
                url_parts = urlparse(loc)
                host = url_parts[1]
                path = url_parts[2]
                headers['referer'] = ref
                return self.doRequest(method, host, path, headers=headers, follow_redirect=False)
                
        except Exception, e:
            self._stateChanged(self.REQUEST_FAILED, error=parseExceptionMsg(e))
            return None, None

     
        return self.conn, resp 
    
    def requestOK(self, conn, resp):
        if resp.status != 200:
            conn.shutdown()
            return False

        return True


    def check_remote_fileinfo(self, host, path):
        self._stateChanged(self.REQUESTING_FILEINFO)
        conn , resp = self.doRequest('HEAD', host, path)
        if conn is None:
            return None

        resp_status = resp.status, resp.reason
        info = resp.msg
        conn.shutdown()

        if resp_status[0] != 200:
            self._stateChanged(self.state, error=resp_status)
            log.error('cannot download file %s', resp_status)
            return None

        return info

    def check_local_fileinfo(self, file_name):
        fp = file_name
        if self.dl_path:
            if not os.path.exists(self.dl_path):
                os.mkdir(self.dl_path)

            fp = os.path.join(self.dl_path, file_name)

        file_size = 0 
        if os.path.exists(fp):
            file_size = os.path.getsize(fp)
        return fp, file_size


    def download_file(self, link, file_name, file_size, content_len=0, content_type='application/', overwrite=False):
        url_parts = urlparse(link)
        host = url_parts[1]
        path = url_parts[2]
        conn, resp = None, None
        headers = {}
        info = {}
        fo = None
        fo_mode = 'wb'
        fo_exists = False
       
        if content_len < 1:
            # do HEAD request
            info = self.check_remote_fileinfo(host, path)
            if info is None:
                return False

        if file_name:
            fp, file_size = self.check_local_fileinfo(file_name)
            fo_exists = file_size > 0


        else:
            # check remote filename 
            fn_parts = info.get('content-disposition', '').split('filename=')

            if len(fn_parts) > 1:
                file_name = clean_filename(fn_parts[1].rstrip(';'))
                log.debug('using remote filename: %s', file_name)
                fp, file_size = self.check_local_fileinfo(file_name)


            else:
                if '/' in path:
                    file_name = clean_filename(path.split('/')[-1])

                else:
                    file_name = clean_filename(path)

                log.debug('using url path as filename: %s', file_name)
                fp, file_size = self.check_local_fileinfo(file_name)
            
            fo_exists = file_size > 0
    

        # read remote file info using GET
        if info == {}:
            if (not overwrite) and (fo_exists):
                if file_size < content_len:
                    headers['Range'] = 'bytes=%d-'%file_size

            self._stateChanged(self.REQUESTING_FILEINFO)
            conn, resp = self.doRequest('GET', host, path, headers=headers)
            if conn is None:
                return False

            info = resp.msg # headers
            if (not overwrite) and (resp.status == 206):
                fo_mode = 'ab'
                content_len = int(info.get('content-length', -1))
                if content_len == 0:
                    self._stateChanged(self.DOWNLOAD_ABORTED, msg=ERRMSG_EMPTY_FILE_FOUND)
                    conn.shutdown()
                    return False
            
                if file_size >= content_len:
                    self._stateChanged(self.DOWNLOAD_ABORTED, msg=ERRMSG_LOCAL_FILE_FOUND)
                    conn.shutdown()
                    return False
                
            else:
                file_size = 0
                log.error(ERRMSG_ACCEPTRANGES_NOT_SUPPORTED)
                #conn.shutdown()
                #return


        else:
            # process HEAD response headers 
            content_len = int(info.get('content-length', -1))
            if content_len == 0:
                self._stateChanged(self.DOWNLOAD_ABORTED, msg=ERRMSG_EMPTY_FILE_FOUND)

                return False

            if (not overwrite) and fo_exists:
                if info.get('accept-ranges') == 'bytes':
                    if file_size < content_len:
                        headers['range'] = 'bytes=%d-'%file_size 
                        fo_mode = 'ab'

                    elif file_size >= content_len:
                        self._stateChanged(self.DOWNLOAD_ABORTED, msg=ERRMSG_LOCAL_FILE_FOUND)
                        return False

                else:
                    log.warn(ERRMSG_ACCEPTRANGES_NOT_SUPPORTED)

        if content_type != None:
            if not info.get('content-type', '').startswith(content_type):
                log.error(ERRMSG_INVALID_FILETYPE)
                self._stateChanged(self.DOWNLOAD_ABORTED, msg=ERRMSG_INVALID_FILETYPE)
                if conn:
                    conn.shutdown()
                return False


        if conn is None:
            conn, resp = self.doRequest('GET', host, path, headers=headers)
            if conn is None:
                return False

            info = resp.msg
            resp_status = resp.status, resp.reason
 
            log.debug('status: %s', resp_status)
            log.debug('headers: %s', info)
            if not resp_status[0] in [200, 206]:
                self._stateChanged(self.DOWNLOAD_ABORTED, error=resp_status)
                conn.shutdown()
                return False


        if content_len == -1:
            content_len = int(info.get('content-length', 0))


        error = None
        to_download = content_len-file_size
        downloaded = 0 
        
        try:
            fo = open(fp, fo_mode)
        except Exception, e:
            self._stateChanged(self.DOWNLOAD_ABORTED, error=parseExceptionMsg(e))
            conn.shutdown()
            return False


        self._stateChanged(self.DOWNLOAD_STARTED, name=file_name, size=content_len, fp=fp)
        while True:
            if content_len > 0:
                if downloaded >= to_download:
                    self._stateChanged(self.DOWNLOAD_DONE)
                    break

            if self.state in [self.DOWNLOAD_ABORTED, self.DOWNLOAD_ABORTED_BY_USER]:
                self._stateChanged(self.state)
                return False

            try:
                chunk = resp.read(self.chunk_size)
                chunk_len = len(chunk)
                if chunk_len == 0:
                    self._stateChanged(self.DOWNLOAD_DONE)
                    break
                
                downloaded += chunk_len
                # rb=read bytes, db=downloaded bytes, tb=total bytes
                self._stateChanged(self.DOWNLOAD_ING, rb=chunk_len, tb=to_download, db=downloaded)
                fo.write(chunk)

            except Exception, e:
                error = parseExceptionMsg(e)
                break

        fo.close()
        conn.shutdown()
        if error:
            self._stateChanged(self.DOWNLOAD_FAILED, error=error)
            return False

        return True


    
    
