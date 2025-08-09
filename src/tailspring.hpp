#pragma once

extern "C" {
#include <sel4/sel4.h>
#include <stdint.h>
#include <sel4platsupport/bootinfo.h>
#include <stdio.h>
#include <sel4utils/helpers.h>
#include <sel4utils/util.h>
}

#include <tailspring_shared.h>

#define CAP_ALLOW_WRITE (1<<0)
#define CAP_ALLOW_READ (1<<1)
#define CAP_ALLOW_GRANT (1<<2)
#define CAP_ALLOW_GRANT_REPLY (1<<3)
#define SYM_VAL(sym) ((seL4_Word)(&sym))
#define NUM_OPERATIONS (sizeof(cap_operations) / sizeof(cap_operations[0]))

// Each platform has its own platform-specific functions to map in pages and page structures.
// The specific mapping functions are chosen in the python script and wrappers are generated for the
// mapping functions, then placed in an array of function pointers, that way the correct function can
// be chosen simply by index rather than name. This is the signature of the mapping function wrapper.
struct CapOperation;
typedef seL4_Error (*MapFuncType)(CapOperation* cap_op, seL4_Word first_empty_slot);

enum CapOperationType { CREATE_OP, MINT_OP, COPY_OP, MOVE_OP, MUTATE_OP, MAP_OP, BINARY_CHUNK_LOAD_OP, TCB_SETUP_OP,
                        MAP_FRAME_OP, RETYPE_LEFTOVER_GP_UNTYPEDS_OP, MOVE_DEVICE_UNTYPEDS_OP,
                        PASS_GP_MEMORY_INFO_OP, PASS_DEVICE_MEMORY_INFO_OP, PASS_SYSTEM_INFO_OP, TCB_START_OP};

struct CapCreateOperation {
    seL4_Word cap_type;
    seL4_Word bytes_required;
    uint32_t dest;
    uint8_t size_bits;
};

struct CapMintOperation {
    seL4_Word badge;
    uint32_t src;
    uint32_t dest;
    uint8_t rights;
};

struct CapCopyOperation {
    uint32_t src;
    uint32_t dest_root;
    uint32_t dest_index;
    uint8_t dest_depth;
};

struct CapMoveOperation {
    uint32_t src;
    uint32_t dest_root;
    uint32_t dest_index;
    uint8_t dest_depth;
};

struct CapMutateOperation {
    seL4_Word guard;
    uint32_t src;
    uint32_t dest;
};

struct MapOperation {
    MapFuncType map_func;
    seL4_Word vaddr;
    uint32_t service;
    uint32_t vspace;
};

struct BinaryChunkLoadOperation {
    seL4_Word src_vaddr;
    seL4_Word dest_vaddr;
    seL4_Word length;
    uint32_t dest_vspace;
};

struct TCBSetupOperation {
    seL4_Word entry_addr;
    seL4_Word stack_pointer_addr;
    seL4_Word ipc_buffer_addr;
    seL4_Word arg0;
    seL4_Word arg1;
    seL4_Word arg2;
    uint32_t cspace;
    uint32_t vspace;
    uint32_t ipc_buffer;
    uint32_t tcb;
};

struct MapFrameOperation {
    seL4_Word vaddr;
    uint32_t frame;
    uint32_t vspace;
};

// This operation takes all the system-provided untypeds, breaks the leftover memory in each untyped (memory not reserved by tailspring)
// into separate, smaller untypeds, and puts these in the designated cnode
struct RetypeLeftoverGPUntypedsOperation {
    uint32_t cnode_dest;
    uint32_t start_slot;
    uint32_t end_slot;
    uint8_t cnode_depth;
};

// Moves device untypeds into the designated cnode
struct MoveDeviceUntypedsOperation {
    uint32_t cnode_dest;
    uint32_t start_slot;
    uint32_t end_slot;
    uint8_t cnode_depth;
};

