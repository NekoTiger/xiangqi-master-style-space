# -*- coding: utf-8 -*-
"""
make_samples.py — 生成可跑通管线的样例 ICCS 棋谱(sample_games/all_games.pgn)

注意:样例仅用于验证"解析→特征→降维→可视化"全流程是否通畅,
着法是合法的开局发展手,但数量少、无残局,聚类不具研究意义。
真实结论请把带棋手名的真实棋谱放进 ../data 后重跑 build.py。

每条模板都是从初始局面出发、逐手合法的着法序列(已用 board.apply_move 校验)。
"""
import os
from board import INIT_FEN, apply_move

# —— 合法开局模板(uci,红先黑后交替) ——
TEMPLATES = {
    "center_attack": ["b2e2", "h9g7", "h0g2", "b9c7", "b0c2", "h7e7", "e2e6"],
    "center_quiet":  ["h2e2", "h7e7", "b0c2", "b9c7", "h0g2", "h9g7", "a0a1", "a9a8"],
    "elephant":      ["c0e2", "h9g7", "g3g4", "b9c7", "b0c2", "h7e7", "h0g2", "a6a5"],
    "pawn_point":    ["g3g4", "h7e7", "b0c2", "h9g7", "h0g2", "b9c7", "c3c4", "a6a5"],
    "horse_start":   ["b0c2", "h7e7", "h0g2", "b9c7", "b2e2", "h9g7", "c3c4", "g6g5"],
}

# —— 棋手 → (执红偏好模板, 执黑偏好模板, 大致胜负倾向) ——
# 每个元素: (red_name, black_name, template, result)
GAMES = [
    ("攻杀手", "稳健王", "center_attack", "1-0"),
    ("攻杀手", "飞相客", "center_attack", "1-0"),
    ("急先锋", "老练手", "center_attack", "1-0"),
    ("急先锋", "指路人", "center_quiet", "1/2-1/2"),
    ("攻杀手", "起马郎", "center_quiet", "1-0"),
    ("稳健王", "攻杀手", "elephant", "1/2-1/2"),
    ("稳健王", "急先锋", "elephant", "0-1"),
    ("老练手", "攻杀手", "elephant", "1/2-1/2"),
    ("老练手", "全能型", "center_quiet", "1/2-1/2"),
    ("飞相客", "急先锋", "elephant", "0-1"),
    ("飞相客", "全能型", "elephant", "1/2-1/2"),
    ("指路人", "稳健王", "pawn_point", "1/2-1/2"),
    ("指路人", "老练手", "pawn_point", "1-0"),
    ("起马郎", "飞相客", "horse_start", "1/2-1/2"),
    ("起马郎", "指路人", "horse_start", "0-1"),
    ("全能型", "起马郎", "center_attack", "1-0"),
    ("全能型", "稳健王", "pawn_point", "1/2-1/2"),
    ("急先锋", "全能型", "center_attack", "1-0"),
    ("攻杀手", "老练手", "center_attack", "1-0"),
    ("稳健王", "指路人", "elephant", "1/2-1/2"),
    ("老练手", "起马郎", "center_quiet", "1/2-1/2"),
    ("飞相客", "攻杀手", "elephant", "0-1"),
    ("指路人", "全能型", "pawn_point", "1/2-1/2"),
    ("起马郎", "稳健王", "horse_start", "1/2-1/2"),
]


def to_iccs(uci):
    """uci 'h2e2' → ICCS 'H2-E2'(大写,带连接符)。"""
    return f"{uci[0].upper()}{uci[1]}-{uci[2].upper()}{uci[3]}"


def movetext(moves):
    out = []
    for i in range(0, len(moves), 2):
        no = i // 2 + 1
        pair = to_iccs(moves[i])
        if i + 1 < len(moves):
            pair += " " + to_iccs(moves[i + 1])
        out.append(f"{no}. {pair}")
    return " ".join(out)


def validate(moves):
    """逐手 apply_move,确保模板合法。返回 True/抛错。"""
    fen = INIT_FEN
    for u in moves:
        fen = apply_move(fen, u)["fen_after"]
    return True


def main():
    for name, mv in TEMPLATES.items():
        validate(mv)                       # 任何非法手会在此抛错
    print(f"[ok] {len(TEMPLATES)} 个模板全部合法")

    here = os.path.dirname(os.path.abspath(__file__))
    out_dir = os.path.join(here, "sample_games")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "all_games.pgn")
    with open(path, "w", encoding="utf-8") as f:
        for i, (red, black, tpl, res) in enumerate(GAMES, 1):
            f.write(f'[Event "样例赛 R{i}"]\n[Date "2024.01.{i:02d}"]\n')
            f.write(f'[Red "{red}"]\n[Black "{black}"]\n[Result "{res}"]\n\n')
            f.write(movetext(TEMPLATES[tpl]) + f" {res}\n\n")
    print(f"[ok] 写出 {len(GAMES)} 盘 → {path}")


if __name__ == "__main__":
    main()
