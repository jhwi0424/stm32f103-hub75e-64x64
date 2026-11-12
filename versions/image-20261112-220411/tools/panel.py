"""ST-Link operations; runtime status reads do not halt scanning."""
import argparse, collections, contextlib, datetime, hashlib, json, socket, subprocess, time
from pathlib import Path
from usb_status import devices

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'build'
FIELDS = 'magic version frames row on_us row_us core_hz enable rgb_mask fault last_frame_cycles'.split()
IMAGE_FIELDS = 'color_bits image_mode max_row_cycles row_overruns'.split()

class Link:
    def __init__(self, port):
        self.sock = socket.create_connection(('127.0.0.1',port), timeout=3)
        self.sock.settimeout(120)
    def command(self, cmd):
        self.sock.sendall(cmd.encode()+b'\x1a')
        data=b''
        while not data.endswith(b'\x1a'):
            chunk=self.sock.recv(65536)
            if not chunk: raise ConnectionError('OpenOCD disconnected')
            data+=chunk
        result=data[:-1].decode()
        if result.startswith('Error'): raise RuntimeError(result)
        return result
    def words(self, address, count=1, bits=32):
        result=self.command(f'read_memory {address} {bits} {count}')
        try: values=[int(x,0) for x in result.split()]
        except ValueError: raise RuntimeError(f'Memory read failed at {address:#x}: {result}') from None
        if len(values)!=count:raise RuntimeError(f'Short memory read at {address:#x}: {result}')
        return values
    def status(self):
        address=json.loads((OUT/'symbols.json').read_text())['panel_status']
        values=self.words(address,len(FIELDS))
        if len(values)!=len(FIELDS) or values[0]!=0x48554237:
            raise RuntimeError(f'Firmware signature mismatch: {values}')
        d=dict(zip(FIELDS,values))
        if d['version'] >= 2:
            d.update(zip(IMAGE_FIELDS,self.words(address+len(FIELDS)*4,len(IMAGE_FIELDS))))
        d['refresh_hz']=round(d['core_hz']/d['last_frame_cycles'],3) if d['last_frame_cycles'] else 0
        return d

