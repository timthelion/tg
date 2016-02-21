#!/usr/bin/python3
#
# Authors: Timothy Hobbs
# Copyright years: 2016
#
# Description:
#
# textgraph is a reference implementation for reading, writting, and manipulating text graphs.
#
########################################################################
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
import sys
import copy
import json
import subprocess
import os

class Street(list):
  def __init__(self,name,destination,origin):
    self.append(name)
    self.append(destination)
    self.origin = origin

  @property
  def name(self):
    return self[0]

  @name.setter
  def name(self,value):
    self[0] = value

  @property
  def destination(self):
    return self[1]

  @destination.setter
  def destination(self,value):
    self[1] = value

  def __repr__(self):
    return self.name + "→" + self.destination

  def __eq__(self,other):
    return self.name == other.name and self.destination == other.destination

class Square():
  def __init__(self,squareId,text,streets):
    self.squareId = squareId
    self.text = text
    self.streets = streets

  def __repr__(self):
    return str((self.squareId,self.text,self.streets))

  @property
  def title(self):
    try:
      return self.text.splitlines()[0]
    except IndexError:
      return "<blank-text>"

  def lookupStreet(self,streetName):
    for street in self.streets:
      if street.name == streetName:
        return street
    raise KeyError("Square "+str(self.squareId)+" : "+self.text+" has no street named "+streetName)

