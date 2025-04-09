#include "tailspring_gen_config.h"

#include <sel4platsupport/bootinfo.h>
#include <stdio.h>
#include <stdlib.h>

seL4_BootInfo* boot_info;
seL4_Word num_empty_slots;
seL4_Word first_empty_slot;

void halt() {
    while (1) seL4_TCB_Suspend(seL4_CapInitThreadTCB);
}

void loadBootInfo() {
    boot_info = platsupport_get_bootinfo();
    first_empty_slot = boot_info->empty.start;
    num_empty_slots = boot_info->empty.end - first_empty_slot;
}

// Comparison function for qsort
int sortCreationOpsDescendingComp(const void* a, const void* b) {
    CapOperation* op1 = (CapOperation*)a;
    CapOperation* op2 = (CapOperation*)b;
    uint8_t op1_size = (op1->op_type == cnode_create) ? (op1->cnode_create_op.size_bits + seL4_SlotBits) : (op1->create_op.size_bits);
    uint8_t op2_size = (op2->op_type == cnode_create) ? (op2->cnode_create_op.size_bits + seL4_SlotBits) : (op2->create_op.size_bits);
    // Typically if 1st < 2nd we return -1, but qsort sorts by ascending and we want descending, so we reverse the conditions
    if (op1_size < op2_size) return 1;
    if (op1_size > op2_size) return -1;
    return 0;
}

// Sort operations that create a cap by descending size
void sortCreationOpsDescending() {
    qsort(cap_operations, NUM_CREATE_OPERATIONS, sizeof(CapOperation), sortCreationOpsDescendingComp);
}

void printOp(const CapOperation* c) {
    switch (c->op_type) {
        case cap_create:
            printf("Create (size=%u) (dest=%u)\n", c->create_op.size_bits, c->create_op.dest);
            break;
            
        case cnode_create:
            printf("CNode create (size=%u) (guard=%u) (dest=%u)\n", c->cnode_create_op.size_bits, c->cnode_create_op.guard, c->cnode_create_op.dest);
            break;
        case cap_mint:
            printf("Mint (src=%u) (dest=%u) (badge=%lu) (rights=%u)\n", c->mint_op.src, c->mint_op.dest, c->mint_op.badge, c->mint_op.rights);
            break;
        case cap_copy:
            printf("Copy (src=%u) (dest_root=%u) (dest_index=%u) (dest_depth=%u)\n", c->copy_op.src, c->copy_op.dest_root, c->copy_op.dest_index, c->copy_op.dest_depth);
            break;
    }
}


int main() {

    printf("Hello world!\n");
    printf("size: %lu\n", sizeof(CapOperation));
    loadBootInfo();
    if (NUM_SLOTS_NEEDED > num_empty_slots) {
        printf("Number of slots needed (%d) is greater than number of empty slots (%lu)!\n", NUM_SLOTS_NEEDED, num_empty_slots);
        halt();
        
    
    }
    
    
    
    for (int i = 0; i < NUM_OPERATIONS; i++) {
        printOp(&cap_operations[i]);
        
    }
    printf("\n\n\n");
    sortCreationOpsDescending();
    
    for (int i = 0; i < NUM_OPERATIONS; i++) {
        printOp(&cap_operations[i]);
    }
    
    halt();
    return 0;
}