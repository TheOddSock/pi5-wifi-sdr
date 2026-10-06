/* Privileged fixed collect/readback outside nl80211/wiphy/RTNL dispatch.
 * A real synchronous BCDC reply, never an early/fabricated firmware ACK.
 * File/module pins plus SDIO verification and single-radio controller gates. */
#include "fwil.h"
struct pi5_private_reply {u32 h[16];u64 start_ns,end_ns;u8 raw[8192];};
static_assert(sizeof(struct pi5_private_reply)==8272);
static int pi5_private_collect_show(struct seq_file *seq,void *unused)
{
 struct brcmf_bus *bi=dev_get_drvdata(seq->private);struct brcmf_sdio *bus;struct brcmf_sdio_dev *sd;
 struct brcmf_if *ifp;struct pi5_private_reply *r;__le32 w[2],l[16];u8 text[32];u32 window;int err,restore;
 static const u8 profile[48]={ [8]=2,[10]=48,[12]=1,[14]=2,[16]=17,[20]=0x90,[21]=1,[24]=0x90,[25]=1 };
 if(!capable(CAP_SYS_RAWIO))return -EPERM;
 if(!bi || !bi->drvr || !bi->bus_priv.sdio)return -ENODEV;
 bus=bi->bus_priv.sdio->bus;sd=bus->sdiodev;ifp=bi->drvr->iflist[0];
 if(!ifp || ifp->ifidx || bus->ci->chip!=BRCM_CC_4345_CHIP_ID || bus->ci->chiprev!=6)return -ENODEV;
 r=kzalloc(sizeof(*r),GFP_KERNEL);if(!r)return -ENOMEM;
 sdio_claim_host(sd->func1);window=sd->sbwad;
 if(bus->pi5_private_attempts++ || !READ_ONCE(bus->pi5_iq_verified) || READ_ONCE(bus->pi5_long_wait)){err=-EACCES;goto checked;}
 if(sd->state!=BRCMF_SDIOD_DATA){err=-EHOSTDOWN;goto checked;}
 err=brcmf_sdio_bus_sleep(bus,false,false);if(err || bus->clkstate!=CLK_AVAIL){err=err?err:-EHOSTDOWN;goto checked;}
 err=brcmf_sdiod_ramrw(sd,false,PI5_OWNED_TEXT,text,32);if(err)goto checked;
 if(memcmp(text,pi5_owned_fingerprint,32)){err=-ESTALE;goto checked;}
 err=brcmf_sdiod_ramrw(sd,false,PI5_OWNED_WORK,(u8 *)w,8);if(err)goto checked;
 err=brcmf_sdiod_ramrw(sd,false,PI5_LEASE,(u8 *)l,64);if(err)goto checked;
 if(w[0] || w[1] || le32_to_cpu(l[3])!=1 || l[0] || l[1] || l[2] || l[8])err=-EPROTO;
checked:
 restore=brcmf_sdiod_pi5_owned_restore_window(sd,window);sdio_release_host(sd->func1);
 if(restore && !err)err=restore;
 if(!err){
  err=brcmf_pi5_private_start(bi->drvr);
  if(!err){
   memcpy(r->raw,"sample_collect",15);memcpy(r->raw+15,profile,48);r->start_ns=ktime_get_ns();
   err=brcmf_fil_cmd_data_get(ifp,262,r->raw,8192);r->end_ns=ktime_get_ns();
   brcmf_pi5_private_end(bi->drvr);
  }
 }
 r->h[0]=0x50524956;r->h[1]=PI5_STREAM_ABI_VERSION;r->h[2]=sizeof(*r);r->h[3]=bus->pi5_private_attempts;
 r->h[4]=(u32)err;r->h[5]=bus->pi5_request_matches;r->h[6]=brcmf_pi5_private_refusals();r->h[7]=(u32)restore;
 r->h[8]=262;r->h[9]=8192;r->h[10]=ifp->ifidx;
 seq_write(seq,r,sizeof(*r));kfree(r);return 0;
}
static int pi5_private_collect_open(struct inode *inode,struct file *file)
{return single_open_size(file,pi5_private_collect_show,inode->i_private,16384);}
static const struct file_operations pi5_private_collect_fops={.owner=THIS_MODULE,.open=pi5_private_collect_open,.read=seq_read,.llseek=seq_lseek,.release=single_release};
