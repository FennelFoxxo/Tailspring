from tailspring_types import *
from tailspring_globals import *

# Start-inclusive, end-exclusive
def doRangesOverlap(range1, range2):
    lower_range = range1 if range1[0] < range2[0] else range2
    upper_range = range1 if lower_range == range2 else range2
    # Ranges overlap if the start of the upper range is less than the end of the lower range
    return upper_range[0] < lower_range[1]

# How many bits of address each structure uses during virtual address translation
paging_structures_bits = {
    PagingEnums.PML4:   9,
    PagingEnums.PDPT:   9,
    PagingEnums.PD:     9,
    PagingEnums.PT:     9,
    PagingEnums.Page:   12
}

# Arranged from top-most structure to bottom-most
x86_64_paging_structures_order = [PagingEnums.PML4, PagingEnums.PDPT, PagingEnums.PD, PagingEnums.PT, PagingEnums.Page]

class PagingStructure:
    def __init__(self, structure_type, structures_order, vaddr):
        self.structure_type = structure_type
        self.structures_order = structures_order
        self.vaddr = vaddr
        self.children = []
        self.addressable_bits = paging_structures_bits[self.structure_type]
        self.index_in_order = self.structures_order.index(self.structure_type)

        # How many bits of address can this structure cover?
        # e.x. PT covers 21 bits total, PMLT covers 48 bits, etc.
        self.total_addressable_bits = 0
        for i in range(self.index_in_order, len(self.structures_order)):
            self.total_addressable_bits += paging_structures_bits[self.structures_order[i]]

    def getAddressableRange(self):
        return (self.vaddr, self.vaddr + 1 << self.total_addressable_bits)

    def createChildrenToCoverRanges(self, load_ranges):
        # If this object is the penultimate element in the order, we don't need to create any children because the
        # next element would be the lowest structure (a single page) and we don't need to keep track of individual pages
        if self.index_in_order == len(self.structures_order) - 2:
            return

        possible_children_num = 1 << self.addressable_bits
        children_total_addressable_bits = self.total_addressable_bits - self.addressable_bits

        # For each paging structure that is lower than this one,
        # see if its range would overlap with the ranges we need to load and create the structure if it does
        for i in range(possible_children_num):
            candidate_vaddr_lower = self.vaddr + i << children_total_addressable_bits
            candidate_vaddr_upper = candidate_vaddr_lower + (1 << children_total_addressable_bits)

            # Do any ranges overlap?
            overlaps = False
            for load_range in load_ranges:
                if doRangesOverlap((candidate_vaddr_lower, candidate_vaddr_upper), load_range):
                    overlaps = True

            # If any do overlap, then add the candidate as a child and have it create children too
            if overlaps:
                new_child = PagingStructure(
                    self.structures_order[self.index_in_order+1],
                    self.structures_order,
                    candidate_vaddr_lower)
                new_child.createChildrenToCoverRanges(load_ranges)
                self.children.append(new_child)
    
    def genCreateOps(self, vspace_name, cap_locations):
        # If this is the top level cap, use the vspace name as the cap name
        # Otherwise, create a unique identifier
        if self.index_in_order == 0:
            cap_name = vspace_name
        else:
            cap_name = f'{vspace_name}_{self.structure_type.name}_{self.vaddr}__'
        cap_locations.append(cap_name)
        
        cap_dest = cap_locations[cap_name]
        cap_type = sel4_name_mapping[self.structure_type]
        cap_size = env.seL4_constants.object_sizes[cap_type]
        
        op_list = [CapCreateOperation(cap_type, cap_dest, cap_size)]
        [op_list.extend(child.genCreateOps(vspace_name, cap_locations)) for child in self.children]
        return op_list
        
def genPagingStructuresCreationOps(cap_locations, vspace_name, load_segments):
    address_ranges_to_map = [(segment.vaddr, segment.vaddr + segment.size) for segment in load_segments]
    mode = env.seL4_constants.paging.mode
    
    if mode == 'x86-64':
        top_paging_structure = PagingStructure(x86_64_paging_structures_order[0], x86_64_paging_structures_order, 0)
    else:
        raise Exception(f"Don't know how to create paging structures for {mode}")
    
    top_paging_structure.createChildrenToCoverRanges(address_ranges_to_map)
    return top_paging_structure.genCreateOps(vspace_name, cap_locations)

def genSegmentLoadOps(cap_locations, load_segments_dict):
    op_list = []
    for vspace_name, load_segments in load_segments_dict.items():
        op_list += genPagingStructuresCreationOps(cap_locations, vspace_name, load_segments)
    return op_list