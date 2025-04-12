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
#define SYM_VAL(sym) ((seL4_Word)(&sym))

enum CapOperationType {CAP_CREATE, CAP_MINT, CAP_COPY, CAP_MUTATE};

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

struct CapOperation {
    CapOperationType op_type;
    union {
        CapCreateOperation create_op;
        CapMintOperation mint_op;
        CapCopyOperation copy_op;
        CapMutateOperation mutate_op;
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