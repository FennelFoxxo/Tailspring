from tailspring.context import Context
import tailspring.ts_types as ts_types
import tailspring.ts_enums as ts_enums
import tailspring.op_types as op_types
from tailspring.paging import Range
from typing import List
from dataclasses import dataclass
import enum


def word_to_bytes(val: int, ctx: Context) -> bytes:
    word_bytes = ctx.sel4_info['literals']['seL4_WordBits'] // 8
    endianness = ctx.sel4_info['endianness']
    return val.to_bytes(length=word_bytes, byteorder=endianness, signed=False)


def int_to_bytes(val: int, ctx: Context) -> bytes:
    int_bytes = ctx.sel4_info['literals']['sizeof(int)']
    endianness = ctx.sel4_info['endianness']
    return val.to_bytes(length=int_bytes, byteorder=endianness, signed=False)


class Stack:
    class CustomDataType(enum.Enum):
        Arg = enum.auto()
        Envp = enum.auto()

    @dataclass
    class CustomData:
        value: bytes
        addr: int
        type: "Stack.CustomDataType"

    @dataclass
    class AuxV:
        a_type: int  # int-sized
        a_val: int  # word-sized

        def to_bytes(self, ctx: Context):
            data = bytes()
            data += int_to_bytes(self.a_type, ctx)
            # Compiler-added padding between struct members a_type and a_un
            data += bytes(ctx.sel4_info['literals']['offsetof(auxv_t, a_un)'] - ctx.sel4_info['literals']['sizeof(int)'])
            data += word_to_bytes(self.a_val, ctx)
            return data

    def __init__(self, thread: ts_types.Thread, ctx: Context):
        self.thread = thread
        self.ctx = ctx

        # As arguments/environment pointers are added, space needs to be created on the stack
        # to place the data. This keeps track of the address of the start
        # of the custom data region
        self.custom_data_start = thread.stack_top_addr
        self.custom_data_arr: List[Stack.CustomData] = []

        # Add the process name as the first argument
        self.add_arg(thread.tcb.name)

        # Create auxiliary vectors array
        self.aux_vectors = []

        # Add IPC buffer address as auxiliary vector
        self.aux_vectors.append(Stack.AuxV(a_type=ctx.sel4_info['literals']['AT_SEL4_IPC_BUFFER_PTR'], a_val=thread.ipc_buffer_addr))

        # Add sel4_vsyscall function pointer as sysinfo auxiliary vector, if it exists
        vsyscall_symbol = thread.vspace.get_symbol('sel4_vsyscall')
        if vsyscall_symbol is not None:
            self.aux_vectors.append(Stack.AuxV(a_type=ctx.sel4_info['literals']['AT_SYSINFO'], a_val=vsyscall_symbol['st_value']))

    def add_arg(self, s: str):
        self.__add_custom_data(s, Stack.CustomDataType.Arg)

    def add_envp(self, s: str):
        self.__add_custom_data(s, Stack.CustomDataType.Envp)

    def __add_custom_data(self, s: str, type: CustomDataType):
        data = bytes(s, 'ascii') + b'\0'  # Add null terminator
        self.custom_data_start -= len(data)  # Create space for arg
        self.custom_data_arr.append(Stack.CustomData(value=data, addr=self.custom_data_start, type=type))

    def gen_stack_data(self) -> bytes:
        # Represents the bytes of the stack as read from the lowest address to the highest
        stack_data = bytes()

        word_size = self.ctx.sel4_info['literals']['seL4_WordBits'] // 8

        # Write num args
        args = [data for data in self.custom_data_arr if data.type == self.CustomDataType.Arg]
        stack_data += word_to_bytes(len(args), self.ctx)

        # Write arg pointers (process name is first arg)
        for arg in args:
            stack_data += word_to_bytes(arg.addr, self.ctx)

        # Empty string
        stack_data += word_to_bytes(0, self.ctx)

        # Write environment pointers
        envps = [data for data in self.custom_data_arr if data.type == self.CustomDataType.Envp]
        for envp in envps:
            stack_data += word_to_bytes(envp.addr, self.ctx)

        # Envp null terminator terminator
        stack_data += word_to_bytes(0, self.ctx)

        # Auxiliary vector entries
        # Each auxiliary vector is a struct consisting of a_type (an int) and a_un (a union of a_val, a_ptr, and a_fnc which are all words)
        for auxv in self.aux_vectors:
            stack_data += auxv.to_bytes(self.ctx)

        # Zero auxiliary vector
        stack_data += Stack.AuxV(a_type=0, a_val=0).to_bytes(self.ctx)

        # Generate region where custom data (args and envp) is to be stored
        custom_data = bytes()
        # Since the first added custom data is placed at the highest address, but we're building the stack from the bottom up,
        # we need to reverse the order so that the first bit of custom data is appended last (at the highest address)
        for data in reversed(self.custom_data_arr):
            custom_data += data.value

        # The stack is expected to be aligned to the nearest 16 bytes
        stack_alignment = 16
        padding_needed = -(len(stack_data) + len(custom_data)) % stack_alignment
        stack_data += bytes(padding_needed)

        # Finally combine the required stack data and the custom data
        stack_data += custom_data

        # Make sure the stack pointer is just under the stack data
        self.thread.stack_pointer_addr = self.thread.stack_top_addr - len(stack_data)

        # Pass argc as first argument to thread and argv as second. argv is the second word above the stack pointer, after argc
        self.thread.arg0 = len(args)  # Argc
        self.thread.arg1 = self.thread.stack_pointer_addr + word_size  # Argv
        self.thread.arg2 = self.thread.arg1 + word_size * len(args) + word_size  # Envp

        return stack_data


