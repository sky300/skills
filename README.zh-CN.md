# Skills

[English](./README.md) | [简体中文](./README.zh-CN.md)

一组符合[开放 agent skills 生态](https://www.npmjs.com/package/skills)规范的 agent 技能集合——可移植的 `SKILL.md` 包，让 AI 编码助手获得新的工作流能力。

## 技能列表

- **[quadlet-creator](./quadlet-creator/)** — 把 `docker run` 命令、Docker Compose 配置或自托管部署文件转换成可审阅的 Podman Quadlet 输出；含 rootless 运行时身份（UserNS/UID）排障。
- **[video-edit-planner](./video-edit-planner/)** — 通过迭代式对话规划视频剪辑：转录音频（FunASR）、提取情感/事件标签与关键帧、分析画面，产出结构化的剪辑/转场/拼接方案。
- **[discord-user-operations](./discord-user-operations/)** — 以普通用户身份操作 Discord：读取、搜索、发帖。
- **[china-weather-query](./china-weather-query/)** — 用中国气象局官方数据查国内天气：实况、预报、预警、空气质量。
- **[chinese-humanizer](./chinese-humanizer/)** — 中文表述拟人化：去掉简体中文里的公文腔、名词化、翻译腔与模板节奏，保留事实、术语与作者声口。
- **[xianyu-operations](./xianyu-operations/)** — 闲鱼（Goofish）操作：关键词搜索、商品详情、自己的商品列表、消息会话，以及发布/下架商品与发消息（写操作需用户逐次同意）。mtop JSON 接口走纯 HTTP，只有搜索需要浏览器。

## 安装

```bash
# 安装全部技能
npx skills add https://git.nite07.com/nite/skills.git -g --all

# 单独安装
npx skills add https://git.nite07.com/nite/skills.git -g -s quadlet-creator

# 仅列出可用技能（不安装）
npx skills add https://git.nite07.com/nite/skills.git --list
```

兼容 73+ agent 框架，包括 Claude Code、Codex、Cursor、OpenCode 等。手动安装与使用说明见各技能目录内的 README。

## 编写规则

本仓库每个技能都要遵守的规则——内容以英文为准、禁止硬编码路径、不留密钥、结构与写作约定——见 [AGENTS.md](./AGENTS.md)。

## 仓库结构

每个顶层目录都是一个自包含的独立技能（`SKILL.md` 加可选支持文件），遵循开放 agent skills 格式：

```text
china-weather-query/      # SKILL.md + references/ + scripts/ + tests/ + README
chinese-humanizer/        # SKILL.md + references/ + README
discord-user-operations/  # SKILL.md + references/ + README
xianyu-operations/        # SKILL.md + references/ + templates/ + README
quadlet-creator/          # SKILL.md + references/ + templates/ + README
video-edit-planner/       # SKILL.md + references/ + scripts/ + README
```

其中若干技能原以独立仓库维护（那些仓库已归档并删除），现已合并到本仓库。
