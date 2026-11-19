MEMORY { CAVE (rx) : ORIGIN = 0x080FF820, LENGTH = 0x7E0 }
SECTIONS { .cave : { *(.text .text.* .rodata .rodata.*) } > CAVE
  /DISCARD/ : { *(.data .data.* .bss .bss.* COMMON .ARM.exidx* .comment) } }
