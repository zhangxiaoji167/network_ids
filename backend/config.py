"""网络协议分析与入侵检测系统 - 配置管理"""
import os
from pathlib import Path

# 项目根目录
BASE_DIR = Path(__file__).resolve().parent

# 数据目录
DATA_DIR = BASE_DIR.parent / "data" / "nsl-kdd"
UNSW_DATA_DIR = BASE_DIR.parent / "data" / "unsw-nb15"

# 模型目录
MODEL_DIR = BASE_DIR / "ml" / "models"

# 规则目录
RULES_DIR = BASE_DIR / "rules"

# 数据库
DB_PATH = BASE_DIR / "database.db"

# ─── 支持的数据集源 ───
DATASET_SOURCES = ["nsl-kdd", "unsw-nb15"]

# ════════════════════════════════════════════
#  NSL-KDD 配置
# ════════════════════════════════════════════

# NSL-KDD 列名（41个特征 + label + difficulty）
FEATURE_COLUMNS = [
    'duration', 'protocol_type', 'service', 'flag', 'src_bytes', 'dst_bytes',
    'land', 'wrong_fragment', 'urgent', 'hot', 'num_failed_logins', 'logged_in',
    'num_compromised', 'root_shell', 'su_attempted', 'num_root',
    'num_file_creations', 'num_shells', 'num_access_files', 'num_outbound_cmds',
    'is_host_login', 'is_guest_login', 'count', 'srv_count', 'serror_rate',
    'srv_serror_rate', 'rerror_rate', 'srv_rerror_rate', 'same_srv_rate',
    'diff_srv_rate', 'srv_diff_host_rate', 'dst_host_count', 'dst_host_srv_count',
    'dst_host_same_srv_rate', 'dst_host_diff_srv_rate',
    'dst_host_same_src_port_rate', 'dst_host_srv_diff_host_rate',
    'dst_host_serror_rate', 'dst_host_srv_serror_rate', 'dst_host_rerror_rate',
    'dst_host_srv_rerror_rate'
]

ALL_COLUMNS = FEATURE_COLUMNS + ['label', 'difficulty']

# 分类特征列
CATEGORICAL_COLUMNS = ['protocol_type', 'service', 'flag']

# 数值特征列
NUMERIC_COLUMNS = [c for c in FEATURE_COLUMNS if c not in CATEGORICAL_COLUMNS]

# NSL-KDD 攻击类型到 5 大类的映射
ATTACK_MAP = {
    'normal': 'Normal',
    # DoS 攻击
    'back': 'DoS', 'land': 'DoS', 'neptune': 'DoS', 'pod': 'DoS',
    'smurf': 'DoS', 'teardrop': 'DoS', 'mailbomb': 'DoS', 'apache2': 'DoS',
    'processtable': 'DoS', 'udpstorm': 'DoS',
    # Probe 探测
    'ipsweep': 'Probe', 'nmap': 'Probe', 'portsweep': 'Probe', 'satan': 'Probe',
    'mscan': 'Probe', 'saint': 'Probe',
    # R2L 远程访问
    'ftp_write': 'R2L', 'guess_passwd': 'R2L', 'imap': 'R2L',
    'multihop': 'R2L', 'phf': 'R2L', 'spy': 'R2L', 'warezclient': 'R2L',
    'warezmaster': 'R2L', 'sendmail': 'R2L', 'named': 'R2L',
    'snmpgetattack': 'R2L', 'snmpguess': 'R2L', 'xlock': 'R2L',
    'xsnoop': 'R2L', 'worm': 'R2L',
    # U2R 提权
    'buffer_overflow': 'U2R', 'loadmodule': 'U2R', 'perl': 'U2R',
    'rootkit': 'U2R', 'httptunnel': 'U2R', 'ps': 'U2R',
    'sqlattack': 'U2R', 'xterm': 'U2R',
}

# 攻击类别列表
ATTACK_CATEGORIES = ['Normal', 'DoS', 'Probe', 'R2L', 'U2R']

# ════════════════════════════════════════════
#  UNSW-NB15 配置
# ════════════════════════════════════════════

# UNSW-NB15 使用 CSV 自带表头，以下为选取的特征列
UNSW_FEATURE_COLUMNS = [
    'dur', 'proto', 'service', 'state',
    'spkts', 'dpkts', 'sbytes', 'dbytes',
    'rate', 'sttl', 'dttl', 'sload', 'dload',
    'sloss', 'dloss', 'sinpkt', 'dinpkt',
    'sjit', 'djit', 'swin', 'stcpb', 'dtcpb', 'dwin',
    'tcprtt', 'synack', 'ackdat',
    'smean', 'dmean', 'trans_depth', 'response_body_len',
    'ct_srv_src', 'ct_state_ttl', 'ct_dst_ltm', 'ct_src_dport_ltm',
    'ct_dst_sport_ltm', 'ct_dst_src_ltm',
    'is_ftp_login', 'ct_ftp_cmd', 'ct_flw_http_mthd', 'ct_src_ltm',
    'ct_srv_dst', 'is_sm_ips_ports',
]

UNSW_CATEGORICAL_COLUMNS = ['proto', 'service', 'state']
UNSW_NUMERIC_COLUMNS = [c for c in UNSW_FEATURE_COLUMNS if c not in UNSW_CATEGORICAL_COLUMNS]

# UNSW-NB15 攻击类别（原始标签直接使用，已经是类别名）
UNSW_ATTACK_CATEGORIES = [
    'Normal', 'Fuzzers', 'Analysis', 'Backdoor', 'DoS',
    'Exploits', 'Generic', 'Reconnaissance', 'Shellcode', 'Worms',
]

# API 配置
API_HOST = "0.0.0.0"
API_PORT = 8000

# 检测配置
ML_CONFIDENCE_THRESHOLD = 0.7  # ML 预测为攻击时的最低置信度阈值
