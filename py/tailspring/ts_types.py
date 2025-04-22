import tailspring.ts_enums as ts_enums
from dataclasses import dataclass, field
from typing import TextIO, BinaryIO, List, Dict, Optional
from pathlib import Path
import elftools.elf.elffile as elffile
import elftools.elf.sections as elfsections


@dataclass
class Cap:
    name: str
    type: ts_enums.CapType
    address: int = field(init=False)


@dataclass
class CapModification:
    dest_cap: Cap
    src_cap: Cap
    rights: List[ts_enums.CapRight]
    badge: int


@dataclass
class CNode(Cap):
    size: int
    guard: int
    caps: Dict[int, Cap]


class CapAddresses:
    def __init__(self):
        self.caps = []
        # Start at 1 to use 0 as a temp slot
        self.next_free_cap = 1

    def append(self, cap: Cap):
        cap.address = self.next_free_cap
        self.caps.append(cap)
        self.next_free_cap += 1

    def get_cap_by_name(self, name: str) -> Cap:
        for cap in self.caps:
            if cap.name == name:
                return cap
        raise KeyError(f"No cap with name {name}")

    def has_cap_with_name(self, name: str) -> bool:
        return any([cap.name == name for cap in self.caps])

    def get_slots_required(self) -> int:
        return self.next_free_cap

    def __repr__(self):
        return str(self.caps)


@dataclass
class BinaryChunk:
    name: str
    data: bytes
    dest_vaddr: int
    min_length: int
    alignment: int

    # vaddr rounded down to be aligned with a page boundary
    dest_vaddr_aligned: int = field(init=False)

    # data with padding added so that the start and end are aligned with a page boundary
    data_aligned: bytes = field(init=False)

    total_length_with_padding: int = field(init=False)

    # Can be generated from segment name
    start_symbol: str = field(init=False)

    def __post_init__(self):
        prefix = f'_binary_{self.name}_bin_'
        self.start_symbol = prefix + 'start'

        # We need to add some padding at the beginning. In the tailspring thread loader, we only have the ability
        # to copy page-sized chunks of data at a time (through remapping the pages). So if a chunk were to start in the middle
        # of a page (say address 0x1020) and we wrote it to the file, then the first byte of the chunk would be at the beginning of the file
        # and would be loaded into memory at address 0x1000 instead! In this example we'd add 0x20 bytes of padding to the beginning to fix this
        head_padding_len = self.dest_vaddr % self.alignment

        # Using the example before, the padding + segment should be loaded in at address 0x1000
        # i.e. load in at p_vaddr (0x1020) - head padding (0x20)
        self.dest_vaddr_aligned = self.dest_vaddr - head_padding_len

        # Then we would write the data - however, the number of bytes we write is only len(data), but we need to reserve min_length which might
        # be much greater. As an example, if a segment only contained the .bss section, len(data) would be 0 but min_length could be much greater
        data_len = len(self.data)
        extra_padding_min_len = self.min_length - data_len  # Extra padding bytes to buff out length to min_length

        # Finally, we need to make sure the end of the chunk is also aligned. When all the chunks are linked together, the linker will insert
        # each one after the other without any padding, so tail padding is needed to make sure the *next* chunk is also aligned to a page
        # Technically we could add alignment in the linker script, but we'd need to list each section individually and use ALIGN in between sections
        tail_padding_len = -(head_padding_len + data_len + extra_padding_min_len) % self.alignment

        self.data_aligned = (b'\0' * head_padding_len +
                             self.data +
                             b'\0' * extra_padding_min_len +
                             b'\0' * tail_padding_len
                             )

        self.total_length_with_padding = len(self.data_aligned)
        assert(self.total_length_with_padding % self.alignment == 0)

    def get_path(self, parent_dir: Path):
        return parent_dir / f'{self.name}.o'


@dataclass
class VSpace(Cap):
    # Not necessarily related to the path or filename of the binary image of the thread. The binary names
    # are the values under the "vspaces" section in the config file, while the vspace names are the keys
    binary_name: str
    binary_name_unique: str = field(init=False)
    # There might be multiple separate vspaces that are loaded from the same elf file
    # The way this is implemented is essentially by copying the segments from the elf file
    # multiple times, but each copy needs its own unique name and linker symbols, so the nonce
    # is just a unique value to distinguish between multiple copies of the same elf file
    nonce: int
    binary_path: Path
    alignment: int  # Minimum alignment of each chunk in the vspace - usually just the page size
    f: BinaryIO = field(init=False)
    elf: elffile.ELFFile = field(init=False)
    binary_chunks: List[BinaryChunk] = field(init=False)
    symtab: elffile.SymbolTableSection = field(init=False)

    def __post_init__(self):
        self.binary_name_unique = f"{self.binary_name}_num{self.nonce}"
        self.f = open(self.binary_path, 'rb')
        self.elf = elffile.ELFFile(self.f)
        self.symtab = self.elf.get_section_by_name('.symtab')
        self.binary_chunks = []
        # We only care about load segments
        for index, segment in enumerate(self.elf.iter_segments('PT_LOAD')):
            chunk = BinaryChunk(name=f"thread_{self.binary_name_unique}_segment{index}", data=segment.data(), dest_vaddr=segment['p_vaddr'], min_length=segment['p_memsz'], alignment=self.alignment)
            self.binary_chunks.append(chunk)

    def get_symbol(self, symbol_name: str) -> Optional[elfsections.Symbol]:
        if self.symtab is None:
            raise RuntimeError(f"No symbol table for '{self.binary_name}' found")
        matching_symbols = self.symtab.get_symbol_by_name(symbol_name)
        return None if matching_symbols is None else matching_symbols[0]


@dataclass
class Thread:
    tcb: Cap
    cspace: Cap
    vspace: VSpace
    ipc_buffer: Cap
    stack_size: int
    entry_addr: int

    # Set in thread_setup when stack is being initialized
    arg0: int = field(init=False)
    arg1: int = field(init=False)

    ipc_buffer_addr: int = field(init=False)
    stack_top_addr: int = field(init=False)  # The address of the top of the stack chunk
    stack_pointer_addr: int = field(init=False)  # The address that should be loaded into the stack pointer on thread start


# Represents a fragment of text that can be flushed to the output file - essentially a buffer
class Fragment:
    def __init__(self):
        self.writes = []

    def write(self, data: str):
        self.writes.append(data)

    def flush(self, file: TextIO):
        file.write(''.join(self.writes))


__all__ = ['Cap', 'CapModification', 'CNode', 'CapAddresses', 'Segment', 'VSpace', 'Thread', 'Fragment']
