import tailspring.context as context
import tailspring.ts_enums as ts_enums
import tailspring.ts_types as ts_types
import tailspring.op_types as op_types
from typing import Optional, List, Dict


class Range:
    def __init__(self, lower: int, upper: int):
        self.lower = lower
        self.upper = upper

    def overlaps_with(self, other: 'Range') -> bool:
        # Whichever range has the lower bound
        lower_range = self if self.lower < other.lower else other
        # Whichever range has the higher bound i.e. whichever isn't lower_range
        upper_range = self if lower_range == other else other

        return upper_range.lower < lower_range.upper


class PagingArchInfo:
    def __init__(self, arch: ts_enums.Arch):
        # Order of paging structures from highest to lowest
        self.order: List[ts_enums.CapType] = []

        # Number of bits of vaddr each paging structure translates
        self.bits: Dict[ts_enums.CapType, int] = {}

        # C name of the mapping function needed to map in a given paging structure, without any wrapper_ or ENABLE_ prefixes
        self.mapping_funcs: Dict[ts_enums.CapType, str] = {}

        if arch == ts_enums.Arch.x86_64:
            self.order = [ts_enums.CapType.pml4, ts_enums.CapType.pdpt, ts_enums.CapType.page_directory, ts_enums.CapType.page_table, ts_enums.CapType.x86_4K]
            self.bits = {
                ts_enums.CapType.pml4: 9,
                ts_enums.CapType.pdpt: 9,
                ts_enums.CapType.page_directory: 9,
                ts_enums.CapType.page_table: 9,
                ts_enums.CapType.x86_4K: 12
            }
            self.mapping_funcs = {
                ts_enums.CapType.pml4: 'X86_ASIDPool_Assign',
                ts_enums.CapType.pdpt: 'X86_PDPT_Map',
                ts_enums.CapType.page_directory: 'X86_PageDirectory_Map',
                ts_enums.CapType.page_table: 'X86_PageTable_Map',
                ts_enums.CapType.x86_4K: 'X86_PAGE_MAP'
            }

    # Returns the next (lower) paging structure after the one passed in
    def next_structure(self, current: ts_enums.CapType) -> Optional[ts_enums.CapType]:
        if current is None:
            return None
        current_index = self.order.index(current)
        return self.order[current_index + 1] if current_index + 1 < len(self.order) else None

    def get_topmost_structure(self) -> ts_enums.CapType:
        return self.order[0]

    # Returns if the structure passed in is the topmost paging structure in the order
    def is_topmost_structure(self, structure: ts_enums.CapType) -> bool:
        return self.order.index(structure) == 0

    # Sums up the addressable bits from the lowest structure up to the one passed in i.e. how many bits of address space can this structure cover?
    def sum_bits_up_to_structure(self, structure: ts_enums.CapType) -> int:
        current_index = self.order.index(structure)
        total_bits = 0
        for i in range(current_index, len(self.order)):
            total_bits += self.bits[self.order[i]]
        return total_bits

    # How many bits of a vaddr does this structure translate i.e. log2 of page entries in this structure
    def get_bits_for_structure(self, structure: ts_enums.CapType) -> int:
        return self.bits[structure]

    def get_mapping_func_for_structure(self, structure: ts_enums.CapType) -> str:
        return self.mapping_funcs[structure]

    def get_mapping_func_enable_str(self):
        s = ''
        for cap in self.order:
            mapping_func_name_upper = self.mapping_funcs[cap].upper()
            s += f'ENABLE_{mapping_func_name_upper}\n'
        return s


