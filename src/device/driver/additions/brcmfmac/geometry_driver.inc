static int pi5_iq_geometry_prearm(struct brcmf_sdio *bus)
{
 static const u32 addresses[10]={0x1ebe98,0x1ebe9c,0x1ee17c,0x1ee194,
  0x1986c8,0x1986c4,0x198708,0x1ee188,0x1986ec,0x1eef68};
 struct pi5_iq_geometry *g=&bus->pi5_iq_geometry;u32 i;int err=0;
 /* Caller already owns SDIO host and exact fingerprint/idle-work admission.
  * No geometry getter ever reads RAM; only this single prearm routine does. */
 g->h[0]=0x47454f31;g->h[1]=1;g->h[2]=sizeof(*g);g->h[5]=10;
 for(i=0;i<10;i++){
  err=brcmf_sdiod_ramrw(bus->sdiodev,false,addresses[i],(u8 *)&g->words[i],4);
  if(err)break;
 }
 g->h[4]=(u32)err;smp_store_release(&g->h[3],err?2u:1u);return err;
}
static int pi5_iq_geometry_show(struct seq_file *seq,void *unused)
{
 struct brcmf_bus *bi=dev_get_drvdata(seq->private);struct brcmf_sdio *bus;
 struct pi5_iq_geometry copy={};
 if(!capable(CAP_SYS_RAWIO))return -EPERM;
 if(!bi || !bi->drvr || !bi->bus_priv.sdio)return -ENODEV;
 bus=bi->bus_priv.sdio->bus;
 if(smp_load_acquire(&bus->pi5_iq_geometry.h[3]))memcpy(&copy,&bus->pi5_iq_geometry,sizeof(copy));
 else {copy.h[0]=0x47454f31;copy.h[1]=1;copy.h[2]=sizeof(copy);copy.h[5]=10;}
 seq_write(seq,&copy,sizeof(copy));return 0;
}
static int pi5_iq_geometry_open(struct inode *inode,struct file *file)
{return single_open_size(file,pi5_iq_geometry_show,inode->i_private,128);}
static const struct file_operations pi5_iq_geometry_fops={.owner=THIS_MODULE,
 .open=pi5_iq_geometry_open,.read=seq_read,.llseek=seq_lseek,.release=single_release};
