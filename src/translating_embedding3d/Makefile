OLB_ROOT ?= $(OPENLB_ROOT)
EXAMPLE := translatingEmbedding3d

ifeq ($(strip $(OLB_ROOT)),)
$(error Set OPENLB_ROOT to the local OpenLB 1.9 checkout)
endif

include $(OLB_ROOT)/config.mk
include $(OLB_ROOT)/rules.mk
CXXFLAGS += -DPLATFORM_CPU_SISD -I$(OLB_ROOT)/src
LDFLAGS += -L$(OLB_ROOT)/build/lib

$(EXAMPLE): $(EXAMPLE).o
	$(CXX) $< -o $@ -lolbcore $(LDFLAGS)

$(EXAMPLE).o: $(EXAMPLE).cpp translatedPorosityEmbedding3D.h
	$(CXX) $(CXXFLAGS) -c -o $@ $<