class TextGraph(list):
  def __init__(self,fileName):
    self.fileName = fileName
    self.edited = False
    self.deleted = []
    self.stagedSquares = []
    self.undone = []
    self.done = []
    self.header = ""
    try:
      with open(fileName) as fd:
        self.json = fd.read()
    except FileNotFoundError:
      self.append(Square(0,"",[]))
    for square in self:
      if square.text is None:
        self.deleted.append(square.squareId)

  def allocSquare(self):
    """
    Return a new or free square Id.
    """
    if self.deleted:
      return self.deleted.pop()
    else:
      squareId = len(self)
      self.append(Square(squareId,None,[]))
      return squareId

  def stageSquare(self,square):
    self.stagedSquares.append(copy.deepcopy(square))

  def applyChanges(self):
    didNow = []
    didSomething = False
    for square in self.stagedSquares:
      if square.text is None:
        self.deleted.append(square.squareId)
      elif square.squareId in self.deleted:
        self.deleted.remove(square.squareId)
      prevState = self[square.squareId]
      didNow.append((copy.deepcopy(prevState),copy.deepcopy(square)))
      if not (prevState.text == square.text and prevState.streets == square.streets):
        didSomething = True
        prevState.text = square.text
        prevState.streets = copy.deepcopy(square.streets)
    if didSomething:
      self.undone = []
      self.stagedSquares = []
      self.done.append(didNow)
      if len(self.done)%5 == 0:
        self.saveDraft()
      self.edited = True

  def undo(self):
    try:
      transaction = self.done.pop()
    except IndexError:
      return
    self.edited = True
    for (prevState,postState) in transaction:
      currentState = self[prevState.squareId]
      currentState.text = prevState.text
      currentState.streets = copy.deepcopy(prevState.streets)
    self.undone.append(transaction)

  def redo(self):
    try:
      transaction = self.undone.pop()
    except IndexError:
      return
    self.edited = True
    for (prevState,postState) in transaction:
      currentState = self[postState.squareId]
      currentState.text = postState.text
      currentState.streets = copy.deepcopy(postState.streets)
    self.done.append(transaction)

  def trimBlankSquaresFromEnd(self):
    try:
      square = self.pop()
    except IndexError:
      pass
    if not square.text is None:
      self.append(square)
    else:
      self.deleted.remove(square.squareId)
      # I am not sure if the return makes for tail recursion, but I hope so.
      return self.trimBlankSquaresFromEnd()

  def getIncommingStreets(self,squareId):
    incommingStreets = []
    for square in self:
      for street in square.streets:
        if squareId == street.destination:
          incommingStreets.append(street)
    return incommingStreets

  def newLinkedSquare(self,streetedSquareId,streetName):
    newSquareId = self.allocSquare()
    newSquare = Square(newSquareId,"",[])
    selectedSquare = copy.deepcopy(self[streetedSquareId])
    selectedSquare.streets.append(Street(streetName,newSquareId,selectedSquare.squareId))
    self.stageSquare(newSquare)
    self.stageSquare(selectedSquare)
    self.applyChanges()
    return newSquareId

  def getDeleteSquareChanges(self,squareId):
    """
    Get the changes that need to be preformed in order to delete a square.
    """
    changes = []
    for incommingStreet in self.getIncommingStreets(squareId):
      if incommingStreet != squareId:
        incommingStreetOrigin = copy.deepcopy(self[incommingStreet.origin])
        incommingStreetOrigin.streets = [street for street in incommingStreetOrigin.streets if street.destination != squareId]
        changes.append(incommingStreetOrigin)
    changes.append(Square(squareId,None,[]))
    return changes

  def stageSquareForDeletion(self,squareId):
    for square in self.getDeleteSquareChanges(squareId):
      self.stageSquare(square)

  def deleteSquare(self,squareId):
    self.stageSquareForDeletion(squareId)
    self.applyChanges()

  def getTree(self,squareId):
    square = self[squareId]
    tree = set([square.squareId])
    for street in square.streets:
      if not street.destination in tree:
        tree.update(self.getTree(street.destination))
    return tree

  def deleteTree(self,squareId):
    squaresForDeletion = set(self.getTree(squareId))
    for square in self:
      if not square.squareId in squaresForDeletion:
        newStreets = []
        for street in square.streets:
          if not street.destination in squaresForDeletion:
            newStreets.append(street.destination)
        if newStreets != square.streets:
          self.stageSquare(Square(square.squareId,square.text,newStreets))
    for square in squaresForDeletion:
      self.stageSquare(Square(square,None,[]))
    self.applyChanges()

  @property
  def json(self):
    self.trimBlankSquaresFromEnd()
    serialized = self.header
    for square in self:
      serialized += json.dumps([square.text,square.streets])
      serialized += "\n"
    return serialized

  @json.setter
  def json(self,text):
    self.header = ""
    readingHeader = True
    squareId = 0
    lineNo = 0
    for line in text.splitlines():
      if not line or line.startswith("#"):
        if readingHeader:
          self.header += line+"\n"
      else:
        readingHeader = False
        try:
          (text,streetsList) = json.loads(line)
          streets = []
          for streetName,destination in streetsList:
            streets.append(Street(streetName,destination,squareId))
          self.append(Square(squareId,text,streets))
          squareId += 1
        except ValueError as e:
          sys.exit("Cannot load file "+self.fileName+"\n"+ "Error on line: "+str(lineNo)+"\n"+str(e))
      lineNo += 1

  def __neighborhood(self,center,level):
    """
    Returns a list of squares around a given square.
    Level gives you some control over the size of the neighborhood.
    """
    neighborhood = set()
    squareIdsInNeighborhood = set()
    edge = [self[center]]
    # Build neighborhood
    for _ in range(0,level):
      newEdge = []
      for square in edge:
        neighborhood.add(square)
        squareIdsInNeighborhood.add(square.squareId)
        for street in square.streets:
          newEdge.append(self[street.destination])
        for street in self.getIncommingStreets(square.squareId):
          newEdge.append(self[street.origin])
      edge = newEdge
    # Remove streets that leave neighborhood.
    finalNeighborhood = []
    for square in neighborhood:
      newSquare = copy.deepcopy(square)
      newSquare.streets = [street for street in newSquare.streets if street.destination in squareIdsInNeighborhood]
      finalNeighborhood.append(newSquare)
    return finalNeighborhood

  def dot(self,markedSquares={},neighborhoodCenter=None,neighborhoodLevel=4):
    if neighborhoodCenter is None:
      neighborhood = self
    else:
      neighborhood = self.__neighborhood(neighborhoodCenter,neighborhoodLevel)
    dot = "digraph graphname{\n"
    labels = ""
    edges = ""
    for square in neighborhood:
      if square.text is not None:
        markings = ""
        if square.squareId in markedSquares:
          for attr,value in markedSquares[square.squareId].items():
            markings += "," + attr + " = " + value
        labels += str(square.squareId)+"[label="+json.dumps(square.title)+markings+"]\n"
        for street in square.streets:
          edges += str(square.squareId)+" -> "+str(street.destination)+" [label="+json.dumps(street.name)+"]\n"
    dot += labels
    dot += edges
    dot += "}"
    return dot

  def showDiagram(self,neighborhoodCenter = None,neighborhoodLevel = 4,markedSquares={}):
    subprocess.Popen(["dot","-T","xlib","/dev/stdin"],stdin=subprocess.PIPE).communicate(input=self.dot(markedSquares=markedSquares,neighborhoodCenter=neighborhoodCenter,neighborhoodLevel=neighborhoodLevel).encode("ascii"))

  def save(self):
    with open(self.fileName,"w") as fd:
      fd.write(self.json)

  def saveDraft(self):
    with open(os.path.join(os.path.dirname(self.fileName),"."+os.path.basename(self.fileName)+".draft"),"w") as fd:
      fd.write(self.json)

  def saveDot(self):
    with open(self.fileName+".dot","w") as fd:
      fd.write(self.dot())
