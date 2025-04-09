include_guard(GLOBAL)

find_package(Python3 REQUIRED COMPONENTS Interpreter)
include(ExternalProject)

set(TAILSPRING_PROJECT_DIR "${CMAKE_CURRENT_LIST_DIR}")
set(TAILSPRING_SOURCE_DIR "${TAILSPRING_PROJECT_DIR}/src")
set(TAILSPRING_BINARY_DIR "${CMAKE_CURRENT_BINARY_DIR}/tailspring")

file(MAKE_DIRECTORY "${TAILSPRING_BINARY_DIR}")

set(TAILSPRING_HEADER_GEN_PYTHON_SCRIPT "${TAILSPRING_PROJECT_DIR}/tailspring_header_gen.py")
set(TAILSPRING_GEN_HEADER_PATH "${TAILSPRING_BINARY_DIR}/tailspring_gen_config.h")


# Generate C program to print out sel4 object sizes
function (tailspring_compile_get_sel4_info)
    add_executable(         tailspring_get_sel4_info "${TAILSPRING_SOURCE_DIR}/get_sel4_info.c")
    target_link_libraries(  tailspring_get_sel4_info sel4 sel4_autoconf)
    set_target_properties(  tailspring_get_sel4_info PROPERTIES RUNTIME_OUTPUT_DIRECTORY "${TAILSPRING_BINARY_DIR}" RUNTIME_OUTPUT_NAME "tailspring_get_sel4_info")
endfunction()


# Use python script to generate header file
function (tailspring_gen_config config_file)
    tailspring_compile_get_sel4_info()

    add_custom_command(
        OUTPUT  "${TAILSPRING_GEN_HEADER_PATH}"
        COMMAND ${Python3_EXECUTABLE} "${TAILSPRING_HEADER_GEN_PYTHON_SCRIPT}" "${config_file}" "$<TARGET_FILE:tailspring_get_sel4_info>" "${TAILSPRING_GEN_HEADER_PATH}"
        DEPENDS "${config_file}" "${TAILSPRING_HEADER_GEN_PYTHON_SCRIPT}" "${TAILSPRING_GET_SEL4_INFO_PATH}" tailspring_get_sel4_info
        COMMENT "Generating Tailspring header file"
        VERBATIM
    )
    
    add_custom_target(TAILSPRING_GEN_HEADER_TARGET DEPENDS ${TAILSPRING_GEN_HEADER_PATH})
endfunction()


function (tailspring_compile config_file)
    tailspring_gen_config(${config_file})

    add_executable(             tailspring ${TAILSPRING_SOURCE_DIR}/tailspring.c)
    target_include_directories( tailspring PRIVATE ${TAILSPRING_BINARY_DIR})
    target_link_libraries(      tailspring sel4muslcsys)
    
    set_target_properties(      tailspring PROPERTIES RUNTIME_OUTPUT_DIRECTORY "${TAILSPRING_BINARY_DIR}" RUNTIME_OUTPUT_NAME "tailspring_bin")
    add_dependencies(           tailspring TAILSPRING_GEN_HEADER_TARGET)

endfunction()