#ifndef __HUGEPAGEALLOC_H__
#define __HUGEPAGEALLOC_H__

#include "Debug.h"

#include <cstdint>

#include <Common.h>
#include <memory.h>
#include <numa.h>
#include <numaif.h>
#include <sys/mman.h>

#ifdef CXL
#define NUMA_NODE 0
#else
#define NUMA_NODE 1
#endif

char *getIP();
inline void *hugePageAlloc(size_t size) {
  if (size == 0) {
    return nullptr;
  }

  const size_t HUGE_PAGE_SIZE = 2 * 1024 * 1024; // 2MB
  size_t aligned_size =
      ((size + HUGE_PAGE_SIZE - 1) / HUGE_PAGE_SIZE) * HUGE_PAGE_SIZE;
  printf("Allocating %dB memory on node %d\n", aligned_size, NUMA_NODE);

  void *res =
      mmap(NULL, aligned_size, PROT_READ | PROT_WRITE,
           MAP_PRIVATE | MAP_ANONYMOUS | MAP_HUGETLB | MAP_POPULATE, -1, 0);
  if (res == MAP_FAILED) {
    Debug::notifyError("%s mmap failed!\n", getIP());
  }

  unsigned long nodemask = (1UL << NUMA_NODE);
  int ret = mbind(res, aligned_size, MPOL_BIND, &nodemask,
                  sizeof(nodemask) * 8 + 1, 0);
  if (ret != 0) {
    Debug::notifyError(
        "%s mbind failed! Ensure Node %d has enough HugePages.\n", getIP(),
        NUMA_NODE);
    exit(-1);
  }

  return res;
}

inline void hugePageFree(void *addr, size_t size) {
  int res = munmap(addr, size);
  if (res == -1) {
    Debug::notifyError("%s munmap failed! %d\n", getIP(), errno);
  }
  return;
}

#endif /* __HUGEPAGEALLOC_H__ */
