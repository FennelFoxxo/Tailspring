from tailspring_globals import *

from elftools.elf.elffile import ELFFile

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
        self.size_bits = slot_bits + seL4_constants.literals.seL4_SlotBits
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

class OperationList:
    def __init__(self):
        self.create_op_list = []
        self.mint_op_list = []
        self.copy_op_list = []

    def append(self, op):
        if type(op) in (CapCreateOperation, CNodeCreateOperation):
            self.create_op_list.append(op)
        elif type(op) == CapMintOperation:
            self.mint_op_list.append(op)
        elif type(op) == CapCopyOperation:
            self.copy_op_list.append(op)

    def getNumCreateOps(self):
        return len(self.create_op_list)

    def getNumMintOps(self):
        return len(self.mint_op_list)

    def getNumCopyOps(self):
        return len(self.copy_op_list)

    def getNumOps(self):
        return self.getNumCreateOps() + self.getNumMintOps() + self.getNumCopyOps()

    def getBytesRequired(self):
        return sum([1 << (op.size_bits) for op in self.create_op_list])

    def getOpList(self):
        # Sort so that biggest operations are at the beginning
        self.create_op_list.sort(key = lambda op: op.size_bits, reverse=True)
        return self.create_op_list + self.mint_op_list + self.copy_op_list

    def formatAsC(self, var_name):
        output_string = f'CapOperation {var_name}[] = {{\n'

        op_string = ',\n'.join([str(op) for op in self.getOpList()])
        output_string += op_string

        output_string += '\n};\n'
        return output_string

class CapLocations:
    def __init__(self):
        self.cap_locations = {}
        # Start at 1 to use 0 as a temp slot for caps that need to be mutated
        self.next_free_cap = 1
    
    def append(self, cap_name):
        self.cap_locations[cap_name] = self.next_free_cap
        self.next_free_cap += 1

    def getSlotsRequired(self):
        return self.next_free_cap
    
    def __getitem__(self, cap_name):
        return self.cap_locations[cap_name]

class ThreadData:
    def __init__(self, filename):
        # This needs to be kept open for program lifetime to read segments
        self.f = open(filename, 'rb')
        self.elf_file = ELFFile(self.f)
        self.load_segments = list(self.elf_file.iter_segments('PT_LOAD'))

    def getNumSegments(self):
        return len(self.load_segments)
    
    def getSegmentData(self, segment_index):
        return self.load_segments[segment_index].data()
    
    def formatSegmentDataAsC(self, segment_index, var_name):
        chunk_size = 4096
        output_string = f'uint8_t {var_name}[] = {{'
        segment_data_to_write = self.getSegmentData(segment_index)
        first = True
        for i in range(0, len(segment_data_to_write), chunk_size):
            if not first:
                output_string += ','
            else:
                first = False
            output_string += ','.join(map(str, segment_data_to_write[i:i+chunk_size]))
        output_string += '};\n'
        return output_string



__all__ = [att for att in dir() if att.endswith('Operation')] + ['OperationList', 'CapLocations', 'ThreadData']