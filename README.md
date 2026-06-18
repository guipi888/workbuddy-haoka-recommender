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

## 作者

**桂皮AI实战**



## License

MIT License — 详见 [LICENSE](./LICENSE)
