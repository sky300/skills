# NapCat OneBot

[English](./README.md) | [简体中文](./README.zh-CN.md)

一个让 agent 通过自建 [NapCat](https://github.com/NapNeko/NapCatQQ) 协议端（对 [OneBot 11](https://github.com/botuniverse/onebot-11) 标准的 HTTP 实现）操作 QQ 的技能。

发送群消息与私聊、按需拉取聊天历史、查询群与好友、传文件，以及那些看着像脚本写错、实际是账号或容器问题的失败模式。

## 覆盖范围

- HTTP 请求/应答面：`POST {base}/<action>`，一次调用一个 JSON 对象，返回一个 JSON 信封
- 消息体用消息段数组（text、at、reply、image、record、video、face、forward），CQ 码字符串作为退路
- 按任务分组的接口清单：发送、读历史、查询、管理、文件与媒体
- 失败处理：token 被拒、`retcode` 语义、id 精度丢失、文件解析不了（协议端有自己的文件系统）
- 发送节奏——QQ 风控作用在账号上，不在进程上
- 每个事实的出处：五个权威来源各自覆盖什么、按什么顺序查证
- 推送类传输（反向 WebSocket、HTTP 上报）及其代价——当需求是「及时」而非「内容」时用
- 没有实例时的部署路径，含 rootless Podman 下「镜像 entrypoint 必须以 root 启动」这个坑
- 容器重建与重启后的免扫码登录持久化：两大数据卷挂载、四项协同环境变量与设备 GUID / MAC 固化机制
- 聊天窗口临时接管：后台事件监听器（Sensor）与主模型推理（Brain）解耦、NapCat WebSocket 服务端配置与拟人防风控规则

## 不覆盖

通用常态下的全量事件长连推送。本技能常规任务刻意改为按需拉历史，但在 `references/chat-takeover.md` 中为需要实时会话接管的场景提供了完整的解耦架构设计与实现蓝图。

## 安装

```bash
npx skills add https://git.nite07.com/nite/skills.git -g -s napcat-onebot
```

手动安装：把本目录复制到你的 agent 读取技能的目录即可。

## 前置条件

- 一个可访问的 NapCat 实例，且已配置 OneBot HTTP 服务端
- 两个由环境提供的值：
  - `NAPCAT_API_URL` —— OneBot HTTP 服务端的基地址，结尾不带斜杠
  - `NAPCAT_ACCESS_TOKEN` —— 该服务端配置的 token

本技能不带脚本：所有调用都是 agent 自行拼装的、有文档的请求。

## 目录结构

```text
SKILL.md                          # 入口：凭据、调用约定、规则
references/sources.md             # 权威来源、覆盖范围、查证顺序
references/api-actions.md         # 按任务分组的接口与参数
references/request-and-errors.md  # 信封、鉴权、retcode、id 精度
references/message-segments.md    # 消息段类型与字段（发送与接收）
references/events-and-push.md     # 推送类传输及其代价（需求是「及时」时）
references/chat-takeover.md       # 接管架构、WS 监听器代码模板与配置指引
references/login-persistence.md   # 容器持久化、四项环境变量与 GUID/MAC 固化
```

## 警告

用个人 QQ 号挂第三方协议端违反 QQ 用户协议，可能导致账号被限制。请使用可承受损失的账号，且不要群发。
