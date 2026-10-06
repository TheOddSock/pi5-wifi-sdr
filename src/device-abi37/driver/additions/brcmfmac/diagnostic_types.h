/* Host-memory-only first failure snapshot. No active radio/SDIO reads. */
struct pi5_iq_failure {u32 h[16];u64 times[28];};
static_assert(sizeof(struct pi5_iq_failure)==288);
enum pi5_iq_reason {
 PI5_REASON_IO=0,PI5_REASON_PUBLISHED_REGRESSED=1,PI5_REASON_PUBLISHED_LAG=2,
 PI5_REASON_SLOT_OVERWRITTEN=3,PI5_REASON_META_CHANGED=4,PI5_REASON_HASH=5
};
