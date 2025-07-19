// This header is included by both tailspring itself, and by child threads to learn about
// the environment that tailspring set up (e.g. the GPMemoryInfo struct declaration)

#pragma once

#define WORDS_IN_PAGE ((1 << seL4_PageBits) / sizeof(seL4_Word))

// Fills one page
typedef struct {
    seL4_Word num_untypeds;
    seL4_Word untyped_size_bits[WORDS_IN_PAGE - 1];
} GPMemoryInfo;

#define GP_MEMORY_INFO_NUM_ENTRIES (sizeof(GPMemoryInfo::untyped_size_bits) / sizeof(seL4_Word))