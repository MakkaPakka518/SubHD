# SubHD Forward

Fork 仓库，部署到 Vercel，打开管理面板复制 `.js` 链接，导入 Forward/rex 直接使用。

Python + Scrapling 后端配合 rex 字幕模块。搜索按 IMDb ID 核对影片，电视剧同时核对季数和集数；只在选择字幕后启动浏览器完成下载流程。

## Fork → Vercel → 导入模块

1. [Fork 此仓库](https://github.com/MakkaPakka518/SubHD-Forward/fork) 到自己的 GitHub 账户。
2. [打开 Vercel](https://vercel.com/new)，选择 **Add New → Project**，导入刚刚 Fork 的仓库。Root Directory 保持仓库根目录。
3. Framework Preset 选择 **Container**。平台会根据 Dockerfile 构建 Python、Chromium 和系统依赖。
4. 设置环境变量：

   | 名称 | 内容 |
   | --- | --- |
   | `API_TOKEN` | 自己设置的至少 24 字符随机管理口令 |
   | `VERCEL_SUPPORT_LARGE_FUNCTIONS` | `1`，启用大体积函数支持 |

5. 部署完成后打开 Vercel 提供的正式域名，它就是管理面板。
6. 输入管理口令登录，点击 **复制模块链接**。
7. 在 Forward/rex 的模块管理中通过 URL 导入该链接并启用「SubHD 字幕」。无需再填写后端地址或口令。

管理面板提供运行状态、模块链接、`.js` 文件下载、缓存状态和清空缓存。模块使用独立访问凭据，不包含管理口令；模块链接应只分享给允许使用此实例的人。

当前 Vercel Container Runtime 和 Large Functions 为 Beta。需要目标账户支持这两个功能；Hobby 额度内可使用，函数最大 2 GB 内存、300 秒运行时间。构建镜像包含完整 Chromium，超过标准函数包体积，必须使用 Large Functions 路径。

如果模块导入或接口访问出现 Vercel 登录页面，检查项目的 Deployment Protection，并使用可供 rex 访问的正式部署地址。

## 使用

- 支持播放器提供的 IMDb ID；只有 TMDB ID 时，模块使用 rex 内置 TMDB 接口取得 IMDb ID。
- 不把其他模块的原始 `id` 拼成 SubHD 地址。缺少可验证的 IMDb/TMDB 身份时返回空列表。
- 剧集需要明确的 `season` 和 `episode`。用 `S01E02`、`1x02`、`S01E01-E03` 等文件标记核对集数；季包中找不到当前集时不返回候选。
- 默认中文，可在模块设置改为英语。结果页码默认为 1；需要较旧字幕时调整页码。
- ZIP、RAR、7z 等由 libarchive 读取，保留支持的文本字幕并转换为 ZIP；下载后 rex 的 `resolveSubtitleArchive` 从提供的真实相对路径中选择对应字幕。
- 搜索使用 HTTP；下载时在同一次调用、同一浏览器会话内准备下载页面、处理 Turnstile 并取得实际文件。

## 接口

| 路径 | 功能 |
| --- | --- |
| `GET /health` | 服务状态与口令配置状态 |
| `GET /` | 管理面板 |
| `GET /widget.js?key=...` | 面板生成的 rex 模块，自动包含后端地址和模块凭据 |
| `GET /api/admin/overview` | 管理面板状态，需要管理口令 |
| `POST /api/admin/cache/clear` | 清空实例下载缓存，需要管理口令 |
| `POST /api/search` | 字幕搜索，需要模块携带的独立访问凭据 |
| `GET /api/download/{字幕ID}.zip?ticket=...` | 使用搜索返回的一小时签名凭证下载，不在 URL 中传管理口令 |

搜索请求示例：

```json
{"imdbId":"tt4154796","type":"movie","language":"zh","page":1}
```

剧集请求示例：

```json
{"imdbId":"tt0944947","type":"tv","season":1,"episode":2,"language":"zh","page":1}
```

## 本地检查

```bash
docker build -t subhd-vercel .
node tests/test_widget.cjs
docker run --rm --memory=2g --cpus=1 \
  -v "$PWD/tests:/app/tests:ro" subhd-vercel \
  sh -c 'pip install httpx==0.28.1 && python -m unittest discover -s tests -v'
docker run --rm --memory=2g --cpus=1 \
  -v "$PWD/tests:/app/tests:ro" subhd-vercel \
  python tests/check_panel.py
```

浏览器测试使用真实 Chromium 和拦截的本地页面，核对会话 Cookie、准备下载请求、下载页面和文件响应，不向 SubHD 的下载接口发送测试请求。

本地启动服务时，在环境中设置 `API_TOKEN`，再运行：

```bash
docker run --rm --memory=2g --cpus=1 -e API_TOKEN -p 8000:80 subhd-vercel
```

## 运行边界

- 同一实例同时处理一个浏览器下载；繁忙时返回 503，稍后重试。
- 热实例按十分钟缓存、最多保留四个下载结果。冷启动会丢失缓存，不依赖本地文件持久化。
- 单个下载文件最多 20 MB，字幕解压数据最多 128 MB。返回 ZIP 使用流式响应。
- 搜索只核对所选结果页，未匹配的页面不代表整站没有字幕。
- 按网站正常下载验证流程请求文件。站点要求的人机验证可能失败，届时返回错误；服务器运行位置不能保证 Turnstile 自动通过。

## 当前验证状态

- 离线解析、IMDb/季集匹配、权限隔离、下载凭证和 ZIP 转换测试通过。
- 使用真实 Chromium 的拦截页面下载流程测试通过。
- 管理面板在 1440px、390px、320px 浏览器视口下通过登录、复制链接、获取模块、刷新和退出检查。
- 真实 SubHD 搜索和详情核对通过。
- 尚未验证真实 SubHD 下载验证码、Vercel 线上下载和 rex 实机字幕加载。浏览器模拟检查不是手机真机检查。

平台说明：[Vercel Container Runtime](https://vercel.com/docs/functions/runtimes/container)、[Python Docker 部署](https://vercel.com/kb/guide/vercel-docker-python-apps)、[函数限制](https://vercel.com/docs/functions/limitations)。
