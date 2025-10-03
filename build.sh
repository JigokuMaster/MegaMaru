#!/bin/bash

set -e

bldmake bldfiles gcce urel

abld build -v gcce urel

makesis -v -d$EPOCROOT MegaMaru.pkg MegaMaru.sis
ver=v2.5
signsis MegaMaru.sis MegaMaru-$ver.sisx mycert.cer mykey.key
