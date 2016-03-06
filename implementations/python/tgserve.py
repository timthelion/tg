#!/usr/bin/python3
import fileinput
import json
import sys
import optparse
import os

class TextGraphServer():
  def __init__(self,filepath = None):
    self.graph = {}
    self.streetsByDestination = {}
    self.nextSquareId = 0
    self.lineNo = 0
    self.readonly = False
    if filepath is None:
      pass
    elif filepath.startswith("http://"):
      import urllib.request
      try:
        with urllib.request.urlopen(filepath) as webgraph:
          for line in webgraph.read().decode("utf-8").splitlines():
            self.interpretLine(line,outputResult = False)
          self.readonly = True
      except urllib.error.URLError as e:
        raise OSError(str(e))
    else:
      try:
        with open(filepath) as fd:
          for line in fd.read().splitlines():
            self.interpretLine(line,outputResult = False)
          self.readonly = False
      except FileNotFoundError:
        pass
    if not 0 in self.graph:
      self.graph[0] = [0,"",[]]
      self.nextSquareId = 1

  def interpretLine(self,line,outputResult = True,repl=False):
    # Lines starting with # and blank lines are ignored.
    if line.startswith("#") or not line:
      return
    try:
      inputObject = json.loads(line)
    except ValueError as e:
      error = str(self.lineNo)+":"+line+"\nCould not be decoded.\n"+str(e)
      if repl:
        print(error)
        return
      else:
        sys.exit(error)
    self.lineNo += 1
    resultingSquares = []
    returnValues = []
    if self.readonly:
      readWritePermissions = "Read only"
    else:
      readWritePermissions = None
    # An empty list returns all squares
    if inputObject == []:
      for squareId in self.graph.keys():
        inputObject.append([squareId])
    # Except either a or a list of squares
    if isinstance(inputObject[0],list):
      squares = inputObject
    else:
      squares = [inputObject]
    # A list of squares sets those squares, but also returns a list of the newly set squares. A return code is also returned, listing None if a value can be set/or has been successfully set and a string explaining an error or permissions problem. This is also how you query for squares.
    # Query square 1
    # <- [[1]]
    # -> [[1,"foo",[["bar St.",2]]]]
    # -> [[1,null,"Read only"]]
    # Set square 1
    # <- [[1,"foobar",[["bar St.",2]]]]
    # -> [[1,"foobar",[["bar St.",2]]]]
    # -> [[1,null,null]]
    for square in squares:
      try:
        squareId = square[0]
        if squareId is None:
          squareId = self.nextSquareId
          self.nextSquareId += 1
        elif isinstance(squareId,int) and squareId > self.nextSquareId:
          self.nextSquareId = squareId + 1
      except IndexError:
        error = lineNo+":"+line + " is invalid."
        if repl:
          print(error)
          return
        else:
          sys.exit(error)
      if self.readonly:
        resultingSquares.append(self.graph[squareId]+[])
        returnValues.append([squareId,"Read only",["Read only"]])
        continue
      try:
        text = square[1]
      except IndexError:
        try:
          _,text,streets = self.graph[squareId]
        except KeyError:
          resultingSquares.append([squareId,None,[],[]])
          returnValues.append([squareId,"Square does not exist.","Square does not exist."])
          continue
      try:
        streets = square[2]
      except IndexError:
        try:
          _,_,streets = self.graph[squareId]
        except KeyError:
          resultingSquares.append([squareId,None,[],[]])
          returnValues.append([squareId,"Square does not exist.","Square does not exist."])
          continue
      if text is None:
        try:
          del self.graph[squareId]
        except KeyError:
          resultingSquares.append([squareId,None,[],[]])
          returnValues.append([squareId,"Square does not exist.","Square does not exist."])
          continue
      else:
        if squareId in self.graph:
          for street in self.graph[squareId][2]:
            self.streetsByDestination[street[1]] = [street for street in self.streetsByDestination[street[1]] if street[0] != squareId]
        self.graph[squareId] = [squareId,text,streets]
        for name,destination in streets:
          if not destination in self.streetsByDestination:
            self.streetsByDestination[destination] = []
          self.streetsByDestination[destination].append([squareId,name,destination])
          self.streetsByDestination[destination].sort()
      if squareId in self.streetsByDestination:
        incommingStreets = self.streetsByDestination[squareId]
      else:
        incommingStreets = []
      resultingSquares.append([squareId,text,streets,incommingStreets])
      returnValues.append([squareId,readWritePermissions,[readWritePermissions for _ in streets]])
    if outputResult:
      sys.stdout.write(json.dumps(resultingSquares)+"\n")
      sys.stdout.flush()
      sys.stdout.write(json.dumps(returnValues)+"\n")
      sys.stdout.flush()

  def repl(self):
    import readline
    import atexit
    try:
      os.makedirs(os.path.join(os.path.expanduser("~"), ".tgserve"))
    except FileExistsError:
      pass
    histfile = os.path.join(os.path.expanduser("~"), ".tgserve","repl_history")
    try:
      readline.read_history_file(histfile)
      # default history len is -1 (infinite), which may grow unruly
      readline.set_history_length(10000)
    except IOError:
      pass
    atexit.register(readline.write_history_file, histfile)
    while True:
      self.interpretLine(input(),repl=True)

  def serve(self):
    for line in iter(sys.stdin.readline,''):
      self.interpretLine(line)

if __name__ == "__main__":
  parser = optparse.OptionParser(usage = "tgserve",description = "Dumb server for the textgraph protocol.")
  parser.add_option("--repl", dest="repl",action="store_true",default=False,help="Run in REPL mode, don't exit on errors.")
  options,args = parser.parse_args(sys.argv[1:])
  if args:
    filepath = args[0]
  else:
    filepath = None
  tgs = TextGraphServer(filepath)
  if options.repl:
    tgs.repl()
  else:
    tgs.serve()
