# China Weather Query 中国天气查询

[English](./README.md) | [简体中文](./README.zh-CN.md)

用中国气象局公开的 `nmc.cn` 数据查国内天气：实况观测、7 天预报、官方预警、空气质量。无需 API key，无需注册，大陆网络可直连。

**仓库地址**：https://git.nite07.com/nite/skills（子目录：`china-weather-query/`）

## 功能

- **观测级实况**——气温、体感温度、湿度、降水、风向风力、日出日落
- **7 天预报**——昼夜间天气现象、气温与预期降水量
- **官方预警**——灾害类型、等级颜色、预警全文与气象局的公众指引
- **空气质量**——站点上报时的 AQI 数值与等级
- **内置站点索引**——2528 个站点，常规查询不联网
- **地名解析**——后缀不敏感（`大兴区` = `大兴`），重名时给出省份提示（`北京朝阳`、`北京 朝阳`、`辽宁朝阳`）
- **零依赖**——只用 Python 标准库，不需要 `pip install`

## 精度边界

站点是**县/区级**。全国站点列表里没有任何乡镇、街道或以下级别的条目，所以这个数据源给不出那个粒度的天气。

要按坐标取精确值，请用格点模式 API；注意那类数据是对全球模式网格（中国境内通常 9–13 km）做插值，"实况"字段是模式输出而非实测。

## 快速开始

### 前置条件

| 依赖 | 说明 |
|---|---|
| `python3` | 3.8 或更新；仅标准库 |

### 安装技能

本技能遵循[开放 agent skills 生态](https://www.npmjs.com/package/skills)格式，可直接安装：

```bash
# 全局安装（所有项目可用）
npx skills add https://git.nite07.com/nite/skills.git -g -s china-weather-query

# 只列出可用技能，不安装
npx skills add https://git.nite07.com/nite/skills.git --list
```

**手动安装**（任何 agent，包括 Hermes Agent）：

```bash
git clone https://git.nite07.com/nite/skills.git
cp -r skills/china-weather-query <your agent's skills directory>/
```

`<your agent's skills directory>` 是刻意的占位符——技能从哪个目录读取由用户和 agent 的环境决定，本技能不假设固定位置。

### 用法

```bash
python3 scripts/weather.py "上海"             # 实况 + 7 天预报
python3 scripts/weather.py "大兴区" --days 3   # 缩短预报天数
python3 scripts/weather.py "北京 朝阳" --json  # 机器可读
python3 scripts/weather.py --search "深圳"     # 查站点代码
```

重建站点索引请运行 `scripts/build_index.py`——见下文[重建索引](#重建索引)。

### 查站点代码

`scripts/cities.json` 存着 2528 个站点（约 150 KB）——**不要整份读**。问脚本就行，它只打印匹配行，且完全不联网：

```bash
python3 scripts/weather.py --search "深圳"
```

```
CODE    CITY        PROVINCE
AhpEU   深圳        广东省
```

匹配是对城市名、省份名、站点代码做子串匹配，最多返回 30 行（`--limit` 可改）。脚本答不上来时，用过滤器收窄文件而不是读全文——索引是一行一个站点，`grep -m` 或 `jq -c '.[] | select(...)'` 只返回你要的行。**务必限制输出量。**

### 重建索引

`scripts/build_index.py` 会重新拉取全国站点列表（35 次请求）并重写 `cities.json`。它是**可选动作且需要用户同意**——不属于任何查询流程，agent 不应自行发起：

```bash
python3 scripts/build_index.py --dry-run   # 只拉取并报告差异，不写文件
python3 scripts/build_index.py             # 原地重建
```

构建是全有或全无的（某个省拉失败会让站点悄悄缺失，所以 34 个省全部到齐才写盘），会打印变更内容，并折叠上游的重名条目。**先跑 `--dry-run`。**

### 输出示例

```
广东省 深圳 [AhpEU]
  Now (2026-09-16 21:40): 多云  26.8°C  feels 30.6°C
       humidity 76%, wind 东南风 微风, sun 06:10–18:26
  Forecast (issued 2026-09-16 20:00):
    2026-09-16: day -- / night 多云 25°C
    2026-09-17: day 多云 32°C / night 晴 25°C
  Air quality: AQI 42 优 (updated 2026-09-16 21:00)
```

出现 `--` 或整行缺失，说明上游给的是 `9999` 哨兵值；这些值被丢弃而不是照原样渲染。

### 城市名与重名

地名解析不需要行政区划后缀——`大兴区` 和 `大兴` 都认，`南昌` 与 `南昌县` 保持区分。

当名字存在于多个省份时，脚本以退出码 `2` 结束并列出候选，而不是猜：

```
$ python3 scripts/weather.py "朝阳"
"朝阳" matches 2 stations — ask the user which one:
  1. 北京市 / 朝阳
  2. 辽宁省 / 朝阳
```

加省份前缀重跑，前缀相连或空格分隔都可以：

```bash
python3 scripts/weather.py "北京朝阳"
python3 scripts/weather.py "北京 朝阳"
```

退出码：`0` 成功 · `1` 无匹配站点 · `2` 重名歧义 · `3` 上游不可达或站点索引缺失。

## 项目结构

```
china-weather-query/
├── SKILL.md                  # 技能定义：工作流、坑、验证方法
├── README.md                 # 英文说明（权威版本）
├── README.zh-CN.md           # 本文件（中文）
├── scripts/
│   ├── weather.py            # 查询、地名解析与渲染
│   ├── build_index.py        # 从上游重建 cities.json（可选动作）
│   └── cities.json           # 内置站点索引（2528 个站点）
├── tests/
│   └── test_build_index.py   # 构建、校验与差异逻辑（不联网）
└── references/
    └── nmc-api.md            # 接口文档与实测字段细节
```

## 数据来源

数据来自 `https://www.nmc.cn/rest/` 下的公开 JSON 接口，也就是气象局预报网站自己用的那套。接口未公开文档，也没有公布的速率限制。数据版权归中国气象局所有。

## 许可证

MIT
