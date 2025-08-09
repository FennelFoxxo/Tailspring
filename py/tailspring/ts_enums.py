import enum
from typing import Type, List, Dict, Any


class Arch(enum.Enum):
    x86_64 = 0


# Serves as both enums and also a mapping of cap type (in config file) -> sel4 cap type
class CapType(enum.Enum):
    tcb = 'seL4_TCBObject'
    endpoint = 'seL4_EndpointObject'
    cnode = 'seL4_CapTableObject'
    pml4 = 'seL4_X64_PML4Object'
    pdpt = 'seL4_X86_PDPTObject'
    page_directory = 'seL4_X86_PageDirectoryObject'
    page_table = 'seL4_X86_PageTableObject'
    x86_4K = 'seL4_X86_4K'
    # These depend on the specific arch and are reassigned later
    frame = 1
    vspace = 2


class CapRight(enum.Enum):
    write = "CAP_ALLOW_WRITE"
    read = "CAP_ALLOW_READ"
    grant = "CAP_ALLOW_GRANT"
    grant_reply = "CAP_ALLOW_GRANT_REPLY"

    @staticmethod
    def list_to_C_expr(rights: List['CapRight']):
        if len(rights) == 0:
            return '0'
        return '(' + ' | '.join([right_enum.value for right_enum in rights]) + ')'


def extend_enums(base_enums: Type[enum.Enum], extra_values: Dict[str, Any]) -> Type[enum.Enum]:
    combined_values = {}
    # If we iterate directly over base_enums, we won't pick up on enums that are an alias of another
    for e_name, e in base_enums.__members__.items():
        combined_values[e_name] = e.value
    combined_values.update(extra_values)
    return enum.Enum(base_enums.__name__, combined_values)


def extend_CapType_enums_with_arch(arch: Arch):
    global CapType
    if arch == Arch.x86_64:
        CapType = extend_enums(CapType, {'frame': CapType.x86_4K.value, 'vspace': CapType.pml4.value})


def get_underivable_cap_types():
    return [CapType.pdpt, CapType.page_directory, CapType.page_table]


__all__ = ['Arch', 'CapType', 'CapRight', 'extend_CapType_enums_with_arch']
