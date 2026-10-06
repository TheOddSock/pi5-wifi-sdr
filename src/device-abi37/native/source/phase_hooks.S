.syntax unified
.cpu cortex-r4
.thumb
.section .text.sparse_hooks,"ax",%progbits
.macro TAIL name,target
.global \name
.type \name,%function
.thumb_func
\name:
 b.w \target
.size \name,.-\name
.endm
TAIL fw_sparse_phy_read,0x1d228c
TAIL fw_sparse_phy_write,0x1d22a2
TAIL fw_old_target,target_collect_checked
TAIL fw_old_matches,matches
