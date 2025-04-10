import argparse
import yaml
import json
import subprocess
from elftools.elf.elffile import ELFFile
from elftools.common.exceptions import ELFError

sel4_name_mapping = {
    'tcb': 'seL4_TCBObject',
    'frame': 'seL4_X86_4K',
    'endpoint': 'seL4_EndpointObject'
}

sel4_constants = {}

class KeyValueAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        result = {}
        if isinstance(values, list):
            for value in values:
                if '=' in value:
                    key, val = value.split('=', 1)
                    with open(val, 'rb') as f:
                        try:
                            result[key] = ELFFile(f)
                        except ELFError as e:
                            parser.error(f'Error loading elf file "{val}"\n  {e}')
        setattr(namespace, self.dest, result)

class CapCreateOperation:
    def __init__(self, cap_type, dest, size_bits):
        self.cap_type = cap_type
        self.dest = dest
        self.size_bits = size_bits
    def __str__(self):
        return f'{{CAP_CREATE, .cap_create_op={{{self.cap_type}, {self.dest}, {self.size_bits}}}}}'

class CNodeCreateOperation:
    def __init__(self, dest, slot_bits, guard):
        self.dest = dest
        self.slot_bits = slot_bits
        self.size_bits = slot_bits + sel4_constants['seL4_SlotBits']
        self.guard = guard
    def __str__(self):
        return f'{{CNODE_CREATE, .cnode_create_op={{{self.dest}, {self.slot_bits}, {self.guard}}}}}'

class CapMintOperation:
    def __init__(self, badge, src, dest, rights):
        self.badge = badge
        self.src = src
        self.dest = dest
        self.rights = rights
    def __str__(self):
        return f'{{CAP_MINT, .mint_op={{{self.badge}, {self.src}, {self.dest}, {self.rights}}}}}'

class CapCopyOperation:
    def __init__(self, src, dest_root, dest_index, dest_depth):
        self.src = src
        self.dest_root = dest_root
        self.dest_index = dest_index
        self.dest_depth = dest_depth
    def __str__(self):
        return f'{{CAP_COPY, .copy_op={{{self.src}, {self.dest_root}, {self.dest_index}, {self.dest_depth}}}}}'

def isValidFile(parser, arg):
    try:
        with open(arg, 'r') as f:
            f.close()
        return arg
    except IOError:
        parser.error(f'"{arg}" is not a valid path')

def getArgs():
    parser = argparse.ArgumentParser(
        prog='Tailspring Parser',
        description='Generates C headers from a configuration file for the Tailspring thread loader')
    
    parser.add_argument('config_file', type=argparse.FileType('r'), help='Path to the configuration file')
    parser.add_argument('get_sel4_info_program', type=lambda x: isValidFile(parser, x), help='Path to the compiled get_sel4_info binary')
    parser.add_argument('output_file', type=argparse.FileType('w'), help='Path to the output generated header file')
    parser.add_argument('thread_executables', nargs='*', action=KeyValueAction, help='Key-value pairs mapping executable names in the configuration file to the executable path')
    
    args = parser.parse_args()
    
    config = yaml.safe_load(args.config_file)
    return (config, args.get_sel4_info_program, args.output_file, args.thread_executables)

def formatDefine(name, value):
    return f'#define {name} ({value})\n'

def formatDefineWord(name, value):
    return f'#define {name} ((seL4_Word){value})\n'

def addPreamble():
    preamble = '''\
#pragma once
#include <sel4/sel4.h>
#include <stdint.h>
typedef struct {seL4_Word cap_type;uint32_t dest;uint8_t size_bits;} CapCreateOperation;
typedef struct {uint32_t dest;uint8_t slot_bits;uint8_t guard;} CNodeCreateOperation;
typedef struct {seL4_Word badge;uint32_t src;uint32_t dest;uint8_t rights;} CapMintOperation;
typedef struct {uint32_t src;uint32_t dest_root;uint32_t dest_index;uint8_t dest_depth;} CapCopyOperation;
typedef enum {CAP_CREATE,CNODE_CREATE,CAP_MINT,CAP_COPY} CapOperationType;
typedef struct {CapOperationType op_type;union {CapCreateOperation cap_create_op;CNodeCreateOperation cnode_create_op;CapMintOperation mint_op;CapCopyOperation copy_op;};} CapOperation;
'''
    preamble += formatDefine("CAP_ALLOW_WRITE",         "1<<0")
    preamble += formatDefine("CAP_ALLOW_READ",          "1<<1")
    preamble += formatDefine("CAP_ALLOW_GRANT",         "1<<2")
    preamble += formatDefine("CAP_ALLOW_GRANT_REPLY",   "1<<3")
    preamble += formatDefine("CREATE_OP_SIZE_BITS(cap_op)", "cap_op.op_type == CAP_CREATE ? cap_op.cap_create_op.size_bits : cap_op.cnode_create_op.slot_bits + seL4_SlotBits")
    return preamble

