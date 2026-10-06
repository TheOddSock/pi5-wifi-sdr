/* Fixed telemetry ABI. Observations are not a monotonic-clock/wrap proof. */
#ifndef PI5_MFG_PROGRESS_H
#define PI5_MFG_PROGRESS_H
#include <stdint.h>
#include <stddef.h>

#define PROGRESS_MAGIC UINT32_C(0x35504750)
#include "ring_config.h"
#define PROGRESS_VERSION RING_ABI_VERSION
#define PROGRESS_CAPACITY 8192u
#define PROGRESS_TRAILER 256u
#define PROGRESS_RECORDS 60u
#define PROGRESS_POLL_LIMIT 128u
#define PROGRESS_SAVED_POLL_RECORDS 54u
_Static_assert(2u+PROGRESS_SAVED_POLL_RECORDS+1u+2u<=PROGRESS_RECORDS,"One rejected observation plus both STOP snapshots fit");
#define PROGRESS_CAPTURES 1u

enum progress_phase { PROGRESS_BEFORE_ARM, PROGRESS_AFTER_ARM, PROGRESS_POLL,
    PROGRESS_RESTART, PROGRESS_STOP, PROGRESS_STOP_AGAIN, PROGRESS_REJECTED };
enum progress_status { PROGRESS_PENDING, PROGRESS_RETURNED, PROGRESS_VENDOR_ERROR };
enum progress_flags {
    PROGRESS_LOG_FULL = 1u, PROGRESS_POLL_OVERFLOW = 2u,
    PROGRESS_RETRIED = 4u, PROGRESS_BAD_EXTENT = 8u,
    PROGRESS_INCOMPLETE = 16u, PROGRESS_UNSTABLE = 32u
};
enum observation_flags {
    OBS_POINTER_MATCH = 1u, OBS_BOUNDS_MATCH = 2u, OBS_CONTROL_MATCH = 4u,
    OBS_TSF_HIGH_MATCH = 8u, OBS_CPU_STATE_MATCH = 16u, OBS_TSF_STATE_MATCH = 32u
};
struct progress_observation {
    uint32_t phase, ordinal, flags;
    uint32_t cycle_before, cycle_after, pmcr_before, pmcr_after;
    uint32_t enable_before, enable_after, scale_before, scale_after;
    uint32_t tsf_high_before, tsf_low, tsf_high_after;
    uint32_t maccontrol_before, maccontrol_after;
    uint32_t fraction_low_before, fraction_high_before;
    uint32_t fraction_low_after, fraction_high_after;
    uint32_t pointer_high_before, pointer_low, pointer_high_after;
    uint32_t extent_before, start_low, stop_low, extent_after;
    uint32_t collect_control_before, collect_control_after;
};
struct progress_record {
    uint32_t magic, version, bytes, sequence;
    uint32_t pre_us, post_us, expected_words, status;
    uint32_t vendor_result, observations, poll_calls, restart_calls;
    uint32_t flags, observer_cycles_total, observer_cycles_max;
    uint32_t entry_cycle, exit_cycle, chanspec, reserved0, reserved1;
    struct progress_observation samples[PROGRESS_RECORDS];
};
_Static_assert(sizeof(struct progress_observation) == 116u, "observation ABI");
_Static_assert(sizeof(struct progress_record) == 7040u, "record ABI");
_Static_assert(PROGRESS_TRAILER + sizeof(struct progress_record) <= PROGRESS_CAPACITY,
               "output bound");
#endif

#define RING_CONTEXT_MAGIC UINT32_C(0x3f52494e)
#define RING_CONTEXT_TRAILER 7360u
struct ring_context {
    uint32_t magic, version, bytes, sequence;
    uint32_t requested_delay, delay_steps, step_argument, flags;
    uint32_t before_private_start, before_private_end, before_cursor, before_final;
    uint32_t after_private_start, after_private_end, after_cursor, after_final;
};
_Static_assert(sizeof(struct ring_context)==64u,"Ring context ABI");
_Static_assert(RING_CONTEXT_TRAILER>=PROGRESS_TRAILER+sizeof(struct progress_record),"No overlap");
_Static_assert(RING_CONTEXT_TRAILER+sizeof(struct ring_context)<=PROGRESS_CAPACITY,"Ring output bound");
