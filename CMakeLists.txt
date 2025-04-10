project(Tailspring)

find_package(Python3 REQUIRED COMPONENTS Interpreter)
include(ExternalProject)

if(NOT DEFINED RUNTIME_CONFIGS_DIR)
    message(FATAL_ERROR "RUNTIME_CONFIGS_DIR is not set")
endif(NOT DEFINED RUNTIME_CONFIGS_DIR)

if(NOT DEFINED TAILSPRING_THREAD_DICT)
    message(FATAL_ERROR "TAILSPRING_THREAD_DICT is not set")
endif(NOT DEFINED TAILSPRING_THREAD_DICT)

set(TAILSPRING_PROJECT_DIR "${CMAKE_CURRENT_LIST_DIR}")
set(TAILSPRING_SOURCE_DIR "${TAILSPRING_PROJECT_DIR}/src")
set(TAILSPRING_BINARY_DIR "${CMAKE_CURRENT_BINARY_DIR}")
set(TAILSPRING_GENERATED_DIR "${TAILSPRING_BINARY_DIR}/generated")
set(TAILSPRING_CONFIG_PATH "${RUNTIME_CONFIGS_DIR}/${TAILSPRING_CONFIG_FILENAME}")

file(MAKE_DIRECTORY "${TAILSPRING_GENERATED_DIR}")

set(TAILSPRING_HEADER_GEN_PYTHON_SCRIPT "${TAILSPRING_PROJECT_DIR}/tailspring_header_gen.py")
set(TAILSPRING_GEN_HEADER_PATH "${TAILSPRING_GENERATED_DIR}/tailspring_gen_config.h")

# Generate C program to print out sel4 object sizes
add_executable(         tailspring_get_sel4_info "${TAILSPRING_SOURCE_DIR}/get_sel4_info.c")
target_link_libraries(  tailspring_get_sel4_info sel4 sel4_autoconf)


# Use python script to generate header file
add_custom_command(
    OUTPUT  "${TAILSPRING_GEN_HEADER_PATH}"
    COMMAND ${Python3_EXECUTABLE} "${TAILSPRING_HEADER_GEN_PYTHON_SCRIPT}"
        "${TAILSPRING_CONFIG_PATH}" "$<TARGET_FILE:tailspring_get_sel4_info>" "${TAILSPRING_GEN_HEADER_PATH}" ${TAILSPRING_THREAD_DICT}
    DEPENDS "${TAILSPRING_CONFIG_PATH}" "${TAILSPRING_HEADER_GEN_PYTHON_SCRIPT}" "${TAILSPRING_GET_SEL4_INFO_PATH}" tailspring_get_sel4_info
    COMMENT "Generating Tailspring header file"
    COMMAND_EXPAND_LISTS
)
add_custom_target(TAILSPRING_GEN_HEADER_TARGET DEPENDS ${TAILSPRING_GEN_HEADER_PATH})

# Compile Tailspring thread
add_executable(             tailspring ${TAILSPRING_SOURCE_DIR}/tailspring.c)
target_include_directories( tailspring PRIVATE ${TAILSPRING_GENERATED_DIR})
target_link_libraries(      tailspring sel4muslcsys)
add_dependencies(           tailspring TAILSPRING_GEN_HEADER_TARGET)
