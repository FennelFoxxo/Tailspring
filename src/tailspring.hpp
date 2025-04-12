#pragma once

extern "C" {
#include <sel4/sel4.h>
#include <stdint.h>
#include <sel4platsupport/bootinfo.h>
#include <stdio.h>
#include <sel4utils/util.h>
}

#define CAP_ALLOW_WRITE (1<<0)
#define CAP_ALLOW_READ (1<<1)
#define CAP_ALLOW_GRANT (1<<2)
#define CAP_ALLOW_GRANT_REPLY (1<<3)
#define SYM_VAL(sym) ((seL4_Word)(&sym))

enum CapOperationType {CREATE_OP, MINT_OP, COPY_OP, MUTATE_OP, MAP_OP, SEGMENT_LOAD_OP, TCB_SETUP_OP, MAP_FRAME_OP};

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

struct CapMutateOperation {
    seL4_Word guard;
    uint32_t src;
    uint32_t dest;
};

struct MapOperation {
    seL4_Word vaddr;
    uint32_t service;
    uint32_t vspace;
    uint16_t mapping_func_index;
};

struct SegmentLoadOperation {
    seL4_Word segment_start_vaddr;
    seL4_Word segment_dest_vaddr;
    seL4_Word segment_length;
    uint32_t vspace;
};

struct TCBSetupOperation {
    seL4_Word entry_addr;
    seL4_Word stack_top_addr;
    seL4_Word ipc_buffer_addr;
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

struct CapOperation {
    CapOperationType op_type;
    union {
        CapCreateOperation create_op;
        CapMintOperation mint_op;
        CapCopyOperation copy_op;
        CapMutateOperation mutate_op;
        MapOperation map_op;
        SegmentLoadOperation segment_load_op;
        TCBSetupOperation tcb_setup_op;
        MapFrameOperation map_frame_op;
    };
};

struct UntypedInfo {
    seL4_Word bytes_left;
    seL4_CPtr cptr;
};

// Address of startup threads data
// The startup thread data should also be at the start of this thread's memory,
// so this address should point to the first frame in userImageFrames
extern void* _startup_threads_data_start;

// Each platform has its own platform-specific functions to map in pages and page structures.
// The specific mapping functions are chosen in the python script and wrappers are generated for the
// mapping functions, then placed in an array of function pointers, that way the correct function can
// be chosen simply by index rather than name. This is the signature of the mapping function wrapper.
typedef seL4_Error (*mappingFuncType)(CapOperation* cap_op, seL4_Word first_empty_slot);
