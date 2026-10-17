# 大肥鱼桌宠 · 维护文档

面向「接手维护」的人：怎么跑、代码怎么组织、素材怎么生成、改哪里、坏了怎么查。
产品向介绍见 [README.md](README.md)。

---

## 1. 快速上手

```bash
# 运行（源码方式）：main.py 是入口
python main.py
# 兼容旧入口（内部转发到 main.py）
python 桌宠.py
# 或双击 启动桌宠.bat（会自动挑 venv / 系统 python）

# 三个自检入口（不弹窗、可进 CI）
python 桌宠.py --check          # 外观清单 + 每张精灵尺寸 + 各档窗口宽高 + 峰谷时段快照
python 桌宠.py --font-check     # 字体加载情况、候选链、最终选中的字体与字重
python 桌宠.py --balance-check  # 真实请求一次余额接口（退出码 0 成功 / 1 无 Key / 2 失败）

# 测试（无头，不需要显示器）
pip install -r requirements-dev.txt
python -m pytest
```

依赖：`PySide6`、`requests`、`psutil`、`pynvml`（见 `requirements.txt`）；素材脚本额外需要 `Pillow`。
`bubble.py` 含 Qt 绘制，所以完整测试需要运行依赖；`holiday.py` / `config.py` 本身仍是纯标准库，见第 13 节。

> `pynvml` 会打印 `FutureWarning: The pynvml package is deprecated`，这是上游包改名提示，**不影响运行**，要消除可换 `nvidia-ml-py`。

---

## 2. 目录结构

```
dafeiyu-pet/
├── main.py                  # 入口：GUI 启动 + --check / --font-check / --balance-check
├── 桌宠.py                  # 兼容入口（转发到 main.py）
├── pet_window.py            # 窗口、动画、菜单、浮层、面板、PetWindow
├── bubble.py                # 气泡绘制 / 字体 / 台词池 / 冷却 / 去重（Qt）
├── outfit.py                # 外观发现、精灵加载、尺寸档位（Qt）
├── ai_chat.py               # DeepSeek 对话请求（无 Qt）
├── weather.py               # 天气查询（无 Qt）
├── balance.py               # 余额查询与展示文本（无 Qt）
├── holiday.py               # 峰谷判定 + 节假日表（纯标准库）
├── config.py                # 配置读写 + 默认值合并 + 运行路径（纯标准库）
├── tests/                   # pytest 用例（无头运行）
├── pytest.ini               # testpaths = tests
├── requirements-dev.txt     # 测试依赖（运行依赖 + pytest）
├── 启动桌宠.bat             # 启动脚本
├── config.json              # 运行时生成，含 API Key，已被 .gitignore 忽略
├── config.example.json      # 配置模板（入库）
├── sprites/                 # 默认外观「深海女仆」精灵（正面/侧面/背面 × 三档 + icon）
│   └── outfits/             # 各套换装外观：<id>/ + manifest.json
├── assets/
│   ├── fonts/               # 内置字体（启动自动加载并优先使用）
│   └── holidays/            # <年>.json 中国法定节假日表（峰谷判定用）
├── docs/                    # README 展示图
├── preprocess_outfits.py    # 精灵生成脚本（唯一入口：抠图 + 多尺寸 + manifest + 扁平输出）
├── fetch_holidays.py        # 抓取节假日表
├── make_zip.py              # 打源码分享 zip
├── 桌宠.spec                # PyInstaller 打包配置（入口 main.py）
└── MAINTENANCE.md           # 本文件
```

> 历史脚本 `preprocess.py` / `preprocess2.py` 已删除，能力全部并入 `preprocess_outfits.py`（见第 7 节）。

---

## 3. 运行时约定

| 变量 | 含义 |
|---|---|
| `APP_DIR` | 可写目录：打包后是 exe 所在目录，源码运行是脚本目录。`config.json` 写在这里 |
| `BUNDLE_DIR` | 只读资源目录：打包后是 `_MEIPASS`，源码运行同 `APP_DIR`。`sprites/`、`assets/` 从这里读 |
| `PYTHONW` | 开机自启时用的解释器（优先项目内 `.venv`） |

