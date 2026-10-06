/* Exact a8793f02... C0 WLTEST synchronous receive stream. Reused owned-RAM
 * slots, stride16 sample reads and original selector restoration; fixed host
 * lease, normal close/expiry cleanup and existing nonzero native watchdog.
 * No fixed sample-count duration. Host pilot/driver remain externally bounded. */
#include "progress.h"

extern int32_t fw_original_collect(void *, const unsigned char *, void *);
extern uint32_t progress_cycle(void);
extern uint32_t progress_pmcr(void);
extern uint32_t progress_enable(void);

struct workspace {
    uint32_t busy, captures;
    void *phy;
    const unsigned char *args;
    volatile unsigned char *pointer_regs, *timer_regs;
    struct progress_record record;
};
__attribute__((section(".progress_workspace")))
struct workspace work = {0};
__attribute__((section(".reader_workspace"))) static struct ring_context context = {0};
extern void fw_delay(uint32_t);
extern void sparse_delay(uint32_t);
extern uint32_t sparse_rate_matches(void *,const unsigned char *);

static uint16_t half(const unsigned char *p)
{ return (uint16_t)((uint16_t)p[0] | (uint16_t)p[1] << 8); }
static uint32_t word(const unsigned char *p)
{ return (uint32_t)p[0] | (uint32_t)p[1] << 8 | (uint32_t)p[2] << 16 | (uint32_t)p[3] << 24; }
static uint16_t reg16(volatile unsigned char *r, uint32_t off)
{ return *(volatile uint16_t *)(r + off); }
static uint32_t reg32(volatile unsigned char *r, uint32_t off)
{ return *(volatile uint32_t *)(r + off); }
#ifdef PROGRESS_HOST_MOCK
extern uint32_t progress_scale(void);
#else
static uint32_t progress_scale(void)
{ return *(volatile uint32_t *)UINT32_C(0x198678); }
#endif

int matches(void *phy, const unsigned char *args)
{ return work.busy && phy == work.phy && args == work.args; }

/* ABI37: coherent TSF acquisition, same existing admission guards. */
#include "coherent_tsf.h"
static void observe(uint32_t phase, uint32_t ordinal)
{
    struct progress_record *r = &work.record;
    struct progress_observation *s;
    volatile unsigned char *p = work.pointer_regs, *t = work.timer_regs;
    uint32_t elapsed;
    struct pi5_tsf_triplet tsf;int tsf_coherent;
    if (r->observations >= PROGRESS_RECORDS) { r->flags |= PROGRESS_LOG_FULL; return; }
    s = &r->samples[r->observations++];
    s->phase = phase; s->ordinal = ordinal;
    s->cycle_before = progress_cycle();
    s->pmcr_before = progress_pmcr(); s->enable_before = progress_enable();
    s->scale_before = progress_scale();
    s->maccontrol_before = reg32(t, 0x120);
    s->fraction_low_before = reg16(t, 0x62e); s->fraction_high_before = reg16(t, 0x630);
    tsf_coherent=pi5_tsf_coherent_next(t,&tsf);
    s->tsf_high_before=tsf_coherent?tsf.high:tsf.first_high;
    s->tsf_low=tsf_coherent?tsf.low:tsf.first_low;
    s->tsf_high_after=tsf_coherent?tsf.high_after:tsf.first_high_after;
    s->pointer_high_before = reg16(p, 0x53a); s->pointer_low = reg16(p, 0x556);
    s->pointer_high_after = reg16(p, 0x53a);
    s->extent_before = reg16(p, 0x538);
    s->start_low = reg16(p, 0x552); s->stop_low = reg16(p, 0x554);
    s->extent_after = reg16(p, 0x538);
    s->collect_control_before = reg16(p, 0xb2e);
    s->collect_control_after = reg16(p, 0xb2e);
    s->fraction_low_after = reg16(t, 0x62e); s->fraction_high_after = reg16(t, 0x630);
    s->maccontrol_after = reg32(t, 0x120);
    s->scale_after = progress_scale();
    s->enable_after = progress_enable(); s->pmcr_after = progress_pmcr();
    s->cycle_after = progress_cycle();
    s->flags = (((s->pointer_high_before ^ s->pointer_high_after) & 15u) == 0u ? OBS_POINTER_MATCH : 0u)
        | (s->extent_before == s->extent_after ? OBS_BOUNDS_MATCH : 0u)
        | (s->collect_control_before == s->collect_control_after ? OBS_CONTROL_MATCH : 0u)
        | (tsf_coherent ? OBS_TSF_HIGH_MATCH : 0u)
        | (s->pmcr_before == s->pmcr_after &&
           ((s->enable_before ^ s->enable_after) & UINT32_C(0x80000007)) == 0u &&
           s->scale_before == s->scale_after ? OBS_CPU_STATE_MATCH : 0u)
        | (s->fraction_low_before == s->fraction_low_after &&
           s->fraction_high_before == s->fraction_high_after &&
           s->maccontrol_before == s->maccontrol_after ? OBS_TSF_STATE_MATCH : 0u);
    if (s->flags != 63u) r->flags |= PROGRESS_UNSTABLE;
    /* Modulo counter ticks, not wall time. This brackets the reads only;
     * save/restore, flag calculation and bookkeeping are outside the bracket. */
    elapsed = s->cycle_after - s->cycle_before;
    r->observer_cycles_total += elapsed;
    if (elapsed > r->observer_cycles_max) r->observer_cycles_max = elapsed;
}

