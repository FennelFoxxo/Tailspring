#include "tailspring.hpp"
#include "tailspring_gen_config.hpp"

// Size of general purpose array to keep track of non-device untypeds
#define GP_UNTYPED_ARRAY_SIZE 100

seL4_BootInfo* boot_info = NULL;
seL4_Word num_empty_slots = 0;
seL4_Word first_empty_slot = 0;

seL4_CPtr first_untyped = 0;
seL4_Word num_untypeds = 0;
seL4_Word num_gp_untypeds = 0;
seL4_Word num_device_untypeds = 0;
UntypedInfo gp_untyped_array[GP_UNTYPED_ARRAY_SIZE];

// Free page that can be unmapped
unsigned char FREE_PAGE[1 << seL4_PageBits] __attribute__((aligned(1 << seL4_PageBits)));

GPMemoryInfo gp_memory_info;

void halt() __attribute__((noreturn));
void halt() {
    while (1) seL4_TCB_Suspend(seL4_CapInitThreadTCB);
}

// Returns the cptr for the user image frame that is mapped at addr
seL4_CPtr getFrameForAddr(seL4_Word addr) {
    seL4_Word lowest_vaddr = SYM_VAL(_lowest_vaddr);
    return boot_info->userImageFrames.start + ((addr - lowest_vaddr) >> seL4_PageBits);
}

