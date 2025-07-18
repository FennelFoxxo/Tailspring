# This file is specifically for classes that represent operations (such as retyping, moving, mapping) performed by the Tailspring task loader

import tailspring.ts_types as ts_types
import tailspring.ts_enums as ts_enums
from typing import List


class Operation:
    # Format arguments as a designated initialized element of the C operation list
    @staticmethod
    def format_args_as_C_entry(op_name, **kwargs):
        # Format like `{OP_NAME, .op_name = {.k1=v1, .k2=v2, .k3=v3}}`
        initializers = ', '.join([f'.{key}={val}' for key, val in kwargs.items()])
        return f'{{{op_name.upper()}, .{op_name.lower()} = {{{initializers}}}}}'

    def format_as_C_entry(self):
        raise NotImplementedError


# Specifically for creating a cap that is *not* a cnode
class CapCreateOperation(Operation):
    def __init__(self, dest: ts_types.Cap, size_bits: int):
        self.dest = dest
        self.size_bits = size_bits
        self.bytes_required = 1 << size_bits

    def format_as_C_entry(self) -> List[str]:
        return [self.format_args_as_C_entry('create_op',
                                            cap_type=self.dest.type.value,
                                            bytes_required=self.bytes_required,
                                            dest=self.dest.address,
                                            size_bits=self.size_bits
                                            )]


class CNodeCreateOperation(Operation):
    # slot_bits is the log2 of the size of a CSlot in bytes
    def __init__(self, dest: ts_types.CNode, slot_bits: int):
        assert (dest.type == ts_enums.CapType.cnode)
        self.dest = dest
        self.bytes_required = 1 << (dest.size + slot_bits)

    def format_as_C_entry(self) -> List[str]:
        # Two ops are needed - one to create the CNode (which is initially placed in slot 0)
        # and then one to mutate it to its final location, setting its guard in the process
        return [self.format_args_as_C_entry('create_op',
                                            cap_type=ts_enums.CapType.cnode.value,
                                            bytes_required=self.bytes_required,
                                            dest=0,
                                            size_bits=self.dest.size
                                            ),
                self.format_args_as_C_entry('mutate_op',
                                            guard=self.dest.guard,
                                            src=0,
                                            dest=self.dest.address
                                            ),
                ]


class MintOperation(Operation):
    def __init__(self, src: ts_types.Cap, dest: ts_types.Cap, rights: List[ts_enums], badge: int):
        self.src = src
        self.dest = dest
        self.rights = rights
        self.rights_str = ts_enums.CapRight.list_to_C_expr(self.rights)
        self.badge = badge

    def format_as_C_entry(self) -> List[str]:
        return [self.format_args_as_C_entry('mint_op',
                                            badge=self.badge,
                                            src=self.src.address,
                                            dest=self.dest.address,
                                            rights=self.rights_str
                                            )]


class CopyOperation(Operation):
    def __init__(self, src: ts_types.Cap, dest: ts_types.CNode, index: int):
        assert (dest.caps[index] == src)
        self.src = src
        self.dest = dest
        self.index = index

    def format_as_C_entry(self) -> List[str]:
        return [self.format_args_as_C_entry('copy_op',
                                            src=self.src.address,
                                            dest_root=self.dest.address,
                                            dest_index=self.index,
                                            dest_depth=self.dest.size + self.dest.guard
                                            )]


class MapOperation(Operation):
    def __init__(self, service: ts_types.Cap, vspace: ts_types.Cap, vaddr: int, map_func: str):
        self.service = service
        self.vspace = vspace
        self.vaddr = vaddr
        self.map_func = map_func

    def format_as_C_entry(self) -> List[str]:
        return [self.format_args_as_C_entry('map_op',
                                            map_func=self.map_func,
                                            vaddr=self.vaddr,
                                            service=self.service.address,
                                            vspace=self.vspace.address
                                            )]


