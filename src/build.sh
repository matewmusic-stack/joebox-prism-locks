#!/bin/bash
# Rebuild prebuilt/ from src/. Needs an arm-none-eabi GCC on PATH (e.g. xPack arm-none-eabi-gcc), or CROSS=/path/to/bin/arm-none-eabi-
set -e
cd "$(dirname "$0")"
X=${CROSS:-arm-none-eabi-}
O=../prebuilt
F="-mcpu=cortex-m7 -mthumb -mfloat-abi=hard -mfpu=fpv5-d16 -Os -ffreestanding -nostdlib -fno-builtin -fno-tree-loop-distribute-patterns -Wall -Wextra -Werror"
mkdir -p $O obj
${X}gcc $F -c -o obj/plk_b2.o plk_b2.c
${X}gcc -mcpu=cortex-m7 -mthumb -mfloat-abi=hard -mfpu=fpv5-d16 -c -o obj/plk_b2_thunk.o plk_b2_thunk.S
${X}ld -T b2.ld -o obj/b2.elf obj/plk_b2.o obj/plk_b2_thunk.o
${X}objcopy -O binary obj/b2.elf $O/b2.bin
${X}gcc $F -c -o obj/plk_b1.o plk_b1.c
${X}ld -T b1.ld -o obj/b1.elf obj/plk_b1.o
${X}objcopy -O binary obj/b1.elf $O/b1.bin
${X}nm obj/b2.elf > $O/b2.sym
${X}nm obj/b1.elf > $O/b1.sym
ls -l $O/b1.bin $O/b2.bin
