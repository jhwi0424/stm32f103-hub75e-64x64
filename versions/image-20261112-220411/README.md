# STM32F103C8T6 HUB75E 64×64 彩色图片显示

按根目录交接文档的引脚分配驱动 64×64、1/32 扫描灯板。
默认启动后持续显示黄色托腮角色图片，断电重启后也会显示。
每通道 4 位、最多 4096 色；当前图片量化后包含 303 种颜色。

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
运行状态通过 SWD 读取，不暂停 CPU。`off`/`on` 只修改 RAM 中的开关，复位后恢复图片显示。
连接不稳定可尝试 `--under-reset` 或 `--speed 10`；NRST 没有接线时不能保证硬件复位生效。

图片转换先用本机 PhotoCraft CLI 等比缩小到 64×64 内并居中补白，再执行 gamma=2.2 的 LED 占空比编码。
当前原图 1200×1091，画面缩为 64×58，上下各补 3 行白边，不裁切或拉伸。
`firmware/panel_image.h` 是 Flash 中的预计算 GPIO 位平面；生成器验证全部 4096 像素的行列、上下半屏及 RGB 编码可还原。
`build/image/panel-64x64.png` 是缩小后的源图，`panel-preview.png` 是放大预览；预览并非实物拍摄或屏幕色彩校准结果。

## 固件配置

- RGB1/RGB2：PA0–PA5；CLK=PA6，LAT=PA7，OE=PA8。
- A/B/C/D/E：PB0/PB1/PB10/PB11/PB12；PB13 输出高以启用文档中的 NMOS 缓冲使能电路。
- HSI/2 ×16 得到标称 64 MHz，无需外部晶振；APB1=32 MHz，APB2=64 MHz。
- 每行地址有 4 个颜色位平面，每平面移入 64 个时钟；消隐时改变数据、地址并锁存。
- RGB1 对应 y=0..31，RGB2 对应 y=32..63；x 向右、y 向下，沿用接线表中的 RGB 通道顺序。实物方向及色序仍需目视确认。
- 32 个行地址，每槽 300 µs，目标帧率约 104 Hz，实际运行值读取 `status`。
- PA8 使用 TIM1_CH1，反相 PWM2 单脉冲，硬件自动结束点亮。
- 参数集中在 `firmware/panel_config.h`。`PANEL_ON_US=70` 表示 4 个平面合计的近似最大曝光时间，当前各平面为 5/9/19/37 µs；不同于原先单平面的 70 µs 设置。
- `on --on-us 0..100` 可调曝光；数值受限于调试负载上限，不代表灯板额定最大亮度。
- 状态版本 2 增加 `color_bits`、`image_mode`、`max_row_cycles` 和 `row_overruns`，可检查扫描耗时是否超出行槽。
- 扫描时长与脉宽依赖内部振荡器精度，灯板端实际波形待测。

输出文件：`build/panel.elf`、`panel.bin`、`panel.hex`、`panel.map`、`size.txt`。
可复现初始化代码在 `firmware/main.c`，本阶段没有生成 `.ioc`。

TIM1 单脉冲用于结束 OE 低电平；程序故障处理先消隐再关闭 PB13。
复位及上电期间的消隐仍依赖交接文档中的硬件上拉和缓冲电路。

## 当前验证状态

详见 `docs/bringup.md`。编译与写入校验通过不等同于灯板显示验收。
