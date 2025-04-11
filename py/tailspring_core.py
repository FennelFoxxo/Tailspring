from tailspring_types import *
from tailspring_globals import *
import tailspring_startup_threads as ts_st

sel4_name_mapping = {
    'tcb': 'seL4_TCBObject',
    'frame': 'seL4_X86_4K',
    'endpoint': 'seL4_EndpointObject'
}

def formatDefine(name, value):
    return f'#define {name} ({value})\n'

def formatDefineWord(name, value):
    return f'#define {name} ((seL4_Word){value})\n'

def getPreamble():
    preamble = '''\
#pragma once
#include <sel4/sel4.h>
#include <stdint.h>
typedef struct {seL4_Word cap_type;uint32_t dest;uint8_t size_bits;} CapCreateOperation;
typedef struct {uint32_t dest;uint8_t slot_bits;uint8_t guard;} CNodeCreateOperation;
typedef struct {seL4_Word badge;uint32_t src;uint32_t dest;uint8_t rights;} CapMintOperation;
typedef struct {uint32_t src;uint32_t dest_root;uint32_t dest_index;uint8_t dest_depth;} CapCopyOperation;
typedef enum {CAP_CREATE,CNODE_CREATE,CAP_MINT,CAP_COPY} CapOperationType;
typedef struct {CapOperationType op_type;
    union {CapCreateOperation cap_create_op;CNodeCreateOperation cnode_create_op;CapMintOperation mint_op;CapCopyOperation copy_op;};
} CapOperation;
'''
    preamble += formatDefine('CAP_ALLOW_WRITE',         '1<<0')
    preamble += formatDefine('CAP_ALLOW_READ',          '1<<1')
    preamble += formatDefine('CAP_ALLOW_GRANT',         '1<<2')
    preamble += formatDefine('CAP_ALLOW_GRANT_REPLY',   '1<<3')
    preamble += formatDefine('CREATE_OP_SIZE_BITS(cap_op)', '(cap_op.op_type == CAP_CREATE ? cap_op.cap_create_op.size_bits : cap_op.cnode_create_op.slot_bits + seL4_SlotBits)')
    preamble += formatDefine('SYM_VAL(sym)', '(seL4_Word)(&sym)')
    preamble += 'extern void* _startup_threads_data_start;\n'
    return preamble

def getCapLocations(config):
    cap_locations = CapLocations()

    for key in config.cnodes:
        cap_locations.append(key)
    for key in config.caps:
        cap_locations.append(key)
    for key in config.cap_modifications:
        cap_locations.append(key)
    return cap_locations

def getObjectSize(object_type):
    return seL4_constants.object_sizes[object_type]

def genCapCreateOpList(config, cap_locations):
    op_list = []
    # Generate creations for CNodes
    for cnode_name, cnode_info in config.cnodes.items():
        cnode_dest = cap_locations[cnode_name]
        cnode_size = cnode_info['size']
        cnode_guard = cnode_info['guard']
        op_list.append(CNodeCreateOperation(cnode_dest, cnode_size, cnode_guard))
    # Generate creations for all other caps
    for cap_name, cap_type in config.caps.items():
        cap_dest = cap_locations[cap_name]
        cap_type = sel4_name_mapping[cap_type]
        cap_size = getObjectSize(cap_type)
        op_list.append(CapCreateOperation(cap_type, cap_dest, cap_size))
    # Sort so that biggest operations are at the beginning
    op_list.sort(key = lambda op: op.size_bits, reverse=True)
    return op_list

def getRightsString(rights_list):
    rights_flags = []
    rights_flags.append('CAP_ALLOW_WRITE') if 'write' in rights_list else None
    rights_flags.append('CAP_ALLOW_READ') if 'read' in rights_list else None
    rights_flags.append('CAP_ALLOW_GRANT') if 'grant' in rights_list else None
    rights_flags.append('CAP_ALLOW_GRANT_REPLY') if 'grant_reply' in rights_list else None
    
    return '&'.join(rights_flags) if len(rights_flags) else 0

def genCapMintOpList(config, cap_locations):
    op_list = []
    for cap_name, mod_info in config.cap_modifications.items():
        original = mod_info['original']
        src = cap_locations[original]
        dest = cap_locations[cap_name]
        rights = mod_info['rights']
        rights_string = getRightsString(rights)
        badge = mod_info['badge'] if 'badge' in mod_info else 0
        op_list.append(CapMintOperation(badge, src, dest, rights_string))
    return op_list

def genCapCopyOpList(config, cap_locations):
    op_list = []
    for cnode_name, cnode_info in config.cnodes.items():
        for cap_pos, cap_name in cnode_info.items():
            if type(cap_pos) is not int:
                continue
            depth = int(cnode_info['size']) + int(cnode_info['guard'])
            src = cap_locations[cap_name]
            dest_root = cap_locations[cnode_name]
            op_list.append(CapCopyOperation(src, dest_root, cap_pos, depth))
    return op_list
        

def genCapOpList(config, cap_locations):
    op_list = OperationList()
    [op_list.append(op) for op in genCapCreateOpList(config, cap_locations)]
    [op_list.append(op) for op in genCapMintOpList(config, cap_locations)]
    [op_list.append(op) for op in genCapCopyOpList(config, cap_locations)]
    return op_list

def genTailspringData():
    segment_load_ops = ts_st.genStartupThreadsObjFile()

    cap_locations = getCapLocations(config)
    
    output_string = getPreamble()

    cap_op_list = genCapOpList(config, cap_locations)
    output_string += cap_op_list.formatAsC('cap_operations')

    output_string += formatDefine('NUM_OPERATIONS', cap_op_list.getNumOps())
    output_string += formatDefine('NUM_CREATE_OPERATIONS', cap_op_list.getNumCreateOps())

    num_slots_required = cap_locations.getSlotsRequired()
    output_string += formatDefineWord('SLOTS_REQUIRED', num_slots_required)

    output_string += formatDefineWord('BYTES_REQUIRED', cap_op_list.getBytesRequired())
    
    output_string += ''.join([op.formatAsCExterns() for op in segment_load_ops])
    
    return output_string
