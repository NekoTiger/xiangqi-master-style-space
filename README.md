# 中国象棋棋手风格空间构建与可视化分析

🌐 **在线演示：https://nekotiger.github.io/xiangqi-master-style-space/**

把每位棋手的所有对局压缩成一个高维"风格向量",经标准化 → PCA 降维 → KMeans 聚类,
投影到一张二维**风格地图**上:位置近 = 风格相似,自动聚成"激进进攻型 / 稳健运营型 /
残局控制型 / 多变全面型 / 速攻速决型"等群体,并支持交互探索与相似棋手推荐。

**课程方向:高维数据可视化(HDV)。** 对象=棋手,特征=风格指标,方法=降维+聚类+交互。

## 目录结构
```
象棋棋手风格空间/
├─ pipeline/                数据→画像→降维 的 Python 管线
│  ├─ board.py              棋盘推演(移植自旧项目 xiangqi.py):落子/吃子
│  ├─ rules.py              将军检测 + 子力统计 + 残局判定
│  ├─ openings.py           开局分类(中炮/飞相/仙人指路/起马)+ 屏风马 + 开局熵
│  ├─ iccs.py               ICCS/PGN 棋谱解析 → 元数据 + uci 着法序列
│  ├─ features.py           逐盘特征提取 + 按棋手聚合成画像表
│  ├─ build.py              主管线:画像 → 标准化 → PCA/KMeans → web/data.js
│  ├─ make_samples.py       生成样例棋谱(仅验证流程)
│  └─ sample_games/         样例 ICCS 棋谱
├─ data/                    放真实棋谱(*.pgn / *.iccs / *.txt),build 优先读这里
├─ web/
│  ├─ index.html            风格地图 + 雷达图 + 相似棋手(纯前端,双击即开)
│  └─ data.js               build 生成的内嵌数据(window.PLAYER_DATA)
└─ out/profiles.csv         棋手画像原始特征表
```

## 快速开始(样例数据)
```powershell
pip install -r requirements.txt
cd pipeline
python make_samples.py            # 生成样例棋谱
python build.py --min-games 3     # 跑通管线,写出 web/data.js
# 双击打开 web/index.html
```
> 样例数据仅验证"解析→特征→降维→可视化"是否通畅,无残局、棋手少,**聚类不具研究意义**。

## 用真实数据
1. 下载带棋手名的棋谱(推荐 GitHub `CGLemon/chinese-chess-PGN`,约 14 万盘 ICCS,含
   Red/Black/Event/Date/Result/Opening),解压到 `data/`。
2. 重跑:`python build.py --min-games 30`(真实数据建议门槛≥30 局,过滤样本过薄的棋手)。
3. 刷新 `web/index.html`。

## 特征体系(约 16 维,第一版全部不依赖引擎)
- **进攻性**:每局吃子数、每局将军数
- **节奏**:平均步数、速胜率(≤40步取胜)、长局率(≥100步)
- **开局偏好**:中炮率、飞相率、仙人指路率、起马率
- **多样性**:开局熵(分布越散越高)
- **胜负**:总胜率、先手胜率、后手胜率
- **残局**:进入残局比例、平均残局长度
> 第二版可引入 Pikafish 引擎(需另行下载)对每盘逐步打分,增量加入
> "失误次数/优势保持率"等特征,作为加分项。

## 可视化与研究问题对应
| 模块 | 回答的问题 |
|---|---|
| 风格地图散点(颜色=群体,大小=对局数) | Q1 风格能否量化 / Q2 是否存在聚类 |
| 底部 PCA 方差解释 + 主导特征载荷 | Q3 哪些特征最能反映风格 |
| 相似棋手推荐(标准化空间余弦相似度) | Q4 棋手相似关系 |
| 风格群体图例 + 雷达图 | 群体结构与典型画像 |

聚类簇数 k 由**轮廓系数**自动选取(非拍脑袋),底部显示 k 与 silhouette 值。
```
