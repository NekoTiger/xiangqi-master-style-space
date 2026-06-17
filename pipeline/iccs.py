# -*- coding: utf-8 -*-
"""
iccs.py — ICCS 坐标棋谱解析

支持 PGN 风格的棋谱:头部标签 [Red "..."]/[Black "..."]/[Result "..."]/[Event/Date],
紧跟 ICCS 坐标着法文本(如 "1. H2-E2 H7-E7 2. ..."),着法形如 字母+数字 字母+数字。
一个文件可含多盘(以下一组头部标签为界)。ICCS 坐标与本项目 uci 同制(a..i / 0..9),
仅做大小写归一并去掉连接符 '-'。

对外:
  parse_text(text)  -> list[game]
  parse_dir(path)   -> list[game]    (读取 *.pgn / *.iccs / *.txt)
  game = {event, date, red, black, result, result_code, moves:[uci...]}
  result_code: 'red' | 'black' | 'draw' | None
"""
import os
import re
import glob

_TAG = re.compile(r'\[(\w+)\s+"(.*?)"\]')
_MOVE = re.compile(r'\b([a-iA-I])(\d)-?([a-iA-I])(\d)\b')
_COMMENT = re.compile(r'\{[^}]*\}|\([^)]*\)')        # 去注释/变着
_RESULT = {
    "1-0": "red", "0-1": "black", "1/2-1/2": "draw", "1-1": "draw",
}


def _norm_move(m):
    """正则 match → 小写 uci,如 ('H','2','E','2') -> 'h2e2'。"""
    return (m.group(1) + m.group(2) + m.group(3) + m.group(4)).lower()


def _split_games(text):
    """把含多盘的文本切成单盘块:每次遇到 [Event] 或 [Game] 标签视作新盘起点。"""
    lines = text.splitlines()
    blocks, cur = [], []
    for ln in lines:
        if re.match(r'\s*\[(Event|Game)\b', ln) and cur and any("[" in x for x in cur) \
                and any(_MOVE.search(x) for x in cur):
            blocks.append("\n".join(cur)); cur = []
        cur.append(ln)
    if cur:
        blocks.append("\n".join(cur))
    return [b for b in blocks if b.strip()]


def clean_name(full, team):
    """东萍 [Red] 常是 '队名 棋手名'(如 '黑龙江 郭莉萍'),且另有 [RedTeam]。
    剥掉队名前缀得到纯棋手名;无队名标签时取最后一个空白分隔 token。"""
    full = re.sub(r"\s+", " ", (full or "")).strip()
    team = (team or "").strip()
    if not full:
        return ""
    if team and full.startswith(team):
        return full[len(team):].strip()
    parts = re.split(r"\s+", full)        # \s 含全角空格
    return parts[-1] if len(parts) > 1 else full


def parse_game(block):
    """解析单盘块 → game dict;无任何着法则返回 None。"""
    tags = {k.lower(): v for k, v in _TAG.findall(block)}
    # 着法只从非标签行提取,先剥注释
    body = "\n".join(ln for ln in block.splitlines() if not ln.strip().startswith("["))
    body = _COMMENT.sub(" ", body)
    moves = [_norm_move(m) for m in _MOVE.finditer(body)]
    if not moves:
        return None
    res_raw = tags.get("result", "").strip()
    return {
        "event": tags.get("event", ""),
        "date": tags.get("date", ""),
        "red": clean_name(tags.get("red", ""), tags.get("redteam", "")),
        "black": clean_name(tags.get("black", ""), tags.get("blackteam", "")),
        "result": res_raw,
        "result_code": _RESULT.get(res_raw),
        "moves": moves,
    }


def parse_text(text):
    games = []
    for blk in _split_games(text):
        g = parse_game(blk)
        if g:
            games.append(g)
    return games


def parse_file(fp):
    with open(fp, "r", encoding="utf-8", errors="ignore") as f:
        return parse_text(f.read())


def parse_dir(path, patterns=("*.pgn", "*.pgns", "*.iccs", "*.txt")):
    """读取路径下所有棋谱 → game 列表。path 可为目录或单个文件。"""
    if os.path.isfile(path):
        return parse_file(path)
    games = []
    for pat in patterns:
        for fp in glob.glob(os.path.join(path, "**", pat), recursive=True):
            try:
                games.extend(parse_file(fp))
            except Exception as e:
                print(f"  [跳过] 读取失败 {fp}: {e}")
    return games


if __name__ == "__main__":
    sample = '''[Event "测试赛"]
[Date "2024.01.01"]
[Red "张三"]
[Black "李四"]
[Result "1-0"]

1. H2-E2 H7-E7 2. B0-C2 B9-C7 1-0

[Event "测试赛"]
[Red "王五"]
[Black "张三"]
[Result "0-1"]

1. C3-C4 H9-G7 0-1
'''
    gs = parse_text(sample)
    assert len(gs) == 2, len(gs)
    assert gs[0]["red"] == "张三" and gs[0]["result_code"] == "red"
    assert gs[0]["moves"][:3] == ["h2e2", "h7e7", "b0c2"], gs[0]["moves"]
    assert gs[1]["result_code"] == "black" and gs[1]["moves"] == ["c3c4", "h9g7"]
    print("== iccs.py 单测通过 ==", [g["red"] + "vs" + g["black"] for g in gs])
