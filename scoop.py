#!/usr/bin/python3

import csv
from curses.ascii import isalnum
from enum import Enum
import os
from dataclasses import dataclass
import random
import time
from typing import Union
import pickle    

NoneType = type(None)

SECOND = 1.0
MINUTE = 60 * SECOND
HOUR = 60 * MINUTE
DAY = 24 * HOUR

DIRNAME = os.path.dirname(os.path.realpath(__file__))
RARITY_CHECKIN_PROB_PER_MINUTE = {
  1 : 0.005,
  2 : 0.002,
  3 : 0.0005
}
HANGOUT_TIME = 10 * MINUTE
RARITY_GRAINS_PER_HOUR = {
  1: 1,
  2: 2,
  3: 4,
  4: 8
}
MAX_HUNGER = 200
RARITY_SCOOP_PROB = {
  1 : 0.5,
  2 : 0.35,
  3 : 0.25
}

@dataclass
class AnimalType:
  emoji: str
  name: str
  rarity: int
  hunger: int

def get_animals() -> list[AnimalType]:
  animals : list[AnimalType] = []
  with open(os.path.join(DIRNAME, "animals.csv")) as f:
    reader = csv.reader(f)
    for row in reader:
      animals.append(AnimalType(row[0], row[1], int(row[2]), int(row[3])))
  return animals

def get_names() -> list[str]:
  names : list[str] = []
  with open(os.path.join(DIRNAME, "names.csv")) as f:
    reader = csv.reader(f)
    for row in reader:
      names.append(row[0])
  return names

ANIMALS = get_animals()
NAMES = get_names()

Timestamp = float

class AnimalState(Enum):
  HANGING_OUT = 'hanging_out'
  LEFT = 'left'
  SCOOPED = 'scooped'
  DEAD = 'dead'

class AnimalFeedResult(Enum):
  NOT_SCOOPED = 'not_scooped'
  NOT_ENOUGH_GRAINS = 'not_enough_grains'
  DEAD = 'dead'

class AnimalCanScoopResult(Enum):
  OK = 'ok'
  NOT_POLITE_ENOUGH = 'not_polite_enough'
  TOO_POLITE = 'too_polite'
  ALREADY_SCOOPED = 'already_scooped'
  GONE = 'gone'

class AnimalScoopResult(Enum):
  OK = 'ok'
  NO_PERMISSION = 'no_permission'
  ALREADY_SCOOPED = 'already_scooped'
  GONE = 'gone'

class Animal:
  type : AnimalType
  leavingBy : Timestamp
  scoopedAt : Union[NoneType, Timestamp]
  scoopPoliteness : int = 0
  canScoopLater: bool = False
  lastFed : Union[NoneType, Timestamp]
  owner: Union[NoneType, str] = None

  def __init__(self, animalType: AnimalType, checkinTimestamp: Timestamp):
    self.type = animalType
    self.state = AnimalState.HANGING_OUT
    self.leavingBy = checkinTimestamp + HANGOUT_TIME
    self.scoopedAt = None
    while (RARITY_SCOOP_PROB[self.type.rarity] < random.random()):
      self.scoopPoliteness += 1
    self.lastFed : Union[NoneType, Timestamp] = None

  def getLastFed(self) -> Union[NoneType, Timestamp]:
    if (self.scoopedAt == None):
      return None
    else:
      if (self.lastFed == None):
        return self.scoopedAt
      else:
        return self.lastFed

  def getState(self, timestamp: Timestamp) -> AnimalState:
    lastFed = self.getLastFed()
    if lastFed == None:
      if (timestamp > self.leavingBy):
        return AnimalState.LEFT
      else:
        return AnimalState.HANGING_OUT
    else:
      theoreticalHunger = self.getTheoreticalHunger(timestamp)
      if (theoreticalHunger > MAX_HUNGER):
        return AnimalState.DEAD
      else:
        return AnimalState.SCOOPED
  
  def getTheoreticalHunger(self, timestamp: Timestamp) -> Union[NoneType, int]:
    lastFed = self.getLastFed()
    if lastFed == None:
      return None
    else:
      hoursSinceLastFed = (timestamp - lastFed) / HOUR
      return int(RARITY_GRAINS_PER_HOUR[self.type.rarity] * hoursSinceLastFed)
  
  def feed(self, timestamp: Timestamp, grains: int, username: str) -> Union[AnimalFeedResult, int]:
    state = self.getState(timestamp)
    if state == AnimalState.SCOOPED:
      if not (self.owner == username):
        return AnimalFeedResult.NOT_SCOOPED
      hunger = self.getTheoreticalHunger(timestamp)
      if (hunger > grains):
        return AnimalFeedResult.NOT_ENOUGH_GRAINS
      else:
        self.lastFed = timestamp
        return hunger
    elif state == AnimalState.DEAD:
      return AnimalFeedResult.DEAD
    else:
      return AnimalFeedResult.NOT_SCOOPED
  
  def canScoop(self, timestamp: Timestamp, politeness: int) -> AnimalCanScoopResult:
    state = self.getState(timestamp)
    if state == AnimalState.HANGING_OUT:
      if (politeness == self.scoopPoliteness):
        self.canScoopLater = True
        return AnimalCanScoopResult.OK
      elif (politeness < self.scoopPoliteness):
        return AnimalCanScoopResult.NOT_POLITE_ENOUGH
      else:
        return AnimalCanScoopResult.TOO_POLITE
    elif state == AnimalState.SCOOPED:
      return AnimalCanScoopResult.ALREADY_SCOOPED
    else:
      return AnimalCanScoopResult.GONE
  
  def scoop(self, timestamp: Timestamp, owner: str) -> AnimalScoopResult:
    state = self.getState(timestamp)
    if state == AnimalState.HANGING_OUT:
      if (self.canScoopLater):
        self.scoopedAt = timestamp
        self.owner = owner
        return AnimalScoopResult.OK
      else:
        return AnimalScoopResult.NO_PERMISSION
    elif state == AnimalState.SCOOPED:
      return AnimalScoopResult.ALREADY_SCOOPED
    else:
      return AnimalScoopResult.GONE