**关键区别**：素材/字体从 `BUNDLE_DIR` 读（打包后进临时解压目录），配置从 `APP_DIR` 读写（持久化）。
新增随包资源时，除了放进 `assets/`，还要确认 `桌宠.spec` 的 `datas` 与 `make_zip.py` 的文件清单都覆盖到。

---

## 4. 配置项全表（`config.json`）

首次启动由 `config.load_config()` 按 `config.DEFAULT_CONFIG` 自动创建；缺字段时合并默认值并回写，用户已有的值和未知字段都保留。

| 键 | 默认 | 说明 |
|---|---|---|
| `mode` | `wander` | `wander` 自由散步 / `follow` 跟随鼠标 / `still` 原地待着 |
| `size` | `0.7` | 档位系数：小 0.55 / 中 0.7 / 大 0.9（对应精灵高 187 / 238 / 306） |
| `topmost` | `true` | 窗口置顶 |
| `passthrough` | `false` | 鼠标穿透（穿透后从托盘解除） |
| `autostart` | `false` | 开机自启（写启动目录快捷方式） |
| `x` / `y` | `null` | 上次位置；`null` = 右下角初始位 |
| `ds_api_key` | `""` | DeepSeek API Key（**不要入库**） |
| `city` | `汕头` | 天气城市 |
| `outfit` | `base` | 当前外观 id；非法值自动回落 `base` |
| `balance_cooldown` | `60` | 两次余额查询的最小间隔（秒），冷却内复用上次结果 |
| `holiday_override` | `""` | 自定义节假日表 json 路径；留空则自动查找 |

---

## 5. 代码地图

按职责拆成以下模块，`桌宠.py` 只剩兼容入口：

| 模块 | 内容 |
|---|---|
| `main.py` | 入口与三个自检：`check_appearance()` / `check_fonts()` / `check_balance()` / `main()` |
| `pet_window.py` | 全部 Qt 控件：`LaceMenu` / `LaceBox` / `LacePanel` / `InfoPanel` / `PricingPanel` / `BalancePanel` / `ChatDialog` / `FunctionPanel` / `FoodPanel` / `OutfitPanel` / `PetWindow` |
| `bubble.py` | 花边主题、字体、气泡/雪花/鲸尾绘制、台词池 `LINES` / `INNER_LINES` / `REACT_LINES` / `DRAG_LINES` / `FOOD_LINES`、`Cooldown` / `LinePicker` / `is_duplicate` |
| `outfit.py` | `DEFAULT_OUTFIT` / `VIEW_NAMES` / `SIZE_LEVELS`、`discover_outfits()`、`load_sprites()`、`sprites_at_height()`、换装台词 |
| `ai_chat.py` | `DS_SYSTEM`、`build_messages()`、`chat_reply()`（纯网络，不碰控件） |
| `weather.py` | `geocode_city()`、`weather_text()`（纯网络，不碰控件） |
| `balance.py` | `BALANCE_ERRORS`、`parse_balance()`、`fetch_balance()`、`money_text()`、`balance_summary_text()`、`balance_panel_rows()` |
| `holiday.py` | `PEAK_WINDOWS` / `PRICE_FACTOR_OFF` / `RATE_TABLE`、`load_holidays()`、`is_china_holiday()`、`price_band()`、`next_switch()`、`fmt_remain()`、`price_snapshot()`、`price_say_text()`、`rate_text()` |
| `config.py` | `APP_DIR` / `BUNDLE_DIR` / 路径常量、`DEFAULT_CONFIG`、`merge_defaults()`、`load_json()`、`load_config()`、`save_config()` |

`pet_window.py` 内部按从上到下：

