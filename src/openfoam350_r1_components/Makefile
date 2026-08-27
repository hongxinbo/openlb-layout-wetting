# Mapping-component audit only: this target is not an OpenLB350 full-board solver.
# Set OPENLB_ROOT locally; no personal path is stored in the repository.
EXAMPLE := r1ComponentAudit
OLB_ROOT ?= $(OPENLB_ROOT)

ifeq ($(strip $(OLB_ROOT)),)
$(error Set OPENLB_ROOT to the local OpenLB 1.9 checkout)
endif

include $(OLB_ROOT)/default.mk
