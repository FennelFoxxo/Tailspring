from tailspring.context import Context
import tailspring.ts_types as ts_types
import subprocess
from pathlib import Path


def gen_startup_threads_obj_file(ctx: Context):
    # Create all the object files for every segment
    for vspace_name, vspace in ctx.vspaces.items():
        gen_obj_files_for_vspace(vspace, ctx)

    # Write linker script that links object files together
    linker_script_path = ctx.output_startup_threads_obj_path.parent / 'script.ld'
    write_linker_script(linker_script_path)

    # We need to get the file paths for every segment
    all_segments = [segment for vspace in ctx.vspaces.values() for segment in vspace.segments]
    all_segment_paths = [segment.segment_obj_path for segment in all_segments]

    # Finally, link all the segments together into the final obj file, containing the data of every startup thread
    result = subprocess.run([ctx.gcc_path,  # GCC path
                             '-static', '-nostdlib', '-Wl,-r,--build-id=none',  # Flags
                             '-Wl,-T', linker_script_path,  # Linker script
                             '-o', ctx.output_startup_threads_obj_path  # Output file
                             ] + all_segment_paths,  # Input files
                            capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Failed to generate startup threads object file with linker error: {result.stderr}")


def gen_obj_files_for_vspace(vspace: ts_types.VSpace, ctx: Context):
    for segment in vspace.segments:
        gen_obj_file_for_segment(segment, ctx)


def gen_obj_file_for_segment(segment: ts_types.Segment, ctx: Context):
    temp_dir = ctx.output_startup_threads_obj_path.parent
    segment.segment_obj_path = temp_dir / f'{segment.name}.o'

    # First, we'll write the .bin file containing raw dump of segment contents
    # We'll need to calculate padding to add at the beginning and the end for alignment reasons

    # We need to add some padding at the beginning. In the tailspring thread loader, we only have the ability
    # to copy page-sized chunks of data at a time (through remapping the pages). So if a segment were to start in the middle
    # of a page (say address 0x1020) and we wrote it to the file, then the first byte of the segment would be at the beginning of the file
    # and would be loaded into memory at address 0x1000 instead! In this example we'd add 0x20 bytes of padding to the beginning to fix this
    head_padding_len = segment.segment_raw['p_vaddr'] % ctx.page_size

    # Using the example before, the padding + segment should be loaded in at address 0x1000
    # i.e. load in at p_vaddr (0x1020) - head padding (0x20)
    segment.load_vaddr = segment.segment_raw['p_vaddr'] - head_padding_len

    # Then we would write the segment length - however, the number of bytes we write is only p_filesz, but we need to reserve p_memsz which might
    # be much greater. As an example, if a segment only contained the .bss section, it would have a p_filesz of 0 but a (potentially) much greater p_memsz
    filesz_len = segment.segment_raw['p_filesz']
    extra_memsz_len = segment.segment_raw['p_memsz'] - filesz_len  # Extra padding bytes to buff out length to p_memsz

    # Finally, we need to make sure the end of the segment is also aligned. When all the segment's sections are linked together, the linker will insert
    # each one after the other without any padding, so tail padding is needed to make sure the *next* segment's section is also aligned to a page
    # Technically we could add alignment in the linker script, but we'd need to list each section individually and use ALIGN in between sections
    tail_padding_len = -(head_padding_len + filesz_len + extra_memsz_len) % ctx.page_size

    # Then write .bin file containing raw dump of segment contents
    segment_bin_path = segment.segment_obj_path.with_suffix('.bin')
    with open(segment_bin_path, 'wb') as f:
        f.write(b'0' * head_padding_len +
                segment.segment_raw.data() +
                b'0' * extra_memsz_len +
                b'0' * tail_padding_len
                )

    # And save the total length in the segment object
    segment.load_length = head_padding_len + segment.segment_raw['p_memsz'] + tail_padding_len

    # Finally, we use the linker (called through gcc) to transform the raw .bin file into a linkable object file
    # The linker will automatically add start, end, and size symbols with a prefix that depends on the input file path,
    # so we set our cwd to the output directory and use relative paths to avoid ridiculously long symbol names
    result = subprocess.run([ctx.gcc_path,  # GCC path
                             '-static', '-nostdlib', '-fno-lto', '-Wl,-r,-b,binary',  # Flags
                             segment_bin_path.name,  # Input file
                             '-o', segment.segment_obj_path.name  # Output file
                             ], cwd=temp_dir, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Failed to generate segment '{segment.name}' with linker error: {result.stderr}")


def write_linker_script(path: Path):
    linker_script_text = 'SECTIONS {.startup_threads_data : { *(.data) }}'
    with open(path, 'w') as f:
        f.write(linker_script_text)
