
UIS := $(wildcard *.ui)
PYS := $(UIS:.ui=.py)

##$(warning $(UIS) $(PYS))

default: $(PYS)

%.py: %.ui
	pyside-uic $^ > $@

