# Copyright (c) 2008 - 2009 Nokia Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

ifeq (WINS,$(findstring WINS, $(PLATFORM)))
ZDIR=$(EPOCROOT)\epoc32\release\$(PLATFORM)\$(CFG)\z
else
ZDIR=$(EPOCROOT)\epoc32\data\z
endif

ICONTARGETFILENAME=$(ZDIR)\resource\apps\MegaMaru_aif.mif

ICONSTARGETFILENAME=$(ZDIR)\resource\apps\MegaMaru_ui.mif



do_nothing :
	@rem do_nothing

MAKMAKE : do_nothing

BLD : do_nothing

CLEAN : do_nothing

LIB : do_nothing

CLEANLIB : do_nothing

RESOURCE :
	mifconv $(ICONTARGETFILENAME) \
		/c32 icons/Menu.svg

	mifconv $(ICONSTARGETFILENAME) \
		/hicons\ui.h /Ficons\ui.miflist

FREEZE : do_nothing

SAVESPACE : do_nothing

RELEASABLES :
	@echo $(ICONTARGETFILENAME)

FINAL : do_nothing
