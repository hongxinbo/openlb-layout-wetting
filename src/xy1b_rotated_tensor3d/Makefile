OLB_ROOT ?= $(if $(OPENLB_ROOT),$(OPENLB_ROOT),$(HOME)/Documents/openlb)
EXAMPLE := xy1bRotatedSmoke
include $(OLB_ROOT)/config.mk
include $(OLB_ROOT)/rules.mk
CXXFLAGS += -DPLATFORM_CPU_SISD -I$(OLB_ROOT)/src
LDFLAGS += -L$(OLB_ROOT)/build/lib
$(EXAMPLE): $(EXAMPLE).o
	$(CXX) $< -o $@ -lolbcore $(LDFLAGS)
$(EXAMPLE).o: $(EXAMPLE).cpp
	$(CXX) $(CXXFLAGS) -c -o $@ $<
