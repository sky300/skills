# xianyu-operations

[English](./README.md) | [简体中文](./README.zh-CN.md)

给 AI agent 用的闲鱼（Xianyu / Goofish）操作：关键词搜索、商品详情、自己的商品列表、消息会话列表，以及发布/下架商品与发送消息（写操作，须用户逐次同意）。

闲鱼没有开放 API，也没有 OAuth 注册，所以访问凭据是一个登录态的浏览器会话导出的 cookie。本技能用两条传输通道承载它，你的环境支持哪条就走哪条：

- **纯 HTTP 的 mtop JSON 接口**（不需要浏览器）：商品详情、自己的商品列表、会话列表，以及你指定名称的任意内部 mtop 接口。
- **浏览器里的渲染 DOM**：关键词搜索——搜索页是客户端渲染的，且站点自己也是把浏览器径当作更稳的那条。

## 安装

```bash
npx skills add https://git.nite07.com/nite/skills.git -g -s xianyu-operations
```

或直接把目录拷进你的 agent skills 目录。

## 目录里有什么

三个模板加四份参考文档：

| 文件 | 作用 |
|---|---|
| `templates/mtop_request.py` | 可复制改造的片段：给 mtop 请求签名（也能顺手发出去）。**只用标准库**，除非你主动打开开关，否则不联网 |
| `templates/publish_item.py` | 发布商品的载荷组装（图片、价格、运费、类目、地址） |
| `templates/im_send_message.py` | 通过 WebSocket 网关发消息：整套 LWP 帧序列（需要 `websockets`） |
| `references/mtop-apis.md` | 已验证的接口、入参、字段路径、错误码、风控说明 |
| `references/browser-search.md` | 搜索提取器与浏览器操作步骤（纯文本） |
| `references/write-operations.md` | 发布 / 下架 / 发消息的配方，以及约束写操作的规则 |
| `references/browser-tool-setup.md` | 本机没有浏览器工具时怎么搭一个 |

代码刻意做窄，而且是模板而非成品工具：它只算那件必须逐字节准确的事，同时把"cookie 放在哪、用什么传输、失败怎么重试"留给你改。依赖环境、依赖判断的部分全部留在文档里，让 agent 能因地制宜，而不是等技能去适配自己的环境。

## 依赖

- Python 3（任意较新版本）。不需要任何第三方包：不需要 `requests`，也不需要 `playwright`。
- 一个已登录的闲鱼会话导出成 cookie（`unb` 与 `_m_h5_tk` 必填）。
- **只有做关键词搜索时才需要浏览器工具**——agent 自己有就用它自己的（任何能注入 cookie 的方式都行），否则按 `references/browser-tool-setup.md` 搭一个。商品详情、自己的列表、会话列表完全不需要浏览器。

## 用法

```bash
cp templates/mtop_request.py ./mtop_request.py
$EDITOR mtop_request.py     # 三处标记：cookie 来源、api/入参、是否由本机发送
python3 mtop_request.py
```

它会打印 URL、query string、form body 与起始 headers（把 `SEND = True` 打开就会直接发）。拿到结果后也可以自己发：`curl`、`requests`，或在已经打开 `www.goofish.com` 的页面里 `fetch()`。响应结构看 `references/mtop-apis.md`——商品数据在 `data.itemDO` 下。

关键词搜索是浏览器的事：照 `references/browser-search.md` 走，提取器与步骤都在那份文档里。

## 写操作

发布商品、下架商品、发送消息都已支持，但受三条规则约束：**具体内容先经用户同意**、写操作节奏约每分钟一次、每次写完都要回读验证（`SUCCESS` 只代表服务端收下了，不代表已生效）。不做批量操作，也不做自动化外联——那才是账号被限制的原因。

## 安全

cookie 文件等同于一个活着的账号会话。别进版本库、别进聊天记录、别贴进对话里；权限设成 `600`。要作废它，用闲鱼 App 里的"退出所有设备"。

## 说明

非官方：它说的是 Web 客户端内部接口，随时可能变。2026-09 对着真实响应验证过一次；请求形状、字段路径与已知响应码记录在 [`references/mtop-apis.md`](./references/mtop-apis.md)。
