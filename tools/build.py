from pathlib import Path
import subprocess, json

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'build'
OUT.mkdir(exist_ok=True)
gcc = next(Path('C:/ST').glob('**/arm-none-eabi-gcc.exe'))
cmsis = ROOT / 'vendor/CMSIS'
hal = ROOT / 'vendor/STM32F1xx_HAL_Driver'
sources = [ROOT/'firmware/main.c',
    cmsis/'Device/ST/STM32F1xx/Source/Templates/system_stm32f1xx.c',
    cmsis/'Device/ST/STM32F1xx/Source/Templates/gcc/startup_stm32f103xb.s']
sources += [hal/'Src'/f'stm32f1xx_{name}.c' for name in
    ['hal', 'hal_cortex', 'hal_gpio', 'hal_rcc', 'hal_rcc_ex', 'hal_flash', 'hal_flash_ex']]
args = [str(gcc), '-mcpu=cortex-m3', '-mthumb', '-std=c11', '-Os', '-g3',
    '-Wall', '-Wextra', '-Werror', '-ffunction-sections', '-fdata-sections',
    '-DSTM32F103xB', '-DUSE_HAL_DRIVER']
for inc in [ROOT/'firmware', hal/'Inc', cmsis/'Include', cmsis/'Device/ST/STM32F1xx/Include']:
    args += ['-I', str(inc)]
args += [str(s) for s in sources]
args += ['-T', str(ROOT/'firmware/panel.ld'), '-nostartfiles', '--specs=nano.specs',
    '--specs=nosys.specs', '-Wl,--gc-sections', f'-Wl,-Map={OUT / "panel.map"}',
    '-o', str(OUT/'panel.elf')]
subprocess.run(args, check=True)
for fmt, ext in [('binary','bin'), ('ihex','hex')]:
    subprocess.run([str(gcc.parent/'arm-none-eabi-objcopy.exe'), '-O',fmt,
        str(OUT/'panel.elf'), str(OUT/f'panel.{ext}')], check=True)
nm = subprocess.check_output([str(gcc.parent/'arm-none-eabi-nm.exe'), str(OUT/'panel.elf')], text=True)
address = next(int(line.split()[0],16) for line in nm.splitlines() if line.endswith(' panel_status'))
(OUT/'symbols.json').write_text(json.dumps({'panel_status':address},indent=2))
size = subprocess.check_output([str(gcc.parent/'arm-none-eabi-size.exe'),str(OUT/'panel.elf')], text=True)
print(size)
(OUT/'size.txt').write_text(size)