# Even if threads share the same vspace, they each need to have their own ipc buffer and stack
# Note that this function does generate operations and append them to the op_list, despite it
# not being in ops_gen - it's just much easier to do the op generation as we crawl over threads
def set_per_thread_values(ctx: Context):
    for vspace in ctx.vspaces.values():
        set_shared_vspace_thread_values(vspace, ctx)


# Given that we only need to worry about overlapping ipc buffers/stacks for threads that share
# the same vspace, it makes sense to process all threads sharing a vspace together as a group
def set_shared_vspace_thread_values(vspace: ts_types.VSpace, ctx: Context):
    # Get all threads sharing this vspace
    threads_sharing_vspace = list(filter(lambda thread: thread.vspace == vspace, ctx.threads.values()))

    # Check if any threads in this vspace need to be passed gp_memory_info
    reserve_gp_memory_info_frame = any(thread.cspace.gp_untypeds_start is not None for thread in threads_sharing_vspace)
    gp_memory_info_addr = 0

    # Get the last address used in the vspace for mapping segments (everything after this should be free)
    last_chunk_vaddr = max([chunk.dest_vaddr_aligned + chunk.total_length_with_padding for chunk in vspace.binary_chunks])
    assert (last_chunk_vaddr % ctx.page_size == 0)

    addr_ptr = last_chunk_vaddr

    # We place a thread's stack above the segment, then the IPC buffer, then the next thread's stack, and so on...
    # We leave unmapped pages in between so that a fault with occur if a stack overrun occurs
    addr_ptr += ctx.page_size

    for thread in threads_sharing_vspace:
        if reserve_gp_memory_info_frame:
            # Use one page for gp memory info (should be plenty)
            gp_memory_info_addr = addr_ptr
            create_gp_memory_info_frame(thread, gp_memory_info_addr, ctx)

            # Move up one page for the memory info frame itself, and another to create a gap in between
            addr_ptr += ctx.page_size * 2

            # Only one gp memory info frame is needed per vspace
            reserve_gp_memory_info_frame = False

        # Round stack size up to the nearest multiple of the page size and move addr_ptr to the top of the stack
        thread.stack_size += -thread.stack_size % ctx.page_size

        addr_ptr += thread.stack_size

        # Save stack address
        thread.stack_top_addr = addr_ptr

        # Leave a frame in between stack and IPC buffer
        addr_ptr += ctx.page_size

        # Map IPC buffer
        thread.ipc_buffer_addr = addr_ptr

        map_existing_frame(thread.ipc_buffer, vspace, addr_ptr, ctx)

        # Leave another frame in between IPC buffer and next thread's stack
        addr_ptr += ctx.page_size

        # Environment pointers
        thread.envps.append(f"ipc_buffer={thread.ipc_buffer_addr}")

        if thread.cspace.gp_untypeds_start is not None:
            thread.envps.append(f"gp_memory_info={gp_memory_info_addr}")

        # Now that we know where everything is placed in memory, we can initialize the values on the stack that the seL4 runtime expects
        init_stack_for_thread(thread, ctx)


def create_gp_memory_info_frame(thread: ts_types.Thread, vaddr: int, ctx: Context):
    frame = ts_types.Cap(f"{thread.tcb.name}_gp_memory_info_frame", ts_enums.CapType.frame)
    ctx.cap_addresses.append(frame)
    ctx.ops_list.append(op_types.CapCreateOperation(dest=frame, size_bits=ctx.page_size_bits))

    ctx.ops_list.append(op_types.PassGPMemoryInfoOperation(dest_vaddr=vaddr, frame=frame, dest_vspace=thread.vspace))

    # Make sure paging structures are created to cover this frame
    paging_structure_for_vspace = ctx.paging_structures[thread.vspace.name]
    paging_structure_for_vspace.create_children_to_cover_range(Range(vaddr, vaddr + ctx.page_size))


def map_existing_frame(frame_cap: ts_types.Cap, vspace: ts_types.VSpace, vaddr: int, ctx: Context):
    # Map stack frame
    map_frame_op = op_types.MapFrameOperation(frame_cap, vspace, vaddr)
    ctx.ops_list.append(map_frame_op)

    # Make sure paging structures are created to cover this frame
    paging_structure_for_vspace = ctx.paging_structures[vspace.name]
    paging_structure_for_vspace.create_children_to_cover_range(Range(vaddr, vaddr + ctx.page_size))


def init_stack_for_thread(thread: ts_types.Thread, ctx: Context):
    stack = Stack(thread, ctx)
    [stack.add_arg(arg) for arg in thread.args]
    [stack.add_envp(arg) for arg in thread.envps]

    stack_data = stack.gen_stack_data()

    # The stack starts from the top and grows down, so padding needs to be added so that the stack data is at the top
    stack_data_padded = bytes(thread.stack_size - len(stack_data)) + stack_data

    stack_chunk = ts_types.BinaryChunk(name=f'{thread.tcb.name}_stack_frame__', alignment=ctx.page_size, data=stack_data_padded, dest_vaddr=thread.stack_top_addr - thread.stack_size, min_length=thread.stack_size)
    thread.vspace.binary_chunks.append(stack_chunk)
