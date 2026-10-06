#ifndef PI5_STREAM_MODULAR_H
#define PI5_STREAM_MODULAR_H
#include <stdint.h>
/* A positive distance inside half-range is meaningful only while the existing
 * per-poll writer/timer bounds hold. Those bounds remain separate guards. */
static inline int pi5_stream_lag(uint32_t produced,uint32_t next,uint32_t *lag)
{
 uint32_t d=produced-next;
 if((d&UINT32_C(0x80000000)) || d<=64u)return 0;
 if(d>=16320u)return -1;
 *lag=d;return 1;
}
#endif
