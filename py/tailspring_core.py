from tailspring_types import *
from tailspring_globals import *
import tailspring_startup_threads as ts_st
import tailspring_paging as ts_paging

def emitDefine(name, value):
    emitLine(f'#define {name} ({value})')

def emitDefineWord(name, value):
    emitLine(f'#define {name} ((seL4_Word){value})')

def getCapLocations():
    cap_locations = CapLocations()

    for key in env.config.cnodes:
        cap_locations.append(key)
    for key in env.config.caps:
        cap_locations.append(key)
    for key in env.config.cap_modifications:
        cap_locations.append(key)
    return cap_locations

def genCapCreateOpList(cap_locations):
    op_list = []
    # Generate creations for CNodes
    for cnode_name, cnode_info in env.config.cnodes.items():
        cnode_dest = cap_locations[cnode_name]
        cnode_size = cnode_info['size']
        cnode_guard = cnode_info['guard']
        op_list.append(CNodeCreateOperation(cnode_dest, cnode_size, cnode_guard))
    # Generate creations for all other caps
    for cap_name, cap_type in env.config.caps.items():
        cap_dest = cap_locations[cap_name]
        cap_type = sel4_name_mapping[cap_type]
        cap_size = env.seL4_constants.object_sizes[cap_type]
        op_list.append(CapCreateOperation(cap_type, cap_dest, cap_size))
    return op_list

def getRightsString(rights_list):
    rights_flags = []
    rights_flags.append('CAP_ALLOW_WRITE') if 'write' in rights_list else None
    rights_flags.append('CAP_ALLOW_READ') if 'read' in rights_list else None
    rights_flags.append('CAP_ALLOW_GRANT') if 'grant' in rights_list else None
    rights_flags.append('CAP_ALLOW_GRANT_REPLY') if 'grant_reply' in rights_list else None

    return ('(' + ' | '.join(rights_flags) + ')') if len(rights_flags) else 0

def genCapMintOpList(cap_locations):
    op_list = []
    for cap_name, mod_info in env.config.cap_modifications.items():
        original = mod_info['original']
        src = cap_locations[original]
        dest = cap_locations[cap_name]
        rights = mod_info['rights']
        rights_string = getRightsString(rights)
        badge = mod_info['badge'] if 'badge' in mod_info else 0
        op_list.append(CapMintOperation(badge, src, dest, rights_string))
    return op_list

def genCapCopyOpList(cap_locations):
    op_list = []
    for cnode_name, cnode_info in env.config.cnodes.items():
        for cap_pos, cap_name in cnode_info.items():
            if type(cap_pos) is not int:
                continue
            depth = int(cnode_info['size']) + int(cnode_info['guard'])
            src = cap_locations[cap_name]
            dest_root = cap_locations[cnode_name]
            op_list.append(CapCopyOperation(src, dest_root, cap_pos, depth))
    return op_list

def genTCBSetupOpList(cap_locations, load_segments_dict):
    op_list = []
    for tcb_name, tcb_config in env.config.threads.items():
        cspace_name = tcb_config['cspace']
        vspace_name = tcb_config['vspace']

        cspace = cap_locations[cspace_name]
        vspace = cap_locations[vspace_name]

        thread_name = env.config.vspaces[vspace_name]
        entry_addr = env.startup_threads[thread_name].getEntryAddress()



        # We also need to find an acceptable location for the ipc buffer and the stack.
        # Starting at the highest segment address, let's skip a frame and put the IPC buffer there,
        # and skip another frame and put the stack there. That should prevent buffer- and stack- overruns
        load_segments = load_segments_dict[vspace_name]
        vaddr = max([segment.vaddr + segment.size for segment in load_segments])

        thread_name = env.config.vspaces[vspace_name]
        thread = env.startup_threads[thread_name]

        vaddr += 4096
        if 'ipc_buffer' in tcb_config:
            ipc_buffer_addr = vaddr
            ipc_buffer = cap_locations[tcb_config['ipc_buffer']]
            vaddr += 4096*2 # Skip two pages for IPC buffer and blank page
            op_list.append(MapFrameOperation(ipc_buffer, vspace, ipc_buffer_addr))
        else:
            ipc_buffer_addr = 0
            ipc_buffer = 0

        stack_addr = vaddr
        if 'stack_size' in tcb_config:
            stack_size = tcb_config['stack_size'] + calcPadding(tcb_config['stack_size'], 4096)
        else:
            stack_size = 4096*4 # Seems reasonable

        # Generate create ops and map frame ops for stack
        for addr in range(stack_addr, stack_addr + stack_size, 4096):
            # Generate a name and an address for it
            stack_frame_cap_name = f'{thread_name}_stack_frame_{addr}__'
            cap_locations.append(stack_frame_cap_name)
            stack_frame_cap = cap_locations[stack_frame_cap_name]

            op_list.append(CapCreateOperation(sel4_name_mapping['frame'], stack_frame_cap, 12))
            op_list.append(MapFrameOperation(stack_frame_cap, vspace, addr))

        op_list.append(TCBSetupOperation(
            cap_locations[tcb_name], cspace, vspace, ipc_buffer, ipc_buffer_addr, entry_addr, stack_addr + stack_size))




    return op_list

def genCapOpList(cap_locations, load_segments_dict):
    op_list = OperationList()
    op_list.append(
        genCapCreateOpList(cap_locations) +
        genCapMintOpList(cap_locations) +
        genCapCopyOpList(cap_locations) +
        ts_paging.genSegmentLoadOps(cap_locations, load_segments_dict) +
        genTCBSetupOpList(cap_locations, load_segments_dict))
    return op_list

def genTailspringData():
    emitLine('#pragma once')
    emitLine('#include "tailspring.hpp"')

    load_segments_dict = ts_st.genStartupThreadsObjFile()

    [segment.emitExterns() for segment_list in load_segments_dict.values() for segment in segment_list]

    cap_locations = getCapLocations()

    cap_op_list = genCapOpList(cap_locations, load_segments_dict)
    cap_op_list.emit('cap_operations')

    emitDefine('NUM_OPERATIONS', '(sizeof(cap_operations) / sizeof(cap_operations[0]))')

    num_slots_required = cap_locations.getSlotsRequired()
    emitDefineWord('SLOTS_REQUIRED', num_slots_required)

    emitDefineWord('BYTES_REQUIRED', cap_op_list.getBytesRequired())