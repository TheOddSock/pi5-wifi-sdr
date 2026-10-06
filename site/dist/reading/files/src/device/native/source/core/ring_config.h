/* Offline only. Each geometry requires its own fingerprint/module ABI. */
#ifndef PI5_SPARSE_RING_CONFIG_H
#define PI5_SPARSE_RING_CONFIG_H
#ifndef RING_SLOTS
#error RING_SLOTS must be explicitly 16 or 32
#endif
#if RING_SLOTS == 16
#define RING_ABI_VERSION 34u
#elif RING_SLOTS == 32
#define RING_ABI_VERSION 36u
#else
#error Unsupported owned-ring geometry
#endif
#endif