| 区块 | 内容 |
|---|---|
| 顶部常量 | `BUBBLE_H`、`MARGIN`、`SPEED`、`TICK`、`IDLE_SPEECH_COOLDOWN` |
| 控件层 | 花边菜单 / 浮层基类 / 定价、余额面板 / 聊天框 / 功能、喂食、换装面板 |
| 主窗口 | `PetWindow`：精灵、`tick()` 主循环、`paintEvent()`、鼠标事件、菜单、各功能；空闲冒泡用 `speech_gate` + `inner_line_picker` / `idle_line_picker` |

### 模块依赖方向
`main.py` → `pet_window.py` → {`bubble.py`, `outfit.py`, `holiday.py`, `ai_chat.py`, `weather.py`, `balance.py`, `config.py`}；
`bubble.py` / `outfit.py` 只依赖 `config.py` 的路径，不反向依赖 `pet_window.py`，避免循环导入。
纯逻辑测试只直接依赖 `holiday.py` / `config.py`。

### 菜单外观
菜单参数集中在 `pet_window.py` 顶部 `MENU_*`；`LaceMenu` 顶部是 `_MenuHeader` 品牌条，分组用 `add_section()`。
系统勾选 / 子菜单箭头在 QSS 里用 `image: none` 关掉，由 `paintEvent` 手绘成蓝白线条；菜单文字也由 `paintEvent` 绘制，
以获得 active item 的 120ms 颜色过渡和灰色退出项。图标是内联 SVG（`MENU_ICON_SVG` + `QSvgRenderer`），高 DPI 自适应。

改菜单间距 / 配色时注意：
- 别删 `image: none`，否则系统黑色勾/三角会叠在蓝线下面。
- 自定义分组条比 QMenu 默认分隔线高，`showEvent()` 里会按 `sizeHint()` 再 resize 一次；这是防止最后几项被裁掉的补偿，别删。

### 绘制顺序（不要改）
`paintEvent()` 里先画**精灵**，最后调用 `_paint_bubble()`。气泡必须最后画，
否则鱼蹦跳/摇摆上顶时头会盖住气泡（这是修过的 bug）。

### 精灵表键
`self.sprites[(outfit_id, 视图名, 高度)] → QPixmap`；左右朝向由 `self.facing` 单独控制，不进 key。
`_sprite_key()` 返回 `(outfit, 视图, cur_h)`，`draw_one()` 按此取图。
改 key 结构时必须同步三处：`outfit.load_sprites`、`_sprite_key`、`draw_one`。

### 外观发现
`discover_outfits()`：
- `base` = `sprites/` 根目录下的 正面/侧面/背面（缺任一视图则不出现）
- 其它 = `sprites/outfits/<id>/`，显示名取 `manifest.json`
- 缺视图的外观会跳过并打印提示，不会崩

### 为什么 `InfoPanel` 不用 Qt 布局引擎
浮层里的 `QLabel` 是**动态重建**的，Qt 布局的 `sizeHint` 在这种场景会失效
（表现为面板空白、宽度塌成 62px）。所以 `InfoPanel` 改成：按字号自己算宽高
（`_extent()`）+ `setGeometry()` 显式摆放，并在重建后显式 `setVisible(True)` / `raise_()`。
**改这个面板时别退回布局引擎**。

---

## 6. 线程模型（最需要注意的坑）

Qt 控件只能在主线程碰。现有两个队列：

| 队列 | 用途 | 消费位置 |
|---|---|---|
| `self._say_queue` | 后台线程 → 一句话气泡 | `tick()` 开头 |
| `self._panel_queue` | 后台线程 → `(kind, data)` 面板数据 | `tick()` 开头（紧随 say 队列） |

写法约定：
```python
def worker():                       # 后台线程：只做网络/IO
    ok, data = fetch_balance(key)
    self._panel_queue.append(("balance", data))
threading.Thread(target=worker, daemon=True).start()
```
禁止在 worker 里直接 `self.say()` / 操作控件 / `self.update()`。

