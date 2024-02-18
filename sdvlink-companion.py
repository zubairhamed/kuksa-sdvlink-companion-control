import keyboard
from kuksa_client.grpc.aio import VSSClient
from kuksa_client.grpc import Datapoint
from kuksa_client.grpc import DataEntry
from kuksa_client.grpc import DataType
from kuksa_client.grpc import EntryUpdate
from kuksa_client.grpc import Field as VssField
from kuksa_client.grpc import Metadata
from kuksa_client.grpc import EntryRequest
from kuksa_client.grpc import View
from kuksa_client.grpc import SubscribeEntry
import asyncio 

# VSS Path definitions
PATH_VEHICLE_SPEED = "Vehicle.Speed"
PATH_LEFTINDICATOR_SIGNALING = "Vehicle.Body.Lights.DirectionIndicator.Left.IsSignaling"
PATH_RIGHTINDICATOR_SIGNALING = "Vehicle.Body.Lights.DirectionIndicator.Right.IsSignaling"
PATH_ENGINE_RUNNING = "Vehicle.Powertrain.CombustionEngine.IsRunning"
PATH_STEERING_ANGLE = "Vehicle.Chassis.Axle.Row1.SteeringAngle"
PATH_BEAM_LOW_ISON = "Vehicle.Body.Lights.Beam.Low.IsOn"
PATH_BEAM_HIGH_ISON = "Vehicle.Body.Lights.Beam.High.IsOn"
PATH_CURRENTGEAR = "Vehicle.Powertrain.Transmission.CurrentGear"
PATH_BRAKEPEDAL_POSITION = "Vehicle.Chassis.Brake.PedalPosition"

DATABROKER_ADDRESS = "localhost"
DATABROKER_PORT = 55555
vssClient = VSSClient(DATABROKER_ADDRESS, DATABROKER_PORT) 

leftSignal = False
rightSignal = False
engineStarted = False
turnAngle = 0
lowBeam = False
highBeam = False
gearPosition = "P" # PRDNS

valueMap = {}
provisioningDict = {
    PATH_VEHICLE_SPEED: 0,
    PATH_LEFTINDICATOR_SIGNALING: False,
    PATH_RIGHTINDICATOR_SIGNALING: False,
    PATH_ENGINE_RUNNING: False,
    PATH_STEERING_ANGLE: 0,
    PATH_BEAM_LOW_ISON: False,
    PATH_BEAM_HIGH_ISON: False,
    PATH_CURRENTGEAR: "P",
    PATH_BRAKEPEDAL_POSITION: 0
}

def kbControlPrint(kb, path, val):
    print (f"[{kb}] Set {path} to {val}")

async def Set(path, val, valType, kb):
    try:        
        async with vssClient:
            updates = (EntryUpdate(DataEntry(path, 
                value=Datapoint(value=val),
                metadata=Metadata(data_type=valType),
            ), (VssField.VALUE,)),)

            # valueMap[path] = val
            if kb != None:
                kbControlPrint(kb, path, val)

            await vssClient.set(updates=updates)
    except Exception as err:
        print(f"ERROR: Unable to connect to Kuksa Databroker {err}. Connection Details: {DATABROKER_ADDRESS} port {DATABROKER_PORT}")

async def handleAccelerate():
    currentSpeed = valueMap[PATH_VEHICLE_SPEED]

    if ((currentSpeed+5) > 240):         
        currentSpeed = 240
    else:
        currentSpeed += 5

    await Set(PATH_VEHICLE_SPEED, currentSpeed, DataType.FLOAT, "W")

async def handleDecelerate():
    currentSpeed = valueMap[PATH_VEHICLE_SPEED]

    if ((currentSpeed-5) < 0):
        currentSpeed = 0
    else:
        currentSpeed -= 5

    await Set(PATH_BRAKEPEDAL_POSITION, 50, DataType.UINT8, "S")
    await Set(PATH_VEHICLE_SPEED, currentSpeed, DataType.FLOAT, "S")
    await Set(PATH_BRAKEPEDAL_POSITION, 0, DataType.UINT8, "S")

async def handleLeftTurn():
    turnAngle = valueMap[PATH_STEERING_ANGLE]

    if (turnAngle+5 > 40): 
        turnAngle = 40
    else:
        turnAngle += 5
    await Set(PATH_STEERING_ANGLE, turnAngle, DataType.FLOAT, "A")

