#pragma once

#include <sel4/sel4.h>
#include <stdbool.h>

#define WORDS_IN_PAGE ((1 << seL4_PageBits) / sizeof(seL4_Word))

// Fills one page
typedef struct {
    seL4_Word num_untypeds;
    seL4_Word untyped_size_bits[WORDS_IN_PAGE - 1];
} GPMemoryInfo;



bool tailspring_get_ipc_buffer_addr(char *envp[], seL4_IPCBuffer** ipc_buffer_addr_out);
bool tailspring_get_gp_memory_info(char *envp[], GPMemoryInfo** gp_memory_info_out);
