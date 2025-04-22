from tailspring.context import Context
import tailspring.ts_types as ts_types
import tailspring.ts_enums as ts_enums


# We're given a configuration file as input which is parsed as a dict,
# but it's a lot more convenient to take the objects in the config (such as
# caps, cap modifications, vspaces, etc.) and wrap them in a class and reference them
# by the object wrapper. The wrappers are defined in ts_types
def create_object_wrappers(ctx: Context):
    create_initial_cap_wrappers(ctx)
    create_cap_modification_wrappers(ctx)
    create_cnode_wrappers(ctx)
    create_vspace_wrappers(ctx)
    create_thread_wrappers(ctx)


# Process initial caps in config file (everything under the 'caps' section)
def create_initial_cap_wrappers(ctx: Context):
    for cap_name, cap_type_str in ctx.config['caps'].items():
        if ctx.cap_addresses.has_cap_with_name(cap_name):
            raise ValueError(f"Found duplicate cap with name '{cap_name}' in caps section")

        cap_type = ts_enums.CapType[cap_type_str]
        if cap_type == ts_enums.CapType.cnode:
            raise ValueError(f"Nested CNode caps are not allowed (cap name: '{cap_name}')")

        cap = ts_types.Cap(name=cap_name, type=cap_type)
        ctx.cap_addresses.append(cap)


# Process cap modifications
def create_cap_modification_wrappers(ctx: Context):
    for dest_cap_name, mod_info in ctx.config['cap_modifications'].items():
        if ctx.cap_addresses.has_cap_with_name(dest_cap_name):
            raise ValueError(f"Found duplicate cap with name '{dest_cap_name}' in cap_modifications section")

        # Get referenced source cap
        src_cap_name = mod_info['original']
        src_cap = ctx.cap_addresses.get_cap_by_name(src_cap_name)

        # Get rights and badge
        rights_list = mod_info['rights']
        rights_enum = [ts_enums.CapRight[right] for right in rights_list]
        badge = mod_info['badge'] if 'badge' in mod_info else 0

        # Create dest cap
        dest_cap = ts_types.Cap(dest_cap_name, src_cap.type)
        ctx.cap_addresses.append(dest_cap)

        # Create cap mod entry
        cap_mod_entry = ts_types.CapModification(dest_cap=dest_cap, src_cap=src_cap, rights=rights_enum, badge=badge)
        ctx.cap_modifications[dest_cap_name] = cap_mod_entry


# Process cnodes
def create_cnode_wrappers(ctx: Context):
    for cnode_name, cnode_info in ctx.config['cnodes'].items():
        if ctx.cap_addresses.has_cap_with_name(cnode_name):
            raise ValueError(f"Found duplicate cap with name '{cnode_name}' in cnodes section")

        size = cnode_info['size']
        guard = cnode_info['guard']

        # The cnode's child caps are defined in the config file as key value pairs, where the key is an int
        # So we need to extract any keys that are ints, get the corresponding value (the cap name) then look
        # up the cap object by its name
        cap_indexes = [key for key in cnode_info.keys() if type(key) == int]
        cap_names = [cnode_info[key] for key in cap_indexes]
        caps = [ctx.cap_addresses.get_cap_by_name(name) for name in cap_names]

        # Finally we create a dict of {index: cap} by zipping up the indexes and the cap objects
        cap_dict = dict(zip(cap_indexes, caps))

        # Create cnode object
        cnode = ts_types.CNode(name=cnode_name, type=ts_enums.CapType.cnode, size=size, guard=guard, caps=cap_dict)
        ctx.cap_addresses.append(cnode)


# Process vspaces
def create_vspace_wrappers(ctx: Context):
    for index, (vspace_name, binary_name) in enumerate(ctx.config['vspaces'].items()):
        if ctx.cap_addresses.has_cap_with_name(vspace_name):
            raise ValueError(f"Found duplicate cap with name '{vspace_name}' in vspace section")

        binary_path = ctx.startup_threads_paths[binary_name]
        vspace = ts_types.VSpace(name=vspace_name, type=ts_enums.CapType.vspace, binary_name=binary_name, nonce=index, binary_path=binary_path, alignment=ctx.page_size)
        ctx.cap_addresses.append(vspace)
        ctx.vspaces[vspace_name] = vspace


# Process threads
def create_thread_wrappers(ctx: Context):
    for tcb_name, thread_info in ctx.config['threads'].items():
        if not ctx.cap_addresses.has_cap_with_name(tcb_name):
            raise ValueError(f"No TCB cap with name '{tcb_name}' found - did you create it in the caps section?")

        # The tcb must have been already created in the 'caps' section and have type 'tcb'
        tcb = ctx.cap_addresses.get_cap_by_name(tcb_name)
        if tcb.type != ts_enums.CapType.tcb:
            raise ValueError(f"Expected TCB '{tcb_name}' in threads section to be a tcb")

        # Same with cspace, it must be a cnode
        cspace_name = thread_info['cspace']
        cspace = ctx.cap_addresses.get_cap_by_name(cspace_name)
        if cspace.type != ts_enums.CapType.cnode:
            raise ValueError(f"Expected CSpace '{cspace_name}' in threads section to be a cnode")

        # Vspace should be a key in ctx.vspaces
        vspace_name = thread_info['vspace']
        if vspace_name not in ctx.vspaces:
            raise ValueError(f"Could not find VSpace '{vspace_name}' in threads section")
        vspace = ctx.vspaces[vspace_name]

        # IPC buffer should be a frame
        ipc_buffer_name = thread_info['ipc_buffer']
        ipc_buffer = ctx.cap_addresses.get_cap_by_name(ipc_buffer_name)
        if ipc_buffer.type != ts_enums.CapType.frame:
            raise ValueError(f"Expected IPC buffer '{ipc_buffer_name}' in threads section to be a frame")

        stack_size = thread_info['stack_size']
        if type(stack_size) != int or stack_size < 0:
            raise ValueError(f"Expected stack size '{stack_size}' in threads section to be a positive int")

        # A custom entry functon may be passed. If so, we need to look up the symbol address. Otherwise, use the entry in the elf file
        if 'entry' in thread_info:
            entry_symbol_name = thread_info['entry']
            entry_symbol = vspace.get_symbol(entry_symbol_name)
            if entry_symbol is None:
                raise RuntimeError(f"Entry symbol '{entry_symbol_name}' for thread '{tcb_name}' not found in vspace '{vspace_name}'")
            entry_addr = entry_symbol['st_value']
        else:
            entry_addr = vspace.elf.header.e_entry

        thread = ts_types.Thread(tcb=tcb, cspace=cspace, vspace=vspace, ipc_buffer=ipc_buffer, stack_size=stack_size, entry_addr=entry_addr)
        ctx.threads[tcb_name] = thread
