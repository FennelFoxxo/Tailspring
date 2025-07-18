project(tailspring C CXX)

find_package(Python3 REQUIRED COMPONENTS Interpreter)
include(ExternalProject)

if(NOT DEFINED RUNTIME_CONFIGS_DIR)
    message(FATAL_ERROR "RUNTIME_CONFIGS_DIR is not set")
endif(NOT DEFINED RUNTIME_CONFIGS_DIR)

if(NOT DEFINED TAILSPRING_THREAD_DICT)
    message(FATAL_ERROR "TAILSPRING_THREAD_DICT is not set")
endif(NOT DEFINED TAILSPRING_THREAD_DICT)

# Given the startup thread dict, get only the values (file paths)
# and combine them into a list to use as a dependency
foreach(keyvalue ${TAILSPRING_THREAD_DICT})
    string(REPLACE "=" ";" keyvalue_list ${keyvalue})
    list(GET keyvalue_list 1 value)
    list(APPEND TAILSPRING_THREAD_DEPENDS ${value})
endforeach()

set(TAILSPRING_PROJECT_DIR "${CMAKE_CURRENT_LIST_DIR}")
set(TAILSPRING_SOURCE_DIR "${TAILSPRING_PROJECT_DIR}/src")
set(TAILSPRING_BINARY_DIR "${CMAKE_CURRENT_BINARY_DIR}")
set(TAILSPRING_GENERATED_DIR "${TAILSPRING_BINARY_DIR}/generated")
set(TAILSPRING_INCLUDE_DIR "${TAILSPRING_GENERATED_DIR}/include")
set(TAILSPRING_CONFIG_PATH "${RUNTIME_CONFIGS_DIR}/${TAILSPRING_CONFIG_FILENAME}")

# Creates both generated and include directories
file(MAKE_DIRECTORY "${TAILSPRING_INCLUDE_DIR}")

set(TAILSPRING_PYTHON_DIR "${TAILSPRING_PROJECT_DIR}/py")
set(TAILSPRING_PYTHON_SCRIPT "${TAILSPRING_PYTHON_DIR}/main.py")
list(APPEND TAILSPRING_PYTHON_DEPENDS
    main.py
    tailspring/context.py
    tailspring/ts_enums.py
    tailspring/ts_types.py
    tailspring/op_types.py
    tailspring/cli_args.py
    tailspring/wrapper_creator.py
    tailspring/obj_file_gen.py
    tailspring/paging.py
    tailspring/thread_setup.py
    tailspring/ops_gen.py
    tailspring/fragment_gen.py
)
list(TRANSFORM TAILSPRING_PYTHON_DEPENDS PREPEND "${TAILSPRING_PYTHON_DIR}/")

# Output paths
set(TAILSPRING_GEN_HEADER_PATH "${TAILSPRING_INCLUDE_DIR}/tailspring_gen_config.hpp")
set(TAILSPRING_GEN_STARTUP_THREADS_OBJ_PATH "${TAILSPRING_GENERATED_DIR}/startup_threads.o")

# Generate C program to print out sel4 object sizes
add_executable(         tailspring_get_sel4_info "${TAILSPRING_SOURCE_DIR}/get_sel4_info.cpp")
target_link_libraries(  tailspring_get_sel4_info sel4 sel4_autoconf sel4runtime)

# Use python script to generate header file
add_custom_command(
    OUTPUT  "${TAILSPRING_GEN_HEADER_PATH}" "${TAILSPRING_GEN_STARTUP_THREADS_OBJ_PATH}"
    COMMAND ${Python3_EXECUTABLE} "${TAILSPRING_PYTHON_SCRIPT}"
        --config "${TAILSPRING_CONFIG_PATH}"
        --sel4-info-getter "$<TARGET_FILE:tailspring_get_sel4_info>"
        --gcc "${CMAKE_C_COMPILER}"
        --startup-threads-paths ${TAILSPRING_THREAD_DICT}
        --output-header "${TAILSPRING_GEN_HEADER_PATH}"
        --output-startup-threads-obj "${TAILSPRING_GEN_STARTUP_THREADS_OBJ_PATH}"
    DEPENDS "${TAILSPRING_CONFIG_PATH}" ${TAILSPRING_PYTHON_DEPENDS} tailspring_get_sel4_info ${TAILSPRING_THREAD_DEPENDS}
    WORKING_DIRECTORY "${TAILSPRING_GENERATED_DIR}"
    COMMENT "Generating Tailspring header file"
    COMMAND_EXPAND_LISTS
)
add_custom_target(TAILSPRING_GEN_HEADER_TARGET DEPENDS ${TAILSPRING_GEN_HEADER_PATH})

# Compile Tailspring thread
add_executable(             tailspring "${TAILSPRING_SOURCE_DIR}/tailspring.cpp")
target_include_directories( tailspring PRIVATE "${TAILSPRING_INCLUDE_DIR}" "${TAILSPRING_SOURCE_DIR}")
target_link_libraries(      tailspring "-Wl,-z noexecstack")
target_link_libraries(      tailspring sel4muslcsys "${TAILSPRING_GEN_STARTUP_THREADS_OBJ_PATH}")
target_link_libraries(      tailspring "-Wl,-T ${TAILSPRING_PROJECT_DIR}/ld_scripts/tailspring.ld")
add_dependencies(           tailspring TAILSPRING_GEN_HEADER_TARGET)
set_target_properties(      tailspring PROPERTIES LINK_DEPENDS "${TAILSPRING_PROJECT_DIR}/ld_scripts/tailspring.ld")