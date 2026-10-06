/* Only called for the exact admitted synchronous capture. Renew short wait
 * while the verified file's successful heartbeat remains fresh. After close
 * or stale renewal allow 2.5s for normal cleanup/reply. No stream-lifetime cap.
 * Other controls retain the original DCMD_RESP_TIMEOUT path verbatim. */
static int pi5_iq_lease_wait(struct brcmf_sdio *bus,uint *condition,bool *pending)
{
 DECLARE_WAITQUEUE(wait,current);u64 grace=0,now;
 int result=0;long chunk=msecs_to_jiffies(250);
 bus->pi5_wait_used=1;bus->pi5_wait_ms=0;
 add_wait_queue(&bus->dcmd_resp_wait,&wait);
 for(;;){
  set_current_state(TASK_INTERRUPTIBLE);
  if(*condition){result=1;break;}
  if(signal_pending(current)){*pending=true;break;}
  now=ktime_get_ns();
  if(READ_ONCE(bus->pi5_iq_verified) && now-READ_ONCE(bus->pi5_lease_ns)<3000000000ULL)grace=0;
  else if(!grace)grace=now;
  else if(now-grace>=2500000000ULL)break;
  schedule_timeout(chunk);
 }
 set_current_state(TASK_RUNNING);remove_wait_queue(&bus->dcmd_resp_wait,&wait);return result;
}
