# -*- coding: utf-8 -*-
"""
openings.py — 开局分类与开局多样性(熵)

仅凭坐标着法做粗分类(够用即可,作为风格特征而非权威开局库):
  红方首着 → 中炮 / 飞相 / 仙人指路 / 起马 / 其他
  黑方前几手双马归心 → 屏风马
开局熵:某棋手(执红)所有对局开局标签分布的香农熵,越高 = 开局越多变。
"""
import math
from collections import Counter

# 红方首着 → 开局大类(uci 坐标)
RED_OPENING = {
    "b2e2": "中炮", "h2e2": "中炮",                 # 炮二平五 / 炮八平五
    "c0e2": "飞相", "g0e2": "飞相",                 # 相三/七进五
    "c3c4": "仙人指路", "g3g4": "仙人指路",         # 兵三/七进一
    "b0c2": "起马", "h0g2": "起马",                 # 马二/八进三
}
OPENING_LABELS = ["中炮", "飞相", "仙人指路", "起马", "其他"]


def classify_opening(moves):
    """根据红方首着返回开局大类。moves 为 uci 列表(红先)。"""
    if not moves:
        return "其他"
    return RED_OPENING.get(moves[0], "其他")


def is_pingfengma(moves):
    """黑方是否走屏风马:前 6 个黑方着法里同时出现两只马归心(h9g7 与 b9c7)。"""
    black_moves = moves[1::2][:6]            # 黑方走的是奇数手(下标 1,3,5...)
    return ("h9g7" in black_moves) and ("b9c7" in black_moves)


def opening_entropy(labels):
    """开局标签列表 → 香农熵(以 2 为底,单位 bit)。空 → 0。"""
    n = len(labels)
    if n == 0:
        return 0.0
    cnt = Counter(labels)
    h = 0.0
    for k in cnt:
        p = cnt[k] / n
        h -= p * math.log2(p)
    return h


if __name__ == "__main__":
    assert classify_opening(["b2e2"]) == "中炮"
    assert classify_opening(["c3c4"]) == "仙人指路"
    assert classify_opening(["a0a1"]) == "其他"
    assert classify_opening([]) == "其他"
    assert is_pingfengma(["b2e2", "h9g7", "h2e2", "b9c7"]) is True
    assert is_pingfengma(["b2e2", "h7e7"]) is False
    assert abs(opening_entropy(["中炮", "中炮"]) - 0.0) < 1e-9
    assert abs(opening_entropy(["中炮", "飞相"]) - 1.0) < 1e-9
    print("== openings.py 单测通过 ==")
