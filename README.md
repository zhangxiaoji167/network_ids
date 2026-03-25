# 网络协议分析与入侵检测系统

基于 **NSL-KDD / UNSW-NB15** 数据集的离线混合入侵检测系统。结合规则引擎与 **XGBoost + GRU 集成模型**进行多分类攻击检测，提供 FastAPI 后端 API 与 Vue3 可视化 Dashboard。

---

## 系统架构

```
┌─────────────────────────────────────────────────────┐
│                   Vue3 前端 Dashboard                │
│     检测面板 │ 模型评估 │ 连接查询                    │
└────────────────────┬────────────────────────────────┘
                     │ HTTP /api/*
┌────────────────────▼────────────────────────────────┐
│               FastAPI 后端 (port 8000)               │
│  routes_detection │ routes_model │ routes_analysis   │
└────────────────────┬────────────────────────────────┘
                     │
        ┌────────────┴─────────────┐
        ▼                         ▼
┌──────────────┐         ┌─────────────────────┐
│   规则引擎    │         │     混合检测引擎      │
│  YAML 规则   │────────▶│  Rule + ML → 决策   │
└──────────────┘         └──────────┬──────────┘
                                    │
                         ┌──────────▼──────────┐
                         │    ML 引擎（集成）    │
                         │  XGBoost × w₁       │
                         │  + GRU × w₂         │
                         │  权重由验证集搜索     │
                         └─────────────────────┘
```

### 检测流程

1. **加载数据**：从 CSV 读取 NSL-KDD / UNSW-NB15，存入 SQLite `connections` 表
2. **规则引擎**：对每条记录匹配 YAML 规则，输出攻击类别和严重级别
3. **ML 集成推理**：XGBoost 概率 × w₁ + GRU 概率 × w₂ → 加权融合预测
4. **混合决策**：规则命中优先，ML 补充高置信度判断
5. **告警生成**：对检测到的攻击生成分级告警，存入 `alerts` 表

### 支持的攻击类别

| 数据集 | 攻击类别 |
|---|---|
| NSL-KDD | Normal · DoS · Probe · R2L · U2R |
| UNSW-NB15 | Normal · Fuzzers · Analysis · Backdoor · DoS · Exploits · Generic · Reconnaissance · Shellcode · Worms |

---

## 模型说明

### XGBoost + GRU 集成

- **XGBoost**：梯度提升树，擅长处理表格特征，训练快，可解释性强
- **GRU**（Gated Recurrent Unit）：PyTorch 实现，利用 GPU 加速，通过 GRU 层提取特征间非线性关系
- **集成策略**：在外部测试集上网格搜索最优权重 w₁（XGB）和 w₂（GRU），使准确率最高

### 训练流程（以 NSL-KDD 为例）

```
全量训练集
    ├── 80% 训练子集 → DataPreprocessor.fit_transform → SMOTENC 过采样
    │       ├── XGBoost 训练（早停，验证集监控）
    │       └── GRU 训练（GPU，100 epochs，早停）
    └── 20% 验证子集 → 集成权重搜索（w_xgb ∈ [0.0, 1.0, step=0.05]）

外部测试集 → 集成准确率评估

全量重训（最优树数量 × 1.1，无早停）→ 保存最终模型
```

### 模型文件

训练完成后保存至 `backend/ml/models/`：

| 文件 | 说明 |
|---|---|
| `xgboost_nslkdd.pkl` | NSL-KDD XGBoost + 预处理器 + 标签编码器 |
| `xgboost_unsw.pkl` | UNSW-NB15 XGBoost + 预处理器 + 标签编码器 |
| `gru_nslkdd.pt` | NSL-KDD GRU 模型权重 |
| `gru_unsw.pt` | UNSW-NB15 GRU 模型权重 |
| `ensemble_nslkdd.pkl` | NSL-KDD 集成权重 `{xgb_weight, gru_weight}` |
| `ensemble_unsw.pkl` | UNSW-NB15 集成权重 |
| `nslkdd_metrics.json` | NSL-KDD 评估指标 |
| `unsw_metrics.json` | UNSW-NB15 评估指标 |

