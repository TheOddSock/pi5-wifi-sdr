/* Experimental single-radio module: enroll EVERY FWIL mutex user before it
 * can queue. Private capture can claim only gate0, so no older waiter exists.
 * The owner issues its one fixed command; every other FWIL call fails EBUSY
 * while capture owns the protocol. Ordinary serialization otherwise unchanged.
 * Static fields avoid changing exported brcmf_pub layout/vendor-module CRCs. */
static atomic_t pi5_proto_gate=ATOMIC_INIT(0),pi5_proto_refused=ATOMIC_INIT(0);
static atomic_t pi5_private_started=ATOMIC_INIT(0);
static struct task_struct *pi5_proto_owner;
static struct brcmf_pub *pi5_proto_device;
static int pi5_proto_admit(struct brcmf_pub *drvr)
{
 int seen;
 for(;;){
  seen=atomic_read_acquire(&pi5_proto_gate);
  if(seen<0){
   if(READ_ONCE(pi5_proto_owner)==current && READ_ONCE(pi5_proto_device)==drvr)return 0;
   atomic_inc(&pi5_proto_refused);return -EBUSY;
  }
  if(seen==INT_MAX)return -EOVERFLOW;
  if(atomic_cmpxchg(&pi5_proto_gate,seen,seen+1)==seen)return 1;
 }
}
int brcmf_pi5_private_start(struct brcmf_pub *drvr)
{
 if(atomic_cmpxchg(&pi5_private_started,0,1)!=0)return -EACCES;
 WRITE_ONCE(pi5_proto_owner,current);WRITE_ONCE(pi5_proto_device,drvr);
 if(atomic_cmpxchg(&pi5_proto_gate,0,INT_MIN)!=0){
  WRITE_ONCE(pi5_proto_owner,NULL);WRITE_ONCE(pi5_proto_device,NULL);return -EBUSY;
 }
 return 0;
}
void brcmf_pi5_private_end(struct brcmf_pub *drvr)
{
 if(READ_ONCE(pi5_proto_owner)!=current || READ_ONCE(pi5_proto_device)!=drvr)return;
 WRITE_ONCE(pi5_proto_owner,NULL);WRITE_ONCE(pi5_proto_device,NULL);atomic_set_release(&pi5_proto_gate,0);
}
int brcmf_pi5_private_refusals(void){return atomic_read(&pi5_proto_refused);}
