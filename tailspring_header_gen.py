import argparse
import sys
import yaml
from elftools.elf.elffile import ELFFile
from elftools.common.exceptions import ELFError

sel4_name_mapping = {
    'tcb': 'seL4_TCBObject',
    'frame': 'seL4_X86_4K',
    'endpoint': 'seL4_EndpointObject'
}

sel4_size_mapping = {
    'seL4_TCBObject': 'seL4_TCBBits',
    'seL4_X86_4K': 'seL4_PageBits',
    'seL4_EndpointObject': 'seL4_EndpointBits'
}

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
                            print(f'Error loading elf file "{val}"\n  {e}')
                            sys.exit(1)
        setattr(namespace, self.dest, result)

class CapCreateOperation:
    def __init__(self, dest, cap_type, size_bits):
        self.dest = dest
        self.cap_type = cap_type
        self.size_bits = size_bits
    def __str__(self):
        return f'{{cap_create, .create_op={{{self.dest}, {self.cap_type}, {self.size_bits}}}}}'

class CNodeCreateOperation:
    def __init__(self, dest, size_bits, guard):
        self.dest = dest
        self.size_bits = size_bits
        self.guard = guard
    def __str__(self):
        return f'{{cnode_create, .cnode_create_op={{{self.dest}, {self.size_bits}, {self.guard}}}}}'

class CapMutateOperation:
    def __init__(self, src, dest, badge):
        self.src = src
        self.dest = dest
        self.badge = badge
    def __str__(self):
        return f'{{cap_mutate, .mutate_op={{{self.src}, {self.dest}, {self.badge}}}}}'

class CapMintOperation:
    def __init__(self, src, dest, badge, rights):
        self.src = src
        self.dest = dest
        self.badge = badge
        self.rights = rights
    def __str__(self):
        return f'{{cap_mint, .mint_op={{{self.src}, {self.dest}, {self.badge}, {self.rights}}}}}'

class CapCopyOperation:
    def __init__(self, src, dest_root, dest_index, dest_depth):
        self.src = src
        self.dest_root = dest_root
        self.dest_index = dest_index
        self.dest_depth = dest_depth
    def __str__(self):
        return f'{{cap_copy, .copy_op={{{self.src}, {self.dest_root}, {self.dest_index}, {self.dest_depth}}}}}'

def getArgs():
    parser = argparse.ArgumentParser(
        prog='Tailspring Parser',
        description='Generates C headers from a configuration file for the Tailspring thread loader')
    parser.add_argument('config_file', type=argparse.FileType('r'), help='Path to the configuration file')
    parser.add_argument('output_file', type=argparse.FileType('w'), help='Path to the output generated header file')
    parser.add_argument('thread_executables', nargs='*', action=KeyValueAction, help='Key-value pairs mapping executable names in the configuration file to the executable path')
    args = parser.parse_args()
    config = yaml.safe_load(args.config_file)
    output_file = args.output_file
    return (config, output_file, args.thread_executables)


def addPreamble(output_string):
    preamble = '''
#pragma once
#include <sel4/sel4.h>
#define CAP_ALLOW_WRITE (1<<0)
#define CAP_ALLOW_READ (1<<1)
#define CAP_ALLOW_GRANT (1<<2)
#define CAP_ALLOW_GRANT_REPLY (1<<3)
struct CapCreateOperation {seL4_Word dest;seL4_Word cap_type;seL4_Word size_bits;};
struct CNodeCreateOperation {seL4_Word dest;seL4_Word size_bits;seL4_Word guard;};
struct CapMintOperation {seL4_Word src;seL4_Word dest;seL4_Word badge;seL4_CapRights_t rights;};
struct CapCopyOperation {seL4_Word src;seL4_Word dest_root;seL4_Word dest_index;seL4_Word dest_depth;};
enum CapOperationType {cap_create,cnode_create,cap_mint,cap_copy};
struct CapOperation {enum CapOperationType op_type;union {struct CapCreateOperation create_op;struct CNodeCreateOperation cnode_create_op;struct CapMintOperation mint_op;struct CapCopyOperation copy_op;};};
'''
    return output_string + '\n' + preamble

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


def generateCapCreateOpList(config, cap_locations):
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
        cap_size = sel4_size_mapping[cap_type]
        op_list.append(CapCreateOperation(cap_dest, cap_type, cap_size))
    return op_list

def getRightsString(rights_list):
    rights_flags = []
    rights_flags.append('CAP_ALLOW_WRITE') if 'write' in rights_list else None
    rights_flags.append('CAP_ALLOW_READ') if 'read' in rights_list else None
    rights_flags.append('CAP_ALLOW_GRANT') if 'grant' in rights_list else None
    rights_flags.append('CAP_ALLOW_GRANT_REPLY') if 'grant_reply' in rights_list else None
    
    return '&'.join(rights_flags) if len(rights_flags) else 0

def generateCapMintOpList(config, cap_locations):
    op_list = []
    for cap_name, mod_info in config['cap_modifications'].items():
        original = mod_info['original']
        src = cap_locations[original]
        dest = cap_locations[cap_name]
        rights = mod_info['rights']
        rights_string = getRightsString(rights)
        badge = mod_info['badge'] if 'badge' in mod_info else 0
        op_list.append(CapMintOperation(src, dest, badge, rights_string))
    return op_list

def generateCapCopyOpList(config, cap_locations):
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
        

def generateCapOpList(config, cap_locations):
    op_list = []
    op_list += generateCapCreateOpList(config, cap_locations)
    op_list += generateCapMintOpList(config, cap_locations)
    op_list += generateCapCopyOpList(config, cap_locations)
    return op_list

def getTailspringHeader(config, thread_executables):
    cap_locations = getCapLocations(config)
    
    output_string = ''
    output_string = addPreamble(output_string)

    output_string += '\nstruct CapOperation cap_operations[] = {\n'

    op_list = generateCapOpList(config, cap_locations)
    op_string = ',\n'.join([str(op) for op in op_list])
    output_string += op_string

    output_string += '\n};\n'

    return output_string

if __name__ == '__main__':
    
    config, output_file, thread_executables = getArgs()

    header_string = getTailspringHeader(config, thread_executables)
    output_file.write(header_string)

