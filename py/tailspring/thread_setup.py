from tailspring.context import Context
import tailspring.ts_types as ts_types
import tailspring.ts_enums as ts_enums
import tailspring.op_types as op_types
from tailspring.paging import Range


# Even if threads share the same vspace, they each need to have their own ipc buffer and stack
# Note that this function does generate operations and append them to the op_list, despite it
# not being in ops_gen - it's just much easier to do the op generation as we crawl over threads
def setPerThreadValues(ctx: Context):
    for vspace in ctx.vspaces.values():
        setSharedVSpaceThreadValues(vspace, ctx)


# Given that we only need to worry about overlapping ipc buffers/stacks for threads that share
# the same vspace, it makes sense to process all threads sharing a vspace together as a group
def setSharedVSpaceThreadValues(vspace: ts_types.VSpace, ctx: Context):
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
        stack_size = thread.stack_size
        stack_padding = -stack_size % ctx.page_size

        # Make sure stack size is multiple of page size
        stack_size_aligned = stack_size + stack_padding

        num_stack_frames = stack_size_aligned // ctx.page_size
        for i in range(num_stack_frames):
            # Each stack frame needs to be allocated
            stack_frame_cap_name = f'{thread.tcb.name}_stack_frame_{addr_ptr}__'
            createAndMapNewFrame(stack_frame_cap_name, vspace, addr_ptr, ctx)

            # Increment address pointer
            addr_ptr += ctx.page_size

        # addr_ptr is now at the top of the stack
        thread.stack_top_addr = addr_ptr

        # Leave a frame in between stack and IPC buffer
        addr_ptr += ctx.page_size

        # Map IPC buffer
        thread.ipc_buffer_addr = addr_ptr
        mapExistingFrame(thread.ipc_buffer, vspace, addr_ptr, ctx)

        # Leave another frame in between IPC buffer and next thread's stack
        addr_ptr += ctx.page_size


def mapExistingFrame(frame_cap: ts_types.Cap, vspace: ts_types.VSpace, vaddr: int, ctx: Context):
    paging_structure_for_vspace = ctx.paging_structures[vspace.name]

    # Map stack frame
    map_frame_op = op_types.MapFrameOperation(frame_cap, vspace, vaddr)
    ctx.ops_list.append(map_frame_op)

    # Make sure paging structures are created to cover this frame
    paging_structure_for_vspace.create_children_to_cover_range(Range(vaddr, vaddr + ctx.page_size))


def createAndMapNewFrame(frame_cap_name: str, vspace: ts_types.VSpace, vaddr: int, ctx: Context):
    frame_cap = ts_types.Cap(frame_cap_name, ts_enums.CapType.frame)
    ctx.cap_addresses.append(frame_cap)

    # Create stack frame
    create_op = op_types.CapCreateOperation(frame_cap, ctx.page_size_bits)
    ctx.ops_list.append(create_op)

    # Map stack frame
    mapExistingFrame(frame_cap, vspace, vaddr, ctx)
