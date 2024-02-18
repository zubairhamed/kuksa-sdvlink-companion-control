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
from colorama import init
from colorama import Fore
import calendar
import time
from datetime import datetime

init(autoreset=True)

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

GEAR_PARKED = 126
GEAR_REVERSE = -1
GEAR_NEUTRAL = 0
GEAR_DRIVE = 127
GEAR_MANUAL = 1

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
    PATH_CURRENTGEAR:GEAR_PARKED,
    PATH_BRAKEPEDAL_POSITION: 0
}

def log(msg):
    current_GMT = time.gmtime()
    ts = calendar.timegm(current_GMT)
    dt = datetime.fromtimestamp(ts)
    print(f"{Fore.GREEN} {dt} {msg}")

def kbMessage(kb, path, val):
    log(f"{Fore.BLUE} [{kb}] {Fore.CYAN}{path} -> {Fore.RED}{val}")

def logError(msg):
    log(f"{Fore.RED} {msg}")
        
def logWarn(msg):
    m = Fore.YELLOW + msg
    log(m)

def logInfo(msg):
    m = Fore.CYAN + msg
    log(m)

def logCarEngineTurnOn():
    logWarn("Car engines are off. Turn on car engine (Q) first")

async def Set(path, val, valType, kb):
    try:
        async with vssClient:
            entry = EntryUpdate(DataEntry(path, value=Datapoint(value=val), metadata=Metadata(data_type=valType)), (VssField.VALUE,))
            await vssClient.set(updates=(entry,))
            if kb is not None:
                kbMessage(kb, path, val)
    except Exception as err:
        logError(f"ERROR: Unable to connect to Kuksa Databroker {err}. Connection Details: {DATABROKER_ADDRESS} port {DATABROKER_PORT}")

async def handleAccelerate():
    """ Accelerate car. If car was in N or R gear and speed goes above 0, automatically goes into D """
    engineOn = valueMap[PATH_ENGINE_RUNNING]
    if not engineOn:        
        logCarEngineTurnOn()
        return

    originalSpeed = valueMap[PATH_VEHICLE_SPEED]
    newSpeed = min(originalSpeed + SPEED_INCREMENT, MAX_SPEED)    

    if newSpeed == 0:
        # We are stationary, so set car to neutral
        await handleGearNeutral()

    if newSpeed > 0 and originalSpeed <= 0:
        # If previous speed was negative and we went into positive speed, go into drive gear
        await handleGearDrive()

    if newSpeed > 0:
        # Increase speed and set gear
        await Set(PATH_VEHICLE_SPEED, newSpeed, DataType.FLOAT, "S")
    else:
        # Decelerate and set brake position
        await Set(PATH_BRAKEPEDAL_POSITION, 50, DataType.UINT8, "S")    
        await Set(PATH_VEHICLE_SPEED, newSpeed, DataType.FLOAT, "S")
        await Set(PATH_BRAKEPEDAL_POSITION, 0, DataType.UINT8, "S")

async def handleDecelerate():
    """ Decelerates car. If car was in N or D gear and speed goes below 0, automatically goes into R """
    engineOn = valueMap[PATH_ENGINE_RUNNING]
    if not engineOn:
        logCarEngineTurnOn()
        return

    originalSpeed = valueMap[PATH_VEHICLE_SPEED]
    newSpeed = max(originalSpeed - SPEED_INCREMENT, -MAX_SPEED)

    if newSpeed == 0:
        # We are stationary, so set car to neutral
        await handleGearNeutral()

    await Set(PATH_VEHICLE_SPEED, newSpeed, DataType.FLOAT, "S")

    if newSpeed < 0 and originalSpeed >= 0:
        # If previous speed was positive and now we're into negative, go into reverse gear
        await handleGearReverse()
    elif newSpeed >= 0:
        # Pump brakes if in positive speed to decelerate
        await Set(PATH_BRAKEPEDAL_POSITION, 50, DataType.UINT8, "S")    
        await Set(PATH_BRAKEPEDAL_POSITION, 0, DataType.UINT8, "S")


async def handleLeftTurn():
    """ Axle turn Left to turn car. VSS Values are Positive """
    engineOn = valueMap[PATH_ENGINE_RUNNING]
    if not engineOn:
        logCarEngineTurnOn()
        return

    turnAngle = min(valueMap[PATH_STEERING_ANGLE] + STEERING_INCREMENT, MAX_STEERING_LEFT)
    await Set(PATH_STEERING_ANGLE, turnAngle, DataType.FLOAT, "A")

async def handleRightTurn():    
    """ Axle turn Right to turn car. VSS Values are Negative """
    engineOn = valueMap[PATH_ENGINE_RUNNING]
    if not engineOn:
        logCarEngineTurnOn()
        return

    turnAngle = max(valueMap[PATH_STEERING_ANGLE] - STEERING_INCREMENT, MAX_STEERING_RIGHT)
    await Set(PATH_STEERING_ANGLE, turnAngle, DataType.FLOAT, "D")