# Represents a paging structure and vaddr, such as a page table mapped at address 0x200000
class PagingStructure:
    def __init__(self, structure_type: ts_enums.CapType, paging_arch_info: PagingArchInfo, vaddr: int):
        self.structure_type = structure_type
        self.paging_arch_info = paging_arch_info
        self.vaddr = vaddr

        # Dict of paging structures underneath this current one, i.e. a page directory might map 3 page tables
        # at entries 1 3 and 5, so there will be PT PagingStructures in self.children at those indexes
        self.children: Dict[int, PagingStructure] = {}

        # Log2 of how many page entries this paging structure contains
        self.addressable_bits = paging_arch_info.get_bits_for_structure(self.structure_type)

        # How many bits of address can this structure cover?
        # e.x. PT covers 21 bits total, PML4 covers 48 bits, etc.
        self.total_addressable_bits = paging_arch_info.sum_bits_up_to_structure(structure_type)

    def get_addressable_range(self):
        return self.vaddr, self.vaddr + 1 << self.total_addressable_bits

    def create_children_to_cover_range(self, range_to_cover: Range):
        # If this object is the penultimate element in the order, we don't need to create any children because the
        # next element would be the lowest structure (a single page) and we don't need to keep track of individual pages
        if self.paging_arch_info.next_structure(self.paging_arch_info.next_structure(self.structure_type)) is None:
            return

        possible_children_num = 1 << self.addressable_bits
        children_total_addressable_bits = self.total_addressable_bits - self.addressable_bits

        # For each paging structure that is lower than this one,
        # see if its range would overlap with the ranges we need to load and create the structure if it does
        for i in range(possible_children_num):
            candidate_vaddr_lower = self.vaddr + (i << children_total_addressable_bits)
            candidate_vaddr_upper = candidate_vaddr_lower + (1 << children_total_addressable_bits)
            candidate_vaddr_range = Range(candidate_vaddr_lower, candidate_vaddr_upper)

            # If the candidate paging structure can map the range, then add it as a child and have it create children too
            if range_to_cover.overlaps_with(candidate_vaddr_range):
                if i in self.children:
                    # If the child already exists (possible if this func is called multiple times) then we don't want to recreate it
                    self.children[i].create_children_to_cover_range(range_to_cover)
                else:
                    # If child doesn't exist then create a new one
                    new_child = PagingStructure(
                        self.paging_arch_info.next_structure(self.structure_type),
                        self.paging_arch_info,
                        candidate_vaddr_lower)
                    new_child.create_children_to_cover_range(range_to_cover)
                    self.children[i] = new_child

    def gen_ops(self, vspace: ts_types.VSpace, ctx: 'context.Context'):
        # If this is the top level cap, use the vspace name as the cap name
        # Otherwise, create a unique identifier
        if self.paging_arch_info.is_topmost_structure(self.structure_type):
            cap = vspace
        else:
            cap_name = f'{vspace.name}_{self.structure_type.name}_{self.vaddr}__'
            can_be_derived = not self.structure_type in ctx.underivable_cap_types
            cap = ts_types.Cap(cap_name, self.structure_type, can_be_derived)
            ctx.cap_addresses.append(cap)

        size_bits = ctx.sel4_info['object_sizes'][cap.type.value]
        create_op = op_types.CapCreateOperation(dest=cap, size_bits=size_bits)

        mapping_func_name = self.paging_arch_info.get_mapping_func_for_structure(self.structure_type)
        map_op = op_types.MapOperation(service=cap, vspace=vspace, vaddr=self.vaddr,
                                       map_func=f'wrapper_{mapping_func_name}')

        ctx.ops_list.append(create_op)
        ctx.ops_list.append(map_op)

        for child in self.children.values():
            child.gen_ops(vspace, ctx)

    def __str__(self):
        lines = [f"{self.structure_type.name} @ [{hex(self.vaddr)}, {hex(self.vaddr + (1 << self.total_addressable_bits))})"]
        for child in self.children.values():
            child_strs_lines = str(child).split('\n')
            lines.append('\n'.join(['  ' + line for line in child_strs_lines]))
        return '\n'.join(lines)


def create_paging_structures(ctx: 'context.Context'):
    arch_info = ctx.paging_arch_info = PagingArchInfo(ctx.arch)
    for vspace_name, vspace in ctx.vspaces.items():
        paging_structure = PagingStructure(arch_info.get_topmost_structure(), arch_info, 0)
        for chunk in vspace.binary_chunks:
            # Need to create page table structures to map every chunk
            chunk_lower_vaddr = chunk.dest_vaddr_aligned
            chunk_upper_vaddr = chunk_lower_vaddr + chunk.total_length_with_padding
            chunk_range = Range(chunk_lower_vaddr, chunk_upper_vaddr)
            paging_structure.create_children_to_cover_range(chunk_range)
        ctx.paging_structures[vspace_name] = paging_structure