#include "sampler.inc"
#include "watchdog.inc"
#include "lease.inc"
static void private_fields(uint32_t *dest)
{
    const unsigned char *p=*(unsigned char **)((unsigned char *)work.phy+0xf8);
    if (!p || ((uintptr_t)p&3u)) {context.flags|=1u;return;}
    dest[0]=word(p+0x11c);dest[1]=word(p+0x120);
    dest[2]=word(p+0x124);dest[3]=word(p+0x128);
}
void target_before_arm(void *phy,const unsigned char *args)
{
    struct progress_observation *p;
    if (!sparse_rate_matches(phy,args)) return;
    observe(PROGRESS_BEFORE_ARM,0u);p=&work.record.samples[work.record.observations-1u];
    if (p->flags!=63u || p->extent_before || p->start_low!=0x8000u || p->stop_low!=0xbfffu
        || p->collect_control_before!=0u) work.record.flags|=PROGRESS_BAD_EXTENT;
    private_fields(&context.before_private_start);
}
void target_after_arm(void *phy,const unsigned char *args)
{ if (matches(phy,args)) observe(PROGRESS_AFTER_ARM,0u); }
uint32_t target_delay(void *phy,const unsigned char *args,uint32_t requested)
{
    uint32_t i,last,tick,next_feed=128u;
    struct progress_observation *p;
    if (!matches(phy,args)) {fw_delay(requested);return 0u;}
    context.requested_delay=requested;context.step_argument=32u;
    if (requested!=400u || work.record.flags || work.record.observations!=2u) {
        context.flags|=2u;fw_delay(requested);return 0u;
    }
    last=progress_cycle();
    for (i=0;!samples.flags;) {
        if(!lease_check()){samples.flags|=BAD_SAMPLE_STATE;break;}
        if((lease.expired || samples.published>=UINT32_MAX-1u) && samples.published && !(samples.count%1024u)){samples.stop_observed=lease.expired?2u:3u;break;}
        if(samples.stop_request && samples.stop_request!=UINT32_C(0x53544f50)){samples.flags|=BAD_SAMPLE_STATE;break;}
        if(samples.stop_request==UINT32_C(0x53544f50) && samples.published && !(samples.count%1024u)){samples.stop_observed=1u;break;}
        sparse_delay(32u);tick=progress_cycle();
        if (!((tick-last)>0u && (tick-last)<=32768u)) {context.flags|=4u;break;}
        last=tick;
        struct progress_observation current;
        if(i<PROGRESS_SAVED_POLL_RECORDS){observe(PROGRESS_POLL,++work.record.poll_calls);p=&work.record.samples[work.record.observations-1u];}
        else {snapshot(&current);work.record.poll_calls++;p=&current;}
        context.delay_steps++;
        if (p->flags!=63u || p->extent_before || p->start_low!=0x8000u || p->stop_low!=0xbfffu
            || (p->pointer_high_after&15u) || p->pointer_low<0x8000u || p->pointer_low>0xbfffu
            || p->collect_control_before!=1u || !(p->pmcr_before&1u) || (p->pmcr_before&40u)
            || !(p->enable_before&UINT32_C(0x80000000)) || !p->scale_before) {
            record_rejected(p,6u);context.flags|=8u;break;
        }
        uint32_t old_count=samples.count;consume(p);if(samples.count<old_count)lease.word_wraps++;
        if(i!=UINT32_MAX)i++;
        if(!samples.flags && samples.published>=next_feed){if(!deadman_service()){record_rejected(p,5u);samples.flags|=BAD_SAMPLE_STATE;break;}next_feed+=128u;}
    }
    /* Once admitted and armed, bounded completion/failure both use the
     * exact existing normal cleanup. Explicit flags/status report failure. */
    if(!samples.stop_observed)samples.flags|=SAMPLE_INCOMPLETE;
    work.record.reserved0=1u;return 1u;
}

