/* release-only single fixed store into our initialized, uncached stop word.
 * No caller address/value/count, radio register or sample-memory write. */
static int pi5_iq_request_stop(struct brcmf_sdio *bus)
{
    struct brcmf_sdio_dev *sd=bus->sdiodev;__le32 h[32],work[2],value=cpu_to_le32(0x53544f50);u8 text[32];int err;
    if(sd->state!=BRCMF_SDIOD_DATA)return -EHOSTDOWN;
    err=brcmf_sdio_bus_sleep(bus,false,false);if(err || bus->clkstate!=CLK_AVAIL)return err?err:-EHOSTDOWN;
    err=brcmf_sdiod_ramrw(sd,false,PI5_OWNED_TEXT,text,32);if(err)return err;
    if(memcmp(text,pi5_owned_fingerprint,32))return -ESTALE;
    err=brcmf_sdiod_ramrw(sd,false,PI5_OWNED_WORK,(u8 *)work,8);if(err)return err;
    err=brcmf_sdiod_ramrw(sd,false,PI5_OWNED_RECORD,(u8 *)h,128);if(err)return err;
    if(le32_to_cpu(h[0])!=0x5354524d || le32_to_cpu(h[1])!=PI5_STREAM_ABI_VERSION || le32_to_cpu(h[2])!=PI5_STREAM_RECORD_BYTES
       || le32_to_cpu(h[3])!=1 || le32_to_cpu(h[5]) || (le32_to_cpu(h[24])&4) || le32_to_cpu(work[1])!=1)return -EPROTO;
    if(le32_to_cpu(h[4])==2 && !le32_to_cpu(work[0])){bus->pi5_stop_already=1;return 0;}
    if(le32_to_cpu(h[4]) || le32_to_cpu(work[0])!=1 || le32_to_cpu(h[22]) || le32_to_cpu(h[29]))return -EPROTO;
    bus->pi5_stop_ns=ktime_get_ns();
    err=brcmf_sdiod_ramrw(sd,true,PI5_OWNED_RECORD+116,(u8 *)&value,4);if(err)return err;
    err=brcmf_sdiod_ramrw(sd,false,PI5_OWNED_RECORD+116,(u8 *)&value,4);if(err)return err;
    return le32_to_cpu(value)==0x53544f50?0:-EUCLEAN;
}
struct pi5_stop_summary {u32 h[16];u64 stop_ns,observed_ns;__le32 header[32],reference[128],tail[128];};
static_assert(sizeof(struct pi5_stop_summary)==1232);
static int pi5_stop_summary_show(struct seq_file *seq,void *unused)
{
    struct brcmf_bus *bi=dev_get_drvdata(seq->private);struct brcmf_sdio *bus;struct brcmf_sdio_dev *sd;
    struct pi5_stop_summary *r;__le32 work[2];u32 window,blocks;int err,restore;
    if(!capable(CAP_SYS_RAWIO))return -EPERM;
    if(!bi || !bi->drvr || !bi->bus_priv.sdio)return -ENODEV;
    bus=bi->bus_priv.sdio->bus;sd=bus->sdiodev;r=kzalloc(sizeof(*r),GFP_KERNEL);if(!r)return -ENOMEM;
    sdio_claim_host(sd->func1);window=sd->sbwad;
    if(bus->pi5_stop_summary_used++){err=-EACCES;goto done;}
    if(sd->state!=BRCMF_SDIOD_DATA){err=-EHOSTDOWN;goto done;}
    err=brcmf_sdio_bus_sleep(bus,false,false);if(err || bus->clkstate!=CLK_AVAIL){err=err?err:-EHOSTDOWN;goto done;}
    err=brcmf_sdiod_ramrw(sd,false,PI5_OWNED_WORK,(u8 *)work,8);if(err)goto done;
    err=brcmf_sdiod_ramrw(sd,false,PI5_OWNED_RECORD,(u8 *)r->header,128);if(err)goto done;
    blocks=le32_to_cpu(r->header[23]);
    if(le32_to_cpu(work[0]) || le32_to_cpu(work[1])!=1 || le32_to_cpu(r->header[1])!=PI5_STREAM_ABI_VERSION
       || le32_to_cpu(r->header[4])!=2 || le32_to_cpu(r->header[5]) || !blocks || blocks>=U32_MAX-1
       || le32_to_cpu(r->header[6])!=blocks*1024 || le32_to_cpu(r->header[19])!=128 || le32_to_cpu(r->header[20])
       || le32_to_cpu(r->header[21]) || le32_to_cpu(r->header[22])!=1 || (le32_to_cpu(r->header[30])==1 ? le32_to_cpu(r->header[29])!=0x53544f50 : le32_to_cpu(r->header[30])!=2 || le32_to_cpu(r->header[29]))){err=-EPROTO;goto done;}
    err=brcmf_sdiod_ramrw(sd,false,PI5_STREAM_REFERENCE,(u8 *)r->reference,512);if(err)goto done;
    err=brcmf_sdiod_ramrw(sd,false,PI5_STREAM_SLOTS+((blocks-1)%PI5_STREAM_SLOT_COUNT)*4128+32+896*4,(u8 *)r->tail,512);if(err)goto done;
    if(memcmp(r->reference,r->tail,512)){err=-EBADMSG;goto done;}
    r->h[8]=le32_to_cpu(work[0]);r->h[9]=le32_to_cpu(work[1]);
done:
    restore=brcmf_sdiod_pi5_owned_restore_window(sd,window);sdio_release_host(sd->func1);
    r->h[0]=0x53544f50;r->h[1]=1;r->h[2]=sizeof(*r);r->h[3]=bus->pi5_stop_attempts;
    r->h[4]=(u32)bus->pi5_stop_error;r->h[5]=bus->pi5_stop_already;r->h[6]=(u32)err;r->h[7]=(u32)restore;
    r->h[10]=bus->pi5_wait_used;r->h[11]=bus->pi5_wait_ms;r->h[12]=bus->pi5_request_matches;
    r->h[13]=bus->pi5_lease_renewals;r->h[14]=(u32)bus->pi5_lease_error;r->h[15]=bus->pi5_lease_withheld;
    r->stop_ns=bus->pi5_stop_ns;r->observed_ns=ktime_get_ns();seq_write(seq,r,sizeof(*r));kfree(r);return 0;
}
static int pi5_stop_summary_open(struct inode *inode,struct file *file)
{return single_open_size(file,pi5_stop_summary_show,inode->i_private,2048);}
static const struct file_operations pi5_stop_summary_fops={.owner=THIS_MODULE,.open=pi5_stop_summary_open,.read=seq_read,.llseek=seq_lseek,.release=single_release};
