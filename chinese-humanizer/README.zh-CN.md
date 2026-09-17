# Chinese Humanizer 中文表述拟人化

[English](./README.md) | [简体中文](./README.zh-CN.md)

中文优先的技能：把简体中文里像 AI 写的部分改回人话——公文腔、名词化、翻译腔句式、模板节奏；事实、术语与作者声口都保留。

**仓库地址**：https://git.nite07.com/nite/skills（子目录：`chinese-humanizer/`）

## 它解决什么

模型写的中文有两个常见的来源层：一层是公文腔（官方文书和通稿语料喂出来的「赋能」「抓手」「闭环」），一层是翻译腔（英文的句子骨架穿中文的字，「进行了研究」对应 conduct a study）。再叠上模型自身的回归均值和 RLHF 奖励过的讨好写法，就成了读起来「没有错但没有人」的那种文字。

这个技能给出判断标准、改写动作和边界：哪些要改、哪些不能动、哪些只是编辑经验、哪些有语料统计支持。

## 安装

```bash
npx skills add https://git.nite07.com/nite/skills.git -g -s chinese-humanizer
```

或者直接把目录拷进你的 agent skills 目录：

```bash
git clone https://git.nite07.com/nite/skills.git
cp -r skills/chinese-humanizer <你的 agent skills 目录>
```

`<你的 agent skills 目录>`是有意留的占位符：skills 放在哪里由你的环境决定，技能不替你假设。

## 结构

```
chinese-humanizer/
├── SKILL.md                    # 主文件：机制、判断尺子、工作流、改写动作库、自查表
├── README.md                   # 英文说明（权威版本）
├── README.zh-CN.md             # 本文件（中文）
├── references/
│   ├── symptoms.md             # 症状目录，四层结构，含触发条件与保护项
│   ├── translationese.md       # 欧化中文与翻译腔（余光中 13 类病症 + 英译中 12 条修正）
│   ├── vocabulary.md           # 中文 AI 高频词分级表、替换建议、白名单
│   ├── evidence.md             # 实测数据与证据等级，检测器为什么不能作为依据
│   ├── boundaries.md           # 不该改的清单、体裁矩阵、声音校准
│   └── sources.md              # 素材出处、许可证、引用时要注意的地方
```

## 用法

```
用 chinese-humanizer 把这段改得像人写的，保留事实和术语。
```

```
检查这篇博客最明显的 AI 腔，先列清单再改。
```

也可以让它附带写作样本做声音校准，样本优先于技能里的词表建议。

## 依据

规则来自公开语料研究（CCL 2023/2025、ACL 2024、EMNLP 2024、arXiv 2402.01158、arXiv 2304.02819）、余光中 1987 年论欧化中文的文章，以及六个开源 humanizer 技能的规则设计。逐项出处见 `references/sources.md`；哪些结论有统计支持、哪些只是编辑经验，见 `references/evidence.md`。

## 边界

不做作者身份鉴定，不承诺"改完检测不出来"，不用于伪造身份或学术不端。正式文体、术语、引语、代码都不改。

## 许可证

MIT
