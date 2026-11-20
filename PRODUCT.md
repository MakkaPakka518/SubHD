# SubHD Forward

## Platform

web

## Stack

Python、FastAPI、Scrapling、Chromium，部署到 Vercel 容器运行时。管理面板采用用户确认的原生 HTML、CSS、JavaScript。

## Users

希望使用 SubHD 字幕的 Forward/rex 用户。通过 Fork 仓库与 Vercel 导入部署自己的实例，不维护 VPS。

## Product Purpose

部署域名打开管理面板，用户登录后复制生成的 `.js` 链接，在 Forward/rex 导入后直接使用。

## Operating Context

用户在 Vercel 设置管理口令，面板生成独立的模块访问凭据。模块自动包含后端地址和模块凭据，不包含管理口令。

## Capabilities and Constraints

搜索核对 IMDb 与季集；下载使用 Scrapling 浏览器。面板展示当前实例状态、模块导入链接、缓存与最近下载结果。桌面和手机均需可用。

真实 SubHD 下载验证成功率和 rex 实机字幕加载仍需实测，不能把浏览器启动或本地模拟下载视为成功通过站点验证。

## Product Principles

- 主操作是复制可直接导入的模块链接。
- 面板状态来自实际后端结果。
- 模块访问权限与管理权限分离。
- 使用低门槛部署与平台原生控件。
