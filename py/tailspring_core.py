from tailspring_types import *
from tailspring_globals import *
import tailspring_startup_threads as ts_st

sel4_name_mapping = {
    'tcb': 'seL4_TCBObject',
    'frame': 'seL4_X86_4K',
    'endpoint': 'seL4_EndpointObject'
}

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

def getObjectSize(object_type):
    return env.seL4_constants.object_sizes[object_type]

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
        cap_size = getObjectSize(cap_type)
        op_list.append(CapCreateOperation(cap_type, cap_dest, cap_size))
    # Sort so that biggest operations are at the beginning
    op_list.sort(key = lambda op: op.bytes_required, reverse=True)
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


def genCapOpList(cap_locations):
    op_list = OperationList()
    [op_list.append(op) for op in genCapCreateOpList(cap_locations)]
    [op_list.append(op) for op in genCapMintOpList(cap_locations)]
    [op_list.append(op) for op in genCapCopyOpList(cap_locations)]
    return op_list

def genTailspringData():
    emitLine('#pragma once')
    emitLine('#include "tailspring.hpp"')

    segment_load_ops = ts_st.genStartupThreadsObjFile()

    cap_locations = getCapLocations()

    cap_op_list = genCapOpList(cap_locations)
    cap_op_list.emit('cap_operations')

    emitDefine('NUM_OPERATIONS', cap_op_list.getNumOps())
    emitDefine('NUM_CREATE_OPERATIONS', cap_op_list.getNumCreateOps())

    num_slots_required = cap_locations.getSlotsRequired()
    emitDefineWord('SLOTS_REQUIRED', num_slots_required)

    emitDefineWord('BYTES_REQUIRED', cap_op_list.getBytesRequired())

    [op.emitExterns() for op in segment_load_ops]