class BinaryChunkLoadOperation(Operation):
    def __init__(self, src_vaddr_sym: str, dest_vaddr: int, length: int, dest_vspace: ts_types.VSpace):
        # src_vaddr is a string because it contains the linker symbol of the chunk's start address
        self.src_vaddr_sym = src_vaddr_sym
        self.dest_vaddr = dest_vaddr
        self.length = length
        self.dest_vspace = dest_vspace

    def format_as_C_entry(self) -> List[str]:
        return [self.format_args_as_C_entry('binary_chunk_load_op',
                                            src_vaddr=f'SYM_VAL({self.src_vaddr_sym})',
                                            dest_vaddr=self.dest_vaddr,
                                            length=self.length,
                                            dest_vspace=self.dest_vspace.address
                                            )]


class TCBSetupOperation(Operation):
    def __init__(self, tcb: ts_types.Cap, cspace: ts_types.Cap, vspace: ts_types.VSpace, ipc_buffer: ts_types.Cap,
                 ipc_buffer_addr: int, entry_addr: int, stack_pointer_addr: int, arg0: int, arg1: int, arg2: int):
        self.tcb = tcb
        self.cspace = cspace
        self.vspace = vspace
        self.ipc_buffer = ipc_buffer
        self.ipc_buffer_addr = ipc_buffer_addr
        self.entry_addr = entry_addr
        self.stack_pointer_addr = stack_pointer_addr
        self.arg0 = arg0
        self.arg1 = arg1
        self.arg2 = arg2

    def format_as_C_entry(self) -> List[str]:
        return [self.format_args_as_C_entry('tcb_setup_op',
                                            entry_addr=self.entry_addr,
                                            stack_pointer_addr=self.stack_pointer_addr,
                                            ipc_buffer_addr=self.ipc_buffer_addr,
                                            arg0=self.arg0,
                                            arg1=self.arg1,
                                            arg2=self.arg2,
                                            cspace=self.cspace.address,
                                            vspace=self.vspace.address,
                                            ipc_buffer=self.ipc_buffer.address,
                                            tcb=self.tcb.address
                                            )]


class MapFrameOperation(Operation):
    def __init__(self, frame: ts_types.Cap, vspace: ts_types.VSpace, vaddr: int):
        # src_vaddr is a string because it contains the linker symbol of the segment's start address
        self.frame = frame
        self.vspace = vspace
        self.vaddr = vaddr

    def format_as_C_entry(self) -> List[str]:
        return [self.format_args_as_C_entry('map_frame_op',
                                            vaddr=self.vaddr,
                                            frame=self.frame.address,
                                            vspace=self.vspace.address
                                            )]


class PassGPUntypedsOperation(Operation):
    def __init__(self, cnode_dest: ts_types.CNode, start_slot: int, end_slot: int, cnode_depth: int):
        self.cnode_dest = cnode_dest
        self.start_slot = start_slot
        self.end_slot = end_slot
        self.cnode_depth = cnode_depth

    def format_as_C_entry(self) -> List[str]:
        return [self.format_args_as_C_entry('pass_gp_untypeds_op',
                                            cnode_dest=self.cnode_dest.address,
                                            start_slot=self.start_slot,
                                            end_slot=self.end_slot,
                                            cnode_depth=self.cnode_depth
                                            )]


class PassGPMemoryInfoOperation(Operation):
    def __init__(self, dest_vaddr: int, frame: ts_types.Cap, dest_vspace: ts_types.VSpace):
        self.dest_vaddr = dest_vaddr
        self.frame = frame
        self.dest_vspace = dest_vspace

    def format_as_C_entry(self) -> List[str]:
        return [self.format_args_as_C_entry('pass_gp_memory_info_op',
                                            dest_vaddr=self.dest_vaddr,
                                            frame=self.frame.address,
                                            dest_vspace=self.dest_vspace.address
                                            )]


class TCBStartOperation(Operation):
    def __init__(self, tcb: ts_types.Cap):
        self.tcb = tcb

    def format_as_C_entry(self) -> List[str]:
        return [self.format_args_as_C_entry('tcb_start_op',
                                            tcb=self.tcb.address
                                            )]
