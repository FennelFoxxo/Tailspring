#include "tailspring.h"

#include <string.h>
#include <stdlib.h>


int tailspring_lib_test_int = 12345;

static bool starts_with(const char *str, const char *prefix) {
    return strncmp(prefix, str, strlen(prefix)) == 0;
}


// Returns the value of the environment variable, or 0 if not found
static bool get_env_var_str(const char *target_name, char *envp[], const char** value_out) {
    int target_name_len = strlen(target_name);

    // Loop until nullptr
    for (char** env_var_ptr = envp; *env_var_ptr; env_var_ptr++) {
        // Full env var string, including key and value
        char* env_var_full = *env_var_ptr;
        // Look for environment variable that starts with target name
        if (starts_with(env_var_full, target_name)) {
            // Make sure the next character after the name is an equal sign
            // We don't want to return the value of "foobar" if we're just looking for "foo"
            if (env_var_full[target_name_len] != '=') continue;

            // Return the string starting just after the equal sign
            *value_out = &env_var_full[target_name_len+1];
            return true;
        }
    }

    // Target env var not found
    return false;
}

static bool get_env_var_num(const char *target_name, char *envp[], seL4_Word* value_out) {
    // Get env var value as string and fail if env var not found
    const char* value_str;
    if (!get_env_var_str(target_name, envp, &value_str)) return false;

    // Fail if value is blank
    if (*value_str == 0) return false;

    char* end;
    *value_out = strtol(value_str, &end, 10);

    // Conversion failed, entire string was not processed
    if (*end != 0) return false;

    return true;

}


bool tailspring_get_ipc_buffer_addr(char *envp[], seL4_IPCBuffer** ipc_buffer_addr_out) {
    return get_env_var_num("ipc_buffer", envp, (seL4_Word*)ipc_buffer_addr_out);
}

bool tailspring_get_gp_memory_info(char *envp[], TailspringMemoryInfo** gp_memory_info_out) {
    return get_env_var_num("gp_memory_info", envp, (seL4_Word*)gp_memory_info_out);
}

bool tailspring_get_device_memory_info(char *envp[], TailspringMemoryInfo** device_memory_info_out) {
    return get_env_var_num("device_memory_info", envp, (seL4_Word*)device_memory_info_out);
}