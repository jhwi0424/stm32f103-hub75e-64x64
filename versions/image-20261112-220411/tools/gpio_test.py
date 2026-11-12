"""GPIO loopback checks. Use only after disconnecting all panel signal wires."""
import argparse, datetime, json, time
from pathlib import Path
from panel import connection

def write(link,address,value):
    link.command(f'write_memory {address} 32 {{{value}}}')

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--signals-disconnected',action='store_true',required=True)
    parser.parse_args()
    report={'timestamp':datetime.datetime.now().astimezone().isoformat(),'pins':[]}
    with connection(True) as link:
        link.command('adapter deassert srst')
        status=link.status()
        address=json.loads((Path('build')/'symbols.json').read_text())['panel_status']
        write(link,address+28,0)
        time.sleep(.02)
        link.command('halt')
        if not link.words(0xe000edf0)[0]&0x20000:
            raise RuntimeError('CPU did not halt; GPIO test cancelled')
        saved_a=link.words(0x40010800,2)
        saved_b=link.words(0x40010c00,2)
        try:
            write(link,0x40012c00,8)
            write(link,0x40012c18,0x40)
            # PA0-8 and PB0/1/10/11/12 only; retain all SWD pins.
            write(link,0x40010810,0x01ff0000)
            write(link,0x40010c10,0x1c030000)
            write(link,0x40010800,0x22222222)
            write(link,0x40010804,(saved_a[1]&~15)|2)
            write(link,0x40010c00,(saved_b[0]&~255)|0x22)
            write(link,0x40010c04,(saved_b[1]&~0xfff00)|0x22200)
            for port,base,pins in [('PA',0x40010800,range(9)),('PB',0x40010c00,[0,1,10,11,12])]:
                for pin in pins:
                    bit=1<<pin
                    write(link,base+0x10,bit<<16)
                    low=(link.words(base+8)[0]>>pin)&1
                    write(link,base+0x10,bit)
                    high=(link.words(base+8)[0]>>pin)&1
                    write(link,base+0x10,bit<<16)
                    report['pins'].append({'pin':f'{port}{pin}','low_read':low,'high_read':high,'pass':low==0 and high==1})
        finally:
            write(link,0x40010810,0x100 | (0xff<<16))
            write(link,0x40010800,saved_a[0]);write(link,0x40010804,saved_a[1])
            write(link,0x40010c00,saved_b[0]);write(link,0x40010c04,saved_b[1])
            link.command('resume')
        report['pass']=all(pin['pass'] for pin in report['pins']) and len(report['pins'])==14
    (Path(__file__).resolve().parents[1]/'build/gpio-test.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
