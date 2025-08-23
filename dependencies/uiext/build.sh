set -e

smake

cp $EPOCROOT/epoc32/release/gcce/urel/kf_uiext.pyd bin

cp $EPOCROOT/epoc32/release/gcce/urel/uiext.pyd bin

cp $EPOCROOT/epoc32/data/z/resource/apps/uiext.rsc bin