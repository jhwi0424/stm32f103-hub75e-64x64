# STM32F103C8T6 HUB75E 64×64 高亮全蓝显示

完整资料入口：

- [当前实物配置、16 针接线、供电、器件选型清单与排查经验](docs/hardware.md)
- [完整原始开发交接、选型依据、参考手册链接](STM32F103C8T6-HUB75E-64x64-开发交接.md)
- [全部调试、烧录、验证与故障记录](docs/bringup.md)
- `firmware/`：当前源码；`tools/`：构建、烧录、诊断和图片转换工具。
- `vendor/`：完整本地 CMSIS / HAL 依赖及原许可证，离线源码依赖。
- `build/`：当前固件、Flash 备份、图片、OpenOCD 日志及 JSON 验证记录。
- `versions/`：修改前工程归档，包含图片版及更早白屏版、编译产物与 SHA-256 清单。
- `assets/`：能够找到的原始素材。

按根目录交接文档的引脚分配驱动 64×64、1/32 扫描灯板。
默认启动后持续显示全屏纯蓝（蓝色通道满档，红绿关闭），断电重启后仍显示。
纯色数据只移入、锁存一次，扫描时只切换行地址；省去图片四位灰度与反复移位的消隐时间。
每行 300 µs，蓝色曝光 294 µs，目标行曝光占比 98%，标称刷新率约 104 Hz。
1/32 扫描下单颗 LED 的时间占比约为 3.06%；98% 指行时间利用率，不能理解为单颗 LED 常亮。
保留 TIM1 单脉冲自动结束曝光、行切换消隐以及故障关闭输出。软件时序已接近满占比，实际光度还受供电与灯板恒流电路限制。

## 历史版本与恢复

修改前完整图片版保存在 `versions/image-20261112-220411/`，含源代码、工具、图片、编译产物、历史白屏版和下载记录；`manifest.json` 记录归档文件的 SHA-256。
原图片固件 SHA-256：`98da9b0c31598ab8afbf70b6778d102282d314962db4389da8cf5d7ff0a4a7eb`。
恢复原图片显示（恢复工具会先完整备份当前设备 Flash）：

```powershell
python versions/image-20261112-220411/tools/panel.py flash
```

下述旧图片转换与四位灰度说明用于历史模式。切回图片源码模式可设 `PANEL_SOLID_BLUE=0` 并重新编译。

## 编译与操作

需要本机 STM32CubeIDE 提供的 GNU Arm 编译器与 OpenOCD；脚本从 `C:/ST` 自动查找。
调试脚本支持 ST-Link 与 CMSIS-DAP，会根据 Windows 当前正常枚举的探针自动选择接口。
源码依赖已从 STM32Cube_FW_F1_V1.8.7 复制到 `vendor`，不需要联网下载。

```powershell
python tools/image_to_panel.py '图片完整路径.jpg'
python tools/build.py
python tools/panel.py identify
python tools/panel.py flash
python tools/panel.py status
python tools/panel.py off
python tools/panel.py on
python tools/panel.py diagnose
```

`flash` 先备份全部 64 KiB Flash，再写入、校验并逐字节比较读回文件，然后启动程序。
运行状态通过 SWD 读取，不暂停 CPU。`off`/`on` 只修改 RAM 中的开关，复位后恢复默认全蓝显示。
连接不稳定可尝试 `--under-reset` 或 `--speed 10`；NRST 没有接线时不能保证硬件复位生效。

图片转换先用本机 PhotoCraft CLI 等比缩小到 64×64 内并居中补白，再执行 gamma=2.2 的 LED 占空比编码。
当前原图 1200×1091，画面缩为 64×58，上下各补 3 行白边，不裁切或拉伸。
`firmware/panel_image.h` 是 Flash 中的预计算 GPIO 位平面；生成器验证全部 4096 像素的行列、上下半屏及 RGB 编码可还原。
`build/image/panel-64x64.png` 是缩小后的源图，`panel-preview.png` 是放大预览；预览并非实物拍摄或屏幕色彩校准结果。

## 固件配置

- RGB1/RGB2：PA0–PA5；CLK=PA6，LAT=PA7，OE=PA8。
- A/B/C/D/E：PB0/PB1/PB10/PB11/PB12；PB13 输出高以启用文档中的 NMOS 缓冲使能电路。
- HSI/2 ×16 得到标称 64 MHz，无需外部晶振；APB1=32 MHz，APB2=64 MHz。
- 全蓝模式启动时移入并锁存 64 个蓝色数据；扫描时消隐、切换地址、等待稳定后曝光。历史图片模式每行地址有 4 个颜色位平面，每平面移入 64 个时钟。
- RGB1 对应 y=0..31，RGB2 对应 y=32..63；x 向右、y 向下，沿用接线表中的 RGB 通道顺序。实物方向及色序仍需目视确认。
- 32 个行地址，每槽 300 µs，目标帧率约 104 Hz，实际运行值读取 `status`。
- PA8 使用 TIM1_CH1，反相 PWM2 单脉冲，硬件自动结束点亮。
- 参数集中在 `firmware/panel_config.h`。当前 `PANEL_ON_US=294`，仅使用一个纯蓝平面；历史图片模式的 70 µs 分配为 5/9/19/37 µs。
- 当前蓝屏模式用 `on --on-us 0..294` 可调曝光；工具读取设备固件上限，旧图片模式仍限 100 µs。
- 状态版本 3 在版本 2 的统计基础上增加 `max_on_us`，工具据此核验曝光上限。`row_overruns` 用于检查扫描耗时是否超出行槽。
- 扫描时长与脉宽依赖内部振荡器精度，灯板端实际波形待测。

输出文件：`build/panel.elf`、`panel.bin`、`panel.hex`、`panel.map`、`size.txt`。
可复现初始化代码在 `firmware/main.c`，本阶段没有生成 `.ioc`。

TIM1 单脉冲用于结束 OE 低电平；程序故障处理先消隐再关闭 PB13。
复位及上电期间的消隐仍依赖交接文档中的硬件上拉和缓冲电路。

## 当前验证状态

详见 `docs/bringup.md`。编译与写入校验通过不等同于灯板显示验收。
