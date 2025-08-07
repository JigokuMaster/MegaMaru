import os, httpslib, urllib, re, random
from threading import Lock
from megacrypto import*
import simplejson as json
from simpleutils import OpState


class ValidationError(Exception):
    """
    Error in validation stage
    """
    pass


_CODE_TO_DESCRIPTIONS = {
    -1: ('EINTERNAL',
         ('An internal error has occurred. Please submit a bug report, '
          'detailing the exact circumstances in which this error occurred')),
    -2: ('EARGS', 'You have passed invalid arguments to this command'),
    -3: ('EAGAIN',
         ('(always at the request level) A temporary congestion or server '
          'malfunction prevented your request from being processed. '
          'No data was altered. Retry. Retries must be spaced with '
          'exponential backoff')),
    -4: ('ERATELIMIT',
         ('You have exceeded your command weight per time quota. Please '
          'wait a few seconds, then try again (this should never happen '
          'in sane real-life applications)')),
    -5: ('EFAILED', 'The upload failed. Please restart it from scratch'),
    -6:
    ('ETOOMANY',
     'Too many concurrent IP addresses are accessing this upload target URL'),
    -7:
    ('ERANGE', ('The upload file packet is out of range or not starting and '
                'ending on a chunk boundary')),
    -8: ('EEXPIRED',
         ('The upload target URL you are trying to access has expired. '
          'Please request a fresh one')),
    -9: ('ENOENT', 'Object (typically, node or user) not found'),
    -10: ('ECIRCULAR', 'Circular linkage attempted'),
    -11: ('EACCESS',
          'Access violation (e.g., trying to write to a read-only share)'),
    -12: ('EEXIST', 'Trying to create an object that already exists'),
    -13: ('EINCOMPLETE', 'Trying to access an incomplete resource'),
    -14: ('EKEY', 'A decryption operation failed (never returned by the API)'),
    -15: ('ESID', 'Invalid or expired user session, please relogin'),
    -16: ('EBLOCKED', 'User blocked'),
    -17: ('EOVERQUOTA', 'Request over quota'),
    -18: ('ETEMPUNAVAIL',
          'Resource temporarily not available, please try again later'),
    -19: ('ETOOMANYCONNECTIONS', 'many connections on this resource'),
    -20: ('EWRITE', 'Write failed'),
    -21: ('EREAD', 'Read failed'),
    -22: ('EAPPKEY', 'Invalid application key; request not processed'),
}


class RequestError(Exception):
    """
    Error in API request
    """
    def __init__(self, message):
        code = message
        self.code = code
        code_desc, long_desc = _CODE_TO_DESCRIPTIONS[code]
        self.message = ', '.join((code_desc, long_desc))

    def __str__(self):
        return self.message


