# 首次点亮记录：2026-11-12

## 22:09 高亮全蓝固件（最新状态）

用户要求保留旧版，并将整屏改为尽可能亮的蓝色。
修改前完整工程、工具及 build 已归档到 `versions/image-20261112-220411/`，
含此前的白屏版、图片版和历史记录，`manifest.json` 保存逐文件 SHA-256。
下载前另完整读出 64 KiB Flash：`build/flash-backup-20261112-220618.bin`。
恢复图片显示：`python versions/image-20261112-220411/tools/panel.py flash`。

当前 `PANEL_SOLID_BLUE=1`：PA2/PA5 蓝色位为高，红、绿位为低，
启动时移入并锁存同一组 64 列数据，扫描期间仅切换 32 个行地址。
每行 300 µs，曝光 294 µs，行时间利用率 98%；1/32 扫描下单颗 LED
的设定占空比约 3.0625%。没有灰度调制或软件调暗，断电重启保持全蓝。
TIM1 仍以硬件单脉冲结束曝光，切行保留消隐和 2 µs 地址稳定等待。
初始化后停止无用途的 SysTick 中断，将 PWM2 前导缩为 1 µs，并内联消隐操作。
首版定时略超行槽，已通过上述修改消除；首版记录为 `build/blue-initial-timing-report.json`。

最终固件 `.text` 3280 B，`.data` 76 B，`.bss` 2052 B（含栈预留）；
GCC `-Wall -Wextra -Werror` 编译通过。3356 B 下载、OpenOCD 校验、逐字节读回全部通过。
最终 SHA-256：`55fad1055523645a0ca0c1fb5a609200bc6142e1d2f041044b57c4df1a0102eb`。
`build/flash-report.json` 两次读数：frames 62→169、fault=0、row_overruns=0，
max_row_cycles=19122（标称时钟下 298.78125 µs），刷新率约 104.067 Hz。
状态版本 3 增加 max_on_us，CLI 按实际连接的固件核验曝光上限。
随后单次连接连续观察 10 秒，frames 57→580→1105，fault 与 row_overruns
始终为 0；GPIOA 的 IDR/ODR 六位 RGB 都读回 0x24（上下半屏仅蓝色位为高）。
归档 89 个文件逐一通过 SHA-256 校验，首次下载前的 64 KiB 备份与归档图片固件
在全部有效固件字节范围一致。详见 `build/blue-verification.json`。

LED 峰值电流仍由灯板恒流电路决定；本次未更改电源或驱动电流设置。
实际颜色、光度、屏端电压、电流及温升尚未实测；周期值基于标称 64 MHz，非外部仪器测量。
TIM1 PWM2/单脉冲依据 ST RM0008：
https://www.st.com/resource/en/reference_manual/rm0008-stm32f101xx-stm32f102xx-stm32f103xx-stm32f105xx-and-stm32f107xx-advanced-armbased-32bit-mcus-stmicroelectronics.pdf

用户确认灯板已单独供电，14 路信号按交接文档连接并共地。

## 已完成

- ST-Link V2J48S7，USB VID:PID 0483:3748，100 kHz SWD 能识别目标。
- 目标 DBGMCU_IDCODE=0x6410，Cortex-M3 CPUID=0x411fc231，Flash 容量字段=64 KiB。
- GCC 14.3.1 编译通过，启用 `-Wall -Wextra -Werror`。
- 固件 `.text` 3236 B，`.data` 56 B；链接器报告 `.bss` 2056 B，其中包含预留的 2048 B 栈空间。
- 原固件完整备份：`build/flash-backup-20261112-170235.bin`，65536 B。
- 原固件备份 SHA-256：`318c4e4bee3e5b1a73d8f6d97585f3253ad9fd0678c047208bdcbed83e80d6f3`。
- 全白固件于 17:02 写入；OpenOCD 校验通过，3292 B 读回文件与 `panel.bin` 逐字节一致。
- `build/flash-backup-20261112-170047.bin` 是超时中断的 32768 B 部分备份，不能用于完整恢复。

## 当前现象与待完成

用户反馈：完全不亮。

`reset run` 后 SWD 通信失败；随后电脑枚举不到 ST-Link，Windows 出现
“Unknown USB Device (Device Descriptor Request Failed)”，问题代码 43。
用户已重插一次，仍未恢复识别；正在通过更换 USB 口检查。
ST-Link 消失的原因未确认，不能据此判断是固件时序、供电、线缆或探针故障。