// Fills a frame with info about how the general-purpose memory was broken into smaller untypeds and placed in the designated cnode,
// then maps the frame into the target vspace at a given address
struct PassGPMemoryInfoOperation {
    seL4_Word dest_vaddr;
    uint32_t frame;
    uint32_t dest_vspace;
};

struct PassDeviceMemoryInfoOperation {
    seL4_Word dest_vaddr;
    uint32_t frame;
    uint32_t dest_vspace;
};

struct PassSystemInfoOperation {
    seL4_Word dest_vaddr;
    uint32_t frame;
    uint32_t dest_vspace;
    bool pass_framebuffer_info;
};

struct TCBStartOperation {
    uint32_t tcb;
};

struct CapOperation {
    CapOperationType op_type;
    union {
        CapCreateOperation create_op;
        CapMintOperation mint_op;
        CapCopyOperation copy_op;
        CapMoveOperation move_op;
        CapMutateOperation mutate_op;
        MapOperation map_op;
        BinaryChunkLoadOperation binary_chunk_load_op;
        TCBSetupOperation tcb_setup_op;
        MapFrameOperation map_frame_op;
        RetypeLeftoverGPUntypedsOperation retype_leftover_gp_untypeds_op;
        MoveDeviceUntypedsOperation move_device_untypeds_op;
        PassGPMemoryInfoOperation pass_gp_memory_info_op;
        PassDeviceMemoryInfoOperation pass_device_memory_info_op;
        PassSystemInfoOperation pass_system_info_op;
        TCBStartOperation tcb_start_op;
    };
};

struct UntypedInfo {
    seL4_Word paddr;
    seL4_Word bytes_left;
    seL4_CPtr cptr;
    char original_size_bits;
};

// Lowest vaddr mapped in this thread's vspace. Whatever page is here will be at the start
// of this thread's memory, so the first frame in userImageFrames should be mapped here
extern void* _lowest_vaddr;

#define ENABLE_X86_ASIDPOOL_ASSIGN \
seL4_Error wrapper_X86_ASIDPool_Assign(CapOperation* cap_op, seL4_Word first_empty_slot) { \
    return seL4_X86_ASIDPool_Assign( \
        seL4_CapInitThreadASIDPool, \
        first_empty_slot + cap_op->map_op.service); \
}

#define ENABLE_X86_PDPT_MAP \
seL4_Error wrapper_X86_PDPT_Map(CapOperation* cap_op, seL4_Word first_empty_slot) { \
    return seL4_X86_PDPT_Map( \
        first_empty_slot + cap_op->map_op.service, \
        first_empty_slot + cap_op->map_op.vspace, \
        cap_op->map_op.vaddr, \
        seL4_X86_Default_VMAttributes); \
}

#define ENABLE_X86_PAGEDIRECTORY_MAP \
seL4_Error wrapper_X86_PageDirectory_Map(CapOperation* cap_op, seL4_Word first_empty_slot) { \
    return seL4_X86_PageDirectory_Map( \
        first_empty_slot + cap_op->map_op.service, \
        first_empty_slot + cap_op->map_op.vspace, \
        cap_op->map_op.vaddr, \
        seL4_X86_Default_VMAttributes); \
}

#define ENABLE_X86_PAGETABLE_MAP \
seL4_Error wrapper_X86_PageTable_Map(CapOperation* cap_op, seL4_Word first_empty_slot) { \
    return seL4_X86_PageTable_Map( \
        first_empty_slot + cap_op->map_op.service, \
        first_empty_slot + cap_op->map_op.vspace, \
        cap_op->map_op.vaddr, \
        seL4_X86_Default_VMAttributes); \
}

#define ENABLE_X86_PAGE_MAP \
seL4_Error wrapperPageMap(seL4_CPtr frame, seL4_CPtr vspace, seL4_Word vaddr) { \
    return seL4_X86_Page_Map( \
        frame, \
        vspace, \
        vaddr, \
        seL4_ReadWrite, \
        seL4_X86_Default_VMAttributes); \
} \
seL4_Error wrapperPageUnmap(seL4_CPtr frame) { \
    return seL4_X86_Page_Unmap(frame); \
}
