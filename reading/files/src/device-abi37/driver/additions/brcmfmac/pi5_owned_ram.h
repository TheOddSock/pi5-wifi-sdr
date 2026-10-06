/* ELF-bound enlarged-ring reader-renewed incremental I/Q frames. One1024-word payload
 * buffer, sequence-bracketed single payload read and explicitly admitted firmware slots.
 * Fixed heartbeat and close STOP stores; no sample/radio writes or proto mutex. Each read returns a completed frame
 * immediately; root/module/file mutex plus SDIO host protect lifecycle/I/O. */
#include <linux/capability.h>
#include <linux/ktime.h>
#include <linux/delay.h>
#include <linux/uaccess.h>
#include "pi5_owned_contract.h"
struct pi5_iq_frame {u32 h[8];u64 start_ns,end_ns;__le32 meta[8],words[1024];};
static_assert(sizeof(struct pi5_iq_frame)==4176);
struct pi5_iq_file {
    struct device *dev;struct mutex lock;
    struct pi5_iq_frame frame;__le32 second[1024],tail[128];
    u32 done,polls,offset,backlog,live;bool final_ready,failed;
    u64 start_ns;
    u32 diag_reason,diag_stage,diag_want,diag_published,diag_slot,diag_payload_copies;
    u64 diag_times[12],last_times[12],last_frame_start_ns,last_frame_end_ns,last_return_ns;
};
#include "lease_driver.inc"
#include "diagnostic_driver.inc"
#include "geometry_driver.inc"
static u32 pi5_iq_hash(const __le32 *p)
{u32 i,h=2166136261;for(i=0;i<1024;i++)h=(h^le32_to_cpu(p[i]))*16777619u;return h;}
static int pi5_iq_poll(struct brcmf_sdio *bus,struct pi5_iq_file *r)
{
    struct brcmf_sdio_dev *sd=bus->sdiodev;__le32 header[32],after[8],work[2],ref[128];
    u8 text[32];u32 want,published,addr;int err;
    r->diag_stage=1;r->diag_reason=PI5_REASON_IO;r->diag_want=r->done+1;
    r->diag_published=0;r->diag_slot=0;r->diag_payload_copies=0;r->diag_times[3]=ktime_get_ns();
    if(sd->state!=BRCMF_SDIOD_DATA)return -EHOSTDOWN;
    r->diag_stage=2;r->diag_times[10]=ktime_get_ns();err=brcmf_sdio_bus_sleep(bus,false,false);r->diag_times[11]=ktime_get_ns();if(err || bus->clkstate!=CLK_AVAIL)return err?err:-EHOSTDOWN;
    if(!r->polls){r->diag_stage=3;err=brcmf_sdiod_ramrw(sd,false,PI5_OWNED_TEXT,text,32);if(err)return err;if(memcmp(text,pi5_owned_fingerprint,32))return -ESTALE;}
    r->diag_stage=4;err=brcmf_sdiod_ramrw(sd,false,PI5_OWNED_RECORD,(u8 *)header,128);if(err)return err;
    r->diag_published=le32_to_cpu(header[23]);r->diag_stage=5;
    if(!le32_to_cpu(header[3]))return 0;
    if(le32_to_cpu(header[0])!=0x5354524d || le32_to_cpu(header[1])!=PI5_STREAM_ABI_VERSION || le32_to_cpu(header[2])!=PI5_STREAM_RECORD_BYTES
       || le32_to_cpu(header[3])!=1 || le32_to_cpu(header[5]) || le32_to_cpu(header[7])!=16 || (le32_to_cpu(header[24])&4)
       || le32_to_cpu(header[26])!=U32_MAX-1 || le32_to_cpu(header[27])!=1024 || le32_to_cpu(header[28])!=PI5_STREAM_SLOT_COUNT)return -EPROTO;
    want=r->done+1;published=le32_to_cpu(header[23]);
    if(published<r->done){r->diag_reason=PI5_REASON_PUBLISHED_REGRESSED;return -EOVERFLOW;}
    if(published-r->done>PI5_STREAM_SLOT_COUNT){r->diag_reason=PI5_REASON_PUBLISHED_LAG;return -EOVERFLOW;}
    if(le32_to_cpu(header[4])!=0 && le32_to_cpu(header[4])!=2)return -EPROTO;
    if(le32_to_cpu(header[4])==2 && r->done==published){
        r->diag_stage=6;err=brcmf_sdiod_ramrw(sd,false,PI5_OWNED_WORK,(u8 *)work,8);if(err)return err;
        if(le32_to_cpu(header[4])!=2 || le32_to_cpu(work[0]))return 0;
        if(le32_to_cpu(header[6])!=published*1024 || le32_to_cpu(header[19])!=128 || le32_to_cpu(header[20])
           || le32_to_cpu(header[21]) || le32_to_cpu(header[22])!=1 || !published || !le32_to_cpu(header[30]) || le32_to_cpu(header[30])>3)return -EPROTO;
        r->diag_stage=7;err=brcmf_sdiod_ramrw(sd,false,PI5_STREAM_REFERENCE,(u8 *)ref,512);if(err)return err;
        if(memcmp(ref,r->tail,512))return -EBADMSG;
        memset(&r->frame,0,sizeof(r->frame));r->frame.h[3]=2;r->frame.h[4]=published;
        r->frame.start_ns=r->start_ns;r->frame.end_ns=ktime_get_ns();
        memcpy(r->frame.words,header,128);memcpy(r->frame.words+32,ref,512);
        r->frame.words[160]=cpu_to_le32(r->done);r->frame.words[161]=cpu_to_le32(r->polls);
        r->frame.words[162]=cpu_to_le32(r->backlog);r->frame.words[163]=cpu_to_le32(r->live);
        r->final_ready=true;return 2;
    }
    if(published<want)return 0;
    memset(&r->frame,0,sizeof(r->frame));r->frame.start_ns=ktime_get_ns();addr=PI5_STREAM_SLOTS+((want-1)%PI5_STREAM_SLOT_COUNT)*4128;
    r->diag_stage=8;err=brcmf_sdiod_ramrw(sd,false,addr,(u8 *)r->frame.meta,32);if(err)return err;
    r->diag_stage=9;r->diag_slot=le32_to_cpu(r->frame.meta[0]);
    if(le32_to_cpu(r->frame.meta[0])>want){r->diag_reason=PI5_REASON_SLOT_OVERWRITTEN;return -EOVERFLOW;}
    if(le32_to_cpu(r->frame.meta[0])!=want)return 0;
    if(le32_to_cpu(r->frame.meta[1])!=(want-1)*1024 || le32_to_cpu(r->frame.meta[2])!=1024 || le32_to_cpu(r->frame.meta[7]))return -EPROTO;
    r->diag_stage=10;err=brcmf_sdiod_ramrw(sd,false,addr+32,(u8 *)r->frame.words,4096);if(err)return err;
    r->diag_payload_copies=1; /* Metadata seqlock proof replaces second payload transfer. */
    r->diag_stage=12;err=brcmf_sdiod_ramrw(sd,false,addr,(u8 *)after,32);if(err)return err;
    r->diag_stage=13;if(memcmp(r->frame.meta,after,32)){r->diag_reason=PI5_REASON_META_CHANGED;return -EUCLEAN;}
    r->diag_stage=15;if(pi5_iq_hash(r->frame.words)!=le32_to_cpu(after[3])){r->diag_reason=PI5_REASON_HASH;return -EBADMSG;}
    r->frame.end_ns=ktime_get_ns();r->frame.h[3]=1;r->frame.h[4]=want;r->frame.h[5]=(want-1)*1024;r->frame.h[6]=1024;r->frame.h[7]=le32_to_cpu(after[3]);
    r->last_frame_start_ns=r->frame.start_ns;r->last_frame_end_ns=r->frame.end_ns;
    memcpy(r->tail,r->frame.words+896,512);r->done++;
    if(!(r->done%128) && !le32_to_cpu(header[4])){r->diag_stage=16;err=pi5_iq_lease_renew(bus);if(err){bus->pi5_lease_error=err;return err;}}
    if(published-want>r->backlog)r->backlog=published-want;
    if(!le32_to_cpu(header[4]))r->live++;
    return 1;
}
static ssize_t pi5_iq_read(struct file *file,char __user *buf,size_t count,loff_t *pos)
{
    struct pi5_iq_file *r=file->private_data;struct brcmf_bus *bi;struct brcmf_sdio *bus=NULL;
    size_t n;int err,step=0,restore=0;u32 window,tries=0;u64 started;
    if(!count)return 0;
    err=mutex_lock_interruptible(&r->lock);if(err)return err;
    memset(r->diag_times,0,sizeof(r->diag_times));r->diag_times[0]=ktime_get_ns();
    if(r->failed){err=-EIO;goto out;}
    if(r->offset==sizeof(r->frame)){
        if(r->final_ready){err=0;goto out;}
        bi=dev_get_drvdata(r->dev);
        if(!bi || !bi->drvr || !bi->bus_priv.sdio){err=-ENODEV;goto fail;}
        bus=bi->bus_priv.sdio->bus;
        started=ktime_get_ns();
        while(!step && tries<4096 && ktime_get_ns()-started<1000000000ULL){
            r->diag_times[1]=ktime_get_ns();sdio_claim_host(bus->sdiodev->func1);r->diag_times[2]=ktime_get_ns();window=bus->sdiodev->sbwad;
            step=pi5_iq_poll(bus,r);r->diag_times[4]=ktime_get_ns();
            /* Native RAM I/O leaves a valid current window/cache on success.
             * A partial failed window update can invalidate that correspondence,
             * so every negative poll result retains the forced restoration. */
            r->diag_times[5]=0;r->diag_times[6]=0;restore=0;
            if(step<0){
                r->diag_times[5]=ktime_get_ns();restore=brcmf_sdiod_pi5_owned_restore_window(bus->sdiodev,window);r->diag_times[6]=ktime_get_ns();
            }
            sdio_release_host(bus->sdiodev->func1);r->diag_times[7]=ktime_get_ns();r->polls++;tries++;
            if(step<0){err=step;goto fail;}
            if(restore){r->diag_stage=17;err=restore;goto fail;}
            if(!step)usleep_range(50,100);
        }
        if(!step){r->diag_stage=18;err=-ETIMEDOUT;goto fail;}
        r->frame.h[0]=0x49514652;r->frame.h[1]=1;r->frame.h[2]=sizeof(r->frame);r->offset=0;
    }
    n=min(count,sizeof(r->frame)-r->offset);
    r->diag_times[8]=ktime_get_ns();
    if(copy_to_user(buf,(u8 *)&r->frame+r->offset,n)){r->diag_stage=19;err=-EFAULT;goto fail;}
    r->diag_times[9]=ktime_get_ns();
    r->offset+=n;*pos+=n;err=n;memcpy(r->last_times,r->diag_times,sizeof(r->last_times));r->last_return_ns=ktime_get_ns();goto out;
fail:r->failed=true;if(bus)pi5_iq_note_failure(bus,r,err,tries,restore);
out:mutex_unlock(&r->lock);return err;
}
static int pi5_iq_verify_open(struct brcmf_sdio *bus)
{
 struct brcmf_sdio_dev *sd=bus->sdiodev;u8 text[32];__le32 work[2];int err;
 err=brcmf_sdio_bus_sleep(bus,false,false);if(err || bus->clkstate!=CLK_AVAIL)return err?err:-EHOSTDOWN;
 err=brcmf_sdiod_ramrw(sd,false,PI5_OWNED_TEXT,text,32);if(err)return err;
 if(memcmp(text,pi5_owned_fingerprint,32))return -ESTALE;
 err=brcmf_sdiod_ramrw(sd,false,PI5_OWNED_WORK,(u8 *)work,8);if(err)return err;
 if(le32_to_cpu(work[0]) || le32_to_cpu(work[1]))return -EBUSY;
 err=pi5_iq_geometry_prearm(bus);if(err)return err;
 return pi5_iq_lease_prearm(bus);
}
static int pi5_iq_open(struct inode *inode,struct file *file)
{
    struct device *dev=inode->i_private;struct brcmf_bus *bi=dev_get_drvdata(dev);struct brcmf_sdio *bus;struct pi5_iq_file *r;int err,restore;u32 window;
    if(!capable(CAP_SYS_RAWIO))return -EPERM;
    if(!bi || !bi->drvr || !bi->bus_priv.sdio)return -ENODEV;
    bus=bi->bus_priv.sdio->bus;if(bus->ci->chip!=BRCM_CC_4345_CHIP_ID || bus->ci->chiprev!=6)return -ENODEV;
    r=kzalloc(sizeof(*r),GFP_KERNEL);if(!r)return -ENOMEM;
    sdio_claim_host(bus->sdiodev->func1);
    if(bus->pi5_owned_attempts++ || bus->sdiodev->state!=BRCMF_SDIOD_DATA){sdio_release_host(bus->sdiodev->func1);kfree(r);return -EACCES;}
    window=bus->sdiodev->sbwad;err=pi5_iq_verify_open(bus);restore=brcmf_sdiod_pi5_owned_restore_window(bus->sdiodev,window);
    if(!err && !restore)WRITE_ONCE(bus->pi5_iq_verified,true);
    sdio_release_host(bus->sdiodev->func1);
    if(err || restore){kfree(r);return err?err:restore;}
    r->dev=get_device(dev);mutex_init(&r->lock);r->start_ns=ktime_get_ns();r->offset=sizeof(r->frame);file->private_data=r;return nonseekable_open(inode,file);
}
#include "stop_driver.inc"
static int pi5_iq_release(struct inode *inode,struct file *file)
{
    struct pi5_iq_file *r=file->private_data;struct brcmf_bus *bi=dev_get_drvdata(r->dev);struct brcmf_sdio *bus;u32 window;int restore;
    if(bi && bi->drvr && bi->bus_priv.sdio){
        bus=bi->bus_priv.sdio->bus;sdio_claim_host(bus->sdiodev->func1);window=bus->sdiodev->sbwad;
        bus->pi5_stop_attempts++;bus->pi5_stop_error=pi5_iq_request_stop(bus);WRITE_ONCE(bus->pi5_iq_verified,false);
        restore=brcmf_sdiod_pi5_owned_restore_window(bus->sdiodev,window);if(restore)bus->pi5_stop_error=restore;
        sdio_release_host(bus->sdiodev->func1);
    }
    put_device(r->dev);kfree(r);return 0;
}
static const struct file_operations pi5_owned_fops={.owner=THIS_MODULE,.open=pi5_iq_open,.read=pi5_iq_read,.release=pi5_iq_release};