运行帧计数、CPU 时钟与引脚寄存器尚未读到；目标 125 Hz 只是程序设定，未作为实测结果。
还需确认 OE、CLK、LAT 到达灯板输入端，以及是否存在电平转换使能问题。
整屏白色显示、板端电压、电流与波形均待验收。

## USB 隔离检查结果

用户先重插 ST-Link，再更换 USB 口，均无法枚举 ST-Link。
之后按指引关闭灯板并将 ST-Link 与目标板的接线全部断开，只连接探针 USB。
独立连接后仍无 VID_0483/PID_3748；Windows 枚举到
`USB\VID_0000&PID_0002\7&2822c9cd&0&3`，描述符请求失败，代码 43。

当前阻碍是探针的 USB 连接无法正常枚举；还不能细分为探针、数据线或 USB 硬件故障。
需要可正常枚举的 ST-Link 或 CMSIS-DAP，恢复后先执行 `python tools/panel.py diagnose`，
读取当前固件状态与 GPIO/TIM1/RCC 寄存器，再继续灯板点亮定位。
先保留完整原程序备份，勿使用部分备份恢复。

## 17:15–17:18 连接变化

17:15 再次检测时 ST-Link USB 恢复正常，OpenOCD 能读取 V2J48S7 版本，
但 SWD 提示无法连接目标。该次记录在 `build/openocd-20261112-171553.log`。
用户随后表示已连接 STM32。17:18 检查再次无法打开 ST-Link，
Windows 枚举到 `USB\VID_0000&PID_0002\7&16179262&0&3`，代码 43。
待用户提供探针到 MCU 的逐根接线与 MCU 实际供电来源，以检查供电连接。
这项时间关联提示需要检查硬件连接，但尚不足以确定故障原因。

## 后续重插：USB 能识别，驱动启动失败

再次重插后 Windows 枚举到 `USB\VID_0483&PID_3748\000000000001`，
名称 STM32 STLink，驱动 oem116.inf；问题代码从 43 变为 10，状态 0xC0000001。
OpenOCD 报 `libusb_open() failed with LIBUSB_ERROR_NOT_SUPPORTED`。
尝试只重启此实例：`pnputil /restart-device "USB\VID_0483&PID_3748\000000000001"`，
Windows 返回 Access is denied，未成功重启。需要用户以管理员权限执行该设备重启命令。

## 17:36 CMSIS-DAP 恢复连接，确认固件扫描运行

检测到正常枚举的 CMSIS-DAP：VID:PID=0D28:0204，序列号
`115E3F319C8E16261F65187D5B32AAEC`，固件版本 2.1.0。
工具已增加正常探针的自动识别并切换为 `interface/cmsis-dap.cfg`。

通过 SWD 成功读取全白固件状态（`build/diagnose-report.json`、`build/status-report.json`）：

- 标称 CPU 时钟 64 MHz，白色输出开关=1，RGB 掩码=0x3F，故障标记=0。
- 同一次连接中帧计数从 68 增加到 194，间隔约 1 秒。
- DWT 帧周期 512594–512615 个 CPU 周期，按标称 64 MHz 换算约 124.85 Hz。
- 点亮脉宽设定 10 µs，行槽设定 250 µs。
- GPIOA PA0–PA5 的输入采样均为高，PA8 配置为复用推挽输出。

刷新率为 MCU 周期计数换算，未使用外部仪器校准；灯板侧 OE 波形和实际显示仍待确认。
已提示用户开启灯板独立 5.0 V 电源观察。
随后两次重连 CMSIS-DAP 自身仍正常，但 SWD 报 `cannot read IDR`，目标连接再次不通。
待用户反馈屏幕状态，并确认目标板供电与 SWD 连线保持连接。

## 17:40 后：确认直连，发现行地址引脚读回异常

用户确认灯板独立 5.0 V 已开启，屏幕完全不亮；未安装 AHCT245，
STM32 直接连接灯板；CMSIS-DAP 未连接 NRST。
以 50 kHz SWD、connect_assert_srst 初始化后恢复读数。
该连接方式下仍不能假设硬件复位有效，因为 NRST 没有实际接线。

`build/sample-report.json` 中 256 次 GPIO 采样：RGB 六位均为 0x3F，
GPIOB 的 PB0/PB1/PB10/PB11/PB12 对应地址均读为 0。
另以不同等待间隔采样 16 次（`build/pin-compare.json`），GPIOB IDR 恒为 0x23F8，
而 ODR 和固件行号均变化。这是 MCU 引脚读回异常，尚未测得灯板端波形。
OE 采样只说明读到两个电平，不可用这些非均匀样本估算脉宽或占空比。

