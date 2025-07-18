import tailspring.ts_types as ts_types
import tailspring.op_types as op_types
import tailspring.ts_enums as ts_enums
import tailspring.paging as paging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List
import argparse


@dataclass
class Context:
    arg_parser: argparse.ArgumentParser = None

    # These are gathered from cli arguments
    config: dict = field(default_factory=dict)
    gcc_path: Path = None
    output_header_path: Path = None
    output_startup_threads_obj_path: Path = None
    # All the startup threads need to be loaded from some binary image, although it's inconvenient to
    # write out the path to the binary every time in the config file. Instead, the thread binaries are
    # referenced by name, and a mapping of name -> path is passed in as an argument which is stored here
    startup_threads_paths: Dict[str, Path] = field(default_factory=dict)
    sel4_info: dict = field(default_factory=dict)  # This is set by invoking the executable passed as the sel4_info_getter

    # These are pulled directly from sel4_info
    arch: ts_enums.Arch = None
    page_size_bits: int = None
    page_size: int = None
    temp_dir: Path = None

    # Simple wrappers to represent the structure of the specified config in an easier-to-use format
    cap_addresses: ts_types.CapAddresses = field(default_factory=ts_types.CapAddresses)
    cap_modifications: Dict[str, ts_types.CapModification] = field(default_factory=dict)
    vspaces: Dict[str, ts_types.VSpace] = field(default_factory=dict)  # Maps vspace name to vspace object
    threads: Dict[str, ts_types.Thread] = field(default_factory=dict)  # Maps thread name (tcb name) to thread object

    # Optional cnode that can be designated to store leftover general purpose untypeds (i.e. the rest of the system's non-device memory)
    # after tailspring is done allocating objects. Only one cnode can be set for this
    gp_untypeds_cnode: ts_types.CNode = None

    # List of operations
    ops_list: List[op_types.Operation] = field(default_factory=list)

    paging_arch_info: paging.PagingArchInfo = None
    # Maps vspace name to paging structures that need to be created and mapped for that vspace
    paging_structures: Dict[str, paging.PagingStructure] = field(default_factory=dict)

    # Fragments
    preamble_fragment: ts_types.Fragment = field(default_factory=ts_types.Fragment)
    ops_fragment: ts_types.Fragment = field(default_factory=ts_types.Fragment)
    mapping_funcs_enable_fragment: ts_types.Fragment = field(default_factory=ts_types.Fragment)
    extern_linker_symbols_fragment: ts_types.Fragment = field(default_factory=ts_types.Fragment)
