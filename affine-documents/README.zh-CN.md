# AFFiNE 文档（agent 读写）

[English](./README.md) | [简体中文](./README.zh-CN.md)

以 agent 身份读写 AFFiNE（Notion 式文档 + 白板）文档：当 markdown 由工具写入而不是在编辑器里敲入时，什么能存活、为什么公式永远创建不了、如何区分完好与已损坏的文档，以及修复一篇文档实际需要做什么。

**仓库**：https://git.nite07.com/nite/skills（子目录：`affine-documents/`）

## 覆盖内容

- **读取** —— 实例暴露的读工具、为什么 markdown 回读是有损重建，以及如何改从存储的块树取真值。
- **写入** —— 工具写入的 markdown 里哪些结构会转成原生块、哪些不会，以及哪些 markdown 解析规则会把公式劈成两半。
- **公式** —— 修复必须遵守的两条分隔符规则（行内公式给开头的 `$` 留空格；`$$` 块内不得缩进），每条都来自可复跑的探针。
- **损坏判定** —— 配对错位的粘贴留下的指纹、哪些内容确实不可恢复，以及那个「像损坏其实无害」的空 latex run。
- **修复** —— 工序：先找完好母本 → 重建 → 由用户在编辑器粘贴 → 从存储快照验证（而不是看页面）。
- **验证** —— 用标记计数证明粘贴落地，包括那个「什么都证明不了」的计数，以及针对正文的抽样方法。

## 安装

```bash
# 全局安装（所有项目可用）
npx skills add https://git.nite07.com/nite/skills.git -g -s affine-documents

# 只列出可用技能、不安装
npx skills add https://git.nite07.com/nite/skills.git --list
```

**手动安装**（任何 agent，含 Hermes Agent）：

```bash
git clone https://git.nite07.com/nite/skills.git
cp -r skills/affine-documents <你的 agent 的技能目录>/
```

`<你的 agent 的技能目录>` 是刻意的占位符——技能从哪里读取由使用者和 agent 决定，本技能不做假设。

## 何时使用

适用场景：

- 想读取文档「实际存了什么」，而不是回读重建出来的样子
- 要往文档里写内容，先知道哪些内容会活不下来
- 排查「公式在文档里显示成源码」
- 修一篇被 markdown 往返流程弄坏公式的文档
- 想证明某次粘贴或写入真的落地，而不靠人肉看页面

## 使用方式

1. 说明是哪篇文档，以及你关心的是「忠实读取」还是「写入」。
2. 写入场景：预期它会先核对转换器支持什么，再对格式（尤其重公式材料）给出承诺。
3. 修复场景：预期它会先找同一内容的完好母本——被吞掉的正文不可能从损坏的文档里取回。
4. 修复的最后一步在**编辑器**里：由用户粘贴修正版 markdown；随后从存储快照做验证。

## 项目结构

```text
affine-documents/
├── SKILL.md                        # 入口：两条事实、规则、修复工序
├── README.md                       # 本文件（英文，权威版）
├── README.zh-CN.md                 # 简体中文翻译
├── references/
│   ├── markdown-and-formulas.md    # 转换对照表、分隔符探针、损坏指纹、验证
│   └── reading-documents.md        # 读工具、块词汇表、快照提取
├── scripts/
│   └── snapshot-strings.py         # 把快照 blob 解成可读的块字符串
└── templates/
    └── read-doc-snapshot.sh        # 复制后改：取快照行，读块树或读 markdown
```

## 注意事项

- **任何写入路径都创建不出公式。** AFFiNE 文档里的公式只能来自编辑器；这是结构性的，不是某种可以绕开的语法问题。
- **带公式的文档绝不能用工具整篇覆盖。** 回读读不出 latex 块与行内公式，据此计算的重写会把它们丢掉。
- **证据是存储的快照**，不是渲染出来的页面，也不是回读结果。
- `templates/` 里的待填值与 references 里的占位符都是刻意的：它们由使用者决定，本技能不代为取值。

## 许可

MIT
