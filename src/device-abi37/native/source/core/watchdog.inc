/* Exact-c0 native deadman service, existing nonzero timeout unchanged.
 * No caller-controlled timer value, interrupt-mask change or scheduler reentry. */
extern void fw_deadman_refresh(uint32_t);
struct watchdog_record {
 uint32_t magic,version,bytes,configured,interval,handle,feeds,max_ticks;
 uint32_t total_ticks,first_cycle,last_cycle,before_period,after_period,flags,core_before,core_after;
};
_Static_assert(sizeof(struct watchdog_record)==64,"Watchdog telemetry ABI");
__attribute__((section(".reader_workspace"))) static struct watchdog_record deadman={0};
static uint32_t deadman_word(uint32_t address){return *(volatile uint32_t *)(uintptr_t)address;}
static int deadman_initialize(void)
{
 uint32_t i;for(i=0;i<sizeof(deadman);i++)((unsigned char *)&deadman)[i]=0;
 deadman.magic=UINT32_C(0x57444f47);deadman.version=PROGRESS_VERSION;deadman.bytes=64;
 deadman.configured=deadman_word(0x19876c);deadman.interval=deadman_word(0x198768);deadman.handle=deadman_word(0x198718);
 if(deadman.configured!=481500000u || !deadman.interval || (deadman.handle&3u) || deadman.handle<0x198000u || deadman.handle>0x25ff00u || deadman_word(0x198324)!=0x19a745u){deadman.flags=1;return 0;}
 deadman.core_before=deadman_word(deadman.handle+0x88u);return deadman.core_before!=0;
}
static int deadman_service(void)
{
 uint32_t t0,ticks;
 deadman.before_period=deadman_word(0x19876c);
 if(deadman.before_period!=deadman.configured || deadman_word(0x198718)!=deadman.handle || deadman_word(0x198324)!=0x19a745u){deadman.flags|=2;return 0;}
 t0=progress_cycle();fw_deadman_refresh(1u);ticks=progress_cycle()-t0;
 if(!deadman.feeds)deadman.first_cycle=t0;
 deadman.last_cycle=t0;deadman.feeds++;deadman.total_ticks+=ticks;if(ticks>deadman.max_ticks)deadman.max_ticks=ticks;
 deadman.after_period=deadman_word(0x19876c);deadman.core_after=deadman_word(deadman.handle+0x88u);
 if(!ticks || ticks>32768u || deadman.after_period!=deadman.configured || deadman.core_after!=deadman.core_before){deadman.flags|=4;return 0;}
 samples.reserved=deadman.feeds;return 1;
}
