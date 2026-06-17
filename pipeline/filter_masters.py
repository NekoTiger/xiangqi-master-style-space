# -*- coding: utf-8 -*-
"""
filter_masters.py — 从大批棋谱里筛出指定大师的对局,每人最多 N 盘

用法:
  python filter_masters.py <原始棋谱目录> [--per 100] [--out ../data/masters.pgn]
  例:把东萍库解压到 ../data/raw,然后
     python filter_masters.py ../data/raw --per 100

做的事:
  1) parse_dir 扫描原始目录所有 *.pgn/*.iccs/*.txt
  2) 棋手名归一(去空格;可在 ALIASES 里登记别名/异体写法)
  3) 只保留红或黑属于 MASTERS 的对局;每位大师累计达到 --per 后不再为他收新盘
  4) 重新写成标准 PGN(ICCS),输出到 data/masters.pgn 供 build.py 使用
统计每位大师实际收录盘数,并提示哪些人不足额(可能是名字写法不同,去 ALIASES 补)。
"""
import os
import re
import sys
from collections import defaultdict

from iccs import parse_dir

# 目标:20 位特级大师
MASTERS = [
    "杨官璘", "胡荣华", "李义庭", "王嘉良", "柳大华", "李来群", "吕钦", "赵国荣",
    "许银川", "徐天红", "陶汉明", "于幼华", "洪智", "蒋川", "赵鑫鑫", "王天一",
    "郑惟桐", "孙勇征", "谢靖", "汪洋",
]
# 别名/异体写法 → 标准名(看统计发现某人不足额时,把库里的实际写法登记到这里)
ALIASES = {
    # "胡榮華": "胡荣华",
    # "吕钦 ": "吕钦",
}


def norm(name):
    if not name:
        return ""
    n = re.sub(r"\s+", "", name).strip()
    return ALIASES.get(n, n)


def to_iccs(uci):
    return f"{uci[0].upper()}{uci[1]}-{uci[2].upper()}{uci[3]}"


def movetext(moves):
    out = []
    for i in range(0, len(moves), 2):
        pair = to_iccs(moves[i])
        if i + 1 < len(moves):
            pair += " " + to_iccs(moves[i + 1])
        out.append(f"{i // 2 + 1}. {pair}")
    return " ".join(out)


def result_str(code):
    return {"red": "1-0", "black": "0-1", "draw": "1/2-1/2"}.get(code, "*")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        print("用法: python filter_masters.py <原始棋谱目录> [--per 100] [--out ../data/masters.pgn]")
        sys.exit(1)
    src = args[0]
    per = int(sys.argv[sys.argv.index("--per") + 1]) if "--per" in sys.argv else 100
    here = os.path.dirname(os.path.abspath(__file__))
    out = (sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv
           else os.path.join(here, "..", "data", "masters.pgn"))

    target = set(MASTERS)
    print(f"[1/3] 扫描原始棋谱:{src}")
    games = parse_dir(src)
    print(f"      共解析 {len(games)} 盘")
    if not games:
        print("[x] 没解析到棋谱。确认目录正确,且文件是 ICCS/PGN;若格式特殊请贴样例给我加适配。")
        sys.exit(1)

    count = defaultdict(int)        # 收录(截断后)盘数
    total = defaultdict(int)        # 全库未截断总盘数 ≈ 影响力/活跃度
    kept = []
    for g in games:
        r, b = norm(g.get("red")), norm(g.get("black"))
        r_t, b_t = r in target, b in target
        if not (r_t or b_t):
            continue
        if r_t:
            total[r] += 1
        if b_t:
            total[b] += 1
        # 至少有一位"还没收满"的目标大师,才收这盘
        if (r_t and count[r] < per) or (b_t and count[b] < per):
            g["red"], g["black"] = r, b
            kept.append(g)
            if r_t:
                count[r] += 1
            if b_t:
                count[b] += 1

    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        for i, g in enumerate(kept, 1):
            f.write(f'[Event "{g.get("event", "")}"]\n[Date "{g.get("date", "")}"]\n')
            f.write(f'[Red "{g["red"]}"]\n[Black "{g["black"]}"]\n[Result "{result_str(g.get("result_code"))}"]\n\n')
            f.write(movetext(g["moves"]) + f' {result_str(g.get("result_code"))}\n\n')

    # 写出影响力(全库总对局数),供 build.py 决定节点大小
    import json
    prom_path = os.path.join(os.path.dirname(out), "prominence.json")
    with open(prom_path, "w", encoding="utf-8") as f:
        json.dump({m: total[m] for m in MASTERS}, f, ensure_ascii=False)

    print(f"[2/3] 收录 {len(kept)} 盘 → {out}")
    print(f"      影响力(全库总局数) → {prom_path}")
    print(f"[3/3] 各大师收录盘数(目标 {per}):")
    short = []
    for m in MASTERS:
        c = count[m]
        flag = "" if c >= per else "  ← 不足额(可能名字写法不同,查库里实际写法补到 ALIASES)"
        if c < per:
            short.append(m)
        print(f"      {m}: {c}{flag}")
    if short:
        print(f"\n[!] 以下大师不足 {per} 盘:{'、'.join(short)}")
        print("    多半是东萍库里名字带空格或异体字。把实际写法登记进 ALIASES 后重跑即可。")
    print(f"\n下一步: python build.py --min-games 20")


if __name__ == "__main__":
    main()
