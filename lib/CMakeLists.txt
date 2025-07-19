project(tailspring_lib C)

set(TAILSPRING_LIB_PROJECT_DIR "${CMAKE_CURRENT_LIST_DIR}")
set(TAILSPRING_LIB_SOURCE_DIR "${TAILSPRING_LIB_PROJECT_DIR}/src")
set(TAILSPRING_LIB_INCLUDE_DIR "${TAILSPRING_LIB_PROJECT_DIR}/include")
set(TAILSPRING_LIB_INCLUDE_SHARED_DIR "${TAILSPRING_LIB_PROJECT_DIR}/include_shared")

# Also set in parent scope so tailspring can use it
set(TAILSPRING_LIB_INCLUDE_SHARED_DIR ${TAILSPRING_LIB_INCLUDE_SHARED_DIR} PARENT_SCOPE)

add_library(tailspring_lib STATIC "${TAILSPRING_LIB_SOURCE_DIR}/tailspring.c")
target_include_directories(tailspring_lib PUBLIC "${TAILSPRING_LIB_INCLUDE_DIR}" "${TAILSPRING_LIB_INCLUDE_SHARED_DIR}")
target_link_libraries(tailspring_lib sel4 sel4_autoconf)