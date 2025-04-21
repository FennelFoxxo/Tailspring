from tailspring.context import Context


def write_fragments(ctx: Context):
    write_preamble_fragment(ctx)
    write_ops_list_fragment(ctx)
    write_mapping_funcs_enable_fragment(ctx)
    write_extern_linker_symbols_fragment(ctx)


def write_preamble_fragment(ctx: Context):
    f = ctx.preamble_fragment
    f.write('#pragma once\n')
    f.write('#include "tailspring.hpp"\n')
    f.write(f'#define SLOTS_REQUIRED ((seL4_Word){ctx.cap_addresses.get_slots_required()})\n')


def write_ops_list_fragment(ctx: Context):
    f = ctx.ops_fragment

    # Format as C array
    f.write('CapOperation cap_operations[] = {\n')
    for op in ctx.ops_list:
        for op_list_entry in op.format_as_C_entry():
            f.write(op_list_entry + ',\n')
    f.write('};\n')


def write_mapping_funcs_enable_fragment(ctx: Context):
    f = ctx.mapping_funcs_enable_fragment
    f.write(ctx.paging_arch_info.get_mapping_func_enable_str())


def write_extern_linker_symbols_fragment(ctx: Context):
    f = ctx.extern_linker_symbols_fragment
    for vspace_name, vspace in ctx.vspaces.items():
        for chunk in vspace.binary_chunks:
            f.write(f'extern void* {chunk.start_symbol};\n')


def flush_fragments(ctx: Context):
    with open(ctx.output_header_path, 'w') as f:
        ctx.preamble_fragment.flush(f)
        ctx.extern_linker_symbols_fragment.flush(f)
        ctx.mapping_funcs_enable_fragment.flush(f)
        ctx.ops_fragment.flush(f)
