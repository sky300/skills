# Video Edit Planner 视频剪辑规划助手

[English](./README.md) | [简体中文](./README.zh-CN.md)

一个 agent skill，通过迭代式对话帮助规划视频剪辑——转录音频、按需提取关键帧、分析画面内容，最终生成结构化的剪辑规划。

**仓库地址**: https://git.nite07.com/nite/skills（子目录：`video-edit-planner/`）

## 功能特性

- **音频转录** — 内置 [funasr-script](https://github.com/modelscope/FunASR)，Fun-ASR-Nano 为主力转录（高质量，中文优化），SenseVoice 提取情感/事件标签
- **SRT 字幕生成** — 转录 JSON 一键转 `.srt`（纯标准库脚本，无需 venv）：长段按标点拆分、可选说话人前缀、UTF-8 BOM 输出
- **按需抽帧** — 基于 ffmpeg 的片段剪辑（`-c copy`）+ 场景变化检测 + 均匀采样，优先使用硬件加速（CUDA/NVDEC）
- **产物索引** — JSON 文件记录所有转录、剪辑片段和帧图片，使用相对路径，避免跨会话重复处理
- **视觉分析指引** — 二分查找式帧采样策略；兼容 agent 运行时提供的任何视觉模型
- **迭代式剪辑规划** — Markdown 表格输出（时间码、片段描述、操作建议、转场方式、备注），支持追问细化
- **双模式剪辑** — 长视频用删去法（删除无聊段落保证连贯），短视频/高光集锦用拼接法（提取精彩片段），也支持混合模式
- **Agent 无关** — 不包含任何平台特定工具名；兼容任何 agent 框架（Hermes、Claude Code、Codex 等）

## 快速开始

### 前置依赖

| 依赖 | 安装方式 |
|---|---|
| `ffmpeg` + `ffprobe` | Linux: `pacman -S ffmpeg` / `apt install ffmpeg`；macOS: `brew install ffmpeg`；Windows: `winget install Gyan.FFmpeg` |
| `uv` | Linux: `pacman -S uv`；macOS: `brew install uv`；Windows: `winget install astral-sh.uv`；备用: `pip install uv` |
| `python3` / Python 3.12 | Linux: `pacman -S python`；macOS: `brew install python@3.12`；Windows: `winget install Python.Python.3.12` |

### 安装 skill

**方式一：`npx skills add`（推荐）**

本 skill 兼容 [开放 agent skills 生态](https://www.npmjs.com/package/skills)，可以直接安装：

```bash
# 全局安装（跨项目可用）
npx skills add https://git.nite07.com/nite/skills.git -g -s video-edit-planner -y

# 安装到指定 agent
npx skills add https://git.nite07.com/nite/skills.git -g -s video-edit-planner -a claude-code -y

# 列出可用 skill（不安装）
npx skills add https://git.nite07.com/nite/skills.git --list
```

支持 73+ agent 框架，包括 Claude Code、Codex、Cursor、OpenCode 等。

**方式二：`git clone`（手动）**

```bash
git clone https://git.nite07.com/nite/skills.git
cp -r skills/video-edit-planner <你的 agent 技能目录>
```

把 `video-edit-planner/` 子目录复制到你的 agent 加载技能的位置。这个位置由你的环境决定，skill 里不写死——请查所用 agent 的文档，不要假定固定路径。

## 工作流程

```
1. 检查依赖（ffmpeg、uv、python3）
2. 收集输入（视频路径 + 音轨索引）
3. 询问剪辑需求（包括删去法 vs 拼接法策略选择）
4. 转录音频（如索引中已有缓存则跳过）
5. 按需提取片段和帧（agent 自主判断转录稿是否足够）
6. 用视觉模型分析帧（二分查找式采样）
7. 生成 Markdown 表格剪辑规划 + 总体建议
8. 迭代——用户追问，规划逐步细化
```

## 生成 SRT 字幕

转录完成后，一条命令把 JSON 转录稿转成字幕文件（纯 Python 标准库，任意 Python 3 可跑，无需 `uv sync`）：

```powershell
# Windows（PowerShell）
$SkillDir = "<path where this skill is installed>"
$VideoJson = "<video directory>\clip_track1_fun-asr-nano.json"
python "$SkillDir\scripts\transcription\convert_srt.py" $VideoJson
```

```bash
# Linux / WSL
SKILL_DIR="<path where this skill is installed>"
VIDEO_JSON="<video directory>/clip_track1_fun-asr-nano.json"
python "$SKILL_DIR/scripts/transcription/convert_srt.py" "$VIDEO_JSON"
```

两处占位符都是刻意的：skill 装在哪里、视频放在哪里，都由你的环境决定，运行时再解析。

SRT 输出到 JSON 同目录（同名 `.srt`）。转录模型可能把多句合并成一条长段（可达 15–20 秒），脚本会按中英文终止标点拆分子句、时间按字符比例分配，保证字幕可读；用 `--max-duration`、`--max-chars` 调整阈值，或 `--no-split` 禁用。其他选项：`--speaker-prefix`（加 `[SPK{n}]` 前缀）、`--bom`（UTF-8 BOM，兼容老播放器）、`--min-duration`。

> ASR 文本只能定位内容，不能当最终文案——发布前务必对照原音频校对字幕。

## 目录结构

```
video-edit-planner/
├── SKILL.md                          # Skill 定义（工作流程、指引、注意事项）
├── README.md                         # 英文说明（canonical）
├── README.zh-CN.md                   # 本文件（中文）
├── scripts/
│   ├── transcription/                # 内置 funasr-script（自包含 uv 项目）
│   │   ├── pyproject.toml
│   │   ├── uv.lock
│   │   ├── .python-version           # 锁定 3.12（funasr 的 editdistance wheel）
│   │   ├── README.md                 # 内置 uv 项目的说明（pyproject 的 readme 指向它）
│   │   ├── funasr_common.py          # 共享：ffprobe、音频提取、模型运行
│   │   ├── funasr_nano.py            # Fun-ASR-Nano 入口（默认，高质量）
│   │   ├── funasr_fast.py            # SenseVoice 入口（情感/事件标签）
│   │   ├── funasr_regular.py         # Paraformer 入口（对比用）
│   │   ├── merge_emotion.py          # 把 SenseVoice 标签合并进 Nano 转录
│   │   ├── main.py                   # 默认模块入口（委托 funasr_nano）
│   │   └── convert_srt.py            # JSON → SRT 转换（纯标准库，无需 venv）
│   ├── frames/
│   │   └── extract_frames.py         # 片段提取 + 抽帧（ffmpeg 封装）
│   └── index/
│       └── manage_index.py           # JSON 索引管理（8 个子命令）
└── references/
    ├── wsl-windows-uv-transcription.md       # WSL 与 Windows 执行环境选择、uv UNC 限制
    ├── windows-funasr-uv-setup.md            # Windows 主机环境准备、PyTorch/wheel 坑
    ├── frame-extraction-guide.md             # 视觉模型 token 成本、分辨率/批次指引
    ├── spot-verification-workflow.md         # 用单帧核对 ASR 转述内容
    └── editing-requirements-questionnaire.md # 完整问题清单与选项
```

## 索引文件

所有处理产物记录在 JSON 文件（`<视频文件名>.vedit.json`）中，存放在视频文件同目录：

- **transcriptions** — JSON 路径、音轨索引、时长
- **clips** — 起止时间、文件路径、提取原因
- **frames** — 时间戳、文件路径、场景分数、提取方法

所有路径存储为**相对路径**（相对于视频目录），移动整个目录不会破坏引用。JSON 文件可读性强，可用任意文本编辑器直接编辑。

## 许可证

MIT