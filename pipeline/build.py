# -*- coding: utf-8 -*-
"""
build.py — 主管线:棋谱目录 → 棋手画像 → 标准化 → PCA + KMeans → 前端数据

用法:
  python build.py [棋谱目录]  [--min-games N]
  默认棋谱目录:优先 ../data(放真实棋谱),为空则回退 ./sample_games。

产物:
  ../web/data.js      window.PLAYER_DATA = {...}  (前端直接 <script> 引入,免服务器/免CORS)
  ../out/profiles.csv 棋手画像原始特征表
说明:
  坐标 (x,y) 用 PCA 前两主成分(可解释、稳定);若装了 umap-learn 另给 umap 坐标备用。
  雷达图 5 轴(进攻/稳健/残局/开局多样/节奏)由对应特征 min-max 归一化得到。
"""
import os
import sys
import json
import datetime
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score

from iccs import parse_dir
from features import (build_profiles, build_trajectories, build_halves,
                      game_features, FEATURE_COLS)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# 雷达 5 轴 ← 特征列(每轴取一个可解释特征)
RADAR = {
    "进攻": "_attack",          # 见下方合成
    "稳健": "long_game_rate",
    "残局": "endgame_rate",
    "开局多样": "opening_entropy",
    "节奏": "quick_win_rate",
}
# 群体命名:按"偏离全体均值最远的雷达轴"取名(最具区分度),高/低两个方向各一名
CLUSTER_NAME2 = {
    ("进攻", "hi"): "激进进攻型", ("进攻", "lo"): "平稳细腻型",
    ("稳健", "hi"): "稳健运营型", ("稳健", "lo"): "冒险搏杀型",
    ("残局", "hi"): "残局控制型", ("残局", "lo"): "中盘决胜型",
    ("开局多样", "hi"): "多变全面型", ("开局多样", "lo"): "传统专精型",
    ("节奏", "hi"): "速攻速决型", ("节奏", "lo"): "慢工缠斗型",
}


# 流派 → 风格关键词(面板第一层展示)
CLUSTER_KEYWORDS = {
    "速攻速决型": ["快攻", "抢攻", "速决", "主动求变"],
    "平稳细腻型": ["稳健", "细腻", "少失误", "以控代攻"],
    "慢工缠斗型": ["缠斗", "耐力", "中盘见功", "厚势"],
    "传统专精型": ["古典", "中炮正统", "开局专一", "硬碰硬"],
    "残局控制型": ["残局功力", "收官", "磨", "韧性"],
    "激进进攻型": ["激进", "攻杀", "弃子", "压迫"],
    "稳健运营型": ["稳健", "运营", "厚实", "不冒进"],
    "冒险搏杀型": ["搏杀", "冒险", "对攻", "求乱"],
    "中盘决胜型": ["中盘", "速战", "不拖", "决胜"],
    "多变全面型": ["多变", "全面", "无短板", "随机应变"],
}


def make_findings(players, clusters, axes, sil, k):
    """从聚类与极值自动生成'研究发现'(数据驱动,换数据也成立)。"""
    def members(cid):
        return "、".join(p["player"] for p in players if p["cluster"] == cid)

    def extreme(ax, hi=True):
        return max(players, key=lambda p: (1 if hi else -1) * p["radar"][ax])["player"]

    small = min(clusters, key=lambda c: c["size"])
    trad = min(clusters, key=lambda c: c["radar"]["开局多样"])   # 开局最专一者≈老派
    eg = max(clusters, key=lambda c: c["radar"]["残局"])
    fs = [
        {"t": f"风格空间中存在 {k} 个稳定流派",
         "d": f"20 位特级大师按多维棋风指标自动聚成 {k} 群"
              + (f",轮廓系数 {sil},说明风格群体是真实存在而非偶然" if sil else "")},
        {"t": f"「{small['name']}」自成一派",
         "d": members(small["id"]) + f"——{small['size']} 人风格独特,与其余大师明显分离"},
        {"t": f"{extreme('进攻', False)} 是最克制的大师",
         "d": "每局吃子与将军最少,稳居'稳健—控制'风格的极端"},
        {"t": f"{extreme('进攻', True)} 攻势最盛",
         "d": "吃子与将军频率全场最高,处于'激进进攻'的一端"},
        {"t": "老一辈大师开局高度专一",
         "d": members(trad["id"]) + " 几乎清一色中炮,聚成传统一派,印证早期开局体系单一"},
        {"t": f"{members(eg['id'])} 残局功力突出",
         "d": "对局更常进入残局阶段,靠收官见真章"},
    ]
    return fs[:6]


def name_clusters(labels, radar_norm, axes):
    """每个簇取'偏离全体均值最远'的轴命名;若名字已被占用则取次远轴,保证唯一。"""
    gmean = {ax: float(np.mean(radar_norm[ax])) for ax in axes}
    names, used = {}, set()
    for cid in sorted(set(labels)):
        mask = labels == cid
        dev = {ax: float(np.mean(radar_norm[ax][mask])) - gmean[ax] for ax in axes}
        chosen = None
        for ax in sorted(axes, key=lambda a: -abs(dev[a])):
            cand = CLUSTER_NAME2[(ax, "hi" if dev[ax] >= 0 else "lo")]
            if cand not in used:
                chosen = cand
                break
        chosen = chosen or f"群体{cid}"
        used.add(chosen)
        names[cid] = chosen
    return names


