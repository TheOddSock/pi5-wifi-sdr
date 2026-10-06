/* Eight reusable1024-word slots in one reader-renewed synchronous capture.
 * Invalidate/ordered commit prevents accepting an in-progress overwrite.
 * No sample-memory writes/ACKs: a slow consumer must detect loss and refuse.
 * Uniform stride16; no anti-alias filtering or calibrated clock claim. */
#include "reader_common.h"
#include "modular.h"
extern void fw_template_set(void *,uint32_t);
#define SAMPLE_MAGIC UINT32_C(0x5354524d)
enum {BAD_SAMPLE_STATE=1u,SAMPLE_LAG=2u,SAMPLE_WRITER=4u,SAMPLE_CLOCK=8u,
      SAMPLE_PORT=16u,SAMPLE_COST=32u,SAMPLE_INCOMPLETE=128u,SAMPLE_TAIL=256u};
struct stream_slot {volatile uint32_t sequence;uint32_t first,count,hash,produced_before,produced_after,copy_ticks,flags;uint32_t words[1024];};
struct sample_record {
    uint32_t magic,version,bytes,sequence,status,flags,count,stride;
    uint32_t first_raw,next_raw,produced,last_pointer,last_cycle,wraps,blocks,max_lag;
    uint32_t copy_ticks,max_copy_ticks,restored,tail_checked,tail_mismatched,vendor_result,cleanup;
    volatile uint32_t published;
    uint32_t sctlr,steps,total_blocks,block_words,slots;volatile uint32_t stop_request;uint32_t stop_observed,reserved;
    struct stream_slot slot[RING_SLOTS];uint32_t reference[128];
};
_Static_assert(sizeof(struct stream_slot)==4128,"reused slot ABI");
_Static_assert(sizeof(struct sample_record)==(640u+4128u*RING_SLOTS),"stream ABI");
__attribute__((section(".reader_workspace"))) struct sample_record samples={0};
static void publish_barrier(void){__asm__ volatile("dmb sy":::"memory");}
static uint32_t read_sctlr(void){uint32_t x;__asm__ volatile("mrc p15,0,%0,c1,c0,0":"=r"(x));return x;}
static void sampler_initialize(uint32_t seq)
{
    uint32_t i;for(i=0;i<sizeof(samples);i++)((unsigned char *)&samples)[i]=0;
    samples.magic=SAMPLE_MAGIC;samples.version=PROGRESS_VERSION;samples.bytes=sizeof(samples);samples.sequence=seq;
    samples.stride=16;samples.first_raw=samples.next_raw=64;samples.last_pointer=0;
    samples.sctlr=read_sctlr();if(samples.sctlr&4u)samples.flags|=BAD_SAMPLE_STATE;samples.total_blocks=UINT32_MAX-1u;samples.block_words=1024;samples.slots=RING_SLOTS;
}
static int sample_admitted(const struct progress_observation *s,uint32_t control)
{
    return s->flags==63u && !s->extent_before && s->start_low==0x8000u && s->stop_low==0xbfffu
      && !(s->pointer_high_after&15u) && s->pointer_low>=0x8000u && s->pointer_low<=0xbfffu
      && s->collect_control_before==control && (s->pmcr_before&1u) && !(s->pmcr_before&40u)
      && (s->enable_before&UINT32_C(0x80000000)) && s->scale_before;
}
extern void sparse_read(uint32_t *,uint32_t,uint32_t);
extern void sparse_read_fnv(uint32_t *,uint32_t,uint32_t);
static void *template_context(void)
{
    unsigned char *sh,*hw;void *indirect;
    sh=*(unsigned char **)((unsigned char *)work.phy+0x38);if(!sh || ((uintptr_t)sh&3u))return 0;
    indirect=*(void **)(sh+0x10);if(!indirect || ((uintptr_t)indirect&3u))return 0;
    hw=*(unsigned char **)indirect;
    if(!hw || ((uintptr_t)hw&3u) || *(volatile unsigned char **)(hw+0x88)!=work.pointer_regs)return 0;
    return indirect;
}
static int advance(const struct progress_observation *s)
{
    uint32_t dt,dw;if(!sample_admitted(s,1)){samples.flags|=BAD_SAMPLE_STATE;return 0;}
    if(!samples.last_pointer){samples.last_cycle=work.record.samples[1].cycle_before;samples.last_pointer=0x8000u;}
    dt=s->cycle_before-samples.last_cycle;dw=(s->pointer_low-samples.last_pointer)&0x3fff;
    if(!dt || dt>32768 || dw>4096){samples.flags|=SAMPLE_WRITER;return 0;}
    if(s->pointer_low<samples.last_pointer)samples.wraps++;
    samples.produced+=dw;samples.last_pointer=s->pointer_low;samples.last_cycle=s->cycle_before;return 1;
}
__attribute__((noinline)) static void consume(const struct progress_observation *before)
{
    struct progress_observation after;struct stream_slot *s;void *indirect;
    uint32_t available,n,port,t0,ticks,lag,first,offset,index;
    if(samples.flags || !advance(before))return;
    if(samples.next_raw!=64+16*samples.count){samples.flags|=BAD_SAMPLE_STATE;return;}
    int admitted=pi5_stream_lag(samples.produced,samples.next_raw,&lag);
    if(!admitted)return;
    if(admitted<0){samples.flags|=SAMPLE_LAG;return;}
    if(lag>samples.max_lag)samples.max_lag=lag;
    available=samples.produced-64-samples.next_raw;n=(available+15)/16;
    if(n<32)return;
    index=samples.published;offset=samples.count%1024;s=&samples.slot[index%RING_SLOTS];
    if(n>128)n=128;
    if(n>1024-offset)n=1024-offset;
    indirect=template_context();if(!indirect){samples.flags|=BAD_SAMPLE_STATE;return;}
    if(!offset){s->sequence=0;publish_barrier();s->first=index*1024;s->count=0;s->hash=0;s->copy_ticks=0;s->flags=0;s->produced_before=samples.produced;}
    first=samples.next_raw;port=reg32(work.pointer_regs,0x130);t0=progress_cycle();
    sparse_read_fnv(s->words+offset,first,n);fw_template_set(indirect,port);ticks=progress_cycle()-t0;snapshot(&after);
    if(!same_clock(before,&after))samples.flags|=SAMPLE_CLOCK;
    if(!advance(&after))return;
    if(samples.produced-first>=16320)samples.flags|=SAMPLE_LAG;
    if(reg32(work.pointer_regs,0x130)!=port)samples.flags|=SAMPLE_PORT;else samples.restored++;
    if(!ticks || ticks>32768)samples.flags|=SAMPLE_COST;
    samples.count+=n;samples.next_raw+=16*n;samples.copy_ticks+=ticks;samples.blocks++;samples.steps=context.delay_steps;
    if(ticks>samples.max_copy_ticks)samples.max_copy_ticks=ticks;
    s->count+=n;s->produced_after=samples.produced;s->copy_ticks+=ticks;
    if(s->count==1024 && !samples.flags){
        /* Incremental hash was completed while sequence remained zero. */
        publish_barrier();s->sequence=index+1;publish_barrier();samples.published=index+1;
    }
}
static void sampler_finish(int32_t result)
{
    struct progress_observation before,after;void *indirect;uint32_t port,i;
    samples.vendor_result=(uint32_t)result;
    if(!samples.published || samples.count%1024u || samples.published*1024u!=samples.count || !samples.stop_observed || context.flags || work.record.flags || !work.record.reserved0 || result)samples.flags|=SAMPLE_INCOMPLETE;
    snapshot(&before);if(!sample_admitted(&before,0))samples.flags|=BAD_SAMPLE_STATE;else samples.cleanup=1;
    if(!samples.flags){
        indirect=template_context();if(!indirect)samples.flags|=BAD_SAMPLE_STATE;
        else{
            port=reg32(work.pointer_regs,0x130);sparse_read(samples.reference,64+16*(samples.count-128),128);fw_template_set(indirect,port);snapshot(&after);
            if(!sample_admitted(&after,0) || before.pointer_low!=after.pointer_low || !same_clock(&before,&after) || reg32(work.pointer_regs,0x130)!=port)samples.flags|=SAMPLE_TAIL;
            for(i=0;i<128;i++){samples.tail_checked++;if(samples.reference[i]!=samples.slot[(samples.published-1u)%RING_SLOTS].words[896+i])samples.tail_mismatched++;}
            if(samples.tail_mismatched)samples.flags|=SAMPLE_TAIL;
        }
    }
    publish_barrier();samples.status=samples.flags?3:2;publish_barrier();
}
int32_t target_export_checked(void *phy,const unsigned char *args,void *output,uint32_t capacity)
{(void)phy;(void)args;(void)output;(void)capacity;return -2;}
