import tailspring.ts_enums as ts_enums
from dataclasses import dataclass, field
from typing import TextIO, BinaryIO, List, Dict
from pathlib import Path
import elftools.elf.elffile as elffile


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
class Segment:
    name: str
    segment_raw: elffile.Segment
    # Can be generated from segment name
    start_symbol: str = field(init=False)

    # Set in startup_threads when obj file is created
    segment_obj_path: Path = field(init=False)
    load_vaddr: int = field(init=False)
    load_length: int = field(init=False)

    def __post_init__(self):
        prefix = f'_binary_{self.name}_bin_'
        self.start_symbol = prefix + 'start'


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
    f: BinaryIO = field(init=False)
    elf: elffile.ELFFile = field(init=False)
    segments: List[Segment] = field(init=False)

    def __post_init__(self):
        self.binary_name_unique = f"{self.binary_name}_num{self.nonce}"
        self.f = open(self.binary_path, 'rb')
        self.elf = elffile.ELFFile(self.f)
        self.segments = []
        # We only care about load segments
        for index, segment_raw in enumerate(self.elf.iter_segments('PT_LOAD')):
            segment = Segment(name=f"thread_{self.binary_name_unique}_segment{index}", segment_raw=segment_raw)
            self.segments.append(segment)


@dataclass
class Thread:
    tcb: Cap
    cspace: Cap
    vspace: VSpace
    ipc_buffer: Cap
    stack_size: int
    ipc_buffer_addr: int = field(init=False)
    stack_top_addr: int = field(init=False)


# Represents a fragment of text that can be flushed to the output file - essentially a buffer
class Fragment:
    def __init__(self):
        self.writes = []

    def write(self, data: str):
        self.writes.append(data)

    def flush(self, file: TextIO):
        file.write(''.join(self.writes))


__all__ = ['Cap', 'CapModification', 'CNode', 'CapAddresses', 'Segment', 'VSpace', 'Thread', 'Fragment']
