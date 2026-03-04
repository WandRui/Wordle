 ~/R/I/Wordle | on main !3 ?1  python benchmark.py                                  ok | Wordle py | at 21:50:58 
Loading 5-letter words from words.txt …
  15,921 words loaded.

Benchmark: 1024 games × 3 solvers  |  batch=64  |  word size=5
============================================================

▶  RANDOM solver
  Pre-computing first guess … 'consy'
  [████████████████████████████████████████] 1024/1024

  Solver : random
  Played : 1024  |  Solved: 1009 (98.5%)  |  Failed: 15
  Avg    : 5.339 guesses
  Dist   : 2×7  3×80  4×285  5×306  6×170  7×63  8×27  9×22  10×15  11×8  12×6  13×9  14×6  15×3  16×2
  Time   : 87.0s  (0.08s/game)

▶  ENTROPY solver
  Pre-computing first guess … 'mares'
  [████████████████████████████████████████] 1024/1024

  Solver : entropy
  Played : 1024  |  Solved: 1010 (98.6%)  |  Failed: 14
  Avg    : 4.879 guesses
  Dist   : 2×12  3×152  4×377  5×256  6×116  7×29  8×17  9×9  10×3  11×5  12×10  13×9  14×8  15×2  16×5
  Time   : 227.1s  (0.22s/game)

▶  MINIMAX solver
  Pre-computing first guess … 'lased'
  [████████████████████████████████████████] 1024/1024

  Solver : minimax
  Played : 1024  |  Solved: 1008 (98.4%)  |  Failed: 16
  Avg    : 4.992 guesses
  Dist   : 2×9  3×128  4×372  5×257  6×131  7×41  8×13  9×13  10×6  11×6  12×11  13×5  14×6  15×4  16×6
  Time   : 265.4s  (0.26s/game)

============================================================
FINAL RANKING  (average guesses, lower is better)

  🥇  #1  entropy   4.879 avg guesses
  🥈  #2  minimax   4.992 avg guesses
  🥉  #3  random    5.339 avg guesses

Total wall time: 579.6s