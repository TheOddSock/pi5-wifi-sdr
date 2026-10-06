/* Only fixed owned heartbeat word is written; exact image/work/cache gates.
 * Called with SDIO host held. Firmware preserves and reads this host word. */
static int pi5_iq_lease_prearm(struct brcmf_sdio *bus)
{
 struct brcmf_sdio_dev *sd=bus->sdiodev;__le32 l[16],v=cpu_to_le32(1);unsigned i;int err;
 err=brcmf_sdiod_ramrw(sd,false,PI5_LEASE,(u8 *)l,64);if(err)return err;
 for(i=0;i<16;i++)if(l[i])return -ESTALE;
 err=brcmf_sdiod_ramrw(sd,true,PI5_LEASE+12,(u8 *)&v,4);if(err)return err;
 err=brcmf_sdiod_ramrw(sd,false,PI5_LEASE+12,(u8 *)&v,4);if(err)return err;
 if(le32_to_cpu(v)!=1)return -EUCLEAN;
 bus->pi5_lease_token=1;WRITE_ONCE(bus->pi5_lease_ns,ktime_get_ns());return 0;
}
static int pi5_iq_lease_renew(struct brcmf_sdio *bus)
{
 struct brcmf_sdio_dev *sd=bus->sdiodev;__le32 l[16],w[2],h[32],v;u32 token;int err;
 if(bus->pi5_lease_withheld)return 0;
 err=brcmf_sdiod_ramrw(sd,false,PI5_OWNED_WORK,(u8 *)w,8);if(err)return err;
 err=brcmf_sdiod_ramrw(sd,false,PI5_OWNED_RECORD,(u8 *)h,128);if(err)return err;
 if(le32_to_cpu(w[0])!=1 || le32_to_cpu(w[1])!=1 || le32_to_cpu(h[1])!=PI5_STREAM_ABI_VERSION ||
    le32_to_cpu(h[4]) || le32_to_cpu(h[5]) || (le32_to_cpu(h[24])&4))return -EPROTO;
 err=brcmf_sdiod_ramrw(sd,false,PI5_LEASE,(u8 *)l,64);if(err)return err;
 if(le32_to_cpu(l[0])!=0x4c454153 || le32_to_cpu(l[1])!=PI5_STREAM_ABI_VERSION || le32_to_cpu(l[2])!=64 ||
    le32_to_cpu(l[3])!=bus->pi5_lease_token || le32_to_cpu(l[6])!=240750000 ||
    le32_to_cpu(l[8]) || le32_to_cpu(l[9])!=1 || le32_to_cpu(l[12]))return -EPROTO;
 token=bus->pi5_lease_token==U32_MAX?1:bus->pi5_lease_token+1;v=cpu_to_le32(token);
 err=brcmf_sdiod_ramrw(sd,true,PI5_LEASE+12,(u8 *)&v,4);if(err)return err;
 err=brcmf_sdiod_ramrw(sd,false,PI5_LEASE+12,(u8 *)&v,4);if(err)return err;
 if(le32_to_cpu(v)!=token)return -EUCLEAN;
 bus->pi5_lease_token=token;bus->pi5_lease_renewals++;WRITE_ONCE(bus->pi5_lease_ns,ktime_get_ns());return 0;
}
/* Fixed privileged test: withhold renewal while continuing every sample read.
 * No firmware/MMIO store. Once per module load; actual expiry still ARM-owned. */
static int pi5_iq_withhold_show(struct seq_file *seq,void *unused)
{
 struct brcmf_bus *bi=dev_get_drvdata(seq->private);struct brcmf_sdio *bus;u32 result[8];
 if(!capable(CAP_SYS_RAWIO))return -EPERM;
 if(!bi || !bi->drvr || !bi->bus_priv.sdio)return -ENODEV;
 bus=bi->bus_priv.sdio->bus;sdio_claim_host(bus->sdiodev->func1);
 if(bus->pi5_withhold_used++ || !READ_ONCE(bus->pi5_iq_verified) || !READ_ONCE(bus->pi5_long_wait) ||
    bus->pi5_lease_renewals<1){sdio_release_host(bus->sdiodev->func1);return -EACCES;}
 WRITE_ONCE(bus->pi5_lease_withheld,true);
 result[0]=0x57495448;result[1]=PI5_STREAM_ABI_VERSION;result[2]=32;result[3]=bus->pi5_lease_token;
 result[4]=bus->pi5_lease_renewals;result[5]=1;result[6]=0;result[7]=0;
 sdio_release_host(bus->sdiodev->func1);seq_write(seq,result,sizeof(result));return 0;
}
static int pi5_iq_withhold_open(struct inode *inode,struct file *file)
{return single_open_size(file,pi5_iq_withhold_show,inode->i_private,128);}
static const struct file_operations pi5_iq_withhold_fops={.owner=THIS_MODULE,.open=pi5_iq_withhold_open,.read=seq_read,.llseek=seq_lseek,.release=single_release};
