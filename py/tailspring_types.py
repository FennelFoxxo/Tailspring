from tailspring_globals import *

from elftools.elf.elffile import ELFFile

class CapCreateOperation:
    def __init__(self, cap_type, dest, size_bits):
        self.cap_type = cap_type
        self.dest = dest
        self.size_bits = size_bits
        self.bytes_required = 1 << size_bits
    def __str__(self):
        return f'{{CAP_CREATE, .create_op={{{self.cap_type}, {self.bytes_required}, {self.dest}, {self.size_bits}}}}}'

class CNodeCreateOperation:
    def __init__(self, dest, size_bits, guard):
        self.dest = dest
        self.size_bits = size_bits
        self.bytes_required = 1 << (size_bits + env.seL4_constants.literals.seL4_SlotBits)
        self.guard = guard
    def __str__(self):
        return (f'{{CAP_CREATE, .create_op={{seL4_CapTableObject, {self.bytes_required}, 0, {self.size_bits}}}}},\n'
                f'{{CAP_MUTATE, .mutate_op={{{self.guard}, 0, {self.dest}}}}}')

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

    def emit(self, var_name):
        emitLine(f'CapOperation {var_name}[] = {{')
        [emitLine(str(op) + ',') for op in self.getOpList()]
        emitLine('};')

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

    def getSegment(self, index):
        return self.load_segments[index]

class SegmentLoadOperation:
    def __init__(self, vaddr, size, parent_dir, filename):
        self.vaddr = vaddr
        self.size = size
        self.parent_dir = parent_dir
        self.filename = filename

    def getPath(self):
        return self.parent_dir / f'{self.filename}.o'

    def getSymbolPrefix(self):
        return f'_binary_{self.filename}_bin'

    def emitExterns(self):
        emitLine(f'extern void* {self.getSymbolPrefix()}_start;')
        emitLine(f'extern void* {self.getSymbolPrefix()}_size;')


__all__ = [att for att in dir() if att.endswith('Operation')] + ['OperationList', 'CapLocations', 'ThreadData']