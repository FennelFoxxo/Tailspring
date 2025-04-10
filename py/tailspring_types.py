from tailspring_globals import *

class CapCreateOperation:
    def __init__(self, cap_type, dest, size_bits):
        self.cap_type = cap_type
        self.dest = dest
        self.size_bits = size_bits
    def __str__(self):
        return f'{{CAP_CREATE, .cap_create_op={{{self.cap_type}, {self.dest}, {self.size_bits}}}}}'

class CNodeCreateOperation:
    def __init__(self, dest, slot_bits, guard):
        self.dest = dest
        self.slot_bits = slot_bits
        self.size_bits = slot_bits + seL4_constants.literals.seL4_SlotBits
        self.guard = guard
    def __str__(self):
        return f'{{CNODE_CREATE, .cnode_create_op={{{self.dest}, {self.slot_bits}, {self.guard}}}}}'

class CapMintOperation:
    def __init__(self, badge, src, dest, rights):
        self.badge = badge
        self.src = src
        self.dest = dest
        self.rights = rights
    def __str__(self):
        return f'{{CAP_MINT, .mint_op={{{self.badge}, {self.src}, {self.dest}, {self.rights}}}}}'

class CapCopyOperation:
    def __init__(self, src, dest_root, dest_index, dest_depth):
        self.src = src
        self.dest_root = dest_root
        self.dest_index = dest_index
        self.dest_depth = dest_depth
    def __str__(self):
        return f'{{CAP_COPY, .copy_op={{{self.src}, {self.dest_root}, {self.dest_index}, {self.dest_depth}}}}}'

__all__ = [att for att in dir() if att.endswith('Operation')]