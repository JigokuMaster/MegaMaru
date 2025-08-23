
set -e


PY_PATH=$(realpath ~/Python-2.2.2)

BIN_PATH=$PY_PATH/build/lib.linux-aarch64-2.2

CFLAGS="-O3 -shared -fPIC -DHAVE_CONFIG_H \
    -I$PY_PATH/Include \
    -I$PY_PATH \
    -I./src"

LDFLAGS="-L$PY_PATH -lpython2.2"

gcc $CFLAGS \
    src/AES.c \
    $LDFLAGS \
    -o $BIN_PATH/_AES.so

gcc $CFLAGS \
    src/_counter.c \
    $LDFLAGS \
    -o $BIN_PATH/_counter.so


# cp -R lib/Crypto $PY_PATH//Lib/site-packages
# python2 test_aes.py

