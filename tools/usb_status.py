"""Read Windows USB enumeration and problem codes without admin rights."""
import argparse, ctypes as c, datetime, json, time
from ctypes import wintypes as w
from pathlib import Path

class GUID(c.Structure):
    _fields_=[('a',w.DWORD),('b',w.WORD),('c',w.WORD),('d',c.c_ubyte*8)]
class Device(c.Structure):
    _fields_=[('size',w.DWORD),('guid',GUID),('node',w.DWORD),('reserved',c.c_size_t)]
setup=c.WinDLL('setupapi',use_last_error=True)
cfg=c.WinDLL('cfgmgr32',use_last_error=True)
setup.SetupDiGetClassDevsW.argtypes=[c.c_void_p,w.LPCWSTR,w.HWND,w.DWORD]
setup.SetupDiGetClassDevsW.restype=w.HANDLE
setup.SetupDiEnumDeviceInfo.argtypes=[w.HANDLE,w.DWORD,c.POINTER(Device)]
setup.SetupDiEnumDeviceInfo.restype=w.BOOL
setup.SetupDiDestroyDeviceInfoList.argtypes=[w.HANDLE]
cfg.CM_Get_Device_IDW.argtypes=[w.DWORD,w.LPWSTR,w.ULONG,w.ULONG]
cfg.CM_Get_DevNode_Status.argtypes=[c.POINTER(w.ULONG),c.POINTER(w.ULONG),w.DWORD,w.ULONG]

def devices():
    handle=setup.SetupDiGetClassDevsW(None,'USB',None,6)
    if handle==c.c_void_p(-1).value: raise c.WinError(c.get_last_error())
    result=[]
    try:
        index=0
        while True:
            item=Device();item.size=c.sizeof(item)
            if not setup.SetupDiEnumDeviceInfo(handle,index,c.byref(item)):
                if c.get_last_error()!=259: raise c.WinError(c.get_last_error())
                break
            index+=1
            name=c.create_unicode_buffer(1024)
            if cfg.CM_Get_Device_IDW(item.node,name,1024,0): continue
            identity=name.value.upper()
            if not any(x in identity for x in ['VID_0483','VID_0000','VID_0D28','PID_DA42']): continue
            flags=w.ULONG();problem=w.ULONG()
            rc=cfg.CM_Get_DevNode_Status(c.byref(flags),c.byref(problem),item.node,0)
            result.append({'id':name.value,'problem_code':problem.value,'status_flags':hex(flags.value),'query_result':rc})
    finally: setup.SetupDiDestroyDeviceInfoList(handle)
    return result

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--watch',type=int,default=0);args=parser.parse_args()
    start=time.monotonic();previous=None;history=[]
    while True:
        state=devices()
        if state!=previous:
            row={'timestamp':datetime.datetime.now().astimezone().isoformat(),'devices':state}
            history.append(row);print(json.dumps(row,ensure_ascii=False),flush=True);previous=state
        if time.monotonic()-start>=args.watch: break
        time.sleep(1)
    (Path(__file__).resolve().parents[1]/'build/usb-latest.json').write_text(json.dumps(history,indent=2),encoding='utf-8')
