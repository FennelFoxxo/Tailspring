from tailspring.context import Context
import tailspring.ts_enums as ts_enums
import tailspring.cli_args as cli_args
import tailspring.wrapper_creator as wrapper_creator
import tailspring.obj_file_gen as obj_file_gen
import tailspring.ops_gen as ops_gen
import tailspring.fragment_gen as fragment_gen
import tailspring.paging as paging
import tailspring.thread_setup as thread_setup


def main():
    # Create empty context object
    ctx = Context()

    # Get cli arguments
    cli_args.declare_args(ctx)
    cli_args.parse_args(ctx)

    # Depending on the arch we're building for, different cap types and so different enums are available
    ts_enums.extend_CapType_enums_with_arch(ctx.arch)

    # Get the list of underivable cap types after we've extended enums
    ctx.underivable_cap_types = ts_enums.get_underivable_cap_types()

    # Convert the data in the configuration file into objects that are easier to manipulate
    wrapper_creator.create_object_wrappers(ctx)

    # Create the paging structures necessary to map in each vspace
    paging.create_paging_structures(ctx)

    # Set the values of per-thread attributes such as stack address and ipc buffer address - this does create some operations as well
    thread_setup.set_per_thread_values(ctx)

    # Parse the elf files associated with each vspace, extract the load segments, and combine them together into a single linkable obj file
    obj_file_gen.gen_startup_threads_obj_file(ctx)

    # Generate the list of operations that need to be performed to set up the system's state according to the config
    ops_gen.gen_cap_ops_list(ctx)

    fragment_gen.write_fragments(ctx)
    fragment_gen.flush_fragments(ctx)


if __name__ == "__main__":
    main()
