set -e

smake

makesis -v -d$EPOCROOT MegaMaru.pkg MegaMaru.sis

signsis MegaMaru.sis MegaMaru.sisx mycert.cer mykey.key
