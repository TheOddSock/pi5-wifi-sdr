/* ABI37 coherent TSF acquisition; existing snapshot and clock guards retained. */
static void snapshot(struct progress_observation *s)
{
    volatile unsigned char *r = work.pointer_regs;
    struct pi5_tsf_triplet tsf;int tsf_coherent;
    s->phase = PROGRESS_STOP; s->ordinal = 0u;
    s->cycle_before = progress_cycle();
    s->pmcr_before = progress_pmcr(); s->enable_before = progress_enable();
    s->scale_before = progress_scale();
    s->maccontrol_before = reg32(r, 0x120);
    s->fraction_low_before = reg16(r, 0x62e); s->fraction_high_before = reg16(r, 0x630);
    tsf_coherent=pi5_tsf_coherent_next(r,&tsf);
    s->tsf_high_before=tsf_coherent?tsf.high:tsf.first_high;
    s->tsf_low=tsf_coherent?tsf.low:tsf.first_low;
    s->tsf_high_after=tsf_coherent?tsf.high_after:tsf.first_high_after;
    s->pointer_high_before = reg16(r, 0x53a); s->pointer_low = reg16(r, 0x556);
    s->pointer_high_after = reg16(r, 0x53a);
    s->extent_before = reg16(r, 0x538); s->start_low = reg16(r, 0x552); s->stop_low = reg16(r, 0x554);
    s->extent_after = reg16(r, 0x538);
    s->collect_control_before = reg16(r, 0xb2e); s->collect_control_after = reg16(r, 0xb2e);
    s->fraction_low_after = reg16(r, 0x62e); s->fraction_high_after = reg16(r, 0x630);
    s->maccontrol_after = reg32(r, 0x120); s->scale_after = progress_scale();
    s->enable_after = progress_enable(); s->pmcr_after = progress_pmcr(); s->cycle_after = progress_cycle();
    s->flags = (((s->pointer_high_before ^ s->pointer_high_after) & 15u) == 0u ? OBS_POINTER_MATCH : 0u)
        | (s->extent_before == s->extent_after ? OBS_BOUNDS_MATCH : 0u)
        | (s->collect_control_before == s->collect_control_after ? OBS_CONTROL_MATCH : 0u)
        | (tsf_coherent ? OBS_TSF_HIGH_MATCH : 0u)
        | (s->pmcr_before == s->pmcr_after && ((s->enable_before ^ s->enable_after) & UINT32_C(0x80000007)) == 0u
           && s->scale_before == s->scale_after ? OBS_CPU_STATE_MATCH : 0u)
        | (s->fraction_low_before == s->fraction_low_after && s->fraction_high_before == s->fraction_high_after
           && s->maccontrol_before == s->maccontrol_after ? OBS_TSF_STATE_MATCH : 0u);
}

static int same_clock(const struct progress_observation *a, const struct progress_observation *b)
{
    return a->pmcr_before == b->pmcr_before && ((a->enable_before ^ b->enable_before) & UINT32_C(0x80000007)) == 0u
        && a->scale_before == b->scale_before && a->maccontrol_before == b->maccontrol_before
        && a->fraction_low_before == b->fraction_low_before && a->fraction_high_before == b->fraction_high_before;
}


/* Copy the first rejected existing snapshot only; no new MMIO on failure.
 * At most54 saved polls plus2 arm and2 STOP observations:59 of60 slots.
 * A bounded scan avoids extra workspace or repurposing existing fields. */
static void record_rejected(const struct progress_observation *observation,uint32_t site)
{
    struct progress_record *record=&work.record;uint32_t i;
    /* Finish admission occurs after both STOP records; all other sites
     * retain their two-slot STOP reservation. Admission bounds the scan. */
    uint32_t reserve=(site==7u || site==9u)?0u:2u;
    if(record->observations>=PROGRESS_RECORDS-reserve)return;
    for(i=0;i<record->observations;i++)if(record->samples[i].phase==PROGRESS_REJECTED)return;
    struct progress_observation *dest=&record->samples[record->observations++];
    for(i=0;i<sizeof(*observation);i++)((unsigned char *)dest)[i]=((const unsigned char *)observation)[i];
    dest->phase=PROGRESS_REJECTED;dest->ordinal=site;
}
