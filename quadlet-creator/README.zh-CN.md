# Quadlet Creator

[English](./README.md) | [简体中文](./README.zh-CN.md)

Quadlet Creator 是一个把 Docker 部署输入转换为 Podman Quadlet 输出的 skill。

## 功能

- 将 `docker run` 命令转换为 Quadlet 单元文件
- 将 Docker Compose 配置转换为 Quadlet 部署结果
- 分析 GitHub 仓库中的自托管部署文件
- 在部署需要时保留 env 文件、挂载配置、初始化资产和辅助脚本
- 将庞杂的 env 模板整理成少量部署决策
- 提供部署、验证和排障指引

## 安装

```bash
npx skills add https://git.nite07.com/nite/skills.git -g -s quadlet-creator
```

## 适用场景

适合在这些场景中使用：

- 将服务从 Docker 迁移到 Podman Quadlet
- 将 Compose 栈转换为 Quadlet 布局
- 审查仓库中的自托管部署文件
- 先生成文件审阅，再决定是否安装
- 验证或排查生成后的 Quadlet 文件

## 使用方式

1. 提供一种输入：
   - 一条 `docker run` 命令
   - 一个 Compose 文件或 Compose 项目
   - 一个 GitHub 仓库 URL
   - 一组需要审查或清理的现有 Quadlet 文件
2. 说明你的目标：
   - 映射建议
   - 部署设计
   - 可审阅的可运行结果
3. 确认域名、主机路径、凭据、存储方案或可选服务等部署取值。
4. 在应用前审阅生成结果。

## 示例请求

```text
把这条 docker run 命令转换成 Quadlet，并解释映射关系。

审查这个 compose.yaml，并给出一个 Podman Quadlet 布局方案。

根据这个仓库的自托管部署生成可审阅的 Quadlet 文件。

帮我把这套服务迁移到 rootless Podman，并保留 env-file 工作流。
```

## 常见产物

- Quadlet 单元文件
- env 文件或 env 增量文件
- 用于 install、reload、start、stop、restart、uninstall 的辅助脚本
- 部署说明与验证指引

## 说明

- 在安装前审阅生成结果。
- 对部署相关取值先确认，再生成结果。
- Docker Compose 与 Quadlet 不完全等价时，要明确说明行为变化。

## 许可证

MIT
