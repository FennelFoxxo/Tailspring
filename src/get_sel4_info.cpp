#include <stdio.h>
#include <type_traits>

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

int main() {
    printf("{");
        
    outputExpr(sizeof(seL4_Word));
    outputExpr(seL4_SlotBits);
    
    {
        startDict("object_sizes");

        outputNum("seL4_TCBObject", seL4_TCBBits);
        outputNum("seL4_X86_4K", seL4_PageBits);
        outputNum("seL4_EndpointObject", seL4_EndpointBits);
        
        endDict();
    }
    
    {
        startDict("found_symbols");

        outputSymbolExists(seL4_X86_4K);
        outputSymbolExists(seL4_ARM_Page);
        outputSymbolExists(seL4_RISCV_4K_Page);
        
        endDict();
        
        
    }

    printf("}\n");
    

}
