import asyncio
import websockets
import json

class Position:
    x:float = 0
    y:float = 0
    z:float = 0
    r:float = 0

    def __init__(self,x:float = 0,y:float = 0,z:float = 0,r:float = 0) -> None:
        self.x = x
        self.y = y
        self.z = z
        self.r = r
    
    def fromJson(data:dict) -> None:
        p = Position()
        if "x" in data:
            p.x = data["x"]
        if "y" in data:
            p.y = data["y"]
        if "z" in data:
            p.z = data["z"]
        if "r" in data:
            p.r = data["r"]
        
        return p

    def toJson(self) -> dict:
        return { "x":self.x,"y":self.y,"z":self.z,"r":self.r }

    def __sub__(self,other):
        if isinstance(other,Position):
            return Position(self.x - other.x,self.y - other.y,self.z - other.z,self.r - other.r)
        
        return NotImplemented

    def __add__(self,other):
        if isinstance(other,Position):
            return Position(self.x + other.x,self.y + other.y,self.z + other.z,self.r + other.r)
        
        return NotImplemented

class smtez:
    serverurl :str
    isConnected : bool
    __isConnectEvent = asyncio.Event()
    websocket: websockets.WebSocketClientProtocol
    __task : asyncio.Task 
    asyncCalls: dict[str,list[asyncio.Future]] = {}

    def __init__(self,serverurl :str) -> None:
        self.serverurl = serverurl
        self.__task = asyncio.create_task(self.__loop())

    def __del__(self) -> None:
        self.__task.cancel()
    
    async def __loop(self) -> None:
        while True:
            try:
                await self.__isConnectEvent.wait()

                while True:
                    if self.isConnected == False:
                        break

                    data = await self.websocket.recv()
                    eventdata = json.loads(data)

                    if "hashCode" in eventdata:
                        hashCode = eventdata["hashCode"]
                        if eventdata["event"] not in self.asyncCalls:
                            continue

                        calls = self.asyncCalls[eventdata["event"]]
                        for call in calls:
                            if call.__hash__() == hashCode:
                                call.set_result(eventdata)
                                calls.remove(call)
                                break
            except asyncio.CancelledError:
                return

                
    
    async def connect(self) -> None:
        self.websocket = await websockets.connect(self.serverurl)
        self.isConnected = True
        self.__isConnectEvent.set()
    
    async def sendCall(self,cmd:dict):
        waitfuture = asyncio.Future()
        if(cmd["cmd"] not in self.asyncCalls):
            self.asyncCalls[cmd["cmd"]] = []
        
        self.asyncCalls[cmd["cmd"]].append(waitfuture)

        cmd["hashCode"] = waitfuture.__hash__()
        await self.websocket.send(json.dumps(cmd))

        return await waitfuture

    def sendCallSync(self,cmd:dict):
        asyncio.create_task(self.websocket.send(json.dumps(cmd)))

    def light(id:int,open:bool):
        return {"status":"light","cmd":"setstatus","light":id,"open":open}
    def move(x:float,y:float):
        return {"cmd": "move","move": True, "local": False, "x": x, "y": y}
    def pump(open:bool):
        return {"cmd": "set", "setting": "pump", "open": open,"nosafe": True}
    def nozzleSwitch(id:int,open:bool):
        return {"cmd": "set","id": id, "setting": "nozzleSwitch", "open": open,"nosafe": True}
    def nozzleToPosition(id:int,x:float,y:float):
        return {"cmd": "task","task": "nozzleToPosition","id": id,"pos": {"x": x, "y": y}}
    def nozzleZ(id:int,z:float):
        return {"cmd": "move","nozzle": id,"local": False,"move": True,"z": z,"nosafe": True}
    def nozzleRot(id:int,r:float,local:bool = False):
        return {"cmd": "move","nozzle": id,"r": r,"nosafe": True,"local": local}
    def detectOffset(part:str,package:str,camera:int,nozzle:int,dst:Position):
        return {"cmd": "detectOffset","value": part,"package": package,"camera": camera,"nozzle": nozzle,"dst":dst.toJson()}
    def pluginsUpdateData():
        return {"cmd": "plugins","call": "updataData"}
    def getFeederPart(part:str,package:str):
        return {"cmd": "plugins","call": "getPart","part":part,"package":package}
    
    async def syncSetting(self):
        await self.sendCall(smtez.pluginsUpdateData())

    async def doLight(self,id: int, open: bool):
        return await self.sendCall(smtez.light(id,open))
    async def doGetFeederPart(self,part:str,package:str):
        return await self.sendCall(smtez.getFeederPart(part,package))
    async def doSafeZ(self):
        return await self.sendCall(smtez.nozzleZ(0,0))
    async def doPump(self,open:bool):
        return await self.sendCall(smtez.pump(open))
    async def doNozzleZ(self,nozzle:int,z:float):
        return await self.sendCall(smtez.nozzleZ(nozzle,z))
    async def doMove(self,pos:Position):
        return await self.sendCall(smtez.move(pos.x,pos.y))
    async def doNozzleSwitch(self,nozzle: int, open: bool):
        return await self.sendCall(smtez.nozzleSwitch(nozzle,open))
    async def doNozzleToPosition(self,nozzle:int,dst:Position):
        return await self.sendCall(smtez.nozzleToPosition(nozzle,dst.x,dst.y))
    async def doNozzleRot(self,nozzle:int,r: float, local: bool = False):
        return await self.sendCall(smtez.nozzleRot(nozzle,r,local))

    async def doTakeUp(self,nozzle:int,pos:Position,delay:float = 0.2):
        await self.doSafeZ()
        await self.doNozzleToPosition(nozzle,pos)
        await self.doNozzleZ(nozzle,pos.z)
        await self.doNozzleSwitch(nozzle,True)
        await asyncio.sleep(delay)
        await self.doSafeZ()
    async def doTakeDown(self,nozzle:int,pos:Position,delay:float = 0.2,keepDown:bool = False):
        await self.doSafeZ()
        await self.doNozzleToPosition(nozzle,pos)
        await self.doNozzleZ(nozzle,pos.z)
        await self.doNozzleSwitch(nozzle,False)
        if not keepDown:
            await asyncio.sleep(delay)
            await self.doSafeZ()

    async def doTakePlace(self,nozzle:int,takepos:Position,placepos:Position):
        await self.doSafeZ()
        await self.doTakeUp(nozzle,takepos)
        await self.doNozzleRot(nozzle,-takepos.r,True)
        await self.doNozzleRot(nozzle,placepos.r,True)
        await self.doTakeDown(nozzle,placepos)

    async def doTopDetectPlace(self,nozzle:int,partname:str,packagename:str,takepos:Position,placepos:Position,autoplaceHeight:bool = True,keepDown:bool = False) -> bool:
        await self.doSafeZ()
        await self.doMove(takepos)
        result = await self.sendCall(smtez.detectOffset(partname,packagename,0,nozzle,placepos))
        if result["result"] != "ok":
            return False

        newpart = Position.fromJson(result["src"][0])
        newplacepos = Position.fromJson(result["dst"])

        newpart.z = takepos.z
        
        if not autoplaceHeight:
            newplacepos.z = placepos.z

        await self.doTakeUp(nozzle,newpart)

        await self.doNozzleRot(nozzle,newpart.r,True)
        
        await self.doTakeDown(nozzle,newplacepos,keepDown)
        
        return True
    
    async def doBottomDetectPlace(self,nozzle:int,partname:str,packagename:str,takepos:Position,placepos:Position,autoplaceHeight:bool = True,isNozzleAtTop:bool = False,keepDown:bool = False) -> bool:
        await self.doSafeZ()
        if not isNozzleAtTop:
            await self.doTakeUp(nozzle,takepos)
            
        await self.doNozzleRot(nozzle,-takepos.r,True)

        result = await self.sendCall(smtez.detectOffset(partname,packagename,1,nozzle,placepos))
        if result["result"] != "ok":
            return False

        newplacepos = Position.fromJson(result["dst"])

        if not autoplaceHeight:
            newplacepos.z = placepos.z

        await self.doNozzleRot(nozzle,newplacepos.r,False)
        await self.doTakeDown(nozzle,newplacepos,keepDown=keepDown)
        
        return True

    
