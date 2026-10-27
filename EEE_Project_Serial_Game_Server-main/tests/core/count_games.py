"""Independent reference: brute-force count of every Tic-Tac-Toe game (pure Python, no shared code with game.c).
Run:  python3 tests/core/count_games.py
The C test (test_game.c) asserts the same totals against game.c."""
import sys
sys.setrecursionlimit(100)
L = [(0,1,2),(3,4,5),(6,7,8),(0,3,6),(1,4,7),(2,5,8),(0,4,8),(2,4,6)]
def win(b, m): return any(b[i]==m and b[j]==m and b[k]==m for i,j,k in L)
from collections import Counter
res = Counter(); length = Counter(); nodes = [0]
def dfs(b, n):
    nodes[0] += 1
    side = 'X' if n % 2 == 0 else 'O'
    for i in range(9):
        if b[i] != '.': continue
        b[i] = side
        if win(b, side):
            res['WIN_'+side] += 1; length[(n+1, 'WIN_'+side)] += 1
        elif n + 1 == 9:
            res['DRAW'] += 1; length[(n+1, 'DRAW')] += 1
        else:
            dfs(b, n+1)
        b[i] = '.'
dfs(['.']*9, 0)
print("terminal games:", sum(res.values()), dict(res))
print("by length:", {k: v for k, v in sorted(length.items())})
print("non-terminal positions incl. start (DFS nodes):", nodes[0])
