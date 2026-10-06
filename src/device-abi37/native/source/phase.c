/* Fresh geometry rebuild of reviewed V26 logic; source changes are explicit.
 * Native paired PHY programming occurs only outside the active delay loop.
 * Restore after original target returns: sampler_finish must read/reference
 * the same modified producer epoch before its complete native pair is reset. */
#include "phase.h"
#include "core/progress.h"

struct old_workspace_head {
 uint32_t busy,captures;void *phy;const unsigned char *args;
 volatile unsigned char *pointer_regs,*timer_regs;struct progress_record record;
};
_Static_assert(offsetof(struct old_workspace_head,record)==24u,"original workspace head");
_Static_assert(offsetof(struct old_workspace_head,record.flags)==72u,"original fatal flags");
extern volatile struct old_workspace_head work;
extern volatile uint32_t lease[];
#define ORIGINAL (&work)
struct phase_context {uint32_t busy,touched;struct sparse_phase_record record;};
__attribute__((section(".sparse_phase_workspace")))
static struct phase_context state={0};

extern uint32_t fw_sparse_phy_read(void *,uint32_t);
extern void fw_sparse_phy_write(void *,uint32_t,uint32_t);
extern int32_t fw_old_target(void *,const unsigned char *,void *,uint32_t);
extern uint32_t fw_old_matches(void *,const unsigned char *);

static uint16_t half(const unsigned char *p)
{return (uint16_t)p[0]|((uint16_t)p[1]<<8);}
static uint32_t word(const unsigned char *p)
{return (uint32_t)p[0]|((uint32_t)p[1]<<8)|((uint32_t)p[2]<<16)|((uint32_t)p[3]<<24);}
static int pointer(const void *p,uint32_t end)
{return p && !((uintptr_t)p&3u) && (uintptr_t)p<=UINTPTR_MAX-end;}
static int arguments(const unsigned char *a)
{
 uint32_t i;
 if(!a || (uintptr_t)a>UINTPTR_MAX-48u)return 0;
 if(half(a+8)!=2u || half(a+10)!=48u || a[12]!=1u || half(a+14)!=2u ||
    half(a+16)!=17u || word(a+20)!=400u || word(a+24)!=400u)return 0;
 for(i=0;i<48u;i++){
  if((i>=8u&&i<13u)||(i>=14u&&i<18u)||(i>=20u&&i<28u))continue;
  if(a[i])return 0;
 }
 return 1;
}
static int context(void *phy)
{
 unsigned char *sh,*hw;unsigned char **indirect;volatile unsigned char *regs;
 if(!pointer(phy,0x144u) || half((unsigned char *)phy+0x10a)!=0x1001u)return 0;
 sh=*(unsigned char **)((unsigned char *)phy+0x38);
 if(!pointer(sh,0x14u))return 0;
 indirect=*(unsigned char ***)(sh+0x10);
 if(!pointer(indirect,4u))return 0;
 hw=*indirect;if(!pointer(hw,0x8cu))return 0;
 regs=*(volatile unsigned char **)((unsigned char *)phy+0xfc);
 return pointer((const void *)regs,0xb30u) &&
   regs==*(volatile unsigned char **)(hw+0x88);
}
static uint32_t native_word(uint32_t address)
{return *(volatile uint32_t *)(uintptr_t)address;}
static int native_admission(void)
{
 uint32_t handle;
 /* Duplicate only the exact original lease/deadman read predicates before
  * pair mutation. The original target still owns their initialization. */
 if(native_word((uint32_t)(uintptr_t)lease+12u)!=1u || native_word(0x19876cu)!=481500000u ||
    !native_word(0x198768u))return 0;
 handle=native_word(0x198718u);
 if((handle&3u) || handle<0x198000u || handle>0x25ff00u ||
    native_word(0x198324u)!=0x19a745u)return 0;
 return native_word(handle+0x88u)!=0u;
}
static uint32_t pair_read(void *phy)
{
 uint32_t low=fw_sparse_phy_read(phy,0x1a6u);
 return low|(fw_sparse_phy_read(phy,0x1a7u)<<16);
}
static void pair_write(void *phy,uint32_t pair)
{
 /* Same low-then-high native helper order as the reviewed finite1.5 pilot.
  * Full high word includes the preserved upper sparse bits. Native subsequent
  * readback clears cache140; no direct selector/cache restoration is added. */
 fw_sparse_phy_write(phy,0x1a6u,pair&0xffffu);
 fw_sparse_phy_write(phy,0x1a7u,pair>>16);
}
static void restore(void *phy)
{
 pair_write(phy,state.record.baseline);
 state.record.restored=pair_read(phy);
 if(state.record.restored!=state.record.baseline)state.record.flags|=8u;
 state.touched=0u;
}
uint32_t sparse_rate_matches(void *phy,const unsigned char *args)
{
 uint32_t matched=fw_old_matches(phy,args);
 if(matched){
  if(!state.busy || !state.touched || state.record.sequence!=ORIGINAL->captures){
   state.record.flags|=16u;ORIGINAL->record.flags|=PROGRESS_UNSTABLE;
  }else{
   state.record.at_arm=pair_read(phy);
   if(state.record.at_arm!=state.record.requested){
    state.record.flags|=16u;ORIGINAL->record.flags|=PROGRESS_UNSTABLE;
   }
  }
 }
 return matched; /* Preserve the original predicate; no invented false edge. */
}
int32_t sparse_collect_checked(void *phy,const unsigned char *args,void *output,uint32_t capacity)
{
 struct sparse_phase_record *r=&state.record;uint32_t i;int32_t result;
 if(!pointer(output,8192u) || capacity!=8192u || !arguments(args))return -24;
 if(state.busy || ORIGINAL->busy)return -16;
 if(ORIGINAL->captures>=1u)return -2;
 if(!context(phy))return -24;
 if(!native_admission())return -2;
 for(i=0;i<sizeof(*r);i++)((unsigned char *)r)[i]=0;
 r->magic=SPARSE_PHASE_MAGIC;r->version=1u;r->bytes=sizeof(*r);r->sequence=ORIGINAL->captures+1u;
 r->status=1u;r->phy_register=0x1a6u;r->mask=UINT32_C(0x03ffffff);
 r->requested=SPARSE_PHASE_REQUESTED;r->vendor_result=UINT32_MAX;
 state.busy=1u;state.touched=0u;
 r->baseline=pair_read(phy);
 if(r->baseline!=SPARSE_PHASE_ORDINARY){r->flags|=1u;result=-2;goto done;}
 state.touched=1u;pair_write(phy,r->requested);r->applied=pair_read(phy);
 if(r->applied!=r->requested){r->flags|=2u;result=-2;goto done;}
 result=fw_old_target(phy,args,output,capacity);
 /* The original function has now finished its stopped latest128 comparison
  * and copied the unchanged descriptor/progress/lease/watchdog into output. */
 r->after_finish=pair_read(phy);
 if(r->after_finish!=r->requested)r->flags|=4u;
 if(ORIGINAL->record.magic==PROGRESS_MAGIC && ORIGINAL->record.sequence==r->sequence)
  r->vendor_result=ORIGINAL->record.vendor_result;
 else r->flags|=32u;
 if(result)r->flags|=32u;
done:
 if(state.touched)restore(phy);
 r->outer_result=(uint32_t)result;r->status=r->flags?3u:2u;
 for(i=0;i<sizeof(*r);i++)((unsigned char *)output)[SPARSE_PHASE_OFFSET+i]=((unsigned char *)r)[i];
 state.busy=0u;
 return result; /* Preserve original API/transport return; host inspects phase. */
}
