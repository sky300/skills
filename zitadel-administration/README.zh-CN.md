# ZITADEL 实例管理

[English](./README.md) | [简体中文](./README.zh-CN.md)

通过 API 运营自建的 [ZITADEL](https://zitadel.com/) 实例：服务账号及其凭证、管理员角色、项目、应用、组织、用户与角色授权。技能内包含精确的请求体结构、ZITADEL 并行提供的两代 API，以及那些看起来像 bug、实际是权限或上下文问题的故障形态。

**仓库**：https://git.nite07.com/nite/skills （子目录：`zitadel-administration/`）

## 覆盖内容

- **拿到访问权限**——创建服务账号（机器用户）、在正确的层级授予管理员角色，以及三种认证方式：个人访问令牌（PAT）、私钥 JWT、客户端凭证。含 ZITADEL API 的 audience scope（缺它每一次调用都会被拒）与各凭证的吊销方式。
- **项目与应用**——创建项目、项目角色、项目授权（project grant），以及 OIDC / API / SAML 应用的完整配置字段；生成客户端密钥与应用密钥；还有真正让用户「进入」应用的角色授权。
- **组织与用户**——创建组织（连同其首批管理员）、人类用户与机器用户、验证流程、元数据、实例设置、自定义域名，以及实例级与组织级的管理员授权。
- **API 约定**——每个服务走哪种传输、错误模型与错误码、分页与过滤、组织上下文、版本与弃用策略，以及「哪些任务至今仍只能用 legacy v1 API」的映射表。

## 决定排障方向的三个事实

1. **两代 API 并存。** 资源化的 v2 API 走 connectRPC（`POST /<package>.<Service>/<Method>` 带 JSON 请求体）；legacy v1（Management / Admin / Auth）是 REST，路径带 `/management/v1/…`、`/admin/v1/…`、`/auth/v1/…` 前缀，请求体用 camelCase。把两种习惯混用——在 v2 路径上发 v1 风格的字段名，或对 v2 调用发 v1 的组织头——通常就是「莫名其妙的报错」的来源。
2. **凭证有效不等于有权限。** 没有管理员角色的服务账号认证一切正常，但失败方式并不统一：有的端点返回 `404` 与 `membership not found`，有的返回 `200` 且带 `totalResult` 却没有条目数组，用户搜索只返回调用者自己。角色按资源层级授予，只有实例级角色能跨组织生效。
3. **路由注册随版本变化。** 某个版本存在的路径在另一个版本可能不存在，响应体也不止一种信封结构。先探测路由（401 = 存在，404 = 不存在），并从响应里读字段名，别假设。

## 安装

```bash
# 全局安装（所有项目可用）
npx skills add https://git.nite07.com/nite/skills.git -g -s zitadel-administration

# 仅列出可用技能（不安装）
npx skills add https://git.nite07.com/nite/skills.git --list
```

**手动安装**（任意 agent，包括 Hermes Agent）：

```bash
git clone https://git.nite07.com/nite/skills.git
cp -r skills/zitadel-administration <你的 agent 技能目录>/
```

`<你的 agent 技能目录>` 是刻意的占位符——技能从哪读取由使用者与其 agent 决定，本技能不假设具体位置。

## 何时使用

适合这些场景：

- 让自动化或 CI 任务在无人值守的情况下管理 ZITADEL
- 创建项目并把应用接上去（回调地址、客户端密钥、角色）
- 把一个客户作为新组织入驻，并配置它自己的管理员
- 排查「服务账号能认证但每次调用都被拒」
- 修改某项实例设置，或发现只有 legacy API 才能改它
- 收尾清理：轮换密钥、吊销个人访问令牌、停用集成账号

## 使用方式

1. 把**实例域名**（即 OIDC issuer）和一份**凭证**（个人访问令牌或服务账号密钥）交给 agent。密钥尽量放在文件或环境变量里，不要直接出现在对话中。
2. 用 ZITADEL 的概念描述目标（项目名、应用类型、组织），而不是端点名——技能会路由到对应的参考文件。
3. 预期每一次写操作之后都有**回读**，凡是与登录相关的改动都会做真实的端到端验证。配置能回读出来，还不等于登录可用。
4. 询问它针对哪个版本做过验证。路由注册跨版本会变，技能里的探测配方一条请求即可确定。

## 配置

技能从环境变量读取连接信息，这样一台机器配置一次，后续每个任务都能直接取用。

| 变量 | 内容 |
|---|---|
| `ZITADEL_DOMAIN` | issuer 主机名，不带协议（`id.example.com`） |
| `ZITADEL_TOKEN` | 现成的持有者令牌——个人访问令牌，或从别处换来的令牌 |
| `ZITADEL_USER_ID` | 服务账号的 user id，私钥 JWT 用 |
| `ZITADEL_KEY_ID` | 已注册公钥的 key id |
| `ZITADEL_KEY_FILE` | PEM 私钥文件的路径 |
| `ZITADEL_CLIENT_ID` | 机器用户的 id（即其用户名），客户端凭证用 |
| `ZITADEL_CLIENT_SECRET` | 机器用户的密钥 |
| `ZITADEL_ORG_ID` | 组织 id，供需要组织的调用使用 |

需要哪些取决于凭证类型：短任务只用 `ZITADEL_TOKEN` 就够；客户端凭证适合本身就持有密钥的服务；私钥文件适合密钥不应以字符串形式传递的场景。变量缺失是**要去问使用者**的信号，不要用看起来合理的值填上。

同名变量也在 `SKILL.md` 的 frontmatter 中声明，供支持环境变量声明的宿主使用（Hermes Agent 会把它们列给 agent，并把已设置的变量透传给沙箱命令）。那里每一条都刻意标为可选：不存在"必须凑齐某一组"的情况，因为凭证可以是令牌、客户端密钥，也可以是私钥文件。

## 目录结构

```text
zitadel-administration/
├── SKILL.md                          # 入口：心智模型、请求形态、硬规则、路由
├── README.md                         # 英文版（权威）
├── README.zh-CN.md                   # 本文件
├── references/
│   ├── authentication.md             # 服务账号、管理员角色、PAT / 私钥 JWT / 客户端凭证
│   ├── projects-and-applications.md  # 项目、角色、授权、OIDC/API/SAML 应用、密钥、角色分配
│   ├── organizations-users-instance.md # 组织、人类与机器用户、设置、域名、管理员
│   └── conventions.md                # 传输方式、错误模型、分页、组织上下文、legacy 覆盖映射
└── templates/
    └── service-account-token.sh      # 复制后自行适配：用服务账号私钥换取访问令牌
```

## 注意

- **PAT 不需要 audience，OAuth 令牌需要。** 通过私钥 JWT 或客户端凭证换来的令牌必须申请 `urn:zitadel:iam:org:project:id:zitadel:aud`，否则 API 会拒绝它——而它 introspection 检查却完全正常。
- **密钥与密钥文件只显示一次。** 创建时就要落进密钥管理器，没有回读路径。
- **legacy v1 API 不是可以省略的退路。** 若干设置没有 v2 的写接口，legacy Admin/Management 的 REST 路由是它们唯一的程序化途径。
- `templates/` 中的标记值与参考文件中的占位符是刻意的：它们由使用者决定，本技能不能替你选。

## 许可证

MIT