---

## 7. 素材流水线

### 7.1 精灵：`preprocess_outfits.py`

一个脚本覆盖两种素材形态、两种输出布局：

| 输入 | 参数 | 输出 |
|---|---|---|
| 一张并排三视图 | `--src 图片` | `--out/<id>/`（换装外观） |
| 三张独立文件 | `--src-dir 目录`（内含 `正面.png`/`侧面.png`/`背面.png`） | 同上 |
| 重建默认外观 | 加 `--flat --out sprites` | 直接写 `sprites/` 根，**不建子目录、不写 manifest** |

常用参数：

| 参数 | 说明 |
|---|---|
| `--id` / `--name` | 外观 id / 菜单显示名 |
| `--preview` | 只出 `preview.png`（棋盘格 / 白底 / 深底三行），不写精灵 |
| `--rembg auto\|on\|off` | 抠图方式，默认 `auto`；失败自动回退白底泛洪 |
| `--force` | 覆盖已存在精灵 |
| `--flip-side` | 侧面左右镜像；`--side-index` 决定并排模式下哪一格做镜像 |
| `--out` | 输出根目录 |

生成的规格固定：母版 **340px 高**，另出 **187 / 238 / 306** 三档 + **64px** icon。
尺寸变体与 icon 都用 **预乘 alpha 缩放**（`premult_resize`），缩小时不产生白边——
这是从旧 `preprocess2.py` 合并进来的关键做法，别改回普通 `resize`。

> 仓库里现有的四套外观是**合并前**用普通缩放生成的；用当前脚本带 `--force` 重跑一遍，
> 尺寸完全不变、仅半透明边缘更干净（实测不透明主体 RGB 总量差异 < 0.1%）。不改也不影响显示。

抠图链路（默认）：`seal_background`（四角/四边反复泛洪补种）→ 裁透明边 →
太瘦时用最大连通域兜底 → `decontaminate`（白底反混合）→ 统一高 340。
`--rembg` 时把第一步换成 rembg，其余不变。

前提：rembg 需要 `onnxruntime` 后端（`pip install "rembg[cpu]"`）与 `~/.u2net/u2net.onnx`
（约 176MB；国内直连 GitHub 易超时，可用 gh-proxy 镜像手动放进去）。

### 7.2 字体：`assets/fonts/`

启动时 `load_bundled_fonts()` 扫描目录下所有 `.ttf/.otf/.ttc` 并注册，**排在最优先**。
回退链：内置字体 → 幼圆 → 微软雅黑 → 华文细黑 → 系统默认。
换字体：把字体文件丢进去即可（可删掉旧的）；`--font-check` 可确认最终生效的族名与字重。

注意：字重统一用 `Bold(700)`（Qt 只在 ≥700 时才对缺粗体字重的字体做合成加粗），
气泡文字另外用 `QPainterPath` 轮廓 + 细描边补厚度。

### 7.3 节假日表：`assets/holidays/<年>.json`

```bash
python fetch_holidays.py --year 2027      # 写入 assets/holidays/2027.json
```

数据源 `https://timor.tech/api/holiday/year/<年>/`，只收录 `holiday=true` 的法定节假日自然日。
**每年初要跑一次**（官方公布后）；某年缺表时程序会把时段判定降级为「时段未知」并按工作日规则估算，不会瞎猜。

---

## 8. DeepSeek 接口与峰谷规则

### 接口
| 用途 | 请求 |
|---|---|
| 聊天 | `POST https://api.deepseek.com/v1/chat/completions`，模型 `deepseek-chat`，回复截断到 30 字 |
| 余额 | `GET https://api.deepseek.com/user/balance`，`Authorization: Bearer <key>` |

余额返回 `is_available` + `balance_infos[]`（`currency` / `total_balance` / `granted_balance` / `topped_up_balance`）。
错误映射集中在 `BALANCE_ERRORS`：`nokey / auth / insufficient / rate / server / timeout / network / parse`。

