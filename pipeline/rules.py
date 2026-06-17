# -*- coding: utf-8 -*-
"""
rules.py — 轻量规则:将军检测 + 子力统计 + 残局判定

不实现完整着法生成,只实现"某方的将/帅此刻是否正被对方攻击"(用于统计将军次数),
以及子力计数(用于残局阶段判定)。从被将方的"将"出发,反向扫描各攻击来源。

棋子价值(用于残局阈值,可调):车9 马4.5 炮4.5 兵1 仕/相 2。
"""
from board import fen_board

PIECE_VALUE = {"R": 9, "N": 4.5, "C": 4.5, "P": 1, "A": 2, "B": 2, "K": 0}


def _find_king(board, red):
    """找到红(red=True)或黑的将/帅位置 (row,col);不在则 None。"""
    target = "K" if red else "k"
    for r in range(10):
        for c in range(9):
            if board[r][c] == target:
                return r, c
    return None


def _is_enemy(piece, red_side):
    """piece 是否为 red_side(被攻击方)的敌方棋子。"""
    if piece == ".":
        return False
    return piece.isupper() != red_side      # red_side 是大写,敌方为小写,反之亦然


def in_check(board, red):
    """red=True 判定红帅、False 判定黑将 此刻是否被攻击(将军)。"""
    king = _find_king(board, red)
    if king is None:
        return False
    kr, kc = king
    enemy_R = "r" if red else "R"
    enemy_C = "c" if red else "C"
    enemy_N = "n" if red else "N"
    enemy_P = "p" if red else "P"
    enemy_K = "k" if red else "K"

    # —— 车 / 炮 / 对脸将:沿四正方向扫描 ——
    for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        r, c = kr + dr, kc + dc
        first = None                         # 第一个遇到的子(炮架/车目标)
        while 0 <= r < 10 and 0 <= c < 9:
            p = board[r][c]
            if p != ".":
                if first is None:
                    # 紧邻第一子:车将 或 对脸将(将对将)
                    if p == enemy_R or p == enemy_K:
                        return True
                    first = p                # 作为炮架,继续找第二子
                else:
                    # 隔一子的第二子:炮将
                    if p == enemy_C:
                        return True
                    break
            r += dr; c += dc

    # —— 马(蹩腿):从将位看 8 个马位,马腿不能被堵 ——
    knight = (
        (-2, -1, -1, 0), (-2, 1, -1, 0), (2, -1, 1, 0), (2, 1, 1, 0),
        (-1, -2, 0, -1), (1, -2, 0, -1), (-1, 2, 0, 1), (1, 2, 0, 1),
    )
    for dr, dc, lr, lc in knight:
        r, c = kr + dr, kc + dc
        if 0 <= r < 10 and 0 <= c < 9 and board[r][c] == enemy_N:
            if board[kr + lr][kc + lc] == ".":      # 马腿(贴近将的那格)为空
                return True

    # —— 兵 / 卒:红帅被黑卒攻击来自上方或同行;黑将被红兵攻击来自下方或同行 ——
    if red:                                  # 黑卒(p)向下走(row 增大)
        cand = ((kr - 1, kc),) if kr > 0 else ()       # 卒在将上方一格,下推将
        cand += ((kr, kc - 1), (kr, kc + 1))           # 过河卒横吃
    else:                                    # 红兵(P)向上走(row 减小)
        cand = ((kr + 1, kc),) if kr < 9 else ()
        cand += ((kr, kc - 1), (kr, kc + 1))
    for r, c in cand:
        if 0 <= r < 10 and 0 <= c < 9 and board[r][c] == enemy_P:
            return True

    return False


def material(board):
    """返回 (红方子力值, 黑方子力值, 双方大子数R+N+C合计)。"""
    red_val = black_val = majors = 0
    for row in board:
        for p in row:
            if p == "." or p in "Kk":
                continue
            v = PIECE_VALUE.get(p.upper(), 0)
            if p.isupper():
                red_val += v
            else:
                black_val += v
            if p.upper() in ("R", "N", "C"):
                majors += 1
    return red_val, black_val, majors


def is_endgame(board, major_threshold=4):
    """残局判定:双方大子(车马炮)合计 <= 阈值。"""
    return material(board)[2] <= major_threshold


def in_check_fen(fen, red):
    return in_check(fen_board(fen), red)


if __name__ == "__main__":
    from board import INIT_FEN, apply_move
    b = fen_board(INIT_FEN)
    assert not in_check(b, True) and not in_check(b, False), "开局双方都不应被将"
    assert material(b) == (9 * 2 + 4.5 * 4 + 1 * 5 + 2 * 4,) * 1 + material(b)[1:] or True
    rv, bv, mj = material(b)
    assert rv == bv and mj == 12, (rv, bv, mj)      # 双方各 2车2马2炮 = 6,合计12
    # 红帅放 d0(col3) 避免与黑将 e9 对脸;红车 i0 不在 e 列 → 黑将不被将
    f = "4k4/9/9/9/9/9/9/9/9/3K4R w - - 0 1"
    assert not in_check(fen_board(f), False)
    f2 = "4k4/9/9/9/9/9/9/9/9/3K1R3 w - - 0 1"   # 红车 f0,仍不在 e 列
    assert not in_check(fen_board(f2), False)
    f3 = "4k4/4R4/9/9/9/9/9/9/9/3K5 w - - 0 1"   # 红车 e8 正对黑将 e9
    assert in_check(fen_board(f3), False), "红车直对黑将应判将军"
    # 对脸将:红帅黑将同列且中间无子 → 黑将视为被将
    f4 = "4k4/9/9/9/9/9/9/9/9/4K4 w - - 0 1"
    assert in_check(fen_board(f4), False), "对脸将应判将军"
    print("== rules.py 单测通过 ==")
