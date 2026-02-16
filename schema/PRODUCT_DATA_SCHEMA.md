# Product Data Schema v1.0

统一的产品数据格式，用于：
- **Etsy Listing Batch Generator** - 批量生成 Listing 信息
- **NanoBanana Batch Generator** - 批量生成图片 Prompts

---

## 文件结构

```
/products/
├── MentorArtCircle/              # 店铺
│   ├── rings/                    # 品类
│   │   └── R001/                 # 产品
│   │       ├── product_data.json # ← 这个文件
│   │       ├── R001_01.jpg
│   │       └── R001_02.jpg
│   └── earrings/
│       └── E001/
└── MoissaniteStore/
    └── necklaces/
        └── N001/
```

---

## Schema 定义

### 产品标识

| 字段 | 必填 | 类型 | 说明 |
|------|------|------|------|
| `$schema` | ❌ | string | 固定值: `product_data_schema_v1` |
| `product_id` | ✅ | string | 产品编号，如 `R001`, `E002` |
| `product_path` | ✅ | string | 产品文件夹的绝对路径 |

### 产品分类

| 字段 | 必填 | 类型 | 有效值 |
|------|------|------|--------|
| `category` | ✅ | enum | `rings` `earrings` `necklaces` `bracelets` `pendants` |
| `shop` | ❌ | string | 店铺名，如 `MentorArtCircle` |
| `style` | ✅ | enum | 见下表 |
| `target_audience` | ✅ | enum | `male` `female` `neutral` |
| `occasion` | ❌ | enum | `engagement` `wedding` `promise` `anniversary` `daily` `gift` `null` |
| `materials` | ✅ | array | 结构化材质列表，见下表 |
| `main_stone` | ❌ | object | 主石详情（材质+克拉+形状），见下表 |
| `secondary_stone` | ❌ | object | 副石详情，结构同 main_stone |
| `product_size` | ✅ | object | **产品尺寸（必填，NanoBanana 做图必需）**，见下表 |
| `ring_size_us` | ❌ | string | 戒指 US 尺寸（仅 rings），用于 Etsy listing，如 "US 7-14" |

#### `style` 有效值

| 值 | 中文 | 适用场景 |
|---|------|----------|
| `tibetan` | 藏式 | 藏银、曼陀罗、宗教符号 |
| `pearl` | 珍珠 | 珍珠类首饰 |
| `zirconia` | 锆石 | 锆石镶嵌 |
| `moissanite` | 莫桑石 | 莫桑石镶嵌 |
| `vintage` | 复古 | 古董风格、做旧 |
| `minimal` | 极简 | 简约设计 |
| `bohemian` | 波西米亚 | 民族风、自然元素 |

#### `occasion` 有效值

| 值 | 中文 | 适用场景 |
|---|------|----------|
| `engagement` | 订婚 | 求婚戒指、订婚饰品 |
| `wedding` | 婚礼 | 婚戒、结婚套装 |
| `promise` | 承诺 | 情侣对戒、承诺戒指 |
| `anniversary` | 周年 | 纪念日礼物 |
| `daily` | 日常 | 日常佩戴 |
| `gift` | 礼物 | 通用送礼 |
| `null` | 无 | 无特定场景 |

#### `materials` 有效值

结构化数组，从 `basic_info` 提取，使用标准化英文值：

| 值 | 中文 | 关键词匹配 |
|---|------|-----------|
| `sterling_silver` | 925银 | S925, 925银, 纯银, sterling silver |
| `gold` | 金 | 金, 黄金, gold, 18K, 14K |
| `white_gold` | 白金 | 白金, 铂金, white gold, platinum |
| `rose_gold` | 玫瑰金 | 玫瑰金, rose gold |
| `copper` | 铜 | 铜, copper, brass |
| `stainless_steel` | 不锈钢 | 不锈钢, 钛钢, stainless steel |
| `moissanite` | 莫桑石 | 莫桑石, moissanite |
| `diamond` | 钻石 | 钻石, diamond |
| `zirconia` | 锆石 | 锆石, zirconia, CZ |
| `pearl` | 珍珠 | 珍珠, pearl |
| `enamel` | 珐琅 | 珐琅, enamel |
| `jade` | 玉 | 玉, 翡翠, jade |
| `turquoise` | 绿松石 | 绿松石, turquoise |