@contextlib.contextmanager
def connection(under_reset=False, speed=50):
    ocd=next(Path('C:/ST').glob('**/openocd.exe'))
    cfg=next(Path('C:/ST').glob('**/stlink-dap.cfg'))
    present=devices()
    stlink=any('VID_0483&PID_3748' in d['id'].upper() and not d['problem_code'] for d in present)
    dap=any(('VID_0D28' in d['id'].upper() or 'PID_DA42' in d['id'].upper()) and not d['problem_code'] for d in present)
    interface='interface/cmsis-dap.cfg' if dap and not stlink else 'interface/stlink-dap.cfg'
    print(f'Probe interface: {interface}',flush=True)
    log=open(OUT/f'openocd-{datetime.datetime.now():%Y%m%d-%H%M%S}.log','w',encoding='utf-8')
    startup=f'bindto 127.0.0.1; tcl_port 16667; telnet_port disabled; gdb_port disabled; adapter speed {int(speed)}; '
    if under_reset:startup+='reset_config srst_only srst_nogate connect_assert_srst; '
    startup+='init'
    p=subprocess.Popen([str(ocd),'-s',str(cfg.parent.parent),
        '-f',interface,'-f','target/stm32f1x.cfg',
        '-c',startup],
        cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
    link=None
    try:
        for _ in range(80):
            if p.poll() is not None:
                log.flush()
                raise RuntimeError(Path(log.name).read_text())
            try: link=Link(16667); break
            except OSError: time.sleep(.1)
        if link is None: raise RuntimeError('OpenOCD startup timed out')
        yield link
    finally:
        if link: link.sock.close()
        p.terminate()
        try:p.wait(timeout=5)
        except subprocess.TimeoutExpired:p.kill();p.wait()
        log.close()

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=['identify','flash','status','off','on','diagnose','sample'])
    parser.add_argument('--under-reset',action='store_true')
    parser.add_argument('--speed',type=int,choices=range(1,1001),default=50,metavar='1..1000',help='SWD clock in kHz')
    parser.add_argument('--on-us',type=int,choices=range(0,101),metavar='0..100')
    a=parser.parse_args()
    report={'timestamp':datetime.datetime.now().astimezone().isoformat(),'action':a.action}
    with connection(a.under_reset,a.speed) as link:
        if a.under_reset:
            link.command('adapter deassert srst')
        if a.action in ('identify','flash'):
            report['device_id']=hex(link.words(0xe0042000)[0])
            report['flash_kib']=link.words(0x1ffff7e0,bits=16)[0]
            report['cpuid']=hex(link.words(0xe000ed00)[0])
            print(json.dumps(report,indent=2),flush=True)
        if a.action=='flash':
            if int(report['device_id'],16)&0xfff != 0x410:
                raise RuntimeError('Expected STM32F103 medium-density device')
            if report['flash_kib']<64: raise RuntimeError('Less than 64 KiB flash')
            # NRST is not wired on this setup. Use the Cortex-M software reset
            # to recover from a partially erased vector table/lockup, then halt.
            link.command('reset_config none')
            link.command('cortex_m reset_config sysresetreq')
            report['reset_halt_result']=link.command('reset halt')
            link.command('wait_halt 2000')
            if not link.words(0xe000edf0)[0] & 0x20000:
                raise RuntimeError('Target did not halt; programming cancelled')
            # Shut down the documented buffer gate, then force panel OE high.
            link.command('halt')
            link.command('mww 0x40021018 0x0000081d')
            link.command('mww 0x40010c10 0x20000000')
            link.command('mww 0x40010810 0x00000100')
            link.command('mww 0x40012c18 0x00000040')
            link.command('mww 0x40012c20 0x00000003')
            backup=OUT/f'flash-backup-{datetime.datetime.now():%Y%m%d-%H%M%S}.bin'
            report['backup']=str(backup)
            report['backup_result']=link.command(f'dump_image {{{backup.relative_to(ROOT).as_posix()}}} 0x08000000 0x10000')
            if not backup.exists() or backup.stat().st_size!=65536:
                raise RuntimeError('Flash backup failed; programming cancelled')
            print('Flash backup complete; programming image...',flush=True)
            image='build/panel.bin'
            report['write_result']=link.command(f'flash write_image erase {{{image}}} 0x08000000 bin')
            if 'wrote ' not in report['write_result']:
                raise RuntimeError(f'Flash programming failed: {report["write_result"]}; see OpenOCD log')
            report['verify_result']=link.command(f'verify_image {{{image}}} 0x08000000 bin')
            if 'verified ' not in report['verify_result']:
                raise RuntimeError(f'Flash verification failed: {report["verify_result"]}; see OpenOCD log')
            print('Flash verified; reading back for byte comparison...',flush=True)
            # Independently compare the programmed image, including vector table.
            image_data=(OUT/'panel.bin').read_bytes()
            readback=OUT/'panel-readback.bin'
            link.command(f'dump_image {{{readback.relative_to(ROOT).as_posix()}}} 0x08000000 {len(image_data)}')
            if not readback.exists() or readback.read_bytes()!=image_data:
                raise RuntimeError('Flash readback differs from firmware image')
            report['readback_matches']=True
            report['image_sha256']=hashlib.sha256(image_data).hexdigest()
            (OUT/'programming-report.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
            link.command('reset run')
            time.sleep(.5)
        if a.action=='diagnose':
            registers={'RCC':(0x40021000,10),'GPIOA':(0x40010800,4),
                'GPIOB':(0x40010c00,4),'AFIO_MAPR':(0x40010004,1),
                'TIM1':(0x40012c00,18),'SCB_FAULT':(0xe000ed28,6)}
            for label,(address,count) in registers.items():
                report[label]=[hex(x) for x in link.words(address,count)]
            try:report['status']=link.status()
            except RuntimeError as e:report['status_error']=str(e)
        if a.action in ('on','off'):
            link.status() # validate image before writing
            address=json.loads((OUT/'symbols.json').read_text())['panel_status']
            if a.on_us is not None:
                link.command(f'write_memory {address+16} 32 {{{a.on_us}}}')
            link.command(f'write_memory {address+28} 32 {{{1 if a.action=="on" else 0}}}')
        if a.action=='sample':
            link.status()
            rgb=collections.Counter();oe=collections.Counter();rows=collections.Counter()
            for _ in range(256):
                pa=link.words(0x40010808)[0];pb=link.words(0x40010c08)[0]
                rgb[str(pa&63)]+=1;oe[str((pa>>8)&1)]+=1
                rows[str((pb&3)|((pb>>8)&28))]+=1
            report['pin_samples']={'samples':256,'rgb':dict(rgb),'oe':dict(oe),
                'row_addresses':dict(sorted(rows.items(),key=lambda x:int(x[0])))}
        if a.action not in ('identify','diagnose'):
            report['first']=link.status()
            time.sleep(1)
            report['second']=link.status()
            if report['second']['frames']<=report['first']['frames']:
                raise RuntimeError('Frame counter is not advancing')
            if report['second']['fault']:raise RuntimeError('Firmware reports fault')
    (OUT/f'{a.action}-report.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps(report,indent=2,ensure_ascii=False))

if __name__=='__main__':main()
