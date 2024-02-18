'''
MIT License

Copyright (c) 2024 Mohammad Zubair

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
'''

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

MAX_STEERING_LEFT = 40
MAX_STEERING_RIGHT = -40
STEERING_INCREMENT = 5

MAX_SPEED = 240
MIN_SPEED = 0
SPEED_INCREMENT = 5

DATABROKER_ADDRESS = "localhost"
DATABROKER_PORT = 55555
vssClient = VSSClient(DATABROKER_ADDRESS, DATABROKER_PORT) 

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
            entry = EntryUpdate(DataEntry(path, value=Datapoint(value=val), metadata=Metadata(data_type=valType)), (VssField.VALUE,))
            await vssClient.set(updates=(entry,))
            if kb is not None:
                kbControlPrint(kb, path, val)
    except Exception as err:
        print(f"ERROR: Unable to connect to Kuksa Databroker {err}. Connection Details: {DATABROKER_ADDRESS} port {DATABROKER_PORT}")

async def handleAccelerate():
    engineOn = valueMap[PATH_ENGINE_RUNNING]
    if not engineOn:
        print("Car engines are off. Turn on car engine (Q) first")
        return

    currentSpeed = min(valueMap[PATH_VEHICLE_SPEED] + SPEED_INCREMENT, MAX_SPEED)
    await Set(PATH_VEHICLE_SPEED, currentSpeed, DataType.FLOAT, "W")


async def handleDecelerate():
    engineOn = valueMap[PATH_ENGINE_RUNNING]
    if not engineOn:
        print("Car engines are off. Turn on car engine (Q) first")
        return

    currentSpeed = max(valueMap[PATH_VEHICLE_SPEED] - SPEED_INCREMENT, 0)
    await Set(PATH_BRAKEPEDAL_POSITION, 50, DataType.UINT8, "S")
    await Set(PATH_VEHICLE_SPEED, currentSpeed, DataType.FLOAT, "S")
    await Set(PATH_BRAKEPEDAL_POSITION, 0, DataType.UINT8, "S")

async def handleLeftTurn():
    engineOn = valueMap[PATH_ENGINE_RUNNING]
    if not engineOn:
        print("Car engines are off. Turn on car engine (Q) first")
        return

    turnAngle = min(valueMap[PATH_STEERING_ANGLE] + STEERING_INCREMENT, MAX_STEERING_LEFT)
    await Set(PATH_STEERING_ANGLE, turnAngle, DataType.FLOAT, "A")

async def handleRightTurn():    
    engineOn = valueMap[PATH_ENGINE_RUNNING]
    if not engineOn:
        print("Car engines are off. Turn on car engine (Q) first")
        return

    turnAngle = max(valueMap[PATH_STEERING_ANGLE] - STEERING_INCREMENT, MAX_STEERING_RIGHT)
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

async def handleEnginePower():
    engineOn = not valueMap[PATH_ENGINE_RUNNING]
    await Set(PATH_ENGINE_RUNNING, engineOn, DataType.BOOLEAN, "Q")

async def handleLowBeam():
    lowBeamOn = not valueMap[PATH_BEAM_LOW_ISON]
    await Set(PATH_BEAM_LOW_ISON, lowBeamOn, DataType.BOOLEAN, "L")

async def handleHighBeam():
    highBeamOn = not valueMap[PATH_BEAM_HIGH_ISON]
    await Set(PATH_BEAM_HIGH_ISON, highBeamOn, DataType.BOOLEAN, "SHIFT+L")

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
            valueMap[path] = e.value.value if e.value is not None else defaultValue
            break

async def provisionVehicleValues():
    print(">>> Initializing values from Data Broker")
    try:
        async with vssClient:
            provisioningEntries = [EntryRequest(key, View.ALL, (VssField.UNSPECIFIED,)) for key in provisioningDict]
            entries = await vssClient.get(entries=provisioningEntries)

            for key, defaultValue in provisioningDict.items():
                provisionValue(entries, key, defaultValue)

            for key, value in valueMap.items():
                print(f"{key} : {value}")

    except Exception as err:
        print(f"ERROR: Unable to connect to Kuksa Databroker {err}. Connection Details: {DATABROKER_ADDRESS} port {DATABROKER_PORT}")



# Keyboard Bindings
keyboard.add_hotkey('Q', lambda: asyncio.run(handleEnginePower()))
keyboard.add_hotkey('W', lambda: asyncio.run(handleAccelerate()))
keyboard.add_hotkey('S', lambda: asyncio.run(handleDecelerate()))
keyboard.add_hotkey('A', lambda: asyncio.run(handleLeftTurn()))
keyboard.add_hotkey('D', lambda: asyncio.run(handleRightTurn()))
keyboard.add_hotkey('SHIFT+A', lambda: asyncio.run(handleLeftSignal()))
keyboard.add_hotkey('SHIFT+D', lambda: asyncio.run(handleRightSignal()))
keyboard.add_hotkey('L', lambda: asyncio.run(handleLowBeam()))
keyboard.add_hotkey('SHIFT+L', lambda: asyncio.run(handleHighBeam()))
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