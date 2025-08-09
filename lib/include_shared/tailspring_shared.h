// This header is included by both tailspring itself, and by child threads to learn about
// the environment that tailspring set up (e.g. the GPMemoryInfo struct declaration)

#pragma once

#include <stdint.h>

#ifndef PACKED
#define PACKED __attribute__((packed))
#endif

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

#ifndef __cplusplus
#define static_assert _Static_assert
#endif

static_assert(sizeof(TailspringMemoryInfo) <= TAILSPRING_PAGE_SIZE);


typedef struct {
    uint64_t addr;
    uint32_t pitch;
    uint32_t width;
    uint32_t height;
    uint8_t  bpp;
    uint8_t  type;
} PACKED TailspringFramebufferInfo;


typedef struct {
    TailspringFramebufferInfo framebuffer_info;
    bool framebuffer_info_present;
} TailspringSystemInfo;

static_assert(sizeof(TailspringSystemInfo) <= TAILSPRING_PAGE_SIZE);