# -*- coding: utf-8 -*-
"""
board.py — 轻量棋盘推演层(移植并精简自旧项目 象棋粒子可视化分析系统/backend/xiangqi.py)

职责:把 UCI/ICCS 坐标着法(如 h2e2)落到 FEN 上,生成后继局面,并报告吃子。
不做合法性裁决(棋谱本身合法),只做最小兜底:起点必须有子、不吃己方子。

坐标约定:
  纵线 a..i → 列 0..8;rank 0(红底线)..9(黑底线)
  矩阵 board[row][col]:row 0 = FEN 第一行 = rank 9(黑方底线在上),row 9 = 红方底线
  row = 9 - rank。大写=红(KABNRCP),小写=黑(kabnrcp)。
"""

INIT_FEN = "rnbakabnr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RNBAKABNR w - - 0 1"

PIECE_NAME = {
    "K": "帅", "A": "仕", "B": "相", "N": "马", "R": "车", "C": "炮", "P": "兵",
    "k": "将", "a": "士", "b": "象", "n": "马", "r": "车", "c": "炮", "p": "卒",
}


def fen_board(fen):
    """FEN 第一字段 → 10x9 矩阵(list[10][9]),空位用 '.'。"""
    rows = fen.split()[0].split("/")
    if len(rows) != 10:
        raise ValueError(f"FEN 应有 10 行,实际 {len(rows)}:{fen}")
    board = []
    for r in rows:
        line = []
        for ch in r:
            if ch.isdigit():
                line.extend(["."] * int(ch))
            else:
                line.append(ch)
        if len(line) != 9:
            raise ValueError(f"FEN 某行宽度非 9:{r}")
        board.append(line)
    return board


def board_fen_field(board):
    """10x9 矩阵 → FEN 第一字段(空位压缩为数字)。"""
    rows = []
    for line in board:
        s, empty = "", 0
        for ch in line:
            if ch == ".":
                empty += 1
            else:
                if empty:
                    s += str(empty); empty = 0
                s += ch
        if empty:
            s += str(empty)
        rows.append(s)
    return "/".join(rows)


def _col(ch):
    return ord(ch) - ord("a")          # a..i → 0..8


def rc(uci_sq):
    """坐标 'h2' → (row, col)。"""
    return 9 - int(uci_sq[1]), _col(uci_sq[0])


def apply_move(fen, uci):
    """把 UCI 着法落子到 FEN,生成后继局面。
    返回 dict:{ fen_after, piece, captured(或 None), is_capture }。
    piece/captured 为原始字母(大写红/小写黑),便于上层判定。
    起点无子或吃己方子 → 抛 ValueError。"""
    if len(uci) != 4 or uci[0] not in "abcdefghi" or uci[2] not in "abcdefghi" \
            or not uci[1].isdigit() or not uci[3].isdigit():
        raise ValueError(f"着法格式非法:{uci}")
    parts = fen.split()
    board = fen_board(fen)
    fr, fc = rc(uci[:2])
    tr, tc = rc(uci[2:])
    piece = board[fr][fc]
    if piece == ".":
        raise ValueError(f"起点无子:{uci[:2]}")
    captured = board[tr][tc]
    if captured != "." and captured.isupper() == piece.isupper():
        raise ValueError(f"不能吃己方子:{uci}")

    board[tr][tc] = piece
    board[fr][fc] = "."
    stm = parts[1]
    new_stm = "b" if stm == "w" else "w"
    fullmove = int(parts[5]) if len(parts) >= 6 and parts[5].isdigit() else 1
    if stm == "b":
        fullmove += 1
    new_fen = f"{board_fen_field(board)} {new_stm} - - 0 {fullmove}"
    return {
        "fen_after": new_fen,
        "piece": piece,
        "captured": None if captured == "." else captured,
        "is_capture": captured != ".",
    }
