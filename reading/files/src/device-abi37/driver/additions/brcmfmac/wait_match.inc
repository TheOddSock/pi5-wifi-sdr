/* Exact BCDC GET_VAR request accepted by the fixed capture profile. Stock
 * timeout remains for every other message. Caller cannot select the timeout. */
static bool pi5_iq_wait_match(struct brcmf_sdio *bus,const u8 *msg,uint len)
{
    static const u8 profile[48]={[8]=2,[10]=48,[12]=1,[14]=2,[16]=17,[20]=0x90,[21]=1,[24]=0x90,[25]=1};
    unsigned int i;u32 flags;
    if(!READ_ONCE(bus->pi5_iq_verified) || len!=1518)return false;
    if(get_unaligned_le32(msg)!=262 || get_unaligned_le32(msg+4)!=8192 || get_unaligned_le32(msg+12))return false;
    flags=get_unaligned_le32(msg+8);if(flags&0xffff)return false;
    if(memcmp(msg+16,"sample_collect\0",15) || memcmp(msg+31,profile,48))return false;
    for(i=79;i<len;i++)if(msg[i])return false;
    return true;
}
