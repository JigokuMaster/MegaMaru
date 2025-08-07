from httplib import HTTPConnection, HTTPS_PORT
import socket, os, tls

USE_TLS_CONNECT = False
try:
    import e32
    USE_TLS_CONNECT = e32.pys60_version_info[:3] == (1, 4, 5)
except:
    pass


class TLSWrapper:
    def __init__(self, addr, socket_fd):
        self.init_tls(addr, socket_fd)

    def close(self):
        self.tls_obj.close()

    def init_tls(self, addr, socket_fd):
        self.tls_obj = tls.init(addr, socket_fd)

        err = self.tls_obj.handshake()

        if err != 0:
            self.close()
            raise Exception("tls.handshake() error: %d"%err)


    def write(self, data):
        r = self.tls_obj.write(data)
        if r <= 0:
            self.close()
            raise Exception("tls.write() error: %d"%r)
        return r 
    
    def readAll(self):
        data = []
        while True:
            data.append(self.tls_obj.read())
            r = self.tls_obj.getError()
            if r < 0:
                self.close()
                raise Exception("tls.read() error: %d"%r)
            if r == 0: #EOF
                break
        return ''.join(data)
 
    def read(self, rlen=-1):
        # print 'TLSWrapper.read(%s)' %rlen
        if rlen < 1:
            return self.readAll()
        else:
            data = self.tls_obj.read(rlen)
            r = self.tls_obj.getError()
            if r < 0:
                self.close()
                raise Exception("tls.read() error: %d"%r)
            else:
                return data

    def getError(self):
        return self.tls_obj.getError()



class TLSFile:

    BUFSIZE = 8192

    def __init__(self, sock, bufsize=None):
        self.sock = sock
        self._buf = ''
        self._bufsize = bufsize or self.__class__.BUFSIZE

    def close(self):
        pass

    def read(self, size=-1):
        return self.sock.recv(size)

    def write(self, data):
        return self.sock.send(data)


    def readline(self):
        L = [self._buf]
        self._buf = ''
        while 1:
            i = L[-1].find("\n")
            if i >= 0:
                break
            s = self.read(1)
            if s == '':
                break
            L.append(s)
        if i == -1:
            return "".join(L)
        else:
            all = "".join(L)
            i = all.find("\n") + 1
            line = all[:i]
            self._buf = all[i:]
            return line

class TLSSocket:
    def __init__(self, host, port, sock, sock_fd):
        self.io_closed = False
        self.sock = sock
        self.sock_fd = sock_fd
        self._tls = TLSWrapper(host, sock_fd)

    def close_io(self):
        if self.sock != None:
            self.sock.close()
        else:
            os.close(self.sock_fd)
            
        if self._tls:
            self._tls.close()
        self.io_closed = True

    def __del__(self):
        if not self.io_closed:
            try:
                self.close_io()
            except:pass    

    def close(self):
        pass

    def makefile(self, mode, bufsize=None):
        return TLSFile(self, bufsize)

    def send(self, stuff, flags = 0):
        return self._tls.write(stuff)

    sendall = send

    def recv(self, rlen = 1024, flags = 0):
        return self._tls.read(rlen)


class HTTPSConnection(HTTPConnection):

    default_port = HTTPS_PORT

    def __init__(self, host, port=None, key_file=None, cert_file=None):
        HTTPConnection.__init__(self, host, port)
        self.key_file = key_file
        self.cert_file = cert_file
        self.timeout = 25

    def connect(self):
        sock = None
        sock_fd = -1
        if USE_TLS_CONNECT:
            ip_addr =  socket.gethostbyname(self.host)
            sock_fd = tls.connect(ip_addr, self.port)
        else:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # sock.settimeout(self.timeout)
            sock.connect((self.host, self.port))
            sock_fd = sock.fileno()

        self.sock = TLSSocket(self.host, self.port, sock, sock_fd)

    def shutdown(self):
        if self.sock:
            try:
                self.sock.close_io()
            except:pass    
        self.close()
            