### 峰谷规则（易过期，改动请对照官网）
来源：<https://api-docs.deepseek.com/zh-cn/quick_start/pricing>

- 高峰 = **周一至周五（不含中国法定节假日）9:00–12:00、14:00–18:00**
- 其余时段（含周末、法定节假日全天）= 空闲，**空闲价 = 高峰价 × 0.5**
- 判定按**本机本地时间**，面板上标注 `UTC±n`

代码常量（`holiday.py` 顶部）：
```python
PEAK_WINDOWS = ((9*60, 12*60), (14*60, 18*60))   # 分钟
PRICE_FACTOR_OFF = 0.5
RATE_TABLE = (  # 元/百万 tokens（高峰价）
    {"model": "deepseek-flash",  "hit": 0.04, "miss": 2.0, "out": 8.0},
    {"model": "deepseek-v4-pro", "hit": 0.30, "miss": 9.0, "out": 27.0},
)
```
**官方调价或调整时段时，改 `holiday.py` 里这三个常量即可**，面板会自动按当前时段折算显示；
`tests/test_holiday.py` 会一起验证边界。

---

## 9. 打包与分发

```bash
# exe（单文件）
pyinstaller --noconfirm --onefile --windowed --name 大肥鱼桌宠 ^
  --add-data "sprites;sprites" --add-data "assets;assets" --icon icon.ico main.py
# 或直接用仓库里的 桌宠.spec（已包含 sprites/ + assets/）
pyinstaller --noconfirm 桌宠.spec

# 源码分享包
python make_zip.py
```

新增随包资源时**三处一起改**：`桌宠.spec` 的 `datas`、`make_zip.py` 的文件清单、本文第 2 节目录结构。
新增纯逻辑模块时，PyInstaller 会自动跟着 `import` 分析；`make_zip.py` 的 `files` 清单要手动加一行。

---

## 10. Git 工作流

- 远端：`decade` → `https://github.com/decade-0110/dafeiyu_pet.git`（本项目），`origin` → 上游原项目，**别推错**。
- `config.json` 恒被 `.gitignore` 忽略，仓库里只有 `config.example.json`。
- `.gitattributes` 统一 `eol=lf`，二进制（png/ttf/ico 等）不做换行转换。
- 推送：
  ```bash
  git push decade HEAD:refs/heads/main
  # 本机代理没开时
  git -c http.proxy= -c https.proxy= push decade HEAD:refs/heads/main
  # 代理开着但报 schannel 凭据错误
  git -c http.sslBackend=openssl push decade HEAD:refs/heads/main
  ```

---

## 11. 排错手册

| 症状 | 可能原因 | 处理 |
|---|---|---|
| 启动就报错弹窗 | 缺 PySide6 / 精灵目录为空 | `pip install -r requirements.txt`；跑 `--check` 看清单 |
| 桌宠不显示 | `sprites/` 下缺 正面/侧面/背面 | 用 `--flat` 重建默认外观 |
| 换装菜单里少了某套 | 该外观缺视图或 manifest 没写 | 看启动控制台 `[换装] 跳过外观…`，重跑生成脚本 |
| 字体不对/太细 | 内置字体没加载 | `--font-check`；确认 `assets/fonts/` 有字体且打包带了 `assets` |
| 气泡被头挡住 | 绘制顺序被改 | 确认 `_paint_bubble()` 在 `draw_one()` 之后调用 |
| 面板空白/宽度很窄 | `InfoPanel` 退回布局引擎 | 用当前 `_extent()` + `setGeometry()` 写法，别用 QLayout 放动态 QLabel |
| 查余额提示「Key 好像失效了」 | Key 被撤销或填错 | 右键「设置 Key」填新 Key；`--balance-check` 复现 |
| 时段显示「时段未知」 | 缺当年节假日表 | `python fetch_holidays.py --year <年>` |
| 时段判定整体偏移几小时 | 系统时区不对 | 校正系统时区（程序按本地时间判定，不读地理时区） |
| `--check` 报宽高比异常 | 切格切歪或素材不是三视图 | 用 `--preview` 看预览图，核对素材并排/独立文件形式 |
| 精灵边缘有白边 | 缩放没走预乘 alpha | 确认尺寸变体用 `premult_resize()` |
| rembg 报缺 onnxruntime | 只装了 rembg 本体 | `pip install "rembg[cpu]"` 或 `pip install onnxruntime` |
| rembg 下载模型超时 | GitHub 直连不通 | 用镜像手动下载 u2net.onnx 到 `~/.u2net/` |
| 打包后没字体/没精灵 | spec 漏了 assets/sprites | 检查 `桌宠.spec` 的 `datas` |
| 推送报代理/凭据错误 | 本机代理状态或 TLS 后端 | 见第 10 节三条命令 |

