import math

class EquiDepthHistogramBuilderWithDP:
  def __init__(self, freqs, bin_count):
    assert type(freqs) == list

    # Set the number of bins.
    self.bin_count = bin_count

    # Set the freqs.
    self.freqs = freqs

    # The bin weight (how many items should be in one bin).
    self.bin_weight = sum([v for (_, v) in self.freqs]) / self.bin_count

    print(f'builder::bin_weight={self.bin_weight}')

    # Pre-compute the prefix sums.
    self.prefix_sums = [0] * len(self.freqs)
    for idx, (_, v) in enumerate(self.freqs):
      self.prefix_sums[idx] = v + (self.prefix_sums[idx - 1] if idx else 0)

    # print(self.prefix_sums)

  def compute_cost(self, start, end):
    # Compute the prefix sums.
    ret = self.prefix_sums[end] - (self.prefix_sums[start - 1] if start else 0)
    # if ret <= self.bin_weight:
    #   return 0.0
    return (ret - self.bin_weight) ** 2

  def rec_compute(self, dp, layer_idx, l, r, optl, optr):
    # D&C-optimization's recursive step.
    # Source: https://cp-algorithms.com/dynamic_programming/divide-and-conquer-dp.html.
    if l > r:
      return
    mid = (l + r) // 2
    best = (math.inf, -1)
    
    for k in range(optl, min(mid, optr) + 1):
      cost = (dp[layer_idx - 1][k - 1] if k > 0 else 0) + self.compute_cost(k, mid)
      if cost < best[0]:
        best = (cost, k)
    
    dp[layer_idx][mid] = best[0]
    opt = best[1]
    
    self.rec_compute(dp, layer_idx, l, mid - 1, optl, opt)
    self.rec_compute(dp, layer_idx, mid + 1, r, opt, optr)

  def optimized_build(self):
    # Computes DP[i][k] = opt. cost until `i` with `k` bins.
    n = len(self.freqs)
    dp = [[math.inf] * n for _ in range(self.bin_count + 1)]

    # First layer.
    for i in range(n):
      dp[1][i] = self.compute_cost(0, i)

    # Optimize all the layers.
    for layer_idx in range(2, self.bin_count + 1):
      self.rec_compute(dp, layer_idx, 0, n - 1, 0, n - 1)

    # Extract the boundaries.
    boundaries = []
    i, layer_idx = n - 1, self.bin_count
    while layer_idx > 1:
      # print(f'i={i}, layer_idx={layer_idx}: {dp[layer_idx][i]}')
      for j in range(i):
        if dp[layer_idx][i] == dp[layer_idx - 1][j] + self.compute_cost(j + 1, i):
          # print(f'Found: {j}')
          boundaries.append(self.freqs[j][0])
          i = j
          break
      layer_idx -= 1
    boundaries.reverse()
    return dp[self.bin_count][n - 1], boundaries