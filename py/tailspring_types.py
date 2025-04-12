from tailspring_globals import *

from elftools.elf.elffile import ELFFile

class Operation:
    def toString(self, op_name, **kwargs):
        initializers = ', '.join([f'.{key}={val}' for key, val in kwargs.items()])
        return f'{{ {op_name.upper()}, .{op_name.lower()} = {{ {initializers} }} }}'

class CapCreateOperation(Operation):
    def __init__(self, cap_type, dest, size_bits):
        self.cap_type = cap_type
        self.dest = dest
        self.size_bits = size_bits
        self.bytes_required = 1 << size_bits
    def __str__(self):
        return self.toString('create_op',
            cap_type = self.cap_type,
            bytes_required = self.bytes_required,
            dest = self.dest,
            size_bits = self.size_bits)

class CNodeCreateOperation(Operation):
    def __init__(self, dest, size_bits, guard):
        self.dest = dest
        self.size_bits = size_bits
        self.bytes_required = 1 << (size_bits + env.seL4_constants.literals.seL4_SlotBits)
        self.guard = guard
    def __str__(self):
        create_op =self.toString('create_op',
            cap_type = 'seL4_CapTableObject',
            bytes_required = self.bytes_required,
            dest = 0,
            size_bits = self.size_bits)

        mutate_op = self.toString('mutate_op',
            guard = self.guard,
            src = 0,
            dest = self.dest)

        return create_op + ',\n' + mutate_op

class CapMintOperation(Operation):
    def __init__(self, badge, src, dest, rights):
        self.badge = badge
        self.src = src
        self.dest = dest
        self.rights = rights
    def __str__(self):
        return self.toString('mint_op',
            badge = self.badge,
            src = self.src,
            dest = self.dest,
            rights = self.rights)

class CapCopyOperation(Operation):
    def __init__(self, src, dest_root, dest_index, dest_depth):
        self.src = src
        self.dest_root = dest_root
        self.dest_index = dest_index
        self.dest_depth = dest_depth
    def __str__(self):
        return self.toString('copy_op',
            src = self.src,
            dest_root = self.dest_root,
            dest_index = self.dest_index,
            dest_depth = self.dest_depth)

class MapOperation(Operation):
    def __init__(self, service, vspace, vaddr, mapping_func_index):
        self.service = service
        self.vspace = vspace
        self.vaddr = vaddr
        self.mapping_func_index = mapping_func_index
    def __str__(self):
        return self.toString('map_op',
            vaddr = self.vaddr,
            service = self.service,
            vspace = self.vspace,
            mapping_func_index = self.mapping_func_index)

class SegmentLoadOperation(Operation):
    def __init__(self, segment_start_vaddr, segment_dest_vaddr, segment_length, vspace):
        self.segment_start_vaddr = segment_start_vaddr
        self.segment_dest_vaddr = segment_dest_vaddr
        self.segment_length = segment_length
        self.vspace = vspace
    def __str__(self):
        return self.toString('segment_load_op',
            segment_start_vaddr = self.segment_start_vaddr,
            segment_dest_vaddr = self.segment_dest_vaddr,
            segment_length = self.segment_length,
            vspace = self.vspace)

class TCBSetupOperation(Operation):
    def __init__(self, tcb, cspace, vspace, entry_addr):
        self.tcb = tcb
        self.cspace = cspace
        self.vspace = vspace
        self.entry_addr = entry_addr
    def __str__(self):
        return self.toString('tcb_setup_op',
            entry_addr = self.entry_addr,
            cspace = self.cspace,
            vspace = self.vspace,
            tcb = self.tcb)

class OperationList:
    def __init__(self):
        self.create_op_list = []
        self.mint_op_list = []
        self.copy_op_list = []
        self.map_op_list = []
        self.segment_load_op_list = []
        self.tcb_setup_op_list = []

    def appendSingle(self, op):
        if type(op) in (CapCreateOperation, CNodeCreateOperation):
            self.create_op_list.append(op)
        elif type(op) == CapMintOperation:
            self.mint_op_list.append(op)
        elif type(op) == CapCopyOperation:
            self.copy_op_list.append(op)
        elif type(op) == MapOperation:
            self.map_op_list.append(op)
        elif type(op) == SegmentLoadOperation:
            self.segment_load_op_list.append(op)
        elif type(op) == TCBSetupOperation:
            self.tcb_setup_op_list.append(op)

    def append(self, ops):
        if type(ops) == list:
            [self.appendSingle(each_op) for each_op in ops]
        else:
            self.appendSingle(ops)

    def getBytesRequired(self):
        return sum([1 << (op.size_bits) for op in self.create_op_list])

    def getOpList(self):
        # Sort so that biggest operations are at the beginning
        self.create_op_list.sort(key = lambda op: op.bytes_required, reverse=True)
        return  (self.create_op_list
                + self.mint_op_list
                + self.copy_op_list
                + self.map_op_list
                + self.segment_load_op_list
                + self.tcb_setup_op_list)

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

    def getEntryAddress(self):
        return self.elf_file.header.e_entry

class LoadSegment:
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


__all__ = [att for att in dir() if att.endswith('Operation')] + ['OperationList', 'CapLocations', 'ThreadData', 'LoadSegment']