static int profile(const unsigned char *a)
{
    uint32_t i;
    if (half(a+8)!=2u || half(a+10)!=48u || a[12]!=1u || half(a+14)!=2u
        || half(a+16)!=17u || word(a+20)!=400u || word(a+24)!=400u) return 0;
    for (i=0;i<48u;i++) {
        if ((i>=8u && i<13u) || (i>=14u && i<18u) || (i>=20u && i<28u)) continue;
        if (a[i]) return 0;
    }
    return 1;
}
int32_t target_collect_checked(void *phy, const unsigned char *args, void *output,
                               uint32_t capacity)
{
    struct progress_record *r = &work.record;
    unsigned char *sh, *hw, **indirect;
    uint32_t i, chanspec, phase_mask = 0u;
    int32_t result;
    if (!phy || !args || !output || ((uintptr_t)phy & 3u) || ((uintptr_t)output & 3u) ||
        (uintptr_t)output > UINTPTR_MAX - PROGRESS_CAPACITY || capacity != PROGRESS_CAPACITY)
        return -24;
    if (work.busy) return -16;
    /* Never -23: UNSUPPORTED would invite dispatcher fallback. */
    if (work.captures >= PROGRESS_CAPTURES || !profile(args)) return -2;
    chanspec = half((const unsigned char *)phy + 0x10a);
    if (chanspec != 0x1001u) return -2;
    sh = *(unsigned char **)((unsigned char *)phy + 0x38);
    if (!sh || ((uintptr_t)sh & 3u)) return -24;
    indirect = *(unsigned char ***)(sh + 0x10);
    if (!indirect || ((uintptr_t)indirect & 3u)) return -24;
    hw = *indirect;
    if (!hw || ((uintptr_t)hw & 3u)) return -24;
    work.pointer_regs = *(volatile unsigned char **)((unsigned char *)phy + 0xfc);
    work.timer_regs = *(volatile unsigned char **)(hw + 0x88);
    if (!work.pointer_regs || !work.timer_regs || ((uintptr_t)work.pointer_regs & 3u) ||
        ((uintptr_t)work.timer_regs & 3u)) return -24;
    /* Separate reviewed pointer chains must identify the same D11 block. */
    if (work.pointer_regs != work.timer_regs) return -2;
    if(!deadman_initialize() || !lease_initialize())return -2;
    for (i = 0; i < sizeof(*r); i++) ((unsigned char *)r)[i] = 0;
    for (i=0;i<sizeof(context);i++) ((unsigned char *)&context)[i]=0;
    context.magic=RING_CONTEXT_MAGIC;context.version=PROGRESS_VERSION;context.bytes=sizeof(context);
    context.sequence=work.captures+1u;
    sampler_initialize(context.sequence);
    r->magic = PROGRESS_MAGIC; r->version = PROGRESS_VERSION; r->bytes = sizeof(*r);
    r->sequence = ++work.captures; r->pre_us = word(args + 20); r->post_us = word(args + 24);
    r->expected_words = (r->pre_us + r->post_us) * 20u; r->chanspec = chanspec;
    work.phy = phy; work.args = args; work.busy = 1u;
    r->entry_cycle = progress_cycle();
    result = fw_original_collect(phy, args, output);
    observe(PROGRESS_STOP,0u);observe(PROGRESS_STOP_AGAIN,0u);
    private_fields(&context.after_private_start);
    sampler_finish(result);
    r->exit_cycle = progress_cycle(); r->vendor_result = (uint32_t)result;
    r->status = result == 0 ? PROGRESS_RETURNED : PROGRESS_VENDOR_ERROR;
    for (i = 0; i < r->observations; i++) phase_mask |= 1u << r->samples[i].phase;
    if ((phase_mask & 51u) != 51u) r->flags |= PROGRESS_INCOMPLETE;
    /* Do not read MMIO after vendor cleanup. Export into checked padding.
     * Missing transport-tail magic must stop the future pilot immediately. */
    for (i = 0; i < sizeof(*r); i++) ((unsigned char *)output)[PROGRESS_TRAILER + i] = ((unsigned char *)r)[i];
    for (i=0;i<sizeof(context);i++) ((unsigned char *)output)[RING_CONTEXT_TRAILER+i]=((unsigned char *)&context)[i];
    for (i=0;i<128u;i++) ((unsigned char *)output)[7488u+i]=((unsigned char *)&samples)[i];
    for(i=0;i<64u;i++)((unsigned char *)output)[7424u+i]=((unsigned char *)&deadman)[i];
    if(!lease.expired && samples.stop_observed==1u)lease.status=2u;
    for(i=0;i<64u;i++)((unsigned char *)output)[7616u+i]=((unsigned char *)&lease)[i];
    work.busy = 0u;
    /* Transport success delivers diagnostic records even after vendor error.
     * Host must inspect vendor_result/status/control, never infer capture success. */
    return 0;
}