async def handleLeftSignal():
    """ Toggles Left Turn Indicator """
    leftSignal = not valueMap[PATH_LEFTINDICATOR_SIGNALING]
    await Set(PATH_LEFTINDICATOR_SIGNALING, leftSignal, DataType.BOOLEAN, "SHIFT+A")

async def handleRightSignal():
    """ Toggles Right Turn Indicator """
    rightSignal = not valueMap[PATH_RIGHTINDICATOR_SIGNALING]
    await Set(PATH_RIGHTINDICATOR_SIGNALING, rightSignal, DataType.BOOLEAN, "SHIFT+D")

async def handleEnginePower():
    """ Toggles Engine """
    engineOn = not valueMap[PATH_ENGINE_RUNNING]

    # TODO: If speed is positive, decelerate speed over time
    await Set(PATH_ENGINE_RUNNING, engineOn, DataType.BOOLEAN, "Q")

async def handleLowBeam():
    """ Toggle Low Beam Light """
    lowBeamOn = not valueMap[PATH_BEAM_LOW_ISON]
    await Set(PATH_BEAM_LOW_ISON, lowBeamOn, DataType.BOOLEAN, "L")

async def handleHighBeam():
    """ Toggle High Beam Light """
    highBeamOn = not valueMap[PATH_BEAM_HIGH_ISON]
    await Set(PATH_BEAM_HIGH_ISON, highBeamOn, DataType.BOOLEAN, "SHIFT+L")

async def unimplemented():
    print("Not implemented yet")
    pass

async def subscribe():
    """ Subscribe to values used by app and sync changes """
    global provisionDict
    print(f"   {Fore.YELLOW}>>> {Fore.RED}Subscribing required values..{Fore.YELLOW}<<<")
    print("")

    async with vssClient:
        entries = []
        for key in valueMap:
            entries.append(SubscribeEntry(key, View.FIELDS, (VssField.VALUE, VssField.ACTUATOR_TARGET)))

        async for updates in vssClient.subscribe(entries=entries): 
            for update in updates:
                if update.entry.value is not None:
                    valueMap[update.entry.path] = update.entry.value.value
                    kbMessage("SUB", update.entry.path, update.entry.value.value)

def provisionValue(entries, path, defaultValue):
    """ Sets up default values for a given entry """
    for e in entries:
        if e.path == path:
            valueMap[path] = e.value.value if e.value is not None else defaultValue
            break

async def provisionVehicleValues():
    """ Get a list of values of interest for app for initialization """
    print(f"   {Fore.YELLOW}>>> {Fore.RED}Initializing values from Data Broker{Fore.YELLOW}<<<")

    try:
        async with vssClient:
            provisioningEntries = [EntryRequest(key, View.ALL, (VssField.UNSPECIFIED,)) for key in provisioningDict]
            entries = await vssClient.get(entries=provisioningEntries)

            for key, defaultValue in provisioningDict.items():
                provisionValue(entries, key, defaultValue)

            for key, value in valueMap.items():
                print(f"   {Fore.CYAN}{key}: {Fore.RED}{value}")
            print("")

    except Exception as err:
        logError(f"ERROR: Unable to connect to Kuksa Databroker {err}. Connection Details: {DATABROKER_ADDRESS} port {DATABROKER_PORT}")

async def handleGearPark():
    """ Set Gear to Park """
    engineOn = valueMap[PATH_ENGINE_RUNNING]
    currentSpeed = valueMap[PATH_VEHICLE_SPEED]

    if not engineOn or currentSpeed > 0:
        if not engineOn:
            logCarEngineTurnOn()
        else:
            logWarn("Unable to shift to Park. Decelerate to a stop before putting into Park")
        return

    logInfo("Shifted to Gear: Parked")
    await Set(PATH_CURRENTGEAR, GEAR_PARKED, DataType.INT8, "1")

async def handleGearReverse():
    engineOn = valueMap[PATH_ENGINE_RUNNING]
    currentSpeed = valueMap[PATH_VEHICLE_SPEED]

    if not engineOn:
        logCarEngineTurnOn()
    elif currentSpeed <= 0:
        logInfo("Shifted to Gear: Reverse")
        await Set(PATH_CURRENTGEAR, GEAR_REVERSE, DataType.INT8, "R")
    else:
        logWarn("Unable to shift to Reverse. Decelerate to a stop before shifting")

async def handleGearNeutral():
    engineOn = valueMap[PATH_ENGINE_RUNNING]

    if not engineOn:
        logCarEngineTurnOn()
        return

    logInfo("Shifted to Gear: Neutral")    
    await Set(PATH_CURRENTGEAR, GEAR_NEUTRAL, DataType.INT8, "2")

async def handleGearDrive():
    engineOn = valueMap[PATH_ENGINE_RUNNING]

    if not engineOn:
        logCarEngineTurnOn()
        return

    logInfo("Shifted to Gear: Drive")
    await Set(PATH_CURRENTGEAR, GEAR_DRIVE, DataType.INT8, "E")

