PHDRS {
  startup_threads_data  PT_LOAD;
  code                  PT_LOAD FLAGS (0x5);
  other                 PT_LOAD FLAGS (0x6);
}

SECTIONS {

. = ALIGN(4K);

_lowest_vaddr = .;

.startup_threads_data : { *(.startup_threads_data) } : startup_threads_data

. = ALIGN(4K);

.text : { *(.text) } : code
.init : { *(.init) } : code
.fini : { *(.fini) } : code
.init_array : { *(.init_array) } : code
.fini_array : { *(.fini_array) } : code

.dummy_other : { } : other

}

INSERT BEFORE .note.gnu.build-id;