class StateMutator(object):
  def __init__(self, username):
    self.username = username
    if not os.path.exists(os.path.join(DIRNAME, "sessions")):
      os.mkdir(os.path.join(DIRNAME, "sessions"))
    if not os.path.isfile(os.path.join(DIRNAME, "sessions", "global.session")):
      with open(os.path.join(DIRNAME, "sessions", "global.session"), "wb") as f:
        pickle.dump([0, {}], f)
    if not os.path.isfile(os.path.join(DIRNAME, "sessions", username)):
      with open(os.path.join(DIRNAME, "sessions", username), "wb") as f:
        pickle.dump(0, f)

  def __enter__(self):
    with open(os.path.join(DIRNAME, "sessions", "global.session"), "rb") as f:
      lastCheckinTime, animals = pickle.load(f)
    with open(os.path.join(DIRNAME, "sessions", self.username), "rb") as f:
      grains = pickle.load(f)
    return lastCheckinTime, grains, animals
  
  def __exit__(self, lastCheckinTime, grains, animals):
    with open(os.path.join(DIRNAME, "sessions", "global.session"), "wb") as f:
      pickle.dump([lastCheckinTime, animals], f)
    with open(os.path.join(DIRNAME, "sessions", self.username), "wb") as f:
      pickle.dump(grains, f)