---

## 环境要求

| 依赖 | 版本 |
|---|---|
| Python | 3.10+ |
| Node.js | 18+ |
| CUDA（可选） | 11.8+（GPU 加速 GRU 训练） |
| Conda | 推荐，用于管理环境 |

> **GPU 说明**：GRU 训练默认尝试使用 CUDA GPU。若无 GPU，会自动回退到 CPU 训练（速度较慢，约增加 3-5 倍时间）。

---

## 复现指南

### 第一步：克隆项目

```bash
git clone https://github.com/EliHuxley4/network-ids.git
cd network-ids
```

### 第二步：创建 Python 环境

```bash
# 使用 Conda（推荐）
conda create -n network-ids python=3.11
conda activate network-ids
pip install -r backend/requirements.txt

# 若有 NVIDIA GPU，安装对应 CUDA 版本的 PyTorch（以 CUDA 12.8 为例）
# pip install torch --index-url https://download.pytorch.org/whl/cu128
```

### 第三步：安装前端依赖

```bash
cd frontend
npm install
cd ..
```

### 第四步：准备数据集

数据集文件**不包含在仓库中**，需手动下载后放置：

#### NSL-KDD

1. 下载地址：https://www.unb.ca/cic/datasets/nsl.html
2. 下载 `NSL-KDD.zip`，解压后取 `KDDTrain+.txt` 和 `KDDTest+.txt`
3. 放置到：

```
data/nsl-kdd/
├── KDDTrain+.txt
└── KDDTest+.txt
```

#### UNSW-NB15

1. 下载地址：https://research.unsw.edu.au/projects/unsw-nb15-dataset
2. 下载 CSV 格式数据集，取训练集和测试集
3. 放置到：

```
data/unsw-nb15/
├── UNSW_NB15_training-set.csv
└── UNSW_NB15_testing-set.csv
```

### 第五步：训练模型

```bash
cd backend
conda activate network-ids

# 训练 NSL-KDD（约 5-15 分钟，含 GRU 训练）
python ml/train.py --source nsl-kdd

# 训练 UNSW-NB15（约 10-20 分钟）
python ml/train.py --source unsw-nb15
```

训练过程日志示例：
```
[train:nsl-kdd] 训练集大小: (125973, 45)
[train:nsl-kdd] 开始训练 XGBoost (类别数: 5)...
[GRU] 使用设备: cuda
[train:nsl-kdd] 开始训练 GRU...
[ensemble] 最优权重: XGBoost=0.65, GRU=0.35, 验证集准确率=0.8123
[train:nsl-kdd] 全部完成，总耗时 482.3 秒
```

### 第六步：启动系统

#### Windows 一键启动

双击 `start.bat`，自动启动后端（端口 8000）和前端（端口 5173）。

#### 手动启动

```bash
# 终端 1：启动后端
cd backend
conda activate network-ids
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# 终端 2：启动前端
cd frontend
npx vite
```

访问：
- **前端界面**：http://localhost:5173
- **API 文档（Swagger）**：http://localhost:8000/docs

### 第七步：运行检测

1. 打开前端，进入**检测面板**
2. 选择数据集（NSL-KDD 或 UNSW-NB15）
3. 选择数据子集（建议先用 test + limit=1000 快速验证）
4. 点击**运行检测**，等待完成
5. 查看**模型评估**页面了解准确率和混淆矩阵

---

## 验证安装

```bash
cd backend
conda activate network-ids

# 运行全套单元测试（50 个）
python -m pytest tests/ -v

# 端到端验证脚本
python test_e2e.py
```

---

## 项目结构

