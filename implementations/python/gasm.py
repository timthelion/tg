#!/usr/bin/python3
#
# Authors: Timothy Hobbs
# Copyright years: 2016
#
# Description:
#
# gasm is a text graph asm to standard textual asm translator
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
from textgraph import *
import optparse

def clearComments(string):
  cleared = ""
  quote = False
  escape = False
  for letter in string:
    if escape:
      cleared += letter
      escape = False
    elif quote:
      if letter == "\\":
        escape = True
      elif letter == "'":
        quote = False
    elif letter == "'":
      quote = True
    elif letter == ";":
      return cleared
    cleared += letter
  return cleared

def getSquareLabel(squareId):
  return "square"+str(squareId)

def translate(filepath):
  tg = TextGraph(filepath)
  asm = ""
  for street in tg[0].streets:
    streetName = street.name
    asm += "section "+street.name+"\n"
    if streetName == ".text":
      asm += "global      _start\n_start:\n"
    squareId = street.destination
    while True:
      square = tg[squareId]
      asm += getSquareLabel(squareId)+":\t"+clearComments(square.text)+"\t"
      arguments = []
      for street in square.streets:
        if street.name == "":
          if tg[street.destination].streets:
            arguments.append(getSquareLabel(street.destination))
          else:
            arguments.append(clearComments(tg[street.destination].text))
      asm += ",".join(arguments)
      asm += "\n"
      try:
        squareId = square.lookupStreet(streetName).destination
      except KeyError:
        break
  with open(filepath+".asm","w") as fd:
    fd.write(asm)


if __name__ == "__main__":
  parser = optparse.OptionParser(usage = "gasm GASM-FILE(s)",description = "Translate a text graph asm file to a standard textual asm file.")
  options,args = parser.parse_args(sys.argv[1:])
  for arg in args:
    translate(arg)