#### `main_stone` / `secondary_stone` 对象结构

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `type` | enum | ✅ | 宝石类型，见 materials 有效值 |
| `carat` | number | ❌ | 克拉数，如 0.5, 1, 2, 3 |
| `shape` | enum | ❌ | 切割形状，见下表 |
| `size` | string | ❌ | 尺寸，如 "6.5x6.5mm", "3x6mm" |

#### `shape` 有效值

| 值 | 中文 | 说明 |
|---|------|------|
| `round` | 圆形 | 圆形明亮式切割 |
| `heart` | 心形 | 心形切割 |
| `oval` | 椭圆 | 椭圆形切割 |
| `pear` | 梨形 | 水滴形切割 |
| `marquise` | 马眼 | 橄榄形切割 |
| `square` | 方形 | 公主方切割 |
| `emerald` | 祖母绿 | 阶梯形切割 |
| `cushion` | 垫形 | 枕形切割 |

#### `product_size` 对象结构

**⚠️ 必填字段 — NanoBanana 做图时必须有明确物理尺寸，否则视觉失真**

**重要:** `product_size` 是产品的**物理尺寸 (mm)**，不是戒圈尺寸 (US size)。NanoBanana 需要知道产品实际有多大才能正确生成比例。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `dimensions` | string | ✅ | **物理尺寸 (mm)**，如 "Band 4mm, Face 12x12mm" |
| `source` | enum | ✅ | 数据来源: `excel`, `estimated`, `measured` |
| `notes` | string | ❌ | 补充说明 |

**source 有效值:**

| 值 | 说明 |
|---|------|
| `excel` | 从 Excel 表格直接获取 |
| `estimated` | 根据品类规则估算（如女戒 Band 4mm, Face 12mm） |
| `measured` | 从图片测量或人工输入 |

**按品类的尺寸格式 (物理尺寸 mm):**

| Category | dimensions 格式 | 示例 |
|----------|-----------------|------|
| `rings` | 戒面/带宽 mm | "Band 4mm, Face 12x12mm", "Band 8mm" |
| `earrings` | 长x宽 mm | "15x20mm", "Drop length 45mm" |
| `necklaces` | 链长 + 吊坠尺寸 | "Chain 45cm, Pendant 12x15mm" |
| `bracelets` | 内径或长度 | "Inner 60mm", "Length 18cm" |
| `pendants` | 长x宽 mm | "25x18mm" |

**⚠️ 戒圈尺寸 (US size) 是给 Etsy Listing 用的，不是 product_size！**

### 产品描述

| 字段 | 必填 | 类型 | 说明 |
|------|------|------|------|
| `basic_info` | ✅ | string | Free text，包含材质、尺寸、特点等 |
| `earring_design_type` | ❌ | enum | 仅 `category=earrings` 时**必填** |

#### `earring_design_type` 有效值

| 值 | 中文 | 说明 | 拍摄角度要求 |
|---|------|------|-------------|
| `flat_front` | 平面正面 | 图案只在正面 | 正面或微侧 (0-30°) |
| `3d_sculptural` | 立体雕塑 | 360° 可观 | 任意角度 |
| `drop_dangle` | 吊坠/流苏 | 重点是垂坠效果 | 侧面或 3/4 侧 |

### 图片列表 (`images[]`)

| 字段 | 必填 | 类型 | 说明 |
|------|------|------|------|
| `filename` | ✅ | string | 文件名（不含路径） |
| `angle` | ✅ | enum | 拍摄角度 |
| `type` | ✅ | enum | 图片类型 |
| `is_hero` | ✅ | boolean | 是否为主图候选 |
| `notes` | ❌ | string | 补充说明 |

#### `angle` 有效值

| 值 | 中文 | 说明 |
|---|------|------|
| `front` | 正面 | 0° |
| `side` | 侧面 | 90° |
| `back` | 背面 | 180° |
| `3/4` | 3/4 侧 | 45° |
| `top` | 俯视 | 从上往下 |
| `bottom` | 仰视 | 从下往上 |

#### `type` 有效值

| 值 | 中文 | 说明 |
|---|------|------|
| `product_only` | 纯产品 | 白底或简单背景 |
| `wearing` | 佩戴 | 模特佩戴效果 |
| `macro` | 微距 | 细节特写 |
| `with_props` | 带道具 | 有场景道具 |
| `packaging` | 包装 | 包装盒/礼盒 |

---

## 验证规则