async def handleGearManual():
    engineOn = valueMap[PATH_ENGINE_RUNNING]

    if not engineOn:
        logCarEngineTurnOn()
        return

    logInfo("Shifted to Gear: Manual")
    await Set(PATH_CURRENTGEAR, GEAR_MANUAL, DataType.INT8, "3")

# Keyboard Bindings
keyboard.add_hotkey('Q', lambda: asyncio.run(handleEnginePower())) # Turn off and On Engine
keyboard.add_hotkey('W', lambda: asyncio.run(handleAccelerate())) # Acceelerate
keyboard.add_hotkey('S', lambda: asyncio.run(handleDecelerate())) # Decelerate/Brake
keyboard.add_hotkey('A', lambda: asyncio.run(handleLeftTurn())) # Turn Axle Left
keyboard.add_hotkey('D', lambda: asyncio.run(handleRightTurn())) # Turn Axle Right
keyboard.add_hotkey('SHIFT+A', lambda: asyncio.run(handleLeftSignal())) # Left Turn Indicator
keyboard.add_hotkey('SHIFT+D', lambda: asyncio.run(handleRightSignal())) # Right Turn Indicator
keyboard.add_hotkey('L', lambda: asyncio.run(handleLowBeam())) # Low Beam Toggle
keyboard.add_hotkey('SHIFT+L', lambda: asyncio.run(handleHighBeam())) # High Beam Toggle
keyboard.add_hotkey('1', lambda: asyncio.run(handleGearPark())) # Gear: Park
keyboard.add_hotkey('2', lambda: asyncio.run(handleGearNeutral())) # Gear: Neutral
keyboard.add_hotkey('3', lambda: asyncio.run(handleGearManual())) # Gear: Sport/Manual
keyboard.add_hotkey('R', lambda: asyncio.run(handleGearReverse())) # Gear: Reverse
keyboard.add_hotkey('E', lambda: asyncio.run(handleGearDrive())) # Gear: Drive

print(f""" {Fore.CYAN}
   _____ _______      ___      _       _    
  / ____|  __ \\ \\    / / |    (_)     | |   
 | (___ | |  | \\ \\  / /| |     _ _ __ | | __
  \\___ \\| |  | |\\ \\/ / | |    | | '_ \\| |/ /
  ____) | |__| | \\  /  | |____| | | | |   < 
 |_____/|_____/   \\(_) |______|_|_| |_|_|\\_\\
      
       {Fore.YELLOW}>>> {Fore.RED}Starting Companion App {Fore.YELLOW}<<<
                                                    
      {Fore.YELLOW} ------- Keyboard Controls ---- 
      {Fore.YELLOW}| {Fore.RED}Key      {Fore.YELLOW}| {Fore.RED}Function          {Fore.YELLOW}|
      {Fore.YELLOW} ------------------------------ 
      {Fore.YELLOW}| {Fore.RED}Q        {Fore.YELLOW}| {Fore.RED}engine start/stop {Fore.YELLOW}|
      {Fore.YELLOW}| {Fore.RED}W        {Fore.YELLOW}| {Fore.RED}accelerate        {Fore.YELLOW}|
      {Fore.YELLOW}| {Fore.RED}A        {Fore.YELLOW}| {Fore.RED}decelerate/brake  {Fore.YELLOW}|
      {Fore.YELLOW}| {Fore.RED}S        {Fore.YELLOW}| {Fore.RED}left turn         {Fore.YELLOW}|
      {Fore.YELLOW}| {Fore.RED}D        {Fore.YELLOW}| {Fore.RED}right turn        {Fore.YELLOW}|
      {Fore.YELLOW}| {Fore.RED}SHIFT+A  {Fore.YELLOW}| {Fore.RED}left signal       {Fore.YELLOW}|
      {Fore.YELLOW}| {Fore.RED}SHIFT+D  {Fore.YELLOW}| {Fore.RED}right signal      {Fore.YELLOW}|
      {Fore.YELLOW}| {Fore.RED}L        {Fore.YELLOW}| {Fore.RED}low beam          {Fore.YELLOW}|
      {Fore.YELLOW}| {Fore.RED}SHIFT+L  {Fore.YELLOW}| {Fore.RED}high beam         {Fore.YELLOW}|
      {Fore.YELLOW}| {Fore.RED}1        {Fore.YELLOW}| {Fore.RED}gear park         {Fore.YELLOW}|
      {Fore.YELLOW}| {Fore.RED}2        {Fore.YELLOW}| {Fore.RED}gear neutral      {Fore.YELLOW}|
      {Fore.YELLOW}| {Fore.RED}3        {Fore.YELLOW}| {Fore.RED}gear sport/manual {Fore.YELLOW}|
      {Fore.YELLOW}| {Fore.RED}R        {Fore.YELLOW}| {Fore.RED}gear reverse      {Fore.YELLOW}|
      {Fore.YELLOW}| {Fore.RED}E        {Fore.YELLOW}| {Fore.RED}gear drive        {Fore.YELLOW}|
      {Fore.YELLOW} ------------------------------ 
      
""")
asyncio.run(provisionVehicleValues())
asyncio.run(subscribe())

keyboard.wait()
