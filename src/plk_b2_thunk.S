    .syntax unified
    .thumb
    .text

/* Lock page builder @0x08119054: in place of `add.w r4, r4, r5, lsl #1 ; ldrsh.w r1, [r4, #4]`
   r4 = the note's record, r5 = selected target. r1 = its value. Only r1 (and flags) change. */
    .global plk_val_thunk
    .thumb_func
plk_val_thunk:
    cmp     r5, #13
    blo     1f
    beq     2f
    ldrsh.w r1, [r4, #2]            @ target 14 (PrTime) at +2
    bx      lr
2:  ldrsh.w r1, [r4, #30]           @ target 13 (PrSpace) at +30
    bx      lr
1:  add.w   r1, r4, r5, lsl #1
    ldrsh.w r1, [r1, #4]
    bx      lr

/* Lock page builder @0x08119064: in place of `cmp r5, #10 ; bls 0x08119080`. Only Start (11) and Length (12) get the
   special label; 0..10 and the Prism targets take the bound parameter's own. */
    .global plk_label_thunk
    .thumb_func
plk_label_thunk:
    cmp     r5, #10
    bls     1f
    cmp     r5, #13
    bhs     1f
    bx      lr
1:  add.w   lr, lr, #0x18           @ -> 0x08119080
    bx      lr
