import asyncio
from smtez import *

async def programmerDownload():
    process = await asyncio.create_subprocess_shell('"C:\\Program Files\\STMicroelectronics\\STM32Cube\\STM32CubeProgrammer\\bin\\STM32_Programmer_CLI.exe" -c port=SWD -w firmware.bin 0x08000000',
    stdout= asyncio.subprocess.PIPE,stderr= asyncio.subprocess.PIPE)

    stdout,stderr = await process.communicate()
    print(stdout)
    print(stderr)

    return_code = process.returncode

    if return_code != 0:
        return False

    return True
async def main():

    smt = smtez("ws://127.0.0.1:9002") #设置目标为本地设备
    await smt.connect() #连接本地设备
    await smt.syncSetting() #触发用户在ui的操作更改生效

    testpoint = Position(-196.9,-37.68,-17,90) #定义烧录器的位置
    droppoint = Position(0,0,0,0) #抛料器位置

    while True:
        nozzleId = 1#使用的吸嘴编号
        
        takeresult = await smt.doGetFeederPart("take","auto") #从元件为"take",封装为"auto"类型的飞达中获取元件
        placeresult = await smt.doGetFeederPart("place","auto") #获取放置元件的飞达位置
        if takeresult["result"] != "ok" or placeresult["result"] != "ok":
            break

        takepos = Position.fromJson(takeresult["part"]) #解析获取到的坐标
        placepos = Position.fromJson(placeresult["part"])

        await smt.doPump(True)
        
        if not await smt.doBottomDetectPlace(nozzleId,"take","auto",takepos,testpoint,autoplaceHeight=True,keepDown=True): #从拾取点拾取后通过底部视觉纠正坐标后放入测试点
            await smt.doTakeDown(nozzleId,droppoint)
            continue

        await smt.doPump(False)
        
        """
        在这里使用外部通讯对元件进行一些测试或者烧录
        """
        await asyncio.sleep(1)
        isDone = await programmerDownload()

        await smt.doPump(True)
        await smt.doNozzleSwitch(nozzleId,True)

        if isDone:
            #元件可用,我们放入飞达
            if not await smt.doBottomDetectPlace(nozzleId,"take","auto",testpoint,placepos,autoplaceHeight=True,isNozzleAtTop=True):
                await smt.doTakePlace(nozzleId,testpoint,droppoint)
        else:
            #不可用丢入回收点
            await smt.doTakePlace(nozzleId,testpoint,droppoint)

        await smt.doPump(False)

        
    
    await smt.doPump(False) #结束:关闭气泵

asyncio.run(main())