已将 RAM 中 enable 设为 0，并临时把五根行地址脚切换为浮空输入，
减少疑似外部拉低条件下继续驱动；此设置复位后失效。
等待用户关闭灯板、断开 HUB75 信号线后，使用 `tools/gpio_test.py`
进行 14 路空载高低电平读回对照，区分 MCU/GPIO 与外部接线或负载问题。

## 17:58 输入口纠正后，提高亮度

用户确认一只 ST-Link 已损坏，灯板信号原先误接 OUT，改接 IN 后已点亮；用户报告此前功耗为 1.86 W。
使用 CMSIS-DAP 和 `--under-reset` 成功读取运行状态：on_us=10、row_us=250、enable=1、rgb_mask=63、fault=0。
随后执行 `python tools/panel.py on --on-us 30 --under-reset`，两次读回 on_us=30，帧计数从 89 增至 215，无固件故障；按标称 CPU 时钟计算刷新率约 124.9 Hz。
本次仅修改 RAM，复位后恢复默认 10 us。新档功耗、屏端电压、温升和显示效果待用户实测。
100 us 是当前固件的调试限制，不是模组额定最大亮度；没有模组额定亮度或实测光度数据。

## 17:59 用户指定提高到 70 us

用户反馈 30 us 档功耗仍为 1.868 W，要求提高到 70 us。
执行 `python tools/panel.py on --on-us 70 --under-reset` 成功，两次读回 on_us=70、enable=1、fault=0，帧计数 92→218，标称时钟换算刷新率约 124.87 Hz。
行槽仍为 250 us，设定点亮占比 28%。仅为 RAM 设置，复位恢复 10 us；本次连接使用 under-reset，不能把重连后复位得到的默认值当作此前设置未生效的证据。
70 us 档的实际功耗与灯板端 OE 波形尚未测得；30 us 功耗未明显变化，不能仅凭 RAM 参数推断灯板实际亮度按比例增加。

## 18:20 彩色图片固件写入完成

用户提供 `aa297712a3d5a96460ddbef9179ccdbe.jpg`，图中为黄色、绿色眼圈、托腮角色。
PhotoCraft 将 1200×1091 原图等比缩为 64×58，上下各补 3 行白色；未裁切或拉伸。
每通道 4 位，gamma=2.2，量化后 303 色。生成器逐像素验证了 4096 个像素的位平面编码和解码，
上下半屏分别走 RGB1/RGB2，行地址相差 32；颜色顺序沿用 PA0..PA5 的 RGB 接线表。
这些软件校验不能代替屏幕实物的方向及色序验收。

固件版本 2 使用 4 个 GPIO 位平面，常量占 Flash 32768 B，不占用图片 SRAM。
总 `.text` 36124 B、`.data` 72 B、链接器报告 `.bss` 2056 B（含 2048 B 栈预留）。
默认每行 300 µs，各平面曝光 5/9/19/37 µs，总计 70 µs，重启后自动显示图片。
最初版本测得约 79.9 Hz、行耗时超限；强制内联信号延时后解决。

下载期间 SWD 曾断连，出现一次写入失败和一次 49152 B 的不完整备份。
因为 NRST 未接，下载工具已使用 Cortex-M SYSRESETREQ 软件复位并确认 halt，
同时严格检查写入/校验返回值。18:20 最终完整写入 36196 B，OpenOCD 校验通过，
逐字节读回与 `build/panel.bin` 一致，SHA-256 为
`98da9b0c31598ab8afbf70b6778d102282d314962db4389da8cf5d7ff0a4a7eb`。

`build/flash-report.json` 的两次运行读数：帧数 64→171、enable=1、image_mode=1、
color_bits=4、fault=0、row_overruns=0。最大行耗时 17639 周期（标称时钟下约 275.6 µs），
整帧 615248–615264 周期，标称时钟换算约 104.02 Hz。没有外部时钟校准或灯板端波形测量。

`build/white-firmware-20261112-181044/` 保留转换前全白固件源码和编译产物。
`build/flash-backup-20261112-181236.bin` 为首次彩色下载前的完整备份；
`build/flash-backup-20261112-181636.bin` 为第一次彩色固件的完整备份。
`181853` 备份只有 49152 B，不能恢复；`182039` 虽有 65536 B，但来自前次写入失败后的状态，不能视为可启动固件。
预览在 `build/image/panel-preview.png`；屏幕实物的左右方向、上下顺序、颜色和观感仍待用户目视确认。
