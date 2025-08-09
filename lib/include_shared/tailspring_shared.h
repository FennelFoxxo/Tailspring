// This header is included by both tailspring itself, and by child threads to learn about
// the environment that tailspring set up (e.g. the GPMemoryInfo struct declaration)

#pragma once

typedef struct {
    seL4_Word size_bits;
    seL4_Word paddr;
} TailspringMemoryEntry;

#define TAILSPRING_PAGE_SIZE (1 << seL4_PageBits)
#define TAILSPRING_MEM_NUM_ENTRIES ((TAILSPRING_PAGE_SIZE - sizeof(seL4_Word)) / sizeof(TailspringMemoryEntry))

// Fills one page
typedef struct {
    seL4_Word num_entries;
    TailspringMemoryEntry entries[TAILSPRING_MEM_NUM_ENTRIES];
} TailspringMemoryInfo;

#ifdef __cplusplus
static_assert(sizeof(TailspringMemoryInfo) <= TAILSPRING_PAGE_SIZE);
#else
_Static_assert(sizeof(TailspringMemoryInfo) <= TAILSPRING_PAGE_SIZE);
#endif