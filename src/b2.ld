MEMORY { B2 (rx) : ORIGIN = 0x0811BA00, LENGTH = 0x4000 }
SECTIONS { .b2 : { *(.text .text.* .rodata .rodata.*) } > B2
  /DISCARD/ : { *(.data .data.* .bss .bss.* COMMON .ARM.exidx* .comment) } }