```
network-ids/
├── README.md
├── start.bat                    # Windows 一键启动
├── data/
│   ├── nsl-kdd/                 # ⚠️ 需手动放置数据集
│   └── unsw-nb15/               # ⚠️ 需手动放置数据集
├── backend/
│   ├── main.py                  # FastAPI 入口，引擎初始化
│   ├── config.py                # 全局配置（特征列、攻击映射、路径）
│   ├── database.py              # SQLite 连接管理
│   ├── requirements.txt
│   ├── api/
│   │   ├── routes_dashboard.py  # GET /api/dashboard/stats
│   │   ├── routes_detection.py  # POST /api/detection/run
│   │   ├── routes_model.py      # GET /api/model/*
│   │   ├── routes_analysis.py   # GET /api/analysis/*
│   │   └── routes_system.py     # POST /api/system/train
│   ├── detection/
│   │   ├── rule_engine.py       # YAML 规则解析与条件匹配
│   │   ├── ml_engine.py         # XGBoost + GRU 集成推理
│   │   └── hybrid_engine.py     # 混合决策 + 告警生成
│   ├── ml/
│   │   ├── train.py             # 训练脚本（SMOTENC + XGBoost + GRU + 权重搜索）
│   │   ├── gru_model.py         # GRU 网络定义、训练、推理、保存/加载
│   │   ├── evaluate.py          # 混淆矩阵、ROC、特征重要性
│   │   └── models/              # ⚠️ 训练后生成，不在仓库中
│   ├── data_loader/
│   │   ├── loader.py            # CSV 加载 + 攻击类别映射
│   │   └── preprocessor.py      # 标准化 + LabelEncoder
│   ├── rules/                   # YAML 规则文件
│   │   ├── dos_rules.yaml
│   │   ├── probe_rules.yaml
│   │   ├── r2l_rules.yaml
│   │   ├── u2r_rules.yaml
│   │   └── anomaly_rules.yaml
│   └── tests/
│       ├── test_rule_engine.py
│       ├── test_ml_engine.py
│       ├── test_hybrid_engine.py
│       ├── test_api.py
│       └── test_training_pipeline.py
└── frontend/
    ├── vite.config.js
    ├── package.json
    └── src/
        ├── views/
        │   ├── DashboardView.vue    # 检测面板
        │   ├── ModelView.vue        # 模型评估
        │   └── ConnectionsView.vue  # 连接查询
        └── components/              # ECharts 图表组件
```

---

## 混合决策逻辑

```
对每条连接记录：
  规则引擎 ──→ rule_matched, rule_category, severity
  ML 集成  ──→ ml_category, ml_confidence

  if rule_matched AND ml_confidence > 0.7:
      final = ml_category, source = "HYBRID", severity = HIGH/CRITICAL
  elif rule_matched:
      final = rule_category, source = "RULE",   severity = 规则定义
  elif ml_confidence > 0.7 AND ml_category != "Normal":
      final = ml_category, source = "ML",       severity = MEDIUM/LOW
  else:
      final = "Normal",    source = "NONE"
```

ML 置信度阈值默认 **0.7**，可在 `backend/config.py` 修改 `ML_CONFIDENCE_THRESHOLD`。

---

## 常见问题

**Q: 后端启动提示"模型不存在，跳过"**
→ 需要先运行 `python ml/train.py --source nsl-kdd`

**Q: GRU 训练报 CUDA 相关错误**
→ 检查 PyTorch 版本是否匹配 CUDA 驱动；或将 `backend/ml/gru_model.py` 中的 `device` 改为 `'cpu'`

**Q: 运行检测时返回 503 "检测引擎未初始化"**
→ 模型文件不存在，需先训练

**Q: 前端显示"暂无数据"**
→ 进入检测面板点击"运行检测"，系统会自动加载数据并执行检测

**Q: 想只跑规则引擎（不用 ML）**
→ 删除 `backend/ml/models/` 下的文件，后端会自动回退到纯规则模式

**Q: 数据库损坏或想重置**
→ 删除 `backend/database.db`，重启后端会自动重建
