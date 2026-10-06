/* Exact previously reviewed snapshot/clock helper, renamed only. */
static void snapshot(struct progress_observation *s)
{
    volatile unsigned char *r = work.pointer_regs;
    s->phase = PROGRESS_STOP; s->ordinal = 0u;
    s->cycle_before = progress_cycle();
    s->pmcr_before = progress_pmcr(); s->enable_before = progress_enable();
    s->scale_before = progress_scale();
    s->maccontrol_before = reg32(r, 0x120);
    s->fraction_low_before = reg16(r, 0x62e); s->fraction_high_before = reg16(r, 0x630);
    s->tsf_high_before = reg32(r, 0x184); s->tsf_low = reg32(r, 0x180); s->tsf_high_after = reg32(r, 0x184);
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
        | (s->tsf_high_before == s->tsf_high_after ? OBS_TSF_HIGH_MATCH : 0u)
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

