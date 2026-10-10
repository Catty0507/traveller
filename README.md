# 出逃计划 · 天气旅行推荐

输入空闲时间和想去的地方,结合真实天气预报,由大模型推荐 1-3 个最值得去的目的地,并附上景点攻略。

- **前端**:React + Vite + TypeScript + Tailwind CSS(端口 5173)
- **后端**:Python FastAPI(端口 8000)
- **天气**:Open-Meteo(免费,无需 key,支持未来 16 天)
- **大模型**:任意 OpenAI 兼容接口(通义千问 / Kimi / 智谱 GLM / DeepSeek 等)

## 快速开始

### 0. 前置要求

- Python ≥ 3.10(`brew install python@3.12`)
- Node.js ≥ 20

### 1. 配置大模型 API key

```bash
cp backend/.env.example backend/.env
```

编辑 `backend/.env`,填入三个值:

```ini
LLM_API_KEY=你的key
LLM_BASE_URL=接口地址      # 智谱: https://open.bigmodel.cn/api/paas/v4
                           # Kimi: https://api.moonshot.cn/v1
                           # 通义: https://dashscope.aliyuncs.com/compatible-mode/v1
                           # DeepSeek: https://api.deepseek.com/v1
LLM_MODEL=模型名           # 如 glm-4-plus / moonshot-v1-8k / qwen-plus / deepseek-chat
```

> 不配置也能启动:天气推荐之外的功能会提示缺少配置;配置后无需改代码。

### 2. 安装依赖

```bash
make install
```

### 3. 启动(两个终端)

```bash
# 终端 1:后端
make backend

# 终端 2:前端
make frontend
```

打开 <http://localhost:5173> 即可使用。

## 部署上线(Render + 静态托管)

### 后端(Render Web Service)

1. 新建 Web Service 连接仓库,**Root Directory** 填 `backend`
2. **Build Command**:`pip install -r requirements.txt`
3. **Start Command**:`uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 2 --proxy-headers`
4. **Health Check Path**:`/api/health`
5. **环境变量**(在 Render 控制台配置,线上值会覆盖本地 .env):

   | 变量 | 说明 |
   |---|---|
   | `PYTHON_VERSION` | `3.12` |
   | `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL` | 同本地 `.env` |
   | `CORS_ORIGINS` | 线上前端域名,逗号分隔,如 `https://your-frontend.vercel.app` |

### 前端(静态站点)

1. 构建命令 `npm run build`,发布目录 `dist`(Vercel / Render Static Site / Cloudflare Pages 均可)
2. 环境变量 `VITE_API_BASE=https://你的后端域名`(不带末尾斜杠;留空则请求同域 `/api`)

## 使用方式

- **选择想去的地方**:多选候选城市(如 杭州/成都/巴黎),系统结合天气挑选最值得去的 1-3 个
- **按偏好推荐**:选择偏好标签(海边/古镇/美食/滑雪…),系统主动推荐契合的目的地
- **空闲时间**:选日期范围或点快捷按钮(本周末/未来3天/未来7天),最远 16 天内(受天气预报窗口限制)
- 推荐卡片附逐日天气、推荐理由与出行提示;攻略由 AI 按行程天数定制(景点/每日行程/美食/穿衣雨具贴士)

## 测试

```bash
make test
```

## API 一览

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | /api/cities | 精选城市列表/搜索(`q` 关键词、`tag` 标签) |
| GET | /api/cities/search | 全球城市搜索(双源 Open-Meteo + Photon,中文查不到时自动翻译复查,精选库优先合并) |
| GET | /api/tags | 偏好标签 |
| POST | /api/recommend | 天气 + LLM 推荐 1-3 个目的地 |
| POST | /api/guide | 单城市 AI 攻略(前端并行调用) |
| POST | /api/drive | 自驾规划:时间充裕给往返自驾玩法,时间不足改推目的地租车 |
| GET | /api/health | 健康检查(含 llm_configured) |

## 项目结构

```
backend/
  app/
    main.py            # FastAPI 入口、CORS、异常处理
    config.py          # .env 配置(LLM_API_KEY / LLM_BASE_URL / LLM_MODEL)
    data/cities.json   # 内置近 200 个精选全球城市(坐标/标签/建议天数)
    data/discovered_cities.json  # 全球搜索发现的动态城市自动登记于此(重启不丢)
    schemas/           # Pydantic 请求/响应模型
    services/          # 天气(Open-Meteo+缓存)、LLM 客户端、推荐、攻略
    routers/           # cities / recommend / guide
  tests/               # pytest
frontend/
  src/
    api/               # 类型与 fetch 封装
    hooks/useRecommend.ts  # 推荐 → 并行攻略状态机
    components/        # 输入区 / 推荐卡片 / 天气条 / 攻略区
```
