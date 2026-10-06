/* Published once after the failed read releases the SDIO host/window. The
 * sole reader/file mutex and one-open quota prevent a second writer. */
static void pi5_iq_note_failure(struct brcmf_sdio *bus,struct pi5_iq_file *r,
                               int error,u32 tries,int restore)
{
 struct pi5_iq_failure *d=&bus->pi5_iq_failure;u32 i;
 if(smp_load_acquire(&d->h[3]))return;
 d->h[0]=0x49514431;d->h[1]=1;d->h[2]=sizeof(*d);d->h[4]=(u32)error;
 d->h[5]=r->diag_reason;d->h[6]=r->diag_stage;d->h[7]=r->done;
 d->h[8]=r->diag_want;d->h[9]=r->diag_published;d->h[10]=r->diag_slot;
 d->h[11]=r->polls;d->h[12]=tries;d->h[13]=r->offset;
 d->h[14]=r->diag_payload_copies;d->h[15]=(u32)restore;
 for(i=0;i<10;i++)d->times[i]=r->diag_times[i];
 d->times[10]=ktime_get_ns();d->times[11]=r->last_frame_start_ns;
 d->times[12]=r->last_frame_end_ns;
 for(i=1;i<10;i++)d->times[12+i]=r->last_times[i];
 d->times[22]=r->last_return_ns;d->times[23]=r->start_ns;
 d->times[24]=r->diag_times[10];d->times[25]=r->diag_times[11];
 d->times[26]=r->last_times[10];d->times[27]=r->last_times[11];
 smp_store_release(&d->h[3],1u);
}
static int pi5_iq_diagnostic_show(struct seq_file *seq,void *unused)
{
 struct brcmf_bus *bi=dev_get_drvdata(seq->private);struct brcmf_sdio *bus;
 struct pi5_iq_failure copy={};
 if(!capable(CAP_SYS_RAWIO))return -EPERM;
 if(!bi || !bi->drvr || !bi->bus_priv.sdio)return -ENODEV;
 bus=bi->bus_priv.sdio->bus;
 /* Acquire protects the immutable record; reading never claims SDIO host. */
 if(smp_load_acquire(&bus->pi5_iq_failure.h[3]))
  memcpy(&copy,&bus->pi5_iq_failure,sizeof(copy));
 else {copy.h[0]=0x49514431;copy.h[1]=1;copy.h[2]=sizeof(copy);}
 seq_write(seq,&copy,sizeof(copy));return 0;
}
static int pi5_iq_diagnostic_open(struct inode *inode,struct file *file)
{return single_open_size(file,pi5_iq_diagnostic_show,inode->i_private,512);}
static const struct file_operations pi5_iq_diagnostic_fops={.owner=THIS_MODULE,
 .open=pi5_iq_diagnostic_open,.read=seq_read,.llseek=seq_lseek,.release=single_release};
