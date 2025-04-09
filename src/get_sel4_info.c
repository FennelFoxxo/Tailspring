#include <stdio.h>
#include <sel4/sel4.h>

int first_line = 1;

void outputNum(const char* key, long value) {
    if (!first_line) printf(",");
    first_line = 0;
    printf("\"%s\":%ld", key, value);
}

void startDict(const char* name) {
    if (!first_line) printf(",");
    printf("\"%s\":{", name);
    first_line = 1;
}

void endDict() {
    printf("}");
    first_line = 0;
}

#define outputExpr(EXPR) outputNum(#EXPR, EXPR)

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

    printf("}\n");
}
