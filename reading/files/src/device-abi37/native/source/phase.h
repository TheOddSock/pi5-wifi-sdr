/* New64-byte append telemetry; fresh geometry has ABI34 or35; phase remains SPH1/v1. */
#ifndef PI5_SPARSE_STREAM_PHASE_H
#define PI5_SPARSE_STREAM_PHASE_H
#include <stdint.h>
#define SPARSE_PHASE_MAGIC UINT32_C(0x53504831)
#define SPARSE_PHASE_OFFSET 7680u
#define SPARSE_PHASE_ORDINARY UINT32_C(0x19e26666)
#define SPARSE_PHASE_REQUESTED UINT32_C(0x1ad39999)
struct sparse_phase_record {
 uint32_t magic,version,bytes,sequence,status,flags,phy_register,mask;
 uint32_t baseline,requested,applied,at_arm,after_finish,restored,vendor_result,outer_result;
};
_Static_assert(sizeof(struct sparse_phase_record)==64u,"new phase64 ABI");
_Static_assert(SPARSE_PHASE_OFFSET+64u<=8192u,"new padding bound");
#endif
