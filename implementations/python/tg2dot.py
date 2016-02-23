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

def translate(filepath):
  tg = TextGraph(filepath)
  tg.saveDot()

if __name__ == "__main__":
  parser = optparse.OptionParser(usage = "tg2dot TG-FILE(s)",description = "Translate a text graph file to dot file.")
  options,args = parser.parse_args(sys.argv[1:])
  for arg in args:
    translate(arg)
