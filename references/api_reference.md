# 好卡 API 数据结构参考

## API 端点

```
POST https://haokawx.lot-ml.com/ProductEn/Index2/8eabe44066833227
Content-Type: application/x-www-form-urlencoded
```

## 请求参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| title | string | "" | 产品名称关键词 |
| PriceTime | string | "全部" | 优惠时间（全部/半年/一年/二年） |
| LiuLiang | string | "全部" | 可用流量（全部/100G以内/100G-200G/200G以上） |
| Tonghua | string | "全部" | 通话时长（全部/100分钟以内/100-200分钟/200分钟以上） |
| Province | string | "全部" | 省份 |
| City | string | "全部" | 城市 |
| redbook | string | "" | 红书参数 |

## 响应格式

```json
{
  "code": 0,
  "data": [
    {
      "name": "广电飞原卡【41元220G】",
      "taocan": "39+2元220G（其中130G需参加2元权益包）",
      "isp": "广电",
      "nowPrice": 41,
      "priceUnitStr": "月租费用",
      "tyLiuliang": 220,       // 通用流量(G)
      "dxLiuliang": 0,         // 定向流量(G)
      "tonghua": 0,            // 通话分钟
      "age1": 18,              // 最小年龄
      "age2": 65,              // 最大年龄
      "isSelectNum": "无需选号",  // 或"支持选号"
      "isPhotos": "无需照片",     // 或"需传照片"
      "keywords": ["全国可发", "链接领取2元130G"],
      "sales": 24391806,       // 销量
      "shareUrl": "https://...",// 办理链接
      "tuiPath": "/producten/...", // 办理路径
      "path": "https://...",   // 产品图片URL
      "zhutui": false,         // 是否主推
      "kuanProID": 0,          // 0=普通卡, 非0=宽带产品
      "isGenericPro": 0,       // 是否通用产品
      "isKuanPro": 0           // 是否宽带产品
    }
  ]
}
```

## 注意事项

- API 可能返回空数据（需要浏览器 session），此时使用本地缓存
- `kuanProID != 0` 的是宽带产品，不在本技能推荐范围
- 宽带产品 URL 为 `/producten/kdindex/{id}`
- 通用产品 URL 为 `/producten/tyindex/{id}`
