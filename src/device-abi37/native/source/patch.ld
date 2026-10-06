OUTPUT_ARCH(arm)
ENTRY(progress_api_entry)
PHDRS { code PT_LOAD FLAGS(5); workspace PT_LOAD FLAGS(6); append PT_LOAD FLAGS(5); }
SECTIONS {
 . = 0x213cb0;
 __progress_start = .;
 .text : { *core-hooks.o(.text*) *core-speed.o(.text*) *core-target.o(.text*) } :code
 .rodata : { *core-target.o(.rodata*) } :code
 .data : { *(.data*) } :workspace
 .bss : { *(.bss*) *(COMMON) } :workspace
 . = ALIGN(8);
 .progress_workspace : { KEEP(*(.progress_workspace)) } :workspace
 . = ALIGN(8);
 .reader_workspace : { KEEP(*(.reader_workspace)) } :workspace
 . = ALIGN(8);
 __sparse_append_start = .;
 .sparse_text : { *average.o(.text*) *phase-hooks.o(.text*) *phase.o(.text*) } :append
 .sparse_rodata : { *phase.o(.rodata*) } :append
 . = ALIGN(8);
 .sparse_phase_workspace : { KEEP(*(.sparse_phase_workspace)) } :workspace
 . = ALIGN(8);
 __progress_end = .;
 .ARM.attributes 0 : { *(.ARM.attributes) } :NONE
 /DISCARD/ : { *(.comment) *(.ARM.exidx*) *(.ARM.extab*) }
 ASSERT(SIZEOF(.data)==0,"unexpected data")
 ASSERT(SIZEOF(.bss)==0,"unexpected uninitialized data")
 ASSERT(SIZEOF(.progress_workspace)==7064,"workspace ABI")
 ASSERT(SIZEOF(.sparse_phase_workspace)==72,"phase workspace ABI")
 /* File-layout capacity hypothesis, not admission of free heap/stack. */
 ASSERT(__progress_end < 0x260000,"exceeds exact native TCM size hypothesis")
}