void loadUntypedInfo(seL4_Word untyped_index) {
    seL4_UntypedDesc* untyped = &boot_info->untypedList[untyped_index];
    if (untyped->isDevice) {
        num_device_untypeds++;
    } else {
        if (num_gp_untypeds < GP_UNTYPED_ARRAY_SIZE) {
            gp_untyped_array[num_gp_untypeds].bytes_left = 1llu << untyped->sizeBits;
            gp_untyped_array[num_gp_untypeds].cptr = untyped_index + first_untyped;
            num_gp_untypeds++;
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
    num_untypeds = boot_info->untyped.end - first_untyped;
    for (seL4_Word offset = 0; offset < num_untypeds; offset++) {
        loadUntypedInfo(offset);
    }
}

void debugPrintOp(const CapOperation* c) {
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
        case BINARY_CHUNK_LOAD_OP:
            printf("Binary chunk load (vspace=%u) (vaddr=%lx) (length=%lx)\n",
                c->binary_chunk_load_op.dest_vspace, c->binary_chunk_load_op.dest_vaddr, c->binary_chunk_load_op.length);
            break;
        case TCB_SETUP_OP:
            printf("TCB Setup (tcb=%u) (cspace=%u) (vspace=%u) (entry addr=%lx)\n",
                c->tcb_setup_op.tcb, c->tcb_setup_op.cspace, c->tcb_setup_op.vspace, c->tcb_setup_op.entry_addr);
            break;
        case MAP_FRAME_OP:
            printf("Map frame (frame=%u) (vspace=%u) (vaddr=%lx)\n",
                c->map_frame_op.frame, c->map_frame_op.vspace, c->map_frame_op.vaddr);
            break;
        case PASS_GP_UNTYPEDS_OP:
            printf("Pass general-purpose untypeds (cnode dest=%u) (start slot=%u) (end slot=%u)\n",
                c->pass_gp_untypeds_op.cnode_dest, c->pass_gp_untypeds_op.start_slot, c->pass_gp_untypeds_op.end_slot);
            break;
        case PASS_GP_MEMORY_INFO_OP:
            printf("Pass general-purpose memory info (dest vaddr=%lu) (dest_vspace=%u) (frame=%u)\n",
                c->pass_gp_memory_info_op.dest_vaddr, c->pass_gp_memory_info_op.dest_vspace, c->pass_gp_memory_info_op.frame);
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
    for (seL4_Word untyped_index = 0; untyped_index < num_gp_untypeds; untyped_index++) {
        seL4_Word untyped_size = gp_untyped_array[untyped_index].bytes_left;
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
    gp_untyped_array[untyped_index].bytes_left -= bytes_required;

    seL4_CPtr untyped = gp_untyped_array[untyped_index].cptr;


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
    seL4_CapRights_t decoded_rights = seL4_CapRights_new(   (cap_op->mint_op.rights & CAP_ALLOW_GRANT_REPLY) != 0,
                                                            (cap_op->mint_op.rights & CAP_ALLOW_GRANT) != 0,
                                                            (cap_op->mint_op.rights & CAP_ALLOW_READ) != 0,
                                                            (cap_op->mint_op.rights & CAP_ALLOW_WRITE) != 0);

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

bool doBinaryChunkLoadOp(CapOperation* cap_op) {
    seL4_Error error;
    seL4_CPtr chunk_start_frame = getFrameForAddr(cap_op->binary_chunk_load_op.src_vaddr);

    for (seL4_Word i = 0; i < (cap_op->binary_chunk_load_op.length >> seL4_PageBits); i++) {
        seL4_CPtr current_frame = chunk_start_frame + i;
        seL4_Word frame_dest_vaddr = cap_op->binary_chunk_load_op.dest_vaddr + (i << seL4_PageBits);

        // Unmap page from this vspace
        error = wrapperPageUnmap(current_frame);
        if (error != seL4_NoError) return false;

        // Map page into destination vspace
        error = wrapperPageMap( current_frame,
                                first_empty_slot + cap_op->binary_chunk_load_op.dest_vspace,
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

    sel4utils_arch_init_local_context(  (sel4utils_thread_entry_fn)cap_op->tcb_setup_op.entry_addr,
                                        (void*)cap_op->tcb_setup_op.arg0,
                                        (void*)cap_op->tcb_setup_op.arg1,
                                        (void*)cap_op->tcb_setup_op.arg2,
                                        (void*)cap_op->tcb_setup_op.stack_pointer_addr,
                                        &regs);

    // sel4utils_arch_init_local_context tries to be smart and tweaks around the stack pointer a little bit,
    // so we need to manually set it again
    sel4utils_set_stack_pointer(&regs, cap_op->tcb_setup_op.stack_pointer_addr);

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

bool doPassGPUntypedsOp(CapOperation* cap_op) {
    // In every untyped, there will be some amount of memory left over, say 13 bytes to make it simple.
    // We need to break the leftover memory into smaller untypeds (if we passed every untypeds as-is to the user process, it could
    // just revoke all the memory and destroy every object tailspring created).
    // How many/what sizes of untypeds do we need to create for each untyped? Well 13=0b1101, so an 1, 4, and 8 byte untyped.
    // To generalize it, we scan each bit from least-to-most significant for every untyped, and if the bit at position n is set,
    // we retype it into a new untyped of size 2^n.

    // How many blocks (new untypeds) could be created from leftover memory?
    seL4_Word total_blocks = 0;
    for (int i = 0; i < num_gp_untypeds; i++) {
        total_blocks += __builtin_popcountll(gp_untyped_array[i].bytes_left);
    }

    uint32_t start_slot = cap_op->pass_gp_untypeds_op.start_slot;
    uint32_t end_slot = cap_op->pass_gp_untypeds_op.end_slot;
    uint32_t num_slots = end_slot - start_slot;

    // Limit the number of slots to how many untypeds we can keep track of
    if (num_slots > GP_MEMORY_INFO_NUM_ENTRIES) {
        num_slots = GP_MEMORY_INFO_NUM_ENTRIES;
    }

    // We iterate from smallest to biggest, but we want to sort the memory so we pass the biggest untyped first. Also, there might not be
    // enough space in the dest cnode to store all the untypeds, so we need to skip a bit before starting to retype
    uint32_t skip, dest_slot;

    if (total_blocks > num_slots) {
        // More potential blocks than we have space for
        skip = total_blocks - num_slots;
        dest_slot = start_slot + num_slots - 1; // Start at end
    } else {
        // Enough space for all the blocks
        skip = 0;
        dest_slot = start_slot + total_blocks - 1;
    }

    // Iterate over every bit position
    for (int bit_pos = 0; bit_pos < seL4_WordBits; bit_pos++) {
        seL4_Word bit_mask = 1llu << bit_pos;
        // Iterate over every general purpose untyped
        for (int i = 0; i < num_gp_untypeds; i++) {
            seL4_Word bytes_left = gp_untyped_array[i].bytes_left;
            // Check if a block of size (1 << bit_pos) should be retyped from this block
            if (bytes_left & bit_mask) {
                // At this point, we should attempt a retype
                // If there are more potential blocks than we have space for, we need to skip a few
                if (skip > 0) {
                    skip--;
                    continue;
                }

                // Keep track of each untyped, making sure to go in reverse order
                // dest_slot - start_slot tells us the "index" of the untyped being processed
                gp_memory_info.untyped_size_bits[dest_slot - start_slot] = bit_pos;
                gp_memory_info.num_untypeds++;

                // Now we can start retyping
                seL4_Error error = seL4_Untyped_Retype(
                                    gp_untyped_array[i].cptr,
                                    seL4_UntypedObject,
                                    bit_pos, // Size bits
                                    seL4_CapInitThreadCNode,
                                    first_empty_slot + cap_op->pass_gp_untypeds_op.cnode_dest,
                                    cap_op->pass_gp_untypeds_op.cnode_depth,
                                    dest_slot,
                                    1);
                if (error != seL4_NoError) return false;
                dest_slot--;
            }
        }
    }

    return true;
}

bool doPassGPMemoryInfoOp(CapOperation* cap_op) {
    seL4_Error error;
    seL4_CPtr dest_frame = first_empty_slot + cap_op->pass_gp_memory_info_op.frame;

    // Take the frame that will hold the GP memory info and map it into our vspace so we can write to it
    error = wrapperPageMap( dest_frame,
                            seL4_CapInitThreadVSpace,
                            (seL4_Word)FREE_PAGE);
    if (error != seL4_NoError) return false;

    // Then copy the GP memory info into the frame
    memcpy(FREE_PAGE, &gp_memory_info, sizeof(gp_memory_info));


    // Unmap the frame and map it in the destination vspace
    error = wrapperPageUnmap(dest_frame);
    if (error != seL4_NoError) return false;

    error = wrapperPageMap( dest_frame,
                            first_empty_slot + cap_op->pass_gp_memory_info_op.dest_vspace,
                            cap_op->pass_gp_memory_info_op.dest_vaddr);
    if (error != seL4_NoError) return false;

    return true;
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
        case BINARY_CHUNK_LOAD_OP:
            return doBinaryChunkLoadOp(cap_op);
        case TCB_SETUP_OP:
            return doTCBSetupOp(cap_op);
        case MAP_FRAME_OP:
            return doMapFrameOp(cap_op);
        case PASS_GP_UNTYPEDS_OP:
            return doPassGPUntypedsOp(cap_op);
        case PASS_GP_MEMORY_INFO_OP:
            return doPassGPMemoryInfoOp(cap_op);
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

void debugPrintOps() {
    for (int i = 0; i < NUM_OPERATIONS; i++) {
        debugPrintOp(&cap_operations[i]);
    }
}

int main() {

    printf("Tailspring launched\n");
    printf("Slots needed: %lu\n", SLOTS_REQUIRED);

    loadBootInfo();

    // Unmap free page so that we can map other frames here
    if (wrapperPageUnmap(getFrameForAddr((seL4_Word)FREE_PAGE)) != seL4_NoError) {
        printf("Failed to unmap free page\n");
        halt();
    }

    if (SLOTS_REQUIRED > num_empty_slots) {
        printf("Number of slots needed (%lu) is greater than number of empty slots (%lu)!\n", SLOTS_REQUIRED, num_empty_slots);
        halt();
    }

    debugPrintOps();

    if (!executeOperations()) {
        printf("Failed to execute operations\n");
        halt();
    }

    printf("\n\n\n");

    seL4_DebugDumpScheduler();

    halt();
    return 0;
}