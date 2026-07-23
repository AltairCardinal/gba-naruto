TARGET          :=  butano-sequel
BUILD           :=  build
LIBBUTANO       :=  ../third_party/butano/butano
PYTHON          :=  python3
SOURCES         :=  src benchmark/src game/src
INCLUDES        :=  include benchmark/include game/include ../third_party/butano/common/include
DATA            :=
GRAPHICS        :=  graphics ../third_party/butano/common/graphics
AUDIO           :=  audio
AUDIOBACKEND    :=  maxmod
AUDIOTOOL       :=
DMGAUDIO        :=
DMGAUDIOBACKEND :=  null
ROMTITLE        :=  KONOHA BASE
ROMCODE         :=  KNBT
USERFLAGS       :=
USERCXXFLAGS    :=
USERASFLAGS     :=
USERLDFLAGS     :=
USERLIBDIRS     :=
USERLIBS        :=
DEFAULTLIBS     :=
STACKTRACE      :=
USERBUILD       :=
EXTTOOL         :=

ifndef LIBBUTANOABS
export LIBBUTANOABS := $(realpath $(LIBBUTANO))
endif

include $(LIBBUTANOABS)/butano.mak
