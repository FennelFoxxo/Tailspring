from tailspring.context import Context
import tailspring.op_types as op_types
import tailspring.ts_types as ts_types


def gen_cap_ops_list(ctx: Context):
    gen_cap_create_ops(ctx)
    gen_cnode_create_ops(ctx)
    gen_mint_ops(ctx)
    gen_copy_ops(ctx)
    gen_paging_ops(ctx)
    gen_binary_chunk_load_ops(ctx)
    gen_tcb_setup_ops(ctx)
    gen_pass_gp_untypeds_ops(ctx)
    gen_tcb_start_ops(ctx)

    sort_ops_list(ctx)


# Corresponds to retype operations to create the caps listed under the config's 'caps' section
def gen_cap_create_ops(ctx: Context):
    for cap_name in ctx.config['caps']:
        cap = ctx.cap_addresses.get_cap_by_name(cap_name)
        size_bits = ctx.sel4_info['object_sizes'][cap.type.value]
        cap_create_op = op_types.CapCreateOperation(dest=cap, size_bits=size_bits)
        ctx.ops_list.append(cap_create_op)


# Corresponds to retype operations to create the cnodes listed under the config's 'cnodes' section
def gen_cnode_create_ops(ctx: Context):
    for cnode_name in ctx.config['cnodes']:
        cnode = ctx.cap_addresses.get_cap_by_name(cnode_name)
        assert isinstance(cnode, ts_types.CNode)
        slot_bits = ctx.sel4_info['literals']['seL4_SlotBits']
        cnode_create_op = op_types.CNodeCreateOperation(dest=cnode, slot_bits=slot_bits)
        ctx.ops_list.append(cnode_create_op)


# Corresponds to mint operations to copy/modify the caps listed under the config's 'cap_modifications' section
def gen_mint_ops(ctx: Context):
    for cap_mod in ctx.cap_modifications.values():
        mint_op = op_types.MintOperation(src=cap_mod.src_cap, dest=cap_mod.dest_cap, rights=cap_mod.rights, badge=cap_mod.badge)
        ctx.ops_list.append(mint_op)


# Corresponds to copy operations to copy the caps into their final location in the created cnodes
def gen_copy_ops(ctx: Context):
    for cnode_name in ctx.config['cnodes']:
        cnode = ctx.cap_addresses.get_cap_by_name(cnode_name)
        assert isinstance(cnode, ts_types.CNode)
        for slot_index, cap_to_copy in cnode.caps.items():
            copy_op = op_types.CopyOperation(src=cap_to_copy, dest=cnode, index=slot_index)
            ctx.ops_list.append(copy_op)


# Generates both create ops and map ops because each page structure needs to be created and mapped
def gen_paging_ops(ctx: Context):
    for vspace_name, paging_structure in ctx.paging_structures.items():
        vspace = ctx.cap_addresses.get_cap_by_name(vspace_name)
        assert isinstance(vspace, ts_types.VSpace)
        paging_structure.gen_ops(vspace, ctx)


def gen_binary_chunk_load_ops(ctx: Context):
    for vspace_name, vspace in ctx.vspaces.items():
        for chunk in vspace.binary_chunks:
            chunk_load_op = op_types.BinaryChunkLoadOperation(src_vaddr_sym=chunk.start_symbol, dest_vaddr=chunk.dest_vaddr_aligned,
                                                              length=chunk.total_length_with_padding, dest_vspace=vspace)
            ctx.ops_list.append(chunk_load_op)


def gen_tcb_setup_ops(ctx: Context):
    for thread in ctx.threads.values():
        tcb_setup_op = op_types.TCBSetupOperation(tcb=thread.tcb, cspace=thread.cspace, vspace=thread.vspace, ipc_buffer=thread.ipc_buffer,
                                                  entry_addr=thread.entry_addr, ipc_buffer_addr=thread.ipc_buffer_addr,
                                                  stack_pointer_addr=thread.stack_pointer_addr, arg0=thread.arg0, arg1=thread.arg1, arg2=thread.arg2)
        ctx.ops_list.append(tcb_setup_op)


def gen_pass_gp_untypeds_ops(ctx: Context):
    if ctx.gp_untypeds_cnode:
        cnode_dest = ctx.gp_untypeds_cnode
        op = op_types.PassGPUntypedsOperation(cnode_dest=cnode_dest, start_slot=cnode_dest.gp_untypeds_start, end_slot=cnode_dest.gp_untypeds_end, cnode_depth=cnode_dest.guard + cnode_dest.size)
        ctx.ops_list.append(op)


def gen_tcb_start_ops(ctx: Context):
    for thread in ctx.threads.values():
        tcb_start_op = op_types.TCBStartOperation(tcb=thread.tcb)
        ctx.ops_list.append(tcb_start_op)


def sort_ops_list(ctx: Context):
    op_order = [op_types.MintOperation, op_types.CopyOperation, op_types.MapOperation, op_types.BinaryChunkLoadOperation,
                op_types.MapFrameOperation, op_types.TCBSetupOperation, op_types.PassGPUntypedsOperation, op_types.PassGPMemoryInfoOperation,
                op_types.TCBStartOperation]

    def sort_func(e):
        # Create ops always go first, sorted by greatest size first
        if type(e) in (op_types.CapCreateOperation, op_types.CNodeCreateOperation):
            # -1 puts this op before the non-create ops, and -bytes_required means the greatest size comes first
            return -1, -e.bytes_required
        # Otherwise, sort them by op_order
        return op_order.index(type(e)), 0

    ctx.ops_list.sort(key=sort_func)
