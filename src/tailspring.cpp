#include "tailspring.hpp"
#include "tailspring_gen_config.hpp"

#define NON_DEVICE_UNTYPED_ARRAY_SIZE 100

seL4_BootInfo* boot_info = NULL;
seL4_Word num_empty_slots = 0;
seL4_Word first_empty_slot = 0;

seL4_CPtr first_untyped = 0;
seL4_Word num_untyped = 0;
seL4_Word num_non_device_untyped = 0;
seL4_Word num_device_untyped = 0;
UntypedInfo non_device_untyped_array[NON_DEVICE_UNTYPED_ARRAY_SIZE];

void halt() __attribute__((noreturn));
void halt() {
    while (1) seL4_TCB_Suspend(seL4_CapInitThreadTCB);
}

void loadUntypedInfo(seL4_Word untyped_index) {
    seL4_UntypedDesc* untyped = &boot_info->untypedList[untyped_index];
    if (untyped->isDevice) {
        num_device_untyped++;
    } else {
        if (num_non_device_untyped < NON_DEVICE_UNTYPED_ARRAY_SIZE) {
            non_device_untyped_array[num_non_device_untyped].bytes_left = 1llu << untyped->sizeBits;
            non_device_untyped_array[num_non_device_untyped].cptr = untyped_index + first_untyped;
            num_non_device_untyped++;
        }
    }
}

void loadBootInfo() {
    boot_info = platsupport_get_bootinfo();

    // Get slot info
    first_empty_slot = boot_info->empty.start;
    num_empty_slots = boot_info->empty.end - first_empty_slot;

    // Get untyped info
    first_untyped = boot_info->untyped.start;
    num_untyped = boot_info->untyped.end - first_untyped;
    for (seL4_Word offset = 0; offset < num_untyped; offset++) {
        loadUntypedInfo(offset);
    }
}

void printOp(const CapOperation* c) {
    switch (c->op_type) {
        case CAP_CREATE:
            printf("Create (size=%u) (dest=%u)\n", c->cap_create_op.size_bits, c->cap_create_op.dest);
            break;

        case CNODE_CREATE:
            printf("CNode create (size=%u) (guard=%u) (dest=%u)\n", c->cnode_create_op.slot_bits, c->cnode_create_op.guard, c->cnode_create_op.dest);
            break;
        case CAP_MINT:
            printf("Mint (src=%u) (dest=%u) (badge=%lu) (rights=%u)\n", c->mint_op.src, c->mint_op.dest, c->mint_op.badge, c->mint_op.rights);
            break;
        case CAP_COPY:
            printf("Copy (src=%u) (dest_root=%u) (dest_index=%u) (dest_depth=%u)\n", c->copy_op.src, c->copy_op.dest_root, c->copy_op.dest_index, c->copy_op.dest_depth);
            break;
    }
}

seL4_Word getUntypedBestFitIndex(seL4_Word size_required) {
    // Keep track of smallest untyped that fits this object
    seL4_Word best_fit_index = ~0llu;
    seL4_Word best_fit_size = ~0llu;
    for (seL4_Word untyped_index = 0; untyped_index < num_non_device_untyped; untyped_index++) {
        seL4_Word untyped_size = non_device_untyped_array[untyped_index].bytes_left;
        // If the untyped is big enough for this object
        if (untyped_size >= size_required) {
            // If the untyped is a better fit than our current best fit
            if (untyped_size < best_fit_size) {
                best_fit_index = untyped_index;
                best_fit_size = untyped_size;
            }
        }
    }
    // Will return ~0llu if no acceptable region found
    return best_fit_index;
}

