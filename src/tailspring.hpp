#pragma once

extern "C" {
#include <sel4/sel4.h>
#include <stdint.h>
#include <sel4platsupport/bootinfo.h>
#include <stdio.h>
}

#define CAP_ALLOW_WRITE (1<<0)
#define CAP_ALLOW_READ (1<<1)
#define CAP_ALLOW_GRANT (1<<2)
#define CAP_ALLOW_GRANT_REPLY (1<<3)
#define CREATE_OP_SIZE_BITS(cap_op) (((cap_op).op_type == CAP_CREATE ? (cap_op).cap_create_op.size_bits : (cap_op).cnode_create_op.slot_bits + seL4_SlotBits))
#define SYM_VAL(sym) ((seL4_Word)(&sym))

enum CapOperationType {CAP_CREATE,CNODE_CREATE,CAP_MINT,CAP_COPY};

struct CapCreateOperation {
    seL4_Word cap_type;
    uint32_t dest;
    uint8_t size_bits;
};

struct CNodeCreateOperation {
    uint32_t dest;
    uint8_t slot_bits;
    uint8_t guard;
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

struct CapOperation {
    CapOperationType op_type;
    union {
        CapCreateOperation cap_create_op;
        CNodeCreateOperation cnode_create_op;
        CapMintOperation mint_op;
        CapCopyOperation copy_op;
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