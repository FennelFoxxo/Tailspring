#include <stdio.h>
#include <type_traits>
#include <cstddef>

#define _Static_assert static_assert // Needed for sel4runtime to compile
extern "C" {
#include <sel4runtime.h>
}

namespace Wrapper {
    struct NotFound{};

    namespace SeL4 {
        #include <sel4/sel4.h>
    }
}

using namespace Wrapper::SeL4;

// Take advantage of how C++ searches namespaces for symbol names
// If a symbol was already #included in sel4.h, then 'name' will refer to that symbol
// Otherwise, the next higher namespace will be searched, which will find the 'NotFound name' declaration
#define addSymbolExistsCheck(name) \
    namespace Wrapper { \
        NotFound name; \
        namespace SeL4 { \
            bool name##_exists = !std::is_same<decltype(name), NotFound>::value; \
        } \
    }

#define symbolExists(name) (name##_exists)

addSymbolExistsCheck(seL4_X86_4K)
addSymbolExistsCheck(seL4_ARM_Page)
addSymbolExistsCheck(seL4_RISCV_4K_Page)

bool first_line = true;

void outputNum(const char* key, long value) {
    if (!first_line) printf(",");
    first_line = false;
    printf("\"%s\":%ld", key, value);
}

void outputString(const char* key, const char* value) {
    if (!first_line) printf(",");
    first_line = false;
    printf("\"%s\":\"%s\"", key, value);
}

void startDict(const char* name) {
    if (!first_line) printf(",");
    printf("\"%s\":{", name);
    first_line = true;
}

void endDict() {
    printf("}");
    first_line = false;
}

#define outputExpr(EXPR) outputNum(#EXPR, EXPR)
#define outputSymbolExists(symbol) outputNum(#symbol, symbolExists(symbol))

void outputArch() {

#ifdef seL4_PML4Bits
    // Arch is x86-64
    outputString("arch", "x86_64");
    return;
#endif

outputString("arch", "unknown");

}

void outputEndianness() {
    long long unsigned n = 1;
    // If first byte is 1 then we're on little endian
    if (*(char*)&n == 1) {
        outputString("endianness", "little");
    } else {
        outputString("endianness", "big");
    }
}


int main() {
    printf("{");

    {
        startDict("literals");

        outputExpr(seL4_WordBits);
        outputExpr(seL4_SlotBits);
        outputExpr(seL4_PageBits);
        outputExpr(sizeof(int));
        outputExpr(offsetof(auxv_t, a_un));
        outputExpr(AT_SEL4_IPC_BUFFER_PTR);
        outputExpr(AT_NULL);
        outputExpr(AT_SYSINFO);

        endDict();
    }

    {
        startDict("object_sizes");

        outputNum("seL4_TCBObject", seL4_TCBBits);
        outputNum("seL4_EndpointObject", seL4_EndpointBits);

        outputNum("seL4_X86_4K", seL4_PageBits);
        outputNum("seL4_X64_PML4Object", seL4_PML4Bits);
        outputNum("seL4_X86_PDPTObject", seL4_PDPTBits);
        outputNum("seL4_X86_PageDirectoryObject", seL4_PageDirBits);
        outputNum("seL4_X86_PageTableObject", seL4_PageTableBits);

        endDict();
    }

    {
        startDict("found_symbols");

        outputSymbolExists(seL4_X86_4K);
        outputSymbolExists(seL4_ARM_Page);
        outputSymbolExists(seL4_RISCV_4K_Page);

        endDict();
    }

    outputArch();
    outputEndianness();

    printf("}\n");


}