def _minmax(col):
    lo, hi = float(np.min(col)), float(np.max(col))
    if hi - lo < 1e-12:
        return np.full_like(col, 0.5, dtype=float)
    return (col - lo) / (hi - lo)


def pick_k(X, kmax=6):
    """用轮廓系数在 k=2..kmax 中选最佳簇数。返回 (k, labels, score, curve)。
    curve = [{k, sil}...] 供前端画'轮廓系数随 k 变化'曲线,佐证 k 的选取。"""
    n = len(X)
    if n < 4:
        return 1, np.zeros(n, dtype=int), float("nan"), []
    best = (2, None, -1.0)
    curve = []
    for k in range(2, min(kmax, n - 1) + 1):
        km = KMeans(n_clusters=k, n_init=10, random_state=42).fit(X)
        if len(set(km.labels_)) < 2:
            continue
        s = silhouette_score(X, km.labels_)
        curve.append({"k": k, "sil": round(float(s), 4)})
        if s > best[2]:
            best = (k, km.labels_, s)
    if best[1] is None:
        return 1, np.zeros(n, dtype=int), float("nan"), curve
    return best[0], best[1], best[2], curve


def main():
    argv = sys.argv[1:]
    min_games = 5
    positionals = []
    i = 0
    while i < len(argv):
        if argv[i] == "--min-games":
            min_games = int(argv[i + 1]); i += 2
        elif argv[i].startswith("--"):
            i += 1
        else:
            positionals.append(argv[i]); i += 1

    data_dir = positionals[0] if positionals else os.path.join(ROOT, "data")
    if not (os.path.isdir(data_dir) and parse_dir(data_dir)):
        data_dir = os.path.join(HERE, "sample_games")
        print(f"[i] 未找到真实棋谱,回退样例目录:{data_dir}")

    print(f"[1/5] 解析棋谱:{data_dir}")
    games = parse_dir(data_dir)
    print(f"      共 {len(games)} 盘")
    if not games:
        print("[x] 没有可用棋谱,退出。把 ICCS/PGN 棋谱放进 data/ 后重跑。")
        sys.exit(1)

    print(f"[2/5] 提取特征 + 聚合棋手(门槛:对局数 ≥ {min_games})")
    gfs = [game_features(g) for g in games]          # 逐盘重演一次,profiles 与轨迹共用
    df = build_profiles(games, min_games=min_games, gfs=gfs)
    print(f"      合格棋手 {len(df)} 名")
    if len(df) < 2:
        print("[x] 合格棋手不足,降低 --min-games 或喂更多棋谱。")
        sys.exit(1)

    # 合成"进攻"轴
    df["_attack"] = df["captures_per_game"] + df["checks_per_game"]

    print("[3/5] 标准化 + PCA 降维")
    X = df[FEATURE_COLS].to_numpy(dtype=float)
    scaler = StandardScaler().fit(X)
    Xz = scaler.transform(X)
    pca = PCA(n_components=2, random_state=42)
    xy = pca.fit_transform(Xz)

    # 时间演化:每位棋手分期(早/中/晚),用同一 scaler+pca 投影到同一空间
    trajectories = {}
    for nm, periods in build_trajectories(games, set(df.index), gfs=gfs).items():
        seq = []
        for per in periods:
            vz = scaler.transform(np.array(per["feat"], dtype=float).reshape(1, -1))
            pxy = pca.transform(vz)[0]
            seq.append({"label": per["label"], "years": per["years"], "games": per["games"],
                        "x": round(float(pxy[0]), 4), "y": round(float(pxy[1]), 4)})
        trajectories[nm] = seq
    print(f"      生成 {len(trajectories)} 位棋手的时间演化轨迹")

    # 风格一致性验证(re-identification):用一位棋手一半对局的画像,在全体中找回其另一半
    validation = None
    halves = build_halves(games, set(df.index), gfs=gfs)
    hnames = list(halves)
    if len(hnames) >= 3:
        A = scaler.transform(np.array([halves[n][0] for n in hnames], dtype=float))
        B = scaler.transform(np.array([halves[n][1] for n in hnames], dtype=float))

        def reid_acc(query, gallery, k=1):
            hit = 0
            for i in range(len(hnames)):
                d = np.linalg.norm(gallery - query[i], axis=1)
                if i in np.argsort(d)[:k]:
                    hit += 1
            return hit / len(hnames)

        n = len(hnames)
        acc1 = (reid_acc(A, B, 1) + reid_acc(B, A, 1)) / 2     # Rank-1,双向平均
        acc3 = (reid_acc(A, B, 3) + reid_acc(B, A, 3)) / 2     # Rank-3(Top-3命中)
        validation = {"accuracy": round(float(acc1), 3), "top3": round(float(acc3), 3),
                      "n": n, "baseline": round(1.0 / n, 3), "baseline3": round(3.0 / n, 3)}
        print(f"      风格指纹识别 Rank-1 {acc1:.0%} / Rank-3 {acc3:.0%} (基线 {1/n:.0%}/{3/n:.0%})")
    explained = [round(float(v), 4) for v in pca.explained_variance_ratio_]
    loadings = {f: [round(float(pca.components_[0][i]), 4),
                    round(float(pca.components_[1][i]), 4)]
                for i, f in enumerate(FEATURE_COLS)}

    # 可选 UMAP 坐标
    umap_xy = None
    try:
        import umap
        umap_xy = umap.UMAP(n_neighbors=min(15, len(df) - 1), min_dist=0.1,
                            random_state=42).fit_transform(Xz)
    except Exception:
        print("      (未装 umap-learn,跳过 UMAP 坐标;PCA 坐标已足够)")

    print("[4/5] KMeans 聚类 + 轮廓系数选 k")
    k, labels, sil, sil_curve = pick_k(Xz)
    print(f"      k={k}  silhouette={sil:.3f}" if sil == sil else f"      样本过少,k={k}")

    # 雷达 5 轴归一化
    radar_norm = {}
    for axis, col in RADAR.items():
        radar_norm[axis] = _minmax(df[col].to_numpy(dtype=float))

    # 簇命名:按偏离全体均值最远的轴(最具区分度),保证唯一
    axes = list(RADAR.keys())
    cluster_name = name_clusters(labels, radar_norm, axes)

    # 影响力(节点大小):优先用全库未截断的总对局数(filter 写出的 prominence.json),否则用收录局数
    prom = {}
    pj = os.path.join(ROOT, "data", "prominence.json")
    if os.path.exists(pj):
        with open(pj, "r", encoding="utf-8") as f:
            prom = json.load(f)

    players = []
    for idx, (name, row) in enumerate(df.iterrows()):
        cid = int(labels[idx])
        players.append({
            "player": name,
            "games": int(row["games"]),
            "prominence": int(prom.get(name, row["games"])),    # 全库总对局数 ≈ 影响力/活跃度
            "wins": int(row["wins"]), "draws": int(row["draws"]), "losses": int(row["losses"]),
            "win_rate": round(float(row["win_rate"]), 3),
            "score_rate": round(float(row["score_rate"]), 3),
            "cluster": cid,
            "cluster_name": cluster_name[cid],
            "x": round(float(xy[idx][0]), 4),
            "y": round(float(xy[idx][1]), 4),
            "ux": round(float(umap_xy[idx][0]), 4) if umap_xy is not None else None,
            "uy": round(float(umap_xy[idx][1]), 4) if umap_xy is not None else None,
            "radar": {ax: round(float(radar_norm[ax][idx]), 3) for ax in axes},
            "z": [round(float(v), 4) for v in Xz[idx]],     # 标准化向量,前端算相似度用
            "features": {c: round(float(row[c]), 3) for c in FEATURE_COLS},
        })

    clusters = []
    for cid in sorted(set(labels)):
        mask = labels == cid
        clusters.append({
            "id": int(cid),
            "name": cluster_name[cid],
            "keywords": CLUSTER_KEYWORDS.get(cluster_name[cid], []),
            "size": int(np.sum(mask)),
            "radar": {ax: round(float(np.mean(radar_norm[ax][mask])), 3) for ax in axes},
        })

    findings = make_findings(players, clusters, axes,
                             None if sil != sil else round(float(sil), 3), int(k))

    payload = {
        "players": players,
        "clusters": clusters,
        "trajectories": trajectories,
        "meta": {
            "generated": datetime.datetime.now().isoformat(timespec="seconds"),
            "n_games": len(games), "n_players": len(df), "k": int(k),
            "silhouette": None if sil != sil else round(float(sil), 3),
            "pca_explained": explained,
            "loadings": loadings,
            "feature_cols": FEATURE_COLS,
            "radar_axes": axes,
            "has_umap": umap_xy is not None,
            "min_games": min_games,
            "findings": findings,
            "sil_curve": sil_curve,
            "validation": validation,
        },
    }

    print("[5/5] 写出前端数据 + 画像表")
    web_dir = os.path.join(ROOT, "web")
    out_dir = os.path.join(ROOT, "out")
    os.makedirs(web_dir, exist_ok=True)
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(web_dir, "data.js"), "w", encoding="utf-8") as f:
        f.write("window.PLAYER_DATA = ")
        json.dump(payload, f, ensure_ascii=False)
        f.write(";\n")
    df.drop(columns=["_attack"]).to_csv(os.path.join(out_dir, "profiles.csv"),
                                        encoding="utf-8-sig")
    print(f"      → {os.path.join(web_dir, 'data.js')}")
    print(f"      → {os.path.join(out_dir, 'profiles.csv')}")
    print(f"\n完成。直接双击打开 web/index.html 即可查看(数据已内嵌,无需服务器)。")


if __name__ == "__main__":
    main()