def getCapLocations(config):
    cap_locations = {}
    index = 1 # Start at 1 since 0 is used as temp slot
    for key in config['cnodes']:
        cap_locations[key] = index
        index += 1
    for key in config['caps']:
        cap_locations[key] = index
        index += 1
    for key in config['cap_modifications']:
        cap_locations[key] = index
        index += 1
    return cap_locations

def getObjectSize(object_type):
    return sel4_constants['object_sizes'][object_type]

def genCapCreateOpList(config, cap_locations):
    op_list = []
    # Generate creations for CNodes
    for cnode_name, cnode_info in config['cnodes'].items():
        cnode_dest = cap_locations[cnode_name]
        cnode_size = cnode_info['size']
        cnode_guard = cnode_info['guard']
        op_list.append(CNodeCreateOperation(cnode_dest, cnode_size, cnode_guard))
    # Generate creations for all other caps
    for cap_name, cap_type in config['caps'].items():
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
    for cap_name, mod_info in config['cap_modifications'].items():
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
    for cnode_name, cnode_info in config['cnodes'].items():
        for cap_pos, cap_name in cnode_info.items():
            if type(cap_pos) is not int:
                continue
            depth = int(cnode_info['size']) + int(cnode_info['guard'])
            src = cap_locations[cap_name]
            dest_root = cap_locations[cnode_name]
            op_list.append(CapCopyOperation(src, dest_root, cap_pos, depth))
    return op_list
        

def genCapOpList(config, cap_locations):
    op_list = []
    op_list += genCapCreateOpList(config, cap_locations)
    op_list += genCapMintOpList(config, cap_locations)
    op_list += genCapCopyOpList(config, cap_locations)
    return op_list

def convertCapOpListToC(cap_op_list):
    output_string = '\nCapOperation cap_operations[] = {\n'

    op_string = ',\n'.join([str(op) for op in cap_op_list])
    output_string += op_string

    output_string += '\n};\n'
    return output_string

def getFramesRequired(config, thread_executables):
    print(thread_executables)

def genTailspringHeader(config, thread_executables):
    cap_locations = getCapLocations(config)
    
    getFramesRequired(config, thread_executables)
    
    output_string = addPreamble()

    cap_op_list = genCapOpList(config, cap_locations)
    output_string += convertCapOpListToC(cap_op_list)

    num_operations = len(cap_op_list)
    num_create_operations = sum([1 if type(op) in (CapCreateOperation, CNodeCreateOperation) else 0 for op in cap_op_list])
    output_string += formatDefine('NUM_OPERATIONS', num_operations)
    output_string += formatDefine('NUM_CREATE_OPERATIONS', num_create_operations)

    num_slots_needed = max(cap_locations.values()) if len(cap_locations) else 0
    output_string += formatDefineWord('SLOTS_NEEDED', num_slots_needed)

    bytes_needed = 0
    for op in cap_op_list:
        if type(op) not in (CapCreateOperation, CNodeCreateOperation):
            continue
        bytes_needed += 1 << (op.size_bits)
    output_string += formatDefineWord('BYTES_NEEDED', bytes_needed)

    return output_string

if __name__ == '__main__':
    config, get_sel4_info_path, output_file, thread_executables = getArgs()

    sel4_constants = json.loads(subprocess.check_output(get_sel4_info_path, shell=False, encoding='utf-8'))
    

    header_string = genTailspringHeader(config, thread_executables)
    output_file.write(header_string)


