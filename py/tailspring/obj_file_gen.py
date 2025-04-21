from tailspring.context import Context
import tailspring.ts_types as ts_types
import subprocess
from pathlib import Path


def gen_startup_threads_obj_file(ctx: Context):
    # Create all the object files for every chunk
    for vspace_name, vspace in ctx.vspaces.items():
        gen_obj_files_for_vspace(vspace, ctx)

    # Write linker script that links object files together
    linker_script_path = ctx.output_startup_threads_obj_path.parent / 'script.ld'
    write_linker_script(linker_script_path)

    # We need to get the file paths for every chunk
    all_chunks = [chunk for vspace in ctx.vspaces.values() for chunk in vspace.binary_chunks]
    all_chunk_paths = [chunk.get_path(ctx.temp_dir) for chunk in all_chunks]

    # Finally, link all the segments together into the final obj file, containing the data of every startup thread
    result = subprocess.run([ctx.gcc_path,  # GCC path
                             '-static', '-nostdlib', '-Wl,-r,--build-id=none',  # Flags
                             '-Wl,-T', linker_script_path,  # Linker script
                             '-o', ctx.output_startup_threads_obj_path  # Output file
                             ] + all_chunk_paths,  # Input files
                            capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Failed to generate startup threads object file with linker error: {result.stderr}")


def gen_obj_files_for_vspace(vspace: ts_types.VSpace, ctx: Context):
    for chunk in vspace.binary_chunks:
        gen_obj_file_for_chunk(chunk, ctx)


def gen_obj_file_for_chunk(chunk: ts_types.BinaryChunk, ctx: Context):
    # Write .bin file containing raw dump of segment contents
    chunk_bin_path = chunk.get_path(ctx.temp_dir).with_suffix('.bin')
    with open(chunk_bin_path, 'wb') as f:
        f.write(chunk.data_aligned)

    # Finally, we use the linker (called through gcc) to transform the raw .bin file into a linkable object file
    # The linker will automatically add start, end, and size symbols with a prefix that depends on the input file path,
    # so we set our cwd to the output directory and use relative paths to avoid ridiculously long symbol names
    result = subprocess.run([ctx.gcc_path,  # GCC path
                             '-static', '-nostdlib', '-fno-lto', '-Wl,-r,-b,binary',  # Flags
                             chunk_bin_path.name,  # Input file
                             '-o', chunk.get_path(ctx.temp_dir).name  # Output file
                             ], cwd=ctx.temp_dir, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Failed to generate chunk '{chunk.name}' with linker error: {result.stderr}")


def write_linker_script(path: Path):
    linker_script_text = 'SECTIONS {.startup_threads_data : { *(.data) }}'
    with open(path, 'w') as f:
        f.write(linker_script_text)
