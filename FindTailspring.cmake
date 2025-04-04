include_guard(GLOBAL)

find_package(Python3 REQUIRED COMPONENTS Interpreter)

set(TAILSPRING_PROJECT_DIR "${CMAKE_CURRENT_LIST_DIR}")
set(TAILSPRING_SOURCE_DIR "${TAILSPRING_PROJECT_DIR}/src")
set(TAILSPRING_BINARY_DIR "${CMAKE_CURRENT_BINARY_DIR}/tailspring")

file(MAKE_DIRECTORY $(TAILSPRING_BINARY_DIR))

set(TAILSPRING_HEADER_GEN_PYTHON_SCRIPT "${TAILSPRING_PROJECT_DIR}/tailspring_header_gen.py")
set(TAILSPRING_GEN_HEADER_PATH "${TAILSPRING_BINARY_DIR}/tailspring_gen_config.h")

function (tailspring_compile config_file)
    add_custom_command(
        OUTPUT "${TAILSPRING_GEN_HEADER_PATH}"
        COMMAND ${Python3_EXECUTABLE} "${TAILSPRING_HEADER_GEN_PYTHON_SCRIPT}" "${config_file}" "${TAILSPRING_GEN_HEADER_PATH}"
        DEPENDS "${config_file}" "${tailspring_python_script}"
        COMMENT "Generating Tailspring header file"
        VERBATIM
    )
    
    add_custom_target(TAILSPRING_GEN_HEADER_TARGET DEPENDS ${TAILSPRING_GEN_HEADER_PATH})
    
    add_executable(tailspring ${TAILSPRING_SOURCE_DIR}/tailspring.c)
    set_target_properties(tailspring PROPERTIES RUNTIME_OUTPUT_DIRECTORY "${TAILSPRING_BINARY_DIR}/tailspring")
    add_dependencies(tailspring TAILSPRING_GEN_HEADER_TARGET)
    target_link_libraries(tailspring sel4muslcsys)
    target_include_directories(tailspring PRIVATE ${TAILSPRING_BINARY_DIR})

endfunction()