class MegaService:

    def __init__(self, cache_dir='tmp'):
        self.cache_dir = cache_dir
        self.api_domain = 'g.api.mega.co.nz'
        self.sid = None
        self.sequence_num = random.randint(0, 0xFFFFFFFF)
        # self.request_id = make_id(10)
        self.op_state = OpState()
        self.conn = None

    def cancelOp(self):
        self.op_state.set(OpState.OP_ABORTED)
        if self.conn:
            self.conn.shutdown()

        
    def cacheData(self, fn, data, isjson=False):
        if not os.path.exists(self.cache_dir):
            os.mkdir(self.cache_dir)

        fp = os.path.join(self.cache_dir, fn)
        f = open(fp, 'w')
        if isjson:
            json.dump(data, f)
        else:
            f.write(data)
        f.close()

    def getCachedData(self, fn, isjson=False):
        if not os.path.exists(self.cache_dir):
            return

        fp = os.path.join(self.cache_dir, fn)
        if not os.path.exists(fp):
            return

        data = None
        f = open(fp, 'r')
        if isjson:
            try:
                data = json.load(f)
            except:
                pass
        else:
            data = f.read()
        f.close()
        return data


    def removeCachedData(self, fn):
        if not os.path.exists(self.cache_dir):
            return

        for f in os.listdir(self.cache_dir):
            fp = os.path.join(self.cache_dir, f)
            if f.startswith(fn) and os.path.isfile(fp):
                os.remove(fp)


    # Source: https://stackoverflow.com/questions/64488709/how-can-i-list-the-contents-of-a-mega-public-folder-by-its-shared-url-using-meg
    def decrypt_node_key(self, key_str, shared_key):
        if key_str.find(':') > 0:
            encrypted_key = base64_to_a32(key_str.split(":")[1])
        else:
            encrypted_key = base64_to_a32(key_str)

        return decrypt_key(encrypted_key, shared_key)

    def _mk_file_info(self, f, node_id, root_id, root_key, shared_key):
        ft = f['t']
        if not ft in [0, 1]:
            raise 'unknow file type: %s' %ft

        k = f['k']
        info = {
            'id': f['h'],
            't': ft,
            'size': 0,
            'parent_id': node_id,
            'root_id': root_id,
            'root_key': root_key,
            'key': None
           }

        if not k:
            if ft == 0:
                info['name'] = 'undecrypted file'
            elif ft == 1:
                info['name'] = 'undecrypted folder'
            return info    

        key = self.decrypt_node_key(k, shared_key)
        k = key
        if ft == 0: # Is a file
           if  len(key) < 8:
                info['name'] = 'undecrypted file'
                info.append(info_item)
                return info

           k = (key[0] ^ key[4], key[1] ^ key[5], key[2] ^ key[6], key[3] ^ key[7])
           info['size'] = f['s']
           info['iv'] = a32_encode(key[4:6] + (0, 0))
           info['meta_mac'] = a32_encode(key[6:8])
        
        attrs = decrypt_attr(base64_url_decode(f['a']) , k)
        info['name'] = attrs['n']
        info['key'] = a32_encode(k)
        return info

    def list_node_files(self, node_data, node_id, root_id, root_key):
        self.op_state.set(OpState.OP_RUNNING)
        info = []
        shared_key = base64_to_a32(root_key)
        root_info = self._mk_file_info(node_data.pop(0), node_id, root_id, root_key, shared_key)
        info.append(root_info)
        for f in node_data:
            if self.op_state.check(OpState.OP_ABORTED):
                return None

            if f['h'] == node_id:
                # add parent info to the root info
                parent_node = self._mk_file_info(f, node_id, root_id, root_key, shared_key)
                info[0]['parent_node'] = parent_node
                continue

            if f['p'] != node_id:
                continue
           
            file_info = self._mk_file_info(f, node_id, root_id, root_key, shared_key)        
            info.append(file_info)
            
        self.op_state.set(OpState.OP_FINISHED)
        return info

    def getNodeFolderInfo(self, folder_id, root_id, root_key):
        cache_fn = ';'.join((root_id, folder_id))
        json_data = self.getCachedData(cache_fn, isjson=True)
        if json_data != None:
            return json_data
 
        json_data = self.getCachedData(root_id, isjson=True)
        if json_data is None:
            params = {'n': root_id}
            data = [{"a": "f", "c": 1, "k": 1, "ca": 1, "r": 1, "ssl": 1}]
            json_data = self._api_request(params, data)
            self.cacheData(root_id, json_data, isjson=True)
         

        node_data = json_data['f']
        info = self.list_node_files(node_data, folder_id, root_id, root_key)
        if info != None:
            self.cacheData(cache_fn, info, isjson=True)
        return info


    def getFolderInfo(self, url):
        folder_id, folder_key = self.parseUrl(url).get('folder')
        cache_fn = ';'.join((folder_id, folder_key))
        json_data = self.getCachedData(cache_fn, isjson=True)
        if json_data != None:
            return json_data

        json_data = self.getCachedData(folder_id, isjson=True)

        if json_data is None:
            params = {'n': folder_id}
            data = [{"a": "f", "c": 1, "ca": 1, "k": 1, "r": 1, "ssl": 1}]
            json_data = self._api_request(params, data)
            self.cacheData(folder_id, json.dumps(json_data))


        root_handle = json_data['f'][0]['h']
        node_data = json_data['f']
        info = self.list_node_files(node_data, root_handle, folder_id, folder_key)
        if info != None:
            self.cacheData(cache_fn, info, isjson=True)
        return info


    def getNodeFileInfo(self, file_id, file_key, parent_id, root_id):
        params = {'n': root_id}
        # data = [{"a": "g", "g": 1, "n": file_id, "v": 2, "ssl": 1 }]
        data = [{"a": "g", "g": 1, "n": file_id, "ssl": 1 }]
        json_data = self._api_request(params, data)
        if 'g' not in json_data:
            raise RequestError('File not accessible anymore')
       
        attrs = decrypt_attr(base64_url_decode(json_data['at']), file_key)
        return {
                'name': attrs['n'],
                'size': json_data['s'],
                'id': file_id,
                'key': file_key,
                'dllink': json_data['g']
                }


    def getFileInfo(self, url):
        file_id, file_key = self.parseUrl(url).get('file')
        data = [{"a": "g", "g": 1, "p": file_id, "ssl": 1}]
        json_data = self._api_request(data=data)
        if 'g' not in json_data:
            raise RequestError('File not accessible anymore')

        file_key = base64_to_a32(file_key)
        k = (file_key[0] ^ file_key[4], file_key[1] ^ file_key[5], file_key[2] ^ file_key[6], file_key[3] ^ file_key[7]) 
        attrs = decrypt_attr(base64_url_decode(json_data['at']), k)     
        return {
                'name': attrs['n'],
                'size': json_data['s'],
                'id': file_id,
                'key': a32_encode(k),
                'iv': a32_encode(k[4:6] + (0, 0)),
                'meta_mac': a32_encode(k[6:8]),
                'dllink': json_data['g']
                }

    def _testURLMatch(self, g, g_len, ex):
        test_failed = len(g) < g_len
        if test_failed:
            raise ex

    def parseUrl(self, url):
        info = {}
        ex = Exception('Invalid URL')
        m = re.match(r'(.*)/#!(.*)!(.*)', url)
        if m:
            g = m.groups()
            self._testURLMatch(g, 3, ex)
            id = g[1] 
            key = g[2]                 
            return {'file': [id, key]}


        v2_pattern = r'(.*)/(file|folder)/(\w\w\w\w\w\w\w\w\W)(.*)'
        v2_sub_pattern = r'(.*)/(file|folder)/(\w\w\w\w\w\w\w\w)'
        m = re.match(v2_pattern, url)
        if m:
            g = m.groups()
            self._testURLMatch(g, 3, ex)
            t = g[1]
            id = g[2][:8]
            rest = g[3]
            if not t in ['file', 'folder']:
                raise ex

            m = re.match(v2_sub_pattern, rest)
            if m:
                g = m.groups()
                self._testURLMatch(g, 3, ex)
                info[t] = [id, g[0]]
                t = g[1]
                if not t in ['file', 'folder']:
                    raise ex

                info['sub'] = {t: g[2]}

            else:
                info[t] = [id, rest]
        else:
            raise ex
        
        return info


    def _api_request(self, params={}, data={}):
        json_data = json.dumps(data)
        content_len = len(json_data)
        self.conn = httpslib.HTTPSConnection(self.api_domain)
 
        headers = {
                'accept': 'application/json',

                'Content-type': 'application/json',

                'Content-lenght': content_len,

                }

        params['id']=self.sequence_num
        self.sequence_num += 1
        req_path = '/cs?' + urllib.urlencode(params)
        self.conn.request('POST', req_path, body=json_data, headers=headers)
        
        resp = self.conn.getresponse()
        resp_headers = resp.msg
        body = resp.read()
        json_resp = json.loads(body)
        self.conn.shutdown()
        self.conn = None
        int_resp = None
        try:
            if isinstance(json_resp, list):
                if isinstance(json_resp[0], int):
                    int_resp = json_resp[0]

            elif isinstance(json_resp, int):
                int_resp = json_resp
        except IndexError:
            int_resp = None

        if int_resp is not None:
            if int_resp == 0:
                return int_resp

            raise RequestError(int_resp)

        return json_resp[0]


