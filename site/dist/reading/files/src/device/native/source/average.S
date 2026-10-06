/* Identical twin6 offsets0/1/2/8/9/10 arithmetic for live and stopped reference.
 * The original admitted owned workspace supplies MMIO; no finite diagnostic
 * context is imported. Two selectors and six native DATA reads per output.
 * Rawbases64+16*k and offsets<=10 need no within-output ring wrap. Original
 * completion/lag/selector/clock/time/lifecycle guards remain unchanged.
 * Only the live
 * entry incrementally folds new packed words into an unpublished slot hash. */
.syntax unified
.cpu cortex-r4
.thumb
.section .text.sparse_read,"ax",%progbits
.global sparse_read
.type sparse_read,%function
.thumb_func
sparse_read:
 push {r4-r7,lr}
 movw r3,#:lower16:work
 movt r3,#:upper16:work
 ldr r4,[r3,#16]
 cbz r2,2f
1:
 ubfx r3,r1,#0,#14
 add.w r3,r3,#0x8000
 lsl.w r3,r3,#2
 str.w r3,[r4,#0x130]
 ldr.w r5,[r4,#0x134]
 ldr.w r6,[r4,#0x134]
 ldr.w r7,[r4,#0x134]
 shadd16 r5,r5,r7
 shadd16 r5,r5,r6
 add.w r3,r3,#32
 str.w r3,[r4,#0x130]
 ldr.w r6,[r4,#0x134]
 ldr.w r7,[r4,#0x134]
 ldr.w r12,[r4,#0x134]
 shadd16 r6,r6,r12
 shadd16 r6,r6,r7
 shadd16 r5,r5,r6
 str.w r5,[r0],#4
 adds r1,#16
 subs r2,#1
 bne 1b
2:
 pop {r4-r7,pc}
.size sparse_read,.-sparse_read

.section .text.sparse_read_fnv,"ax",%progbits
.global sparse_read_fnv
.type sparse_read_fnv,%function
.thumb_func
sparse_read_fnv:
 push {r4-r10,lr}
 cmp r2,#0
 beq.w 5f
 /* Original consume owns count and invalidates sequence before this call.
  * words32/hash12 => hash = out - 4*(count&1023) - 20. */
 movw r3,#:lower16:samples
 movt r3,#:upper16:samples
 ldr r3,[r3,#24]
 ubfx r3,r3,#0,#10
 sub.w r10,r0,r3,lsl #2
 sub.w r10,r10,#20
 cbnz r3,3f
 movw r8,#0x9dc5
 movt r8,#0x811c
 b 4f
3:
 ldr.w r8,[r10]
4:
 movw r9,#0x0193
 movt r9,#0x0100
 movw r3,#:lower16:work
 movt r3,#:upper16:work
 ldr r4,[r3,#16]
6:
 ubfx r3,r1,#0,#14
 add.w r3,r3,#0x8000
 lsl.w r3,r3,#2
 str.w r3,[r4,#0x130]
 ldr.w r5,[r4,#0x134]
 ldr.w r6,[r4,#0x134]
 ldr.w r7,[r4,#0x134]
 shadd16 r5,r5,r7
 shadd16 r5,r5,r6
 add.w r3,r3,#32
 str.w r3,[r4,#0x130]
 ldr.w r6,[r4,#0x134]
 ldr.w r7,[r4,#0x134]
 ldr.w r12,[r4,#0x134]
 shadd16 r6,r6,r12
 shadd16 r6,r6,r7
 shadd16 r5,r5,r6
 str.w r5,[r0],#4
 eor.w r8,r8,r5
 mul.w r8,r9,r8
 adds r1,#16
 subs r2,#1
 bne 6b
 str.w r8,[r10]
5:
 pop {r4-r10,pc}
.size sparse_read_fnv,.-sparse_read_fnv

.section .text.sparse_delay,"ax",%progbits
.global sparse_delay
.type sparse_delay,%function
.thumb_func
sparse_delay:
 push {r4,lr}
 movw r3,#:lower16:samples
 movt r3,#:upper16:samples
 ldr r1,[r3,#40]
 ldr r2,[r3,#36]
 subs r1,r1,r2
 cmp.w r1,#2112
 blo 7f
 cmp.w r1,#16320
 bhs 7f
 pop {r4,pc}
7:
 bl 0x891c
 pop {r4,pc}
.size sparse_delay,.-sparse_delay
