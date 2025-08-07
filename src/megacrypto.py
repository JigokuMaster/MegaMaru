from Crypto.Cipher import AES
from Crypto.Util import Counter
import simplejson as json
import base64
import struct
import binascii
import random
import sys

# Python3 compatibility
if sys.version_info < (3, ):

    def makebyte(x):
        return x

    def makestring(x):
        return x
else:
    import codecs

    def makebyte(x):
        return codecs.latin_1_encode(x)[0]

    def makestring(x):
        return codecs.latin_1_decode(x)[0]
      
def aes_cbc_encrypt(data, key):
    aes_cipher = AES.new(key, AES.MODE_CBC, makebyte('\0' * 16))
    return aes_cipher.encrypt(data)


def aes_cbc_decrypt(data, key):
    aes_cipher = AES.new(key, AES.MODE_CBC, makebyte('\0' * 16))
    return aes_cipher.decrypt(data)


def aes_cbc_encrypt_a32(data, key):
    return str_to_a32(aes_cbc_encrypt(a32_to_str(data), a32_to_str(key)))


def aes_cbc_decrypt_a32(data, key):
    return str_to_a32(aes_cbc_decrypt(a32_to_str(data), a32_to_str(key)))


def stringhash(str, aeskey):
    s32 = str_to_a32(str)
    h32 = [0, 0, 0, 0]
    for i in range(len(s32)):
        h32[i % 4] ^= s32[i]
    for r in range(0x4000):
        h32 = aes_cbc_encrypt_a32(h32, aeskey)
    return a32_to_base64((h32[0], h32[2]))


def prepare_key(arr):
    pkey = [0x93C467E3, 0x7DB0C7A4, 0xD1BE3F81, 0x0152CB56]
    for r in range(0x10000):
        for j in range(0, len(arr), 4):
            key = [0, 0, 0, 0]
            for i in range(4):
                if i + j < len(arr):
                    key[i] = arr[i + j]
            pkey = aes_cbc_encrypt_a32(pkey, key)
    return pkey


def encrypt_key(a, key):
    pass

def decrypt_key(a, key):
    keys = []
    for i in range(0, len(a), 4):
        k = aes_cbc_decrypt_a32(a[i:i + 4], key)
        keys += k
    
    return tuple(keys) # sum(keys) ????



def encrypt_attr(attr, key):
    attr = makebyte('MEGA' + json.dumps(attr))
    if len(attr) % 16:
        attr += '\0' * (16 - len(attr) % 16)
    return aes_cbc_encrypt(attr, a32_to_str(key))


def decrypt_attr(attr, key):
    attr = aes_cbc_decrypt(attr, a32_to_str(key))
    attr = makestring(attr)
    attr = attr.rstrip('\0')
    if attr[:6] == 'MEGA{"':
        return json.loads(attr[4:])
    else: 
        return False


def a32_to_str(a):
    return struct.pack('>%dI' % len(a), *a)


def str_to_a32(b):
    if isinstance(b, str):
        b = makebyte(b)
    if len(b) % 4:
        # pad to multiple of 4
        b += '\0' * (4 - len(b) % 4)
    return struct.unpack('>%dI' % (len(b) / 4), b)


def mpi_to_int(s):
    """
    A Multi-precision integer is encoded as a series of bytes in big-endian
    order. The first two bytes are a header which tell the number of bits in
    the integer. The rest of the bytes are the integer.
    """
    return int(binascii.hexlify(s[2:]), 16)


def extended_gcd(a, b):
    if a == 0:
        return (b, 0, 1)
    else:
        g, y, x = extended_gcd(b % a, a)
        return (g, x - (b // a) * y, y)


def modular_inverse(a, m):
    g, x, y = extended_gcd(a, m)
    if g != 1:
        raise Exception('modular inverse does not exist')
    else:
        return x % m


def base64_url_decode(data):
    data += '=='[(2 - len(data) * 3) % 4:]
    for search, replace in (('-', '+'), ('_', '/'), (',', '')):
        data = data.replace(search, replace)
    return base64.decodestring(data)


def base64_to_a32(s):
    return str_to_a32(base64_url_decode(s))


def base64_url_encode(data):
    data = base64.encodestring(data)
    data = makestring(data)
    for search, replace in (('+', '-'), ('/', '_'), ('=', '')):
        data = data.replace(search, replace)
    return data


def a32_to_base64(a):
    return base64_url_encode(a32_to_str(a))

def a32_encode(a):
    return a32_to_base64(a)
    #return base64.encodestring(a32_to_str(a))

def a32_decode(s):
    return base64_to_a32(s.replace('\n', ''))
    #return str_to_a32(base64.decodestring(s))


def make_chunk_decryptor(key, iv, meta_mac):
    k_str = a32_to_str(key)
    counter = Counter.new(128, initial_value=((iv[0] << 32) + iv[1]) << 64)
    return AES.new(k_str, AES.MODE_CTR, counter=counter)


def decrypt_file(fi, fo, file_info):
    file_size = file_info['size']
    file_key = file_info['key']
    iv = file_info['iv']
    meta_mac = file_info['meta_mac']
    chunk_decryptor = make_chunk_decryptor(file_key, iv, meta_mac)
    
    chunk_size = 0x20000
    
    while True:
        chunk = fi.read(chunk_size)
        if not chunk:
            break
        
        chunk = chunk_decryptor.decrypt(chunk)
        fo.write(chunk)

 


def get_chunks(size):
    pass
#    p = 0
#    s = 0x20000
#    while p + s < size:
#        yield (p, s)
#        p += s
#        if s < 0x100000:
#            s += 0x20000
#    yield (p, size - p)


def make_id(length):
    text = ''
    possible = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    for i in range(length):
        text += random.choice(possible)
    return text


