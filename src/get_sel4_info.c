#include <stdio.h>
#include <sel4/sel4.h>

void outputNum(const char* key, long value) {
    static int first_line = 1;
    if (!first_line) printf(",");
    first_line = 0;
    printf("\"%s\":%ld", key, value);
}

int main() {
    printf("{");
        
    outputNum("number 1", 5);
    outputNum("number 2", 5);
    outputNum("number 3", 5);
    
    outputNum("sizeof(seL4_Word)", sizeof(seL4_Word));
    outputNum("seL4_SlotBits", seL4_SlotBits);
        
        
    printf("}\n");
    
}
