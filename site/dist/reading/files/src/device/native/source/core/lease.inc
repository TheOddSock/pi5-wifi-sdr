/* One fixed uncached owned-RAM heartbeat, prearmed by the exact driver.
 * Firmware never writes heartbeat after host token1 is admitted. */
struct lease_record {
 uint32_t magic,version,bytes;volatile uint32_t heartbeat;
 uint32_t seen,renewals,expiry_ticks,last_cycle,expired,status;
 uint32_t age_ticks,max_gap_ticks,flags,word_wraps,initial_token,reserved;
};
_Static_assert(sizeof(struct lease_record)==64,"Lease ABI");
__attribute__((section(".reader_workspace"))) struct lease_record lease={0};
static int lease_initialize(void)
{
 uint32_t i,token=lease.heartbeat;if(token!=1u)return 0;
 for(i=0;i<sizeof(lease);i++)if(i<12u || i>=16u)((unsigned char *)&lease)[i]=0;
 lease.magic=UINT32_C(0x4c454153);lease.version=PROGRESS_VERSION;lease.bytes=64;
 lease.seen=lease.initial_token=token;lease.expiry_ticks=deadman.configured/2u;
 lease.last_cycle=progress_cycle();lease.status=1u;publish_barrier();return 1;
}
static int lease_check(void)
{
 uint32_t now=progress_cycle(),token=lease.heartbeat,age=now-lease.last_cycle;
 if(lease.expired)return 1;
 if(age>lease.expiry_ticks){lease.expired=1u;lease.status=3u;lease.age_ticks=age;return 1;}
 if(token!=lease.seen){
  uint32_t expected=lease.seen==UINT32_MAX?1u:lease.seen+1u;
  if(token!=expected){lease.flags|=1u;return 0;}
  if(age>lease.max_gap_ticks)lease.max_gap_ticks=age;
  lease.seen=token;lease.renewals++;lease.last_cycle=now;age=0;
 }
 lease.age_ticks=age;
 return 1;
}
