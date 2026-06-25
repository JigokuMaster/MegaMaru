
prebuild:
	cd group && bldmake bldfiles gcce urel

build:
	abld build -v gcce urel

clean: 
	abld reallyclean gcce urel

APP_VER=v2.7
APP_NAME=MegaMaru
SIS="$(APP_NAME)-$(APP_VER).sis"
EXE=$(APP_NAME).exe
EXE_FP=$(EPOCROOT)/epoc32/release/gcce/urel/$(EXE)

mksis:
	cd sis && PLATFORM=gcce TARGET=urel makesis -v -d$(EPOCROOT) $(APP_NAME).pkg $(SIS) 

mksisx:
	cd sis && signsis $(SIS) $(SIS)x mycert.cer mykey.key

depoly:
	renv send "sis/$(SIS)" "C:\\$(SIS)"
	renv send "sis/$(SIS)x" "C:\\$(SIS)x"
run:
	renv send "$(EXE_FP)" "C:\\sys\\bin\\$(EXE)"
	renv start -w $(EXE)

