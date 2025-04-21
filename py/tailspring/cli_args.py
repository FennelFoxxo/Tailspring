from tailspring.context import Context
import tailspring.ts_enums as ts_enums
from pathlib import Path
import argparse
import yaml
import json
import subprocess


# argparse custom action to parse a list of key-value pairs that represent a dictionary of str -> Path
class FileDictAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        result = {}
        for value in values:
            if '=' in value:
                key, val = value.split('=', 1)
                path = Path(val)
                if not path.is_file():
                    raise ValueError(f"Invalid file path: {path}")
                result[key] = path
        setattr(namespace, self.dest, result)


def declare_args(ctx: Context):
    parser = argparse.ArgumentParser(
        prog='Tailspring Parser',
        description='Generates C headers from a configuration file for the Tailspring thread loader')

    parser.add_argument('--config', dest='config_path', required=True,
                        help='Path to the configuration file')

    parser.add_argument('--sel4-info-getter', dest='sel4_info_getter_path', required=True,
                        help='Path to the compiled sel4_info_getter binary')

    parser.add_argument('--gcc', dest='gcc_path', required=True,
                        help='Path to the GCC compiler (used for linking)')

    parser.add_argument('--startup-threads-paths', dest='startup_threads_paths', required=True, nargs='*',
                        help='Key-value pairs mapping startup thread names in the config file to the path of the thread binary')

    parser.add_argument('--output-header', dest='output_header_path', required=True,
                        help='Path to the output generated header file')

    parser.add_argument('--output-startup-threads-obj', dest='output_startup_threads_obj_path', required=True,
                        help='Path to the output generated object file containing startup thread data')

    ctx.arg_parser = parser


def parse_args(ctx: Context):
    args = ctx.arg_parser.parse_args()

    # Parse config file
    ctx.config = parse_config(args.config_path)

    # Validate GCC path
    gcc_path = Path(args.gcc_path)
    if not gcc_path.is_file():
        raise ValueError(f"GCC path is invalid: {gcc_path}")
    ctx.gcc_path = gcc_path

    # Validate output header path
    output_header_path = Path(args.output_header_path)
    if not output_header_path.parent.is_dir():
        raise ValueError(f"Output header path is invalid: {output_header_path}")
    ctx.output_header_path = output_header_path

    # Validate output startup threads data path
    output_startup_threads_obj_path = Path(args.output_startup_threads_obj_path)
    if not output_startup_threads_obj_path.parent.is_dir():
        raise ValueError(f"Output startup threads data path is invalid: {output_startup_threads_obj_path}")
    ctx.output_startup_threads_obj_path = output_startup_threads_obj_path

    # Parse key-value pairs for startup threads paths dict
    startup_threads_paths_dict = {}
    for key_value in args.startup_threads_paths:
        key, val = key_value.split('=', 1)
        path = Path(val)
        if not path.is_file():
            raise ValueError(f"Invalid startup thread binary path: {path}")
        startup_threads_paths_dict[key] = path
    ctx.startup_threads_paths = startup_threads_paths_dict

    # Call seL4 info getter
    sel4_info_getter_path = Path(args.sel4_info_getter_path)
    if not sel4_info_getter_path.parent.is_dir():
        raise ValueError(f"seL4 info getter path is invalid: {sel4_info_getter_path}")
    ctx.sel4_info = get_sel4_info(sel4_info_getter_path)

    # Extract frequently used symbols from sel4_info
    arch_from_sel4_info = ctx.sel4_info['arch']
    for arch_enum in ts_enums.Arch:
        if arch_enum.name == arch_from_sel4_info:
            ctx.arch = arch_enum
            break
    else:
        raise RuntimeError(f"Could not find arch '{arch_from_sel4_info}' returned from seL4 info getter")
    ctx.page_size_bits = ctx.sel4_info['literals']['seL4_PageBits']
    ctx.page_size = 1 << ctx.page_size_bits
    ctx.temp_dir = ctx.output_startup_threads_obj_path.parent


def parse_config(config_path: Path) -> dict:
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def get_sel4_info(sel4_info_getter_path: Path) -> dict:
    result = subprocess.run([sel4_info_getter_path], capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Failed to call sel4 info getter with error: {result.stderr}")
    return json.loads(result.stdout)
