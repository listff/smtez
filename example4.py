# -*- coding: utf-8 -*-
import asyncio
import time
from smtez import *
import ctypes
from ctypes import wintypes
import threading
import signal
import sys

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# ---- 常量 ----
WM_HOTKEY      = 0x0312

MOD_ALT        = 0x0001
MOD_CONTROL    = 0x0002
MOD_SHIFT      = 0x0004
MOD_WIN        = 0x0008
MOD_NOREPEAT   = 0x4000   # Win7+

# 一些常用虚拟键（更多可查 winuser.h）
VK_A = 0x41; VK_B = 0x42; VK_C = 0x43; VK_D = 0x44
VK_E = 0x45; VK_F = 0x46; VK_G = 0x47; VK_H = 0x48
VK_S = 0x53
VK_F9 = 0x78
VK_SPACE = 0x20

# ---- 结构体 ----
class MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd",    wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam",  wintypes.WPARAM),
        ("lParam",  wintypes.LPARAM),
        ("time",    wintypes.DWORD),
        ("pt_x",    wintypes.LONG),   # POINT.x
        ("pt_y",    wintypes.LONG),   # POINT.y
        ("lPrivate", wintypes.DWORD),
    ]

# ---- 工具函数 ----
def register_hotkey(hotkey_id: int, modifiers: int, vk: int):
    """
    注册一个全局快捷键。
    hotkey_id: 你自定义的ID（1,2,3...）
    modifiers: 修饰键组合（如 MOD_CONTROL | MOD_ALT | MOD_NOREPEAT）
    vk:        虚拟键码（如 VK_H，或 ord('X') 也可以）
    """
    if not user32.RegisterHotKey(None, hotkey_id, modifiers, vk):
        raise OSError("RegisterHotKey 失败，可能是被其他程序占用或权限不足")

def unregister_hotkey(hotkey_id: int):
    user32.UnregisterHotKey(None, hotkey_id)

def unregister_all(ids):
    for i in ids:
        user32.UnregisterHotKey(None, i)

# ---- 消息循环线程 ----
stop_flag = threading.Event()

def message_loop(on_hotkey,loop):
    HOTKEYS = [
        (1, MOD_NOREPEAT, VK_SPACE),
        # (3, MOD_CONTROL | MOD_ALT | MOD_NOREPEAT, VK_F9),
    ]
    
    for hid, mods, vk in HOTKEYS:
        register_hotkey(hid, mods, vk)

    msg = MSG()
    while not stop_flag.is_set():
        # GetMessageW: 取消息（阻塞）。返回 -1 失败，0 退出，>0 正常
        ret = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
        if ret == -1:
            # 出错
            break
        elif ret == 0:
            # 收到 WM_QUIT
            break
        else:
            if msg.message == WM_HOTKEY:
                hotkey_id = msg.wParam
                # lParam: 低位是修饰键，高位是虚拟键
                modifiers = msg.lParam & 0xFFFF
                vk        = (msg.lParam >> 16) & 0xFFFF
                asyncio.run_coroutine_threadsafe(on_hotkey(hotkey_id, modifiers, vk),loop)
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

lastkeytime = 0.0

async def onKeyboard(smt:smtez):
    global lastkeytime

    if (time.time() - lastkeytime) < 3:
        return
    
    lastkeytime = time.time()
        
    takeresult = await smt.doGetFeederPart("take","auto")
    print(takeresult)
    if takeresult["result"] != "ok":
        print("识别失败")
        return
    
    print("识别成功")

    takepos = Position.fromJson(takeresult["part"])

    cmd = {
        "op":"replace",
        "path":"/boards/0/allchildparts/0/setting",
        "value":{
                    "autoheight": False,
                    "boardheight": takepos.z,
                    "markrange": 1.5,
                    "marktype": "none",
                    "origin_r": takepos.r,
                    "origin_x": takepos.x,
                    "origin_y": takepos.y
                }
    }
    
    await smt.sendCall({"cmd": "database","value": [cmd]})
    await smt.sendCall({
    "cmd": "task",
    "task": "fiducialcheck",
    "board": 0,
    "childboard": 0,
    "global": True,
    })

    await smt.sendCall({
        "cmd": "aciton",
        "aciton": "replay",
        "forceBoardIndex": -1,
        "ignore":True
        })

async def on_hotkey(hid, mods, vk):
    global smt
    asyncio.create_task(onKeyboard(smt))

async def main():
    global smt
    print("开始连接中")

    smt = smtez("ws://127.0.0.1:9002") #设置目标为本地设备
    await smt.connect() #连接本地设备
    await smt.syncSetting() #触发用户在ui的操作更改生效

    print("连接成功")

    kernel32.SetConsoleOutputCP(65001)
    
    def handle_sigint(signum, frame):
        stop_flag.set()
        user32.PostQuitMessage(0)  # 让 GetMessage 退出
        exit(0)

    signal.signal(signal.SIGINT, handle_sigint)

    loop = asyncio.get_running_loop()

    t = threading.Thread(target=message_loop, args=(on_hotkey,loop), daemon=True)
    t.start()

    while True:
        await asyncio.sleep(0.1)

asyncio.run(main())
