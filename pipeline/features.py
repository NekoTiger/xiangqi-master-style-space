# -*- coding: utf-8 -*-
"""
features.py — 逐盘特征提取 + 按棋手聚合成高维画像表

game_features(game): 从初始局面回放着法,统计红/黑各自的吃子、将军、残局信息。
build_profiles(games, min_games): 把每位棋手在所有对局(分执红/执黑)里的行为聚合,
输出一行约 16 维的风格特征(pandas DataFrame,index = 棋手名)。

设计要点:
  - 吃子/将军按"行棋方"归到该方棋手(进攻性信号)。
  - 胜负、节奏分先后手统计(先手更易主动,需分开看)。
  - 开局类别只看执红方对局;屏风马只看执黑方对局。
  - 残局阶段 = 双方大子≤4 起;残局长度 = 进入残局后的步数。
"""
import pandas as pd
from collections import defaultdict

from board import INIT_FEN, apply_move, fen_board
from rules import in_check, is_endgame
from openings import classify_opening, is_pingfengma, opening_entropy

QUICK_PLIES = 40        # ≤ 该步数取胜 = 速胜
LONG_PLIES = 100        # ≥ 该步数 = 长局


def game_features(game):
    """回放单盘,返回 {plies, red:{caps,checks}, black:{caps,checks},
    endgame_reached, endgame_len, opening, pingfengma}。"""
    moves = game["moves"]
    fen = INIT_FEN
    caps = {"red": 0, "black": 0}
    checks = {"red": 0, "black": 0}
    endgame_onset = None
    applied = 0
    for i, uci in enumerate(moves):
        mover = "red" if i % 2 == 0 else "black"
        try:
            res = apply_move(fen, uci)
        except Exception:
            break                                   # 遇到无法落子的着法,止于此
        fen = res["fen_after"]
        applied = i + 1
        if res["is_capture"]:
            caps[mover] += 1
        board = fen_board(fen)
        # 走完后对方是否被将 = 该方将军
        opp_is_red = (mover == "black")
        if in_check(board, opp_is_red):
            checks[mover] += 1
        if endgame_onset is None and is_endgame(board):
            endgame_onset = applied
    return {
        "plies": len(moves),
        "red": {"caps": caps["red"], "checks": checks["red"]},
        "black": {"caps": caps["black"], "checks": checks["black"]},
        "endgame_reached": endgame_onset is not None,
        "endgame_len": (applied - endgame_onset) if endgame_onset is not None else 0,
        "opening": classify_opening(moves),
        "pingfengma": is_pingfengma(moves),
    }


def _new_acc():
    return {
        "games": 0, "wins": 0, "draws": 0, "losses": 0,
        "red_games": 0, "red_wins": 0, "black_games": 0, "black_wins": 0,
        "plies_sum": 0, "caps_sum": 0, "checks_sum": 0,
        "quick_wins": 0, "long_games": 0,
        "openings": [],            # 执红对局的开局标签
        "pfm_games": 0,            # 执黑屏风马盘数
        "eg_games": 0, "eg_len_sum": 0,
    }


def _accumulate(a, side, gf, rc):
    """把一盘棋(某方视角)的统计累加到该棋手的累加器 a。"""
    a["games"] += 1
    a[f"{side}_games"] += 1
    won = (rc == side)
    if won:
        a["wins"] += 1; a[f"{side}_wins"] += 1
    elif rc == "draw":
        a["draws"] += 1
    elif rc in ("red", "black"):       # 有胜负且非己方胜 → 己方负
        a["losses"] += 1
    # rc 为 None(结果未知)的对局只计入总局,不计胜/和/负
    a["plies_sum"] += gf["plies"]
    a["caps_sum"] += gf[side]["caps"]
    a["checks_sum"] += gf[side]["checks"]
    if won and gf["plies"] <= QUICK_PLIES:
        a["quick_wins"] += 1
    if gf["plies"] >= LONG_PLIES:
        a["long_games"] += 1
    if gf["endgame_reached"]:
        a["eg_games"] += 1; a["eg_len_sum"] += gf["endgame_len"]
    if side == "red":
        a["openings"].append(gf["opening"])
    if side == "black" and gf["pingfengma"]:
        a["pfm_games"] += 1


