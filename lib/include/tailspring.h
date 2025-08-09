#pragma once

#include <sel4/sel4.h>
#include <stdbool.h>

#include <tailspring_shared.h>

bool tailspring_get_ipc_buffer_addr(char *envp[], seL4_IPCBuffer** ipc_buffer_addr_out);
bool tailspring_get_gp_memory_info(char *envp[], TailspringMemoryInfo** gp_memory_info_out);
bool tailspring_get_device_memory_info(char *envp[], TailspringMemoryInfo** device_memory_info_out);
bool tailspring_get_system_info(char *envp[], TailspringSystemInfo** system_info_out);