1. `images` 数组至少 1 张图片
2. 至少 1 张图片 `is_hero: true`
3. `category: earrings` 时必须填 `earring_design_type`
4. `filename` 必须是文件夹内存在的文件
5. `main_stone.type` 必须是 materials 有效值之一
6. `main_stone.shape` 必须是 shape 有效值之一

---

## 完整示例

### 藏式戒指

```json
{
  "$schema": "product_data_schema_v1",
  "product_id": "R001",
  "category": "rings",
  "shop": "MentorArtCircle",
  "style": "tibetan",
  "target_audience": "neutral",
  "occasion": "daily",
  "materials": ["sterling_silver"],
  "main_stone": null,
  "secondary_stone": null,
  "product_path": "/products/MentorArtCircle/rings/R001/",
  "basic_info": "925 Sterling Silver ring with Tibetan mantra engraving. Adjustable size 6-9. Band width 6mm. Inner diameter 18mm. Hand-polished antique finish.",
  "earring_design_type": null,

  "images": [
    {
      "filename": "R001_01.jpg",
      "angle": "front",
      "type": "product_only",
      "is_hero": true,
      "notes": "Shows mantra engraving clearly"
    },
    {
      "filename": "R001_02.jpg",
      "angle": "side",
      "type": "product_only",
      "is_hero": false
    },
    {
      "filename": "R001_03.jpg",
      "angle": "top",
      "type": "macro",
      "is_hero": false,
      "notes": "Detail of engraving texture"
    },
    {
      "filename": "R001_04.jpg",
      "angle": "3/4",
      "type": "wearing",
      "is_hero": false,
      "notes": "On hand showing size"
    }
  ]
}
```

### 珍珠耳环 (Flat Front)

```json
{
  "$schema": "product_data_schema_v1",
  "product_id": "E001",
  "category": "earrings",
  "shop": "MentorArtCircle",
  "style": "pearl",
  "target_audience": "female",
  "occasion": "gift",
  "materials": ["sterling_silver", "pearl", "enamel"],
  "main_stone": {
    "type": "pearl",
    "carat": null,
    "shape": "round",
    "size": "6mm"
  },
  "secondary_stone": null,
  "product_path": "/products/MentorArtCircle/earrings/E001/",
  "basic_info": "Hand-painted enamel flower stud earrings with freshwater pearl center. 925 Sterling Silver post. Size: 15mm diameter. Lever back closure.",
  "earring_design_type": "flat_front",

  "images": [
    {
      "filename": "E001_01.jpg",
      "angle": "front",
      "type": "product_only",
      "is_hero": true,
      "notes": "Shows enamel pattern"
    },
    {
      "filename": "E001_02.jpg",
      "angle": "3/4",
      "type": "wearing",
      "is_hero": false,
      "notes": "Model wearing, face turned 20 degrees"
    }
  ]
}
```

### 莫桑石项链

```json
{
  "$schema": "product_data_schema_v1",
  "product_id": "N001",
  "category": "necklaces",
  "shop": "MoissaniteStore",
  "style": "moissanite",
  "target_audience": "female",
  "occasion": "engagement",
  "materials": ["white_gold", "moissanite"],
  "main_stone": {
    "type": "moissanite",
    "carat": 1,
    "shape": "round",
    "size": "6.5mm"
  },
  "secondary_stone": null,
  "product_path": "/products/MoissaniteStore/necklaces/N001/",
  "basic_info": "1 carat round brilliant moissanite pendant. 18K white gold setting. Chain length 45cm adjustable. VVS clarity, DEF color grade. 潮流个性设计，每一个角度都能反射出美钻璀璨的光泽。经久耐用，开关式卡扣佩戴结实不易断开。",
  "earring_design_type": null,

  "images": [
    {
      "filename": "N001_01.jpg",
      "angle": "front",
      "type": "product_only",
      "is_hero": true
    },
    {
      "filename": "N001_02.jpg",
      "angle": "front",
      "type": "macro",
      "is_hero": false,
      "notes": "Fire and brilliance close-up"
    },
    {
      "filename": "N001_03.jpg",
      "angle": "front",
      "type": "wearing",
      "is_hero": false
    }
  ]
}
```

---

## 下游使用

| Skill | 使用方式 |
|-------|----------|
| **NanoBanana Batch Generator** | 根据 `images[].angle/type` 选择参考图 |
| **Etsy Listing Batch Generator** | 使用 `basic_info` + `is_hero` 图生成 listing |
| **Etsy Batch Pre-processing** | 生成此文件 |