def _finalize(a):
    """累加器 → 一行特征(各比率/均值)。不含 'player'。"""
    g = a["games"]
    rg = max(a["red_games"], 1)
    bg = max(a["black_games"], 1)
    ops = a["openings"]
    op_n = max(len(ops), 1)
    decided = max(a["wins"] + a["draws"] + a["losses"], 1)
    return {
        "games": g,
        "wins": a["wins"], "draws": a["draws"], "losses": a["losses"],
        "win_rate": a["wins"] / decided,                          # 与和棋率/得分率同口径(已知结果局为分母)
        "score_rate": (a["wins"] + 0.5 * a["draws"]) / decided,   # 得分率(胜+半和)
        "draw_rate": a["draws"] / decided,                        # 和棋率(风格特征)
        "red_win_rate": a["red_wins"] / rg,
        "black_win_rate": a["black_wins"] / bg,
        "avg_plies": a["plies_sum"] / g,
        "captures_per_game": a["caps_sum"] / g,
        "checks_per_game": a["checks_sum"] / g,
        "quick_win_rate": a["quick_wins"] / g,
        "long_game_rate": a["long_games"] / g,
        "central_cannon_rate": ops.count("中炮") / op_n,
        "elephant_rate": ops.count("飞相") / op_n,
        "pawn_point_rate": ops.count("仙人指路") / op_n,
        "horse_rate": ops.count("起马") / op_n,
        "opening_entropy": opening_entropy(ops),
        "pingfengma_rate": a["pfm_games"] / bg,
        "endgame_rate": a["eg_games"] / g,
        "avg_endgame_len": a["eg_len_sum"] / max(a["eg_games"], 1),
    }


def build_profiles(games, min_games=5, gfs=None):
    """聚合所有对局 → 棋手画像 DataFrame(过滤对局数 < min_games 的棋手)。
    gfs:可传入预先算好的 game_features 列表(与 games 等长),避免重复重演。"""
    if gfs is None:
        gfs = [game_features(g) for g in games]
    acc = defaultdict(_new_acc)
    for g, gf in zip(games, gfs):
        if not g.get("red") or not g.get("black"):
            continue
        rc = g.get("result_code")
        _accumulate(acc[g["red"]], "red", gf, rc)
        _accumulate(acc[g["black"]], "black", gf, rc)

    rows = [{"player": name, **_finalize(a)} for name, a in acc.items() if a["games"] >= min_games]
    df = pd.DataFrame(rows)
    if "player" in df.columns:
        df = df.set_index("player").sort_index()
    return df


def build_trajectories(games, keep, gfs=None):
    """棋手风格时间演化:把每位棋手(限 keep 集合)的对局按日期排序,切成早/中/晚期,
    各期单独聚合成一行特征向量。返回 {棋手: [{label, years, games, feat:[18维]}...]}。
    带日期对局 ≥24 切 3 期,≥12 切 2 期,更少则不出轨迹。"""
    if gfs is None:
        gfs = [game_features(g) for g in games]
    byp = defaultdict(list)
    for g, gf in zip(games, gfs):
        if not g.get("red") or not g.get("black"):
            continue
        yr = (g.get("date") or "")[:4]
        if not (len(yr) == 4 and yr.isdigit() and yr != "0000"):
            continue
        rc = g.get("result_code")
        for side in ("red", "black"):
            if g[side] in keep:
                byp[g[side]].append((g["date"], side, gf, rc))

    out = {}
    for name, items in byp.items():
        items.sort(key=lambda t: t[0])
        n = len(items)
        nper = 3 if n >= 24 else (2 if n >= 12 else 0)
        if nper == 0:
            continue
        labels = ["早期", "中期", "晚期"] if nper == 3 else ["前期", "后期"]
        periods = []
        for pi in range(nper):
            chunk = items[pi * n // nper:(pi + 1) * n // nper]
            a = _new_acc()
            for (_d, side, gf, rc) in chunk:
                _accumulate(a, side, gf, rc)
            row = _finalize(a)
            yrs = [it[0][:4] for it in chunk]
            periods.append({"label": labels[pi], "years": f"{yrs[0]}–{yrs[-1]}",
                            "games": a["games"], "feat": [row[c] for c in FEATURE_COLS]})
        out[name] = periods
    return out


# 进入降维/聚类的特征列(不含 games:它只作点大小,不作风格维度)
FEATURE_COLS = [
    "win_rate", "draw_rate", "red_win_rate", "black_win_rate", "avg_plies",
    "captures_per_game", "checks_per_game", "quick_win_rate", "long_game_rate",
    "central_cannon_rate", "elephant_rate", "pawn_point_rate", "horse_rate",
    "opening_entropy", "pingfengma_rate", "endgame_rate", "avg_endgame_len",
]