---

## 12. 改动检查清单

改完代码，收尾前过一遍：

- [ ] `python -m py_compile main.py 桌宠.py pet_window.py bubble.py outfit.py ai_chat.py weather.py balance.py holiday.py config.py preprocess_outfits.py fetch_holidays.py make_zip.py`
- [ ] `python -m pytest` 全绿（无头运行，不需要显示器）
- [ ] `python 桌宠.py --check`（外观/尺寸/窗口/时段快照）返回 0
- [ ] `python 桌宠.py --font-check` 字体正常
- [ ] 改到素材流水线时：`--preview`、`--rembg off`、`--rembg on`、`--src-dir`、`--flat` 各跑一次
- [ ] 改到 UI/绘制时：开起来目视一遍菜单、四个面板、气泡（普通/心声/长句）
- [ ] 改到外观/尺寸时：三档大小 × 四个方向都看一下
- [ ] 新增随包资源：`桌宠.spec`、`make_zip.py`、本文件目录结构三处同步
- [ ] 不把 `config.json`（含 Key）提交进仓库

---

## 13. 测试（pytest）

测试在**无显示器**环境运行；`bubble.py` 含 Qt 绘制，所以 `requirements-dev.txt` 会装运行依赖，但不会创建窗口。

```bash
pip install -r requirements-dev.txt   # 运行依赖 + pytest
python -m pytest                      # 全部用例
python -m pytest tests/test_holiday.py -q   # 只跑峰谷
```

| 文件 | 覆盖点 |
|---|---|
| `tests/test_holiday.py` | 工作日高峰边界（9/12/14/18 点）、周末、法定节假日、调休补班日（周末仍空闲）、缺当年表降级为 `unknown`、节假日表查找优先级/损坏兜底/缓存、`next_switch()` 跨周末与长假、`price_snapshot()` 字段 |
| `tests/test_config.py` | 首次创建、缺字段合并并回写、`null`/`false` 不被默认值覆盖、损坏 JSON 不覆盖原文件、未知字段保留、`load_json`/`save_config` 往返、`config.example.json` 与默认值同步 |
| `tests/test_bubble.py` | 连续两次不重复、单句/空池边界、冷却门（含共享冷却、注入时钟）、`say()` 的天气例外去重 |
| `tests/test_headless.py` | 子进程里 import `holiday` / `config`，断言没有拉入 `PySide6` / `requests`；再 import `balance` / `ai_chat` / `weather`，断言没有拉入 Qt |

约定：
- `tests/conftest.py` 把项目根加入 `sys.path`，并在每个用例前后 `clear_holiday_cache()`，避免 `tmp_path` 里的表串味。
- 配置测试全部用 pytest 的 `tmp_path`，**不读写仓库里的真实 `config.json`**。
- 时间一律用显式 `datetime` 传参，测试不依赖运行当天的日期或时区。
- 某些 Windows 沙箱会拦截 pytest 创建的 0700 临时目录；遇到 `tmp_path` 权限错误时，在普通终端跑，或给 pytest 指定可写的 `--basetemp`。
