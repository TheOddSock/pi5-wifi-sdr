/* Exact C0 vendor triggered arm and pre-trigger delay hook ABI. */
.syntax unified
.arch armv7-r
.thumb
.section .text.hooks,"ax",%progbits
.align 2
.macro OBSERVE function
    push {r0-r3, r12, lr}
    mrs r12, APSR
    sub sp, sp, #8
    str r12, [sp]
    mov r0, r4
    mov r1, r5
    bl \function
    ldr r12, [sp]
    add sp, sp, #8
    msr APSR_nzcvqg, r12
    pop {r0-r3, r12, lr}
.endm
.global progress_api_entry
.type progress_api_entry,%function
.thumb_func
progress_api_entry:
    push {r4,lr}
    mov r3,r7
    bl sparse_collect_checked
    pop {r4,pc}
.size progress_api_entry, .-progress_api_entry
.global progress_arm_entry
.type progress_arm_entry,%function
.thumb_func
progress_arm_entry:
    OBSERVE target_before_arm
    strh.w r2,[r3,#0xb2e]
    OBSERVE target_after_arm
    bx lr
.size progress_arm_entry, .-progress_arm_entry
.global ring_delay_entry
.type ring_delay_entry,%function
.thumb_func
ring_delay_entry:
    push {r4,lr}
    mov r2,r0
    mov r0,r4
    mov r1,r5
    bl target_delay
    cmp r0,#0
    beq 1f
    ldr r0,=0x1cf9ed
    str r0,[sp,#4]
1:  pop {r4,pc}
.size ring_delay_entry, .-ring_delay_entry
.macro FW_TAIL name,address
    .global \name
    .type \name,%function
    .thumb_func
\name:
    b.w \address
    .size \name, .-\name
.endm
FW_TAIL fw_original_collect,0x1d2c82
FW_TAIL fw_delay,0x891c
FW_TAIL fw_template_set,0x1d839c
FW_TAIL progress_cycle,0x1997ac
.global progress_pmcr
.type progress_pmcr,%function
.thumb_func
progress_pmcr:
    mrc p15,0,r0,c9,c12,0
    bx lr
.size progress_pmcr, .-progress_pmcr
.global progress_enable
.type progress_enable,%function
.thumb_func
progress_enable:
    mrc p15,0,r0,c9,c12,1
    bx lr
.size progress_enable, .-progress_enable
.ltorg

.global ring_export_entry
.type ring_export_entry,%function
.thumb_func
ring_export_entry:
    cmp r6,#48
    blo 1f
    push {r4,lr}
    mov r0,r4
    mov r1,r8
    mov r2,r9
    mov r3,r7
    bl target_export_checked
    pop {r4,lr}
    b.w fw_data_exit
1:  mvn r0,#23
    b.w fw_data_exit
.size ring_export_entry,.-ring_export_entry

FW_TAIL fw_data_exit,0x1d2e36

FW_TAIL fw_deadman_refresh,0x86e8
