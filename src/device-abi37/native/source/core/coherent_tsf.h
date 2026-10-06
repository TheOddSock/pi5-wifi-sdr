/* Offline candidate only: acquire a coherent existing TSF high/low/high triplet.
 * No MMIO writes, clock programming, delay, native threshold or sample read.
 * Only an adjacent high-word carry permits one immediate retry. The retry
 * must stay at that post-carry high word; every other mismatch still refuses.
 * Caller retains all original snapshot/admission/clock/lag/timing guards.
 */
#ifndef PI5_COHERENT_TSF_NEXT_H
#define PI5_COHERENT_TSF_NEXT_H
#include <stdint.h>
#ifndef PI5_TSF_READ32
#define PI5_TSF_READ32(base, offset) reg32((base), (offset))
#endif
struct pi5_tsf_triplet {
    uint32_t first_high,first_low,first_high_after;
    uint32_t high,low,high_after,attempts,carried,coherent;
};
static inline int pi5_tsf_coherent_next(volatile unsigned char *base,
                                       struct pi5_tsf_triplet *out)
{
    uint32_t high,low,after;
    out->attempts=1u;out->carried=0u;out->coherent=0u;
    high=PI5_TSF_READ32(base,0x184u);
    low=PI5_TSF_READ32(base,0x180u);
    after=PI5_TSF_READ32(base,0x184u);
    out->first_high=out->high=high;out->first_low=out->low=low;
    out->first_high_after=out->high_after=after;
    if(high==after){out->coherent=1u;return 1;}
    if(after!=(uint32_t)(high+1u))return 0;
    out->attempts=2u;
    high=PI5_TSF_READ32(base,0x184u);
    low=PI5_TSF_READ32(base,0x180u);
    after=PI5_TSF_READ32(base,0x184u);
    out->high=high;out->low=low;out->high_after=after;
    if(high!=out->first_high_after || after!=high)return 0;
    out->carried=1u;out->coherent=1u;return 1;
}
#endif
