import asyncio
from smtez import *

async def main():
    smt = smtez("ws://127.0.0.1:9002") #设置目标为本地设备
    await smt.connect() #连接本地设备
    await smt.syncSetting() #触发用户在ui的操作更改生效

    await smt.doPump(True) #工作前打开气泵

    nozzleId = 0#使用的吸嘴编号
    
    takeresult = await smt.doGetFeederPart("take","auto") #从元件为"take",封装为"auto"类型的飞达中获取元件
    placeresult = await smt.doGetFeederPart("place","auto") #获取放置元件的飞达位置

    takepos = Position.fromJson(takeresult["part"]) #解析获取到的坐标
    placepos = Position.fromJson(placeresult["part"])

    testpoint = Position(-70,10,-10,0) #定义测试器的位置
    await smt.doBottomDetectPlace(nozzleId,"take","auto",takepos,testpoint,False) #从拾取点拾取后通过底部视觉纠正坐标后放入测试点

    """
    在这里使用外部通讯对元件进行一些测试或者烧录
    """

    if xx:
        #元件可用,我们放入飞达
        await smt.doBottomDetectPlace(nozzleId,"take","auto",testpoint,placepos,False)
    else:
        #不可用丢入回收点
        await smt.doTakePlace(nozzleId,testpoint,Position(0,0,0,0),False)

    await smt.doPump(False) #结束:关闭气泵

asyncio.run(main())