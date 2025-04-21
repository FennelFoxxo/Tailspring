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
        case CREATE_OP:
            printf("Create (size=%u) (dest=%u)\n",
                c->create_op.size_bits, c->create_op.dest);
            break;
        case MINT_OP:
            printf("Mint (src=%u) (dest=%u) (badge=%lu) (rights=%u)\n",
                c->mint_op.src, c->mint_op.dest, c->mint_op.badge, c->mint_op.rights);
            break;
        case COPY_OP:
            printf("Copy (src=%u) (dest_root=%u) (dest_index=%u) (dest_depth=%u)\n",
                c->copy_op.src, c->copy_op.dest_root, c->copy_op.dest_index, c->copy_op.dest_depth);
            break;
        case MUTATE_OP:
            printf("Mutate (src=%u) (dest=%u) (guard=%lu)\n",
                c->mutate_op.src, c->mutate_op.dest, c->mutate_op.guard);
            break;
        case MAP_OP:
            printf("Map (service=%u) (vspace=%u) (vaddr=%lx)\n",
                c->map_op.service, c->map_op.vspace, c->map_op.vaddr);
            break;
        case SEGMENT_LOAD_OP:
            printf("Segment load (vspace=%u) (vaddr=%lx) (length=%lx)\n",
                c->segment_load_op.dest_vspace, c->segment_load_op.dest_vaddr, c->segment_load_op.length);
            break;
        case TCB_SETUP_OP:
            printf("TCB Setup (tcb=%u) (cspace=%u) (vspace=%u) (entry addr=%lx)\n",
                c->tcb_setup_op.tcb, c->tcb_setup_op.cspace, c->tcb_setup_op.vspace, c->tcb_setup_op.entry_addr);
            break;
        case MAP_FRAME_OP:
            printf("Map frame (frame=%u) (vspace=%u) (vaddr=%lx)\n",
                c->map_frame_op.frame, c->map_frame_op.vspace, c->map_frame_op.vaddr);
            break;
        case TCB_START_OP:
            printf("TCB start (tcb=%u)\n",
                c->tcb_start_op.tcb);
            break;
    }
}

seL4_Word getUntypedBestFitIndex(seL4_Word bytes_required) {
    // Keep track of smallest untyped that fits this object
    seL4_Word best_fit_index = ~0llu;
    seL4_Word best_fit_size = ~0llu;
    for (seL4_Word untyped_index = 0; untyped_index < num_non_device_untyped; untyped_index++) {
        seL4_Word untyped_size = non_device_untyped_array[untyped_index].bytes_left;
        // If the untyped is big enough for this object
        if (untyped_size >= bytes_required) {
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
    seL4_Word bytes_required = cap_op->create_op.bytes_required;
    seL4_Word untyped_index = getUntypedBestFitIndex(bytes_required);
    if (untyped_index == ~0llu) return false;
    non_device_untyped_array[untyped_index].bytes_left -= bytes_required;

    seL4_CPtr untyped = non_device_untyped_array[untyped_index].cptr;


    seL4_Error error = seL4_Untyped_Retype(untyped,
                                    cap_op->create_op.cap_type,
                                    cap_op->create_op.size_bits,
                                    seL4_CapInitThreadCNode, 0, 0,
                                    first_empty_slot + cap_op->create_op.dest,
                                    1);
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

bool doMutateOp(CapOperation* cap_op) {
    seL4_Error error = seL4_CNode_Mutate(   seL4_CapInitThreadCNode, first_empty_slot + cap_op->mutate_op.dest, seL4_WordBits,
                                            seL4_CapInitThreadCNode, first_empty_slot + cap_op->mutate_op.src, seL4_WordBits,
                                            cap_op->mutate_op.guard);
    return (error == seL4_NoError);
}

bool doMapOp(CapOperation* cap_op) {
    MapFuncType map_func = cap_op->map_op.map_func;
    return (map_func(cap_op, first_empty_slot) == seL4_NoError);
    return true;
}

bool doSegmentLoadOp(CapOperation* cap_op) {
    seL4_Word frames_start_address = SYM_VAL(_startup_threads_data_start);
    seL4_Word segment_src_address = cap_op->segment_load_op.src_vaddr;
    seL4_CPtr segment_start_frame = boot_info->userImageFrames.start
                                    + ((segment_src_address - frames_start_address) >> seL4_PageBits);
    seL4_Error error;
    for (seL4_Word i = 0; i < (cap_op->segment_load_op.length >> seL4_PageBits); i++) {
        seL4_CPtr current_frame = segment_start_frame + i;
        seL4_Word frame_dest_vaddr = cap_op->segment_load_op.dest_vaddr + (i << seL4_PageBits);

        // Unmap page from this vspace
        error = wrapperPageUnmap(current_frame);
        if (error != seL4_NoError) return false;

        // Map page into destination vspace
        error = wrapperPageMap( current_frame,
                                first_empty_slot + cap_op->segment_load_op.dest_vspace,
                                frame_dest_vaddr);
        if (error != seL4_NoError) return false;
    }
    return true;
}

bool doTCBSetupOp(CapOperation* cap_op) {
    seL4_Error error = seL4_TCB_Configure(
        first_empty_slot + cap_op->tcb_setup_op.tcb,
        0,
        first_empty_slot + cap_op->tcb_setup_op.cspace,
        0,
        first_empty_slot + cap_op->tcb_setup_op.vspace,
        0,
        cap_op->tcb_setup_op.ipc_buffer_addr,
        first_empty_slot + cap_op->tcb_setup_op.ipc_buffer);
    if (error != seL4_NoError) return false;

    seL4_UserContext regs = {0};
    error = seL4_TCB_ReadRegisters(first_empty_slot + cap_op->tcb_setup_op.tcb, 0, 0, sizeof(regs)/sizeof(seL4_Word), &regs);
    if (error != seL4_NoError) return false;

    sel4utils_set_instruction_pointer(&regs, cap_op->tcb_setup_op.entry_addr);
    sel4utils_set_stack_pointer(&regs, cap_op->tcb_setup_op.stack_top_addr);

    error = seL4_TCB_WriteRegisters(first_empty_slot + cap_op->tcb_setup_op.tcb, 0, 0, sizeof(regs)/sizeof(seL4_Word), &regs);
    if (error != seL4_NoError) return false;

    return true;
}

bool doMapFrameOp(CapOperation* cap_op) {
    seL4_Error error = wrapperPageMap(  first_empty_slot + cap_op->map_frame_op.frame,
                                        first_empty_slot + cap_op->map_frame_op.vspace,
                                        cap_op->map_frame_op.vaddr);
    return (error == seL4_NoError);
}

bool doTCBStartOp(CapOperation* cap_op) {
    seL4_Error error = seL4_TCB_Resume(first_empty_slot + cap_op->tcb_start_op.tcb);
    return (error == seL4_NoError);
}

bool dispatchOperation(CapOperation* cap_op) {
    switch (cap_op->op_type) {
        case CREATE_OP:
            return doCreateOp(cap_op);
        case COPY_OP:
            return doCopyOp(cap_op);
        case MINT_OP:
            return doMintOp(cap_op);
        case MUTATE_OP:
            return doMutateOp(cap_op);
        case MAP_OP:
            return doMapOp(cap_op);
        case SEGMENT_LOAD_OP:
            return doSegmentLoadOp(cap_op);
        case TCB_SETUP_OP:
            return doTCBSetupOp(cap_op);
        case MAP_FRAME_OP:
            return doMapFrameOp(cap_op);
        case TCB_START_OP:
            return doTCBStartOp(cap_op);
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

    loadBootInfo();


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