if __name__ == "__main__":

  username : str = ""
  while ((username == "") or (not username.isalnum())):
    username = input("Enter a username to begin: ")
    
  print("")
  print(f"Welcome {username}! Available commands are: barn, caniscoop <name>, checkin, exit, feed <name>, pick, scoop <name>")
  print("Hint: try starting out by checking in: `checkin`")
  print("")

  mutator = StateMutator(username)

  while True:
    command = input("> ")
    print("")
    lastCheckinTime, grains, animals = mutator.__enter__()
    if command == "barn":
      animalCount = 0
      print("Here's all the animals in the barn right now:")
      for name, animal in animals.items():
        if animal.owner != username:
          continue
        animalState = animal.getState(time.time())
        if (animalState == AnimalState.SCOOPED):
          print(f"  {animal.type.emoji} {name} (the {animal.type.name})")
          animalCount += 1
      if (animalCount == 0):
        print("  There's no animals in the barn right now :/")
        print("  Try checking in the backyard for new animals: `checkin`")
    elif command.startswith("caniscoop "):
      options : list[str] = command.split(" ")
      name : str = options[1].capitalize()
      politeness = len(list(filter(lambda option: option == "please", options)))
      if (name not in animals):
        print(f"There's no such animal named '{name}'")
      else:
        animal = animals[name]
        canScoopResult = animal.canScoop(time.time(), politeness)
        if (canScoopResult == AnimalCanScoopResult.OK):
          print(f"{animal.type.emoji} {name} says: You can scoop me! Try: `scoop {name}`")
        elif (canScoopResult == AnimalCanScoopResult.NOT_POLITE_ENOUGH):
          morePolite = ("please " * (politeness + 1)).rstrip()
          print(f"{animal.type.emoji} {name} is wary. Try being more polite: `caniscoop {name} {morePolite}`")
        elif (canScoopResult == AnimalCanScoopResult.TOO_POLITE):
          print(f"{animal.type.emoji} {name} is confused. You're being too polite!")
        elif (canScoopResult == AnimalCanScoopResult.ALREADY_SCOOPED):
          print(f"{animal.type.emoji} {name} is already scooped, silly! Check the barn: `barn`")
        else:
          print(f"{animal.type.emoji} {name} is gone! It's too late to scoop!")
          del animals[name]
    elif command == "checkin":
      currentTimestamp = time.time()
      timePeriod = min(currentTimestamp - lastCheckinTime, HANGOUT_TIME)
      lastCheckinTime = currentTimestamp
      oldAnimals = animals.copy()
      animalCount = 0
      print("In the backyard:")
      for animal in ANIMALS:
        checkinProb = 1 - (1 - RARITY_CHECKIN_PROB_PER_MINUTE[animal.rarity]) ** (timePeriod / MINUTE)
        if (checkinProb > random.random()):
          name = random.choice(NAMES)
          while (name in animals):
            name = random.choice(NAMES)
          animals[name] = Animal(animal, currentTimestamp - timePeriod * random.random())
          modifier = ({
            1 : "",
            2: " (* rare! *)",
            3: " (** super-rare! **)"
          })[animal.rarity]
          print(f"  {animal.emoji} {name} (the {animal.name}) has come to hang out!{modifier}")
          animalCount += 1
      if animalCount > 0:
        print("")
      for name in oldAnimals:
        animal : Animal = animals[name]
        animalState : AnimalState = animal.getState(currentTimestamp)
        if (animalState == AnimalState.HANGING_OUT):
          modifier = ({
            1 : "",
            2: " (* rare! *)",
            3: " (** super-rare! **)"
          })[animal.type.rarity]
          print(f"  {animal.type.emoji} {name} (the {animal.type.name}) is hanging out.{modifier}")
          animalCount += 1
      if animalCount == 0:
        print("  No animals are hanging out in the backyard right now :( Check in later!")
      print("")
      print("In the barn:")
      barnCount = 0
      for animal in animals:
        animal : Animal = animals[name]
        if animal.owner != username:
          continue
        animalState : AnimalState = animal.getState(currentTimestamp)
        if (animalState == AnimalState.SCOOPED):
          hunger = animal.getTheoreticalHunger(currentTimestamp)
          if (hunger > 10):
            print(f"  {animal.type.emoji} {name} is hungry for {hunger} grains!")
            barnCount += 1
        elif (animalState == AnimalState.DEAD):
          print(f"   {animal.type.emoji} {name} died from hunger :( Be sure to feed your animals!")
          barnCount += 1
          del animals[name]
        elif (animalState == AnimalState.LEFT):
          del animals[name]
      if barnCount == 0:
        print("  Nothing to report in the barn!")
    elif command == "exit":
      break
    elif command.startswith("feed "):
      name : str = command.split(" ")[1].capitalize()
      if (name not in animals):
        print(f"There's no such animal named '{name}'")
      else:
        animal = animals[name]
        feedResult = animal.feed(time.time(), grains, username)
        if (type(feedResult) == int):
          grains -= feedResult
          print(f"You fed {animal.type.emoji} {name} {feedResult} grains! They're full now!")
        elif (feedResult == AnimalFeedResult.NOT_ENOUGH_GRAINS):
          print(f"You don't have enough grains to feed {animal.type.emoji} {name}! Try picking some: `pick`")
        elif (feedResult == AnimalFeedResult.NOT_SCOOPED):
          print(f"{animal.type.emoji} {name} is not scooped! Try scooping them: `caniscoop {name}`")
        elif (feedResult == AnimalFeedResult.DEAD):
          print(f"{animal.type.emoji} {name} is dead :( Feed your animals on time next time!")
          del animals[name]
    elif command == "pick":
      grains += 10
      print(f"You now have {grains} grains!")
    elif command.startswith("scoop "):
      name : str = command.split(" ")[1].capitalize()
      if (name not in animals):
        print(f"There's no such animal named '{name}'")
      else:
        animal = animals[name]
        scoopResult = animal.scoop(time.time(), username)
        if (scoopResult == AnimalScoopResult.OK):
          print(f"{animal.type.emoji} {name} has been scooped! Check the barn: `barn`")
        elif (scoopResult == AnimalScoopResult.NO_PERMISSION):
          print(f"You can't scoop an animal without their permission! {animal.type.emoji} {name} has fled.")
          del animals[name]
        elif (scoopResult == AnimalScoopResult.ALREADY_SCOOPED):
          print(f"You've already scooped {animal.type.emoji} {name}, silly! Check the barn: `barn`")
        else:
          print(f"Looks like {animal.type.emoji} {name} is already gone :/")
          del animals[name]
    else:
      print("Unknown command. Available commands are: barn, caniscoop <name>, checkin, exit, feed <name>, pick, scoop <name>")
    print("")

    mutator.__exit__(lastCheckinTime, grains, animals)