async def handleRightTurn():    
    turnAngle = valueMap[PATH_STEERING_ANGLE]

    if (turnAngle-5 < -40): 
        turnAngle = -40
    else:
        turnAngle -= 5
    await Set(PATH_STEERING_ANGLE, turnAngle, DataType.FLOAT, "D")

async def handleLeftSignal():
    leftSignal = valueMap[PATH_LEFTINDICATOR_SIGNALING]

    if leftSignal:
        leftSignal = False
    else:
        leftSignal = True
        
    await Set(PATH_LEFTINDICATOR_SIGNALING, leftSignal, DataType.BOOLEAN, "SHIFT+A")

async def handleRightSignal():
    rightSignal = valueMap[PATH_RIGHTINDICATOR_SIGNALING]

    if rightSignal:
        rightSignal = False
    else:
        rightSignal = True
        
    await Set(PATH_RIGHTINDICATOR_SIGNALING, rightSignal, DataType.BOOLEAN, "SHIFT+D")

async def unimplemented():
    print("Not implemented yet")
    pass

async def subscribe():
    global provisionDict

    async with vssClient:
        entries = []
        for key in valueMap:
            entries.append(SubscribeEntry(key, View.FIELDS, (VssField.VALUE, VssField.ACTUATOR_TARGET)))

        async for updates in vssClient.subscribe(entries=entries): 
            for update in updates:
                if update.entry.value is not None:
                    valueMap[update.entry.path] = update.entry.value.value
                    print(f"[SUB] {update.entry.path}: {update.entry.value.value}")

def provisionValue(entries, path, defaultValue):
    for e in entries:
        if e.path == path:
            if e.value != None:
                valueMap[path] = e.value.value
            else:
                valueMap[path] = defaultValue

async def provisionVehicleValues():
    print(">>> Initializing values from Data Broker")
    try:        
        async with vssClient:
            provisioningEntries = []
            for key in provisioningDict:
                provisioningEntries.append(EntryRequest(key, View.ALL, (VssField.UNSPECIFIED,)))

            entries = await vssClient.get(entries=provisioningEntries)

            for key in provisioningDict:
                provisionValue(entries, key, provisioningDict[key])

            for key in valueMap:
                print(f"{key} : {valueMap[key]}")

    except Exception as err:
        print(f"ERROR: Unable to connect to Kuksa Databroker {err}. Connection Details: {DATABROKER_ADDRESS} port {DATABROKER_PORT}")


# Keyboard Bindings
keyboard.add_hotkey('Q', lambda: asyncio.run(unimplemented()))
keyboard.add_hotkey('W', lambda: asyncio.run(handleAccelerate()))
keyboard.add_hotkey('S', lambda: asyncio.run(handleDecelerate()))
keyboard.add_hotkey('A', lambda: asyncio.run(handleLeftTurn()))
keyboard.add_hotkey('D', lambda: asyncio.run(handleRightTurn()))
keyboard.add_hotkey('SHIFT+A', lambda: asyncio.run(handleLeftSignal()))
keyboard.add_hotkey('SHIFT+D', lambda: asyncio.run(handleRightSignal()))
keyboard.add_hotkey('L', lambda: asyncio.run(unimplemented()))
keyboard.add_hotkey('SHIFT+L', lambda: asyncio.run(unimplemented()))
keyboard.add_hotkey('UP', lambda: asyncio.run(unimplemented())) 
keyboard.add_hotkey('DOWN', lambda: asyncio.run(unimplemented()))

print("")
print(">>>> SDV.Link Vehicle Controller Companion App <<<<")
print("")
print("")
print(" ------- Keyboard Controls ---- ")
print("| Key       | function         |")
print(" ------------------------------ ")
print("| Q        | engine start/stop |")
print("| W        | accelerate        |")
print("| A        | decelerate/brake  |")
print("| S        | left turn         |")
print("| D        | right turn        |")
print("| SHIFT+A  | left signal       |")
print("| SHIFT+D  | right signal      |")
print("| L        | low beam          |")
print("| SHIFT+L  | high beam         |")
print("| UP       | gear shift up     |")
print("| DOWN     | gear shift down   |")
print(" ----------------------------- ")
print("")
asyncio.run(provisionVehicleValues())
asyncio.run(subscribe())


keyboard.wait()