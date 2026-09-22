# AFFiNE 管理

[English](./README.md) | [简体中文](./README.zh-CN.md)

管理运行中的自托管 AFFiNE 实例：某项配置到底由哪一层说了算、接入外部身份提供方、把内置 AI 指向自己的端点，以及通过 MCP 服务器把访问权交给 agent——包括这个服务器在两道闸门都打开之前会拒绝做什么。

**仓库**：https://git.nite07.com/nite/skills（子目录：`affine-administration/`）

## 覆盖内容

- **配置分层** —— 部署自身的配置文件与 `app_configs` 表、谁覆盖谁、怎么读当前生效值，以及两层为何在生效时机上不同。
- **OIDC 登录** —— 面板要的那段 JSON、让「看起来完全正确」的 provider 永不注册的 SSRF 防护、必须在应用容器内部做的解析检查，以及表现为通用 OAuth 报错的邮箱验证硬门槛。
- **Copilot BYOK** —— 允许自定义 AI 端点的开关、自托管实例的权益绕过、为什么探测按钮问的是「容器网络」而不是「浏览器网络」，以及首先要问的错误分类。
- **MCP 访问** —— 工具清单、决定写工具是否存在的那两道独立闸门、如何通过探测闸门驱动的分支来证明它已打开、API 做不了的凭据步骤，以及如何在镜像里检查任意闸门。
- **工作原则** —— 在动作真正发生的那一层判状态、以运行中的 bundle 作为「这个构建能做什么」的权威、开启任何开关前先说明代价。

## 安装

```bash
# 全局安装（所有项目可用）
npx skills add https://git.nite07.com/nite/skills.git -g -s affine-administration

# 只列出可用技能、不安装
npx skills add https://git.nite07.com/nite/skills.git --list
```

**手动安装**（任何 agent，含 Hermes Agent）：

```bash
git clone https://git.nite07.com/nite/skills.git
cp -r skills/affine-administration <你的 agent 的技能目录>/
```

`<你的 agent 的技能目录>` 是刻意的占位符——技能从哪里读取由使用者和 agent 决定，本技能不做假设。

## 何时使用

适用场景：

- 排查「用户改了设置却看不出效果」
- 接入或调试外部身份提供方
- 把内置 AI 指向自托管的 OpenAI / Gemini 兼容端点
- 通过 MCP 给 agent 开访问权，或排查「只能读不能写」
- 不想等 release notes，直接判断某个功能在这个构建里到底有没有

## 使用方式

1. 说明是哪个实例、改动做在哪一层——面板、配置文件还是环境变量。
2. 提供已有证据：报错日志行、探测返回的 `errorKind`、面板状态。
3. 预期它会去读**运行中的实例**（数据库行、容器自己的解析器与网络、镜像内的 bundle），而不是复述文档。
4. 凡是要用户提供的值——客户端密钥、MCP token、账号验证状态——预期会被追问，因为这些都无法从服务端取回。

## 项目结构

```text
affine-administration/
├── SKILL.md                        # 入口：两个层、身份、AI、MCP、工作原则
├── README.md                       # 本文件（英文，权威版）
├── README.zh-CN.md                 # 简体中文翻译
└── references/
    ├── config-layering.md          # 第二层、值得记住的键、读取方法
    ├── oidc-sso.md                 # OIDC 接线与那些看起来像配置错的故障
    ├── copilot-byok.md             # 自定义 AI 端点与探测诊断
    └── mcp-access.md               # 工具清单、写闸门、开关验证、凭据、bundle 检查
```

## 注意事项

- **数据库层优先。** 面板改动与配置文件改动冲突时以面板那行为准——先读它再推理。
- **「闸门存在但不可达」应当明说**，并一并说明开启它对别处造成的代价（升级频道、手机端用户看到的界面）。
- **验证要在动作真正发生的那一层做**，而不是在别处做等价检查。
- references 里的占位符都是刻意的：它们由使用者决定，本技能不代为取值。

## 许可

MIT
