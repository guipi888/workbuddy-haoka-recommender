# 运营商大额流量卡推荐 · WorkBuddy Skill

运营商大额流量卡推荐技能。当用户询问流量卡、手机卡、套餐推荐、大流量卡、便宜流量卡等问题时使用。从鸣日科技店铺抓取全部76+张流量卡数据，根据用户需求（省份、预算、流量、通话、运营商偏好、年龄等）智能筛选匹配的卡片推荐。

## 特性

- 请参考 SKILL.md 中的详细说明

## 安装

### WorkBuddy 技能市场（推荐）

在 WorkBuddy 中搜索「运营商大额流量卡推荐」一键安装。

### 手动安装

```bash
git clone https://github.com/guipi888/workbuddy-haoka-recommender.git \
  ~/.workbuddy/skills/haoka-recommender
```

### 环境依赖

请参考 SKILL.md 中的环境要求章节

## 使用

```bash
python3 scripts/pipeline.py <参数>
```

详细参数请参考 SKILL.md

## 输出

请参考 SKILL.md

## 项目结构

```
.gitignore
LICENSE
SKILL.md
assets
assets/cards_cache.json
assets/icon.png
references
references/api_reference.md
scripts
scripts/scraper.py
```

## 关于作者

**桂皮 Guipi** — AI Agent 开发者 · 超级个体践行者
专注 AI 效率工具与一人公司方法论，帮普通人用 AI 成为超级个体

| 平台 | 账号 |
|------|------|
| 📱 小红书 | [桂皮AI实战](https://www.xiaohongshu.com/user/profile/5a409dda44363b313b9d7e15) |
| 🎬 抖音 | [桂皮AI实战](https://v.douyin.com/QJRjHGAtrvA/) |
| 📺 视频号 | 微信内搜「桂皮AI实战」|
| 💬 公众号 | 微信搜「桂皮AI实战」|
| 🌟 知识星球 | [AI超级个体](https://t.zsxq.com/guSUk) — AI工具 · 创作 · 产品 · 流量 · 变现 |
| 🐙 GitHub | [guipi888](https://github.com/guipi888) |
| 💬 微信 | guipi996（注明来意）|

## License

MIT License — 详见 [LICENSE](./LICENSE)