bool doCreateOp(CapOperation* cap_op) {
    seL4_Word size_required = 1llu << CREATE_OP_SIZE_BITS(*cap_op);
    seL4_Word untyped_index = getUntypedBestFitIndex(size_required);
    if (untyped_index == ~0llu) return false;
    non_device_untyped_array[untyped_index].bytes_left -= size_required;

    seL4_CPtr untyped = non_device_untyped_array[untyped_index].cptr;


    seL4_Error error;

    if (cap_op->op_type == CAP_CREATE) {
        error = seL4_Untyped_Retype(untyped,
                                    cap_op->cap_create_op.cap_type,
                                    cap_op->cap_create_op.size_bits,
                                    seL4_CapInitThreadCNode, 0, 0,
                                    first_empty_slot + cap_op->cap_create_op.dest,
                                    1);
        return (error == seL4_NoError);
    }

    // If we're creating a CNode then we need to first create it into slot 0,
    // then mutate it into its destination slot to set its guard
    error = seL4_Untyped_Retype(untyped,
                                seL4_CapTableObject,
                                cap_op->cnode_create_op.slot_bits,
                                seL4_CapInitThreadCNode, 0, 0,
                                first_empty_slot, 1);
    if (error != seL4_NoError) return false;

    error = seL4_CNode_Mutate(  seL4_CapInitThreadCNode, first_empty_slot + cap_op->cnode_create_op.dest, seL4_WordBits,
                                seL4_CapInitThreadCNode, first_empty_slot, seL4_WordBits,
                                cap_op->cnode_create_op.guard);
    return (error == seL4_NoError);
}

bool doCopyOp(CapOperation* cap_op) {
    seL4_Error error = seL4_CNode_Copy( first_empty_slot + cap_op->copy_op.dest_root,
                                        cap_op->copy_op.dest_index,
                                        cap_op->copy_op.dest_depth,
                                        seL4_CapInitThreadCNode,
                                        first_empty_slot + cap_op->copy_op.src,
                                        seL4_WordBits, seL4_AllRights);
    return (error == seL4_NoError);
}

bool doMintOp(CapOperation* cap_op) {
    seL4_CapRights_t decoded_rights = seL4_CapRights_new(   cap_op->mint_op.rights & CAP_ALLOW_GRANT_REPLY != 0,
                                                            cap_op->mint_op.rights & CAP_ALLOW_GRANT != 0,
                                                            cap_op->mint_op.rights & CAP_ALLOW_READ != 0,
                                                            cap_op->mint_op.rights & CAP_ALLOW_WRITE != 0);

    seL4_Error error = seL4_CNode_Mint( seL4_CapInitThreadCNode,
                                        first_empty_slot + cap_op->mint_op.dest,
                                        seL4_WordBits,
                                        seL4_CapInitThreadCNode,
                                        first_empty_slot + cap_op->mint_op.src,
                                        seL4_WordBits, decoded_rights,
                                        cap_op->mint_op.badge);
    return (error == seL4_NoError);
}

bool dispatchOperation(CapOperation* cap_op) {
    switch (cap_op->op_type) {
        case CAP_CREATE:
            return doCreateOp(cap_op);
        case CNODE_CREATE:
            return doCreateOp(cap_op);
        case CAP_COPY:
            return doCopyOp(cap_op);
        case CAP_MINT:
            return doMintOp(cap_op);
        default:
            halt();
    }
}

bool executeOperations() {
    for (seL4_Word op_index = 0; op_index < NUM_OPERATIONS; op_index++) {
        if (!dispatchOperation(&cap_operations[op_index])) return false;
    }
    return true;
}

int main() {

    printf("Hello world!\n");
    printf("Slots needed: %lu\n", SLOTS_REQUIRED);
    printf("Bytes needed: %lu\n", BYTES_REQUIRED);

    loadBootInfo();

    seL4_Word start = SYM_VAL(_startup_threads_data_start);
    seL4_Word seg0_start = SYM_VAL(_binary_startup_thread_thread_elf__0_segment_0_bin_start);
    seL4_Word seg1_start = SYM_VAL(_binary_startup_thread_thread_elf__0_segment_1_bin_start);
    seL4_Word seg2_start = SYM_VAL(_binary_startup_thread_thread_elf__0_segment_2_bin_start);
    printf("%lx, %lx, %lx, %lx\n", start, seg0_start, seg1_start, seg2_start);

    if (SLOTS_REQUIRED > num_empty_slots) {
        printf("Number of slots needed (%lu) is greater than number of empty slots (%lu)!\n", SLOTS_REQUIRED, num_empty_slots);
        halt();
    }

    for (int i = 0; i < NUM_OPERATIONS; i++) {
        printOp(&cap_operations[i]);
    }

    if (!executeOperations()) {
        printf("Failed to execute operations\n");
        halt();
    }

    printf("\n\n\n");

    seL4_DebugDumpScheduler();

    halt();
    return 0;
}