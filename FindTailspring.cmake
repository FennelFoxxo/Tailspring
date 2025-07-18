include_guard(GLOBAL)

set(TAILSPRING_CONFIG_FILENAME "tailspringconfig.yaml" CACHE STRING "Name of the Tailspring configuration file in runtime-configs/")

add_subdirectory("${CMAKE_CURRENT_LIST_DIR}" Tailspring)
add_subdirectory("${CMAKE_CURRENT_LIST_DIR}/lib" tailspring_lib)