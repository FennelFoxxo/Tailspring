from tailspring.context import Context
import tailspring.ts_types as ts_types
import tailspring.ts_enums as ts_enums
import tailspring.op_types as op_types
from tailspring.paging import Range
from typing import List
from dataclasses import dataclass, field


class Stack:
    @dataclass
    class Arg:
        data: bytes
        addr: int

    @dataclass
    class AuxV:
        a_type: int  # int-sized
        a_val: int  # word-sized

    def __init__(self, thread: ts_types.Thread, ctx: Context):
        self.thread = thread
        self.ctx = ctx

        # As arguments are added, space needs to be created on the stack
        # to place the arguments. This keeps track of the address of the start
        # of the argument region
        self.args_start = thread.stack_top_addr
        self.args: List[Stack.Arg] = []

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
        arg_length = len(s) + 1  # Add one for null terminator
        data = bytes(s, 'ascii') + b'\0'
        self.args_start -= arg_length  # Create space for arg
        self.args.append(Stack.Arg(data=data, addr=self.args_start))

    def gen_stack_data(self) -> bytes:
        # Represents the bytes of the stack as read from the lowest address to the highest
        data = bytes()

        word_size = self.ctx.sel4_info['literals']['seL4_WordBits'] // 8

        # Write num args
        data += self.word_to_bytes(len(self.args))

        # Write arg pointers (process name is first arg)
        for arg in self.args:
            data += self.word_to_bytes(arg.addr)

        # Empty string
        data += self.word_to_bytes(0)

        # Environment pointers would go here, but we're not using them

        # Null terminator
        data += self.word_to_bytes(0)

        # Auxiliary vector entries
        # Each auxiliary vector is a struct consisting of a_type (an int) and a_un (a union of a_val, a_ptr, and a_fnc which are all words)
        for auxv in self.aux_vectors:
            data += self.int_to_bytes(auxv.a_type)
            # Compiler-added padding between struct members a_type and a_un
            data += bytes(self.ctx.sel4_info['literals']['offsetof(auxv_t, a_un)'] - self.ctx.sel4_info['literals']['sizeof(int)'])
            data += self.word_to_bytes(auxv.a_val)

        # Zero auxiliary vector
        data += self.int_to_bytes(self.ctx.sel4_info['literals']['AT_NULL'])
        data += self.word_to_bytes(0)

        # Generate region where args are to be stored
        arg_data = bytes()
        # Since the first arg is placed at the top of the stack, but we're building the stack from the bottom up,
        # we need to revers args so that the first arg added through add_arg is appended last
        for arg in reversed(self.args):
            arg_data += arg.data

        # The stack is expected to be aligned to the nearest 16 bytes
        stack_alignment = 16
        padding_needed = -(len(data) + len(arg_data)) % stack_alignment
        data += bytes(padding_needed)

        # Finally combine the required stack data and the custom arg data
        data += arg_data

        # Make sure the stack pointer is just under the stack data
        self.thread.stack_pointer_addr = self.thread.stack_top_addr - len(data)

        # Pass argc as first argument to thread and argv as second. argv is the second word above the stack pointer, after argc
        self.thread.arg0 = len(self.args)
        self.thread.arg1 = self.thread.stack_pointer_addr + word_size

        return data

    def word_to_bytes(self, val: int) -> bytes:
        word_bytes = self.ctx.sel4_info['literals']['seL4_WordBits'] // 8
        endianness = self.ctx.sel4_info['endianness']
        return val.to_bytes(length=word_bytes, byteorder=endianness, signed=False)

    def int_to_bytes(self, val: int) -> bytes:
        int_bytes = self.ctx.sel4_info['literals']['sizeof(int)']
        endianness = self.ctx.sel4_info['endianness']
        return val.to_bytes(length=int_bytes, byteorder=endianness, signed=False)


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
    threads_sharing_vspace = filter(lambda thread: thread.vspace == vspace, ctx.threads.values())

    # Get the last address used in the vspace for mapping segments (everything after this should be free)
    last_chunk_vaddr = max([chunk.dest_vaddr_aligned + chunk.total_length_with_padding for chunk in vspace.binary_chunks])
    assert (last_chunk_vaddr % ctx.page_size == 0)

    addr_ptr = last_chunk_vaddr

    # We place a thread's stack above the segment, then the thread's IPC buffer, then the next thread's stack, and so on...
    # We leave unmapped pages in between so that a fault with occur if a stack overrun occurs
    addr_ptr += ctx.page_size
    for thread in threads_sharing_vspace:
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

        # Now that we know the ipc buffer address, we can initialize the values on the stack that the seL4 runtime expects
        init_stack_for_thread(thread, ctx)


def map_existing_frame(frame_cap: ts_types.Cap, vspace: ts_types.VSpace, vaddr: int, ctx: Context):
    paging_structure_for_vspace = ctx.paging_structures[vspace.name]

    # Map stack frame
    map_frame_op = op_types.MapFrameOperation(frame_cap, vspace, vaddr)
    ctx.ops_list.append(map_frame_op)

    # Make sure paging structures are created to cover this frame
    paging_structure_for_vspace.create_children_to_cover_range(Range(vaddr, vaddr + ctx.page_size))


def init_stack_for_thread(thread: ts_types.Thread, ctx: Context):
    stack = Stack(thread, ctx)
    stack_data = stack.gen_stack_data()

    # The stack starts from the top and grows down, so padding needs to be added so that the stack data is at the top
    stack_data_padded = bytes(thread.stack_size - len(stack_data)) + stack_data

    stack_chunk = ts_types.BinaryChunk(name=f'{thread.tcb.name}_stack_frame__', alignment=ctx.page_size, data=stack_data_padded, dest_vaddr=thread.stack_top_addr-thread.stack_size, min_length=thread.stack_size)
    thread.vspace.binary_chunks.append(stack_chunk)
