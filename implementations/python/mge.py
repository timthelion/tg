#!/usr/bin/python3
#
# Authors: Timothy Hobbs
# Copyright years: 2016
#
# Description:
#
# mge is a simple TUI Vim style modal editor for text graphs.
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
import optparse
import copy
try:
  import urwid
except ImportError:
  sys.exit("The urwid TUI toolkit is required to run this program. On debian based systems you need to install python3-urwid. On other systems you'll have to search the web.")
from textgraph import *

def showErrorDialog(error):
  # http://stackoverflow.com/questions/12876335/urwid-how-to-see-errors
  import tkinter as tk
  root = tk.Tk()
  window = tk.Label(root, text=error)
  window.pack()
  root.mainloop()

class GraphView(urwid.Frame):
  def __init__(self,graph):
    self.__mode = 'command'
    self.defaultStreetName = ""
    self.clipboard = ""
    self.graph = graph
    self._selection = 0
    self.history = []
    # clipboard
    self.clipboard = Clipboard(self)
    self.clipboardBoxAdapter = urwid.BoxAdapter(self.clipboard,3)
    # incommingStreets
    self.incommingStreets = IncommingStreetsList(self)
    # current square
    self.currentSquare = CurrentSquare(self)
    self.currentSquareWidget = urwid.Padding(urwid.Filler(urwid.AttrMap(self.currentSquare,None,"selection")),left=3)
    # streets
    self.streets = StreetsList(self)
    # status bar
    self.statusMessage = ""
    self.statusBar = urwid.Text("")
    # command bar
    self.commandBar = CommandBar(self)
    # search box
    self.searchBox = SearchBox(self)
    # main frame
    self.pile = urwid.Pile([self.incommingStreets,self.currentSquareWidget,self.streets])
    self.body = urwid.WidgetPlaceholder(self.pile)
    super(GraphView,self).__init__(self.body,header=self.clipboardBoxAdapter,footer=urwid.BoxAdapter(urwid.ListBox(urwid.SimpleFocusListWalker([self.statusBar,self.commandBar])),height=3))
    self.update()
    self.updateStatusBar()
    self.focus_item = self.currentSquareWidget

  def update(self):
    # clipboard
    self.clipboard.update()
    # incommingStreets
    incommingStreets = []
    for incommingStreet in self.graph.getIncommingStreets(self.selection):
      incommingStreets.append(copy.deepcopy(incommingStreet))
    self.incommingStreets.update(incommingStreets)
    # current square
    self.currentSquare.edit_text = self.graph[self.selection].text
    # streets
    self.streets.update(self.graph[self.selection].streets)

  def updateStatusBar(self):
    if self.graph.edited:
      edited = "Edited"
    else:
      edited = "Saved"
    if self.mode == 'search':
      try:
        currentSquareId = self.searchBox.focused_square
      except IndexError:
        currentSquareId = 0
    elif self.focus_item == self.incommingStreets:
      try:
        currentSquareId = self.incommingStreets.streets[self.incommingStreets.focus_position].origin
      except IndexError:
        currentSquareId = self.selection
    elif self.focus_item == self.streets:
      try:
        currentSquareId = self.streets.streets[self.streets.focus_position].destination
      except IndexError:
        currentSquareId = self.selection
    else:
      currentSquareId = self.selection
    self.statusBar.set_text("□:"+str(currentSquareId) + " " + edited + " Undo: "+str(len(self.graph.done))+" Redo: "+str(len(self.graph.undone))+" Mode: "+self.mode+" → "+self.defaultStreetName+" | "+self.statusMessage)

  def recordChanges(self):
    if self.graph[self.selection].text != self.currentSquare.edit_text:
      currentSquare = copy.deepcopy(self.graph[self.selection])
      currentSquare.text = self.currentSquare.edit_text
      self.graph.stageSquare(currentSquare)
      self.graph.applyChanges()
    self.streets.recordChanges()
    self.incommingStreets.recordChanges()

  @property
  def selection(self):
    return self._selection

  @selection.setter
  def selection(self,value):
    self.history.append(self.selection)
    self._selection = value

  @property
  def focus_item(self):
    if self.focus_position == 'header':
      return self.clipboard
    elif self.focus_position == 'body':
      return self.contents['body'][0].original_widget.focus_item
    elif self.focus_position == 'footer':
      return self.commandBar

  @focus_item.setter
  def focus_item(self,value):
    if value == self.clipboard:
      self.focus_position = 'header'
    elif value == self.commandBar:
      self.focus_position = 'footer'
    else:
      self.focus_position = 'body'
      self.contents['body'][0].original_widget.focus_item = value

  @property
  def mode(self):
    return self.__mode
  @mode.setter
  def mode(self,value):
    self.__mode = value
    if value == 'command':
      self.body.original_widget = self.pile
      self.update()
    elif value == 'search':
      self.body.original_widget = self.searchBox
    elif value == 'insert':
      self.update()
    else:
      raise ValueError("Invalid mode"+value)

  def keypress(self,size,key):
    if self.mode == 'search':
      return self.keypressSearchmode(size, key)
    focusedBeforeProcessing = self.focus_item
    value = self.handleKeypress(size,key)
    if key in keybindings['command-mode.down'] and focusedBeforeProcessing == self.currentSquareWidget and self.focus_item == self.streets:
      self.streets.focus_position = 0
    self.updateStatusBar()
    return value

  def handleKeypress(self,size,key):
    if key in ['left','right','up','down','home','end']:
      self.recordChanges()
      return super(GraphView,self).keypress(size,key)
    if key in keybindings['command-mode'] and self.mode != 'command':
      self.recordChanges()
      self.mode = 'command'
    elif key in keybindings['move-down-one-mega-widget']:
      self.recordChanges()
      if self.focus_position == 'header':
        self.focus_position = 'body'
        self.contents['body'][0].original_widget.focus_position = 0
      elif self.focus_position == 'body':
        if self.contents['body'][0].original_widget.focus_position < 2:
          self.contents['body'][0].original_widget.focus_position += 1
        else:
          self.focus_position = 'footer'
      elif self.focus_position == 'footer':
        pass
    elif key in keybindings['move-up-one-mega-widget']:
      self.recordChanges()
      if self.focus_position == 'footer':
        self.focus_position = 'body'
        self.contents['body'][0].original_widget.focus_position = 2
      elif self.focus_position == 'body':
        if self.contents['body'][0].original_widget.focus_position > 0:
          self.contents['body'][0].original_widget.focus_position -= 1
        else:
          self.focus_position = 'header'
      elif self.focus_position == 'header':
        pass
    elif self.mode == 'command':
      if key in keybindings['leave-and-go-to-mainer-part']:
        self.focus_item = self.currentSquareWidget
      if self.focus_item == self.commandBar:
        return super(GraphView,self).keypress(size,key)
      else:
        self.recordChanges()
        if key in keybindings['insert-mode']:
          self.mode = 'insert'
          return None
        if key in keybindings["back"]:
          if self.history:
            self._selection = self.history.pop()
            self.update()
        elif key in keybindings['move-to-square-zero']:
          self.selection = 0
          self.update()
          self.focus_item = self.currentSquareWidget
        elif key in keybindings['search-mode']:
          self.mode = 'search'
          self.searchBox.searchEdit.edit_text = ""
          self.searchBox.update()
          self.updateStatusBar()
          return None
        elif key in keybindings['jump-to-command-bar']:
          self.focus_item = self.commandBar
        elif key in keybindings['show-map']:
          self.graph.showDiagram(markedSquares={self.selection:{"fontcolor":"white","fillcolor":"black","style":"filled"}})
          return None
        elif key in keybindings['show-map-of-neighborhood']:
          self.graph.showDiagram(neighborhoodCenter = self.selection, neighborhoodLevel = 4,markedSquares={self.selection:{"fontcolor":"white","fillcolor":"black","style":"filled"}})
          return None
        elif key in keybindings['go-down-default-street']:
          try:
            self.selection = self.graph[self.selection].lookupStreet(self.defaultStreetName).destination
            self.update()
          except KeyError:
            pass
        elif key in keybindings['go-up-default-street']:
          for street in self.incommingStreets.streets:
            if street.name == self.defaultStreetName:
              self.selection = street.origin
              self.update()
              break
        elif key in keybindings['clear-default-street-name']:
          self.defaultStreetName = ""
        elif key in keybindings['command-mode.up']:
          return super(GraphView,self).keypress(size,'up')
        elif key in keybindings['command-mode.down']:
          return super(GraphView,self).keypress(size,'down')
        elif key in keybindings['command-mode.left']:
          return super(GraphView,self).keypress(size,'left')
        elif key in keybindings['command-mode.right']:
          return super(GraphView,self).keypress(size,'right')
        elif key in keybindings['command-mode.undo']:
          self.graph.undo()
          if self.selection >= len(self.graph):
            self.selection = 0
          if self.graph[self.selection].text is None:
            self.selection = 0
          self.update()
        elif key in keybindings['command-mode.redo']:
          self.graph.redo()
          self.update()
        else:
          return super(GraphView,self).keypress(size,key)
    else:
      return super(GraphView,self).keypress(size,key)

  def keypressSearchmode(self,size,key):
    if key == 'esc':
      if self.focus_position != 'body':
        self.focus_position = 'body'
        return None
      else:
        self.mode = 'command'
        self.body.original_widget = self.pile
        self.updateStatusBar()
        return None
    elif self.focus_position == 'body':
      value = self.body.keypress(size,key)
      self.updateStatusBar()
      return value
    else:
      super(GraphView,self).keypress(size,key)

class SquareList(urwid.ListBox):
  def __init__(self,selectionCollor,alignment):
    self.selectionCollor = selectionCollor
    self.alignment = alignment
    self.squares = []
    super(SquareList,self).__init__(urwid.SimpleFocusListWalker([]))

  def update(self,squares=None):
    if squares is not None:
      self.squares = squares
    items = []
    if not self.squares:
      items.append(urwid.AttrMap(urwid.Padding(urwid.SelectableIcon(" ",0),align=self.alignment,width="pack"),None,self.selectionCollor))
    for square in self.squares:
      items.append(urwid.AttrMap(urwid.Padding(urwid.SelectableIcon(square.title,0),align=self.alignment,width="pack"),None,self.selectionCollor))
    self.body.clear()
    self.body.extend(items)

class Clipboard(SquareList):
  def __init__(self,view):
    self.view = view
    super(Clipboard,self).__init__("clipboard","right")

  def keypress(self,size,key):
    if key in keybindings["remove-from-stack"]:
      fcp = self.focus_position
      del self.squares[fcp]
      self.update()
      if fcp < len(self.squares):
        self.focus_position = fcp
    if key in keybindings['street-to-stack-item'] or key in keybindings['street-to-stack-item-no-pop']:
      try:
        fcp = self.focus_position
      except IndexError:
        pass
      else:
        square = self.squares[fcp]
        if not key in keybindings['street-to-stack-item-no-pop']:
          del self.squares[fcp]
        currentSquare = copy.deepcopy(self.view.graph[self.view.selection])
        currentSquare.streets.append(Street(self.view.defaultStreetName,square.squareId,currentSquare.squareId))
        self.view.graph.stageSquare(currentSquare)
        self.view.graph.applyChanges()
        self.view.update()
    if key in keybindings['incommingStreet-to-stack-item'] or key in keybindings['incommingStreet-to-stack-item-no-pop']:
      try:
        fcp = self.focus_position
      except IndexError:
        pass
      else:
        square = self.squares[fcp]
        if not key in keybindings['incommingStreet-to-stack-item-no-pop']:
          del self.squares[fcp]
        square.streets.append(Street(self.view.defaultStreetName,self.view.selection,square.squareId))
        self.view.graph.stageSquare(square)
        self.view.graph.applyChanges()
        self.view.update()
    else:
      return super(Clipboard,self).keypress(size,key)

class CurrentSquare(urwid.Edit):
  def __init__(self,view):
    self.selection = (0,0)
    self.view = view
    super(CurrentSquare,self).__init__(edit_text="",align="left",multiline=True)
    self.cursorCords = (0,0)

  def render(self,size,focus=False):
    self.move_cursor_to_coords(size,self.cursorCords[0],self.cursorCords[1])
    return super(CurrentSquare,self).render(size,focus=focus)

  def keypress(self,size,key):
    if key in keybindings['new-square-streeted-to-previous-square']:
      prevSquare = self.view.history[-1]
      self.view.recordChanges()
      newSquareId = self.view.graph.newLinkedSquare(prevSquare,self.view.defaultStreetName)
      self.view.selection = newSquareId
      self.view.history.append(prevSquare)
      self.view.update()
    if self.view.mode =='command':
      if key in keybindings['add-to-stack']:
        self.view.clipboard.squares.append(self.view.graph[self.view.selection])
        self.view.update()
      elif key in keybindings['delete-square']:
        if self.view.selection != 0:
          self.view.graph.deleteSquare(self.view.selection)
          while True:
            prevSelection = self.view.history.pop()
            if prevSelection != self.view.selection:
              self.view.selection = prevSelection
              break
          if self.view.graph[self.view.selection].text is None:
            self.view.selection = 0
        else:
          self.view.statusMessage = "Cannot delete square 0."
        self.view.update()
      elif key in keybindings['delete-tree']:
        self.view.graph.deleteTree(self.view.selection)
        self.view.update()
      elif not self.valid_char(key):
        value = super(CurrentSquare,self).keypress(size,key)
        self.cursorCords = self.get_cursor_coords(size)
        return value
      else:
        return key
    else:
      value = super(CurrentSquare,self).keypress(size,key)
      self.cursorCords = self.get_cursor_coords(size)
      return value

class StreetNavigator(urwid.ListBox):
  def __init__(self,view,selectionCollor,alignment):
    self.view = view
    self.selectionCollor = selectionCollor
    self.alignment = alignment
    self.streets = []
    self.streetNameEdits = []
    super(StreetNavigator,self).__init__(urwid.SimpleFocusListWalker([]))

  def update(self,streets=None):
    if streets is not None:
      self.streets = streets
    items = []
    self.streetNameEdits = []
    if not self.streets:
      items.append(urwid.AttrMap(urwid.Padding(urwid.SelectableIcon(" ",0),align=self.alignment,width="pack"),None,self.selectionCollor))
    for street in self.streets:
      if self.alignment == 'left':
        if self.view.mode == 'command':
          items.append(urwid.Columns([urwid.AttrMap(urwid.Padding(urwid.SelectableIcon(self.view.graph[street.origin].title + " → ",0),width="pack"),None,self.selectionCollor),urwid.Text(street.name)]))
        elif self.view.mode == 'insert':
          edit = urwid.Edit(edit_text=street.name)
          self.streetNameEdits.append(edit)
          items.append(urwid.Columns([urwid.Text(self.view.graph[street.origin].title + " → "),edit]))
      elif self.alignment == 'right':
        if self.view.mode == 'command':
          items.append(urwid.Columns([urwid.Text(street.name),urwid.AttrMap(urwid.Padding(urwid.SelectableIcon(" → " + self.view.graph[street.destination].title,0),width="pack"),None,self.selectionCollor)]))
        elif self.view.mode == 'insert':
          edit = urwid.Edit(edit_text=street.name)
          self.streetNameEdits.append(edit)
          items.append(urwid.Columns([edit,urwid.Text(" → " + self.view.graph[street.destination].title)]))
    self.body.clear()
    self.body.extend(items)

  def keypress(self,size,key):
    if self.view.mode == "insert":
      return super(StreetNavigator,self).keypress(size,key)
    if key in keybindings['new-square']:
      self.view.selection = self.newStreetToNewSquare(useDefaultStreetName=True)
      self.view.focus_item = self.view.currentSquareWidget
      self.view.mode = 'insert'
    if key in keybindings['new-square-with-blank-street-name']:
      self.view.selection = self.newStreetToNewSquare(useDefaultStreetName=False)
      self.view.focus_item = self.view.currentSquareWidget
      self.view.mode = 'insert'
      self.view.update()
    if key in keybindings['new-square-setting-street-name']:
      self.newStreetToNewSquare(useDefaultStreetName=False)
      self.view.mode = 'insert'
      self.view.update()
      return None
    if key in keybindings['set-default-street-name']:
      if self.streets:
        self.view.defaultStreetName = self.streets[self.focus_position].name
    if key in [self.alignment,'enter']:
      if self.streets:
        self.view.recordChanges()
        self.view.selection = self.selectedSquareId
        if key == 'enter':
          self.view.focus_item = self.view.currentSquareWidget
          self.view.mode = 'insert'
        self.view.update()
      else:
        self.view.selection = self.newStreetToNewSquare()
        self.view.focus_item = self.view.currentSquareWidget
        self.view.mode = 'insert'
        self.view.update()
    if key in keybindings["delete-square"]:
      if self.streets:
        squareId = self.selectedSquareId
        if squareId != 0:
          self.view.graph.deleteSquare(squareId)
          self.view.update()
        else:
          self.view.statusMessage = "Cannot delete square 0."
    if key in keybindings["delete-tree"]:
      if self.streets:
        squareId = self.selectedSquareId
        if squareId != 0:
          self.view.graph.deleteTree(squareId)
          self.view.update()
        else:
          self.view.statusMessage = "Cannot delete square 0."
    if key in keybindings["add-to-stack"]:
      if self.streets:
        self.view.clipboard.squares.append(self.view.graph[self.selectedSquareId])
        fcp = self.focus_position
        self.view.update()
        self.focus_position = fcp
    else:
      return super(StreetNavigator,self).keypress(size,key)

class IncommingStreetsList(StreetNavigator):
  def __init__(self,view):
    super(IncommingStreetsList,self).__init__(view,'incommingStreet_selected','left')

  def recordChanges(self):
    if self.view.mode == "insert":
      newStreetNamesBySquareOfOrigin = {}
      for edit,street in zip(self.streetNameEdits,self.streets):
        if street.origin not in newStreetNamesBySquareOfOrigin:
          newStreetNamesBySquareOfOrigin[street.origin] = []
        newStreetNamesBySquareOfOrigin[street.origin].append(edit.edit_text)
      for squareOfOrigin,streetNames in newStreetNamesBySquareOfOrigin.items():
        square = copy.deepcopy(self.view.graph[squareOfOrigin])
        changed = False
        for street in square.streets:
          if street.destination == self.view.selection:
            newStreetName = streetNames.pop()
            if not street.name == newStreetName:
              street.name = newStreetName
              changed = True
        if changed:
          self.view.graph.stageSquare(square)
      self.view.graph.applyChanges()

  @property
  def selectedSquareId(self):
    """
    The square that the selected street points to, in the direction going away from the current square.
    """
    return self.streets[self.focus_position].origin

  def newStreetToNewSquare(self,useDefaultStreetName=True):
    self.view.recordChanges()
    squareId = self.view.graph.allocSquare()
    if useDefaultStreetName:
      streetName = self.view.defaultStreetName
    else:
      streetName = ""
    square = Square(squareId,"",[Street(streetName,self.view.selection,squareId)])
    self.view.graph.stageSquare(square)
    self.view.graph.applyChanges()
    return square.squareId

  def keypress(self,size,key):
    if self.view.mode == "insert":
      return super(IncommingStreetsList,self).keypress(size,key)
    if key in ['right']:
      self.view.focus_item = self.view.streets
      try:
        self.view.streets.focus_position = 0
      except IndexError:
        pass
    if key in keybindings['street-or-back-street-last-stack-item']:
      if self.view.clipboard.squares:
        square = self.view.clipboard.squares.pop()
        square.streets.append(Street(self.view.defaultStreetName,self.view.selection,square.squareId))
        self.view.graph.stageSquare(square)
        self.view.graph.applyChanges()
        self.view.update()
        self.focus_position = len(self.streets) - 1
    elif key in keybindings['remove-street-or-incommingStreet']:
      try:
        fcp = self.focus_position
        street = self.streets[fcp]
        square = copy.deepcopy(self.view.graph[street.origin])
        square.streets = [street for street in square.streets if street.destination != self.view.selection]
        self.view.graph.stageSquare(square)
        self.view.graph.applyChanges()
        self.view.update()
      except IndexError:
        pass
    else:
      return super(IncommingStreetsList,self).keypress(size,key)

class StreetsList(StreetNavigator):
  def __init__(self,view):
    self.view = view
    super(StreetsList,self).__init__(view,'street_selected','right')

  def recordChanges(self):
    if self.view.mode == 'insert':
      square = copy.deepcopy(self.view.graph[self.view.selection])
      changed = False
      for street,streetEdit in zip(square.streets,self.streetNameEdits):
        if not street.name == streetEdit.edit_text:
          street.name = streetEdit.edit_text
          changed = True
      if changed:
        self.view.graph.stageSquare(square)
        self.view.graph.applyChanges()

  @property
  def selectedSquareId(self):
    """
    The square that the selected street points to, in the direction going away from the current square.
    """
    return self.streets[self.focus_position].destination

  def newStreetToNewSquare(self,useDefaultStreetName=True):
    self.view.recordChanges()
    if useDefaultStreetName:
      streetName = self.view.defaultStreetName
    else:
      streetName = ""
    return self.view.graph.newLinkedSquare(self.view.selection,streetName)

  def keypress(self,size,key):
    if self.view.mode == "insert":
      return super(StreetsList,self).keypress(size,key)
    if key in keybindings['move-square-up']:
      sel = copy.deepcopy(self.view.graph[self.view.selection])
      fcp = self.focus_position
      if fcp >= 1:
        street = sel.streets[fcp]
        prevStreet = sel.streets[fcp - 1]
        sel.streets[fcp] = prevStreet
        sel.streets[fcp - 1] = street
        self.view.graph.stageSquare(sel)
        self.view.graph.applyChanges()
        self.view.update()
        self.focus_position = fcp - 1
    elif key in keybindings['move-square-down']:
      sel = copy.deepcopy(self.view.graph[self.view.selection])
      fcp = self.focus_position
      if fcp < len(sel.streets):
        street = sel.streets[fcp]
        nextStreet = sel.streets[fcp + 1]
        sel.streets[fcp] = nextStreet
        sel.streets[fcp + 1] = street
        self.view.graph.stageSquare(sel)
        self.view.graph.applyChanges()
        self.view.update()
        self.focus_position = fcp + 1
    elif key in ['left']:
      self.view.focus_item = self.view.incommingStreets
    elif key in keybindings['street-or-back-street-last-stack-item']:
      if self.view.clipboard.squares:
        if self.streets:
          fcp = self.focus_position
        else:
          fcp = -1
        square = self.view.clipboard.squares.pop()
        sel = copy.deepcopy(self.view.graph[self.view.selection])
        sel.streets.insert(fcp + 1,Street(self.view.defaultStreetName,square.squareId,self.view.selection))
        self.view.graph.stageSquare(sel)
        self.view.graph.applyChanges()
        self.view.update()
        self.focus_position = fcp + 1
    elif key in keybindings['remove-street-or-incommingStreet']:
      try:
        fcp = self.focus_position
        street = self.streets[fcp]
        selectedSquare = copy.deepcopy(self.view.graph[self.view.selection])
        selectedSquare.streets.remove(street)
        self.view.graph.stageSquare(selectedSquare)
        self.view.graph.applyChanges()
        self.view.update()
      except IndexError:
        pass
    else:
      return super(StreetsList,self).keypress(size,key)

class SearchBox(urwid.ListBox):
  def __init__(self,view):
    self.view = view
    self.squares = self.view.graph.values()
    super(SearchBox,self).__init__(urwid.SimpleFocusListWalker([]))
    self.searchEdit = urwid.Edit()
    self.body.append(self.searchEdit)
    self.update()

  def update(self):
    self.squares = []
    items = []
    for square in self.view.graph.values():
      if square.text is not None:
        if self.searchEdit.edit_text in square.text:
          self.squares.append(square)
          items.append(urwid.Padding(urwid.SelectableIcon(square.title,0),align='left',width="pack"))
    del self.body[1:]
    self.body.extend(items)
    self.focus_position = 0

  @property
  def focused_square(self):
    if self.focus_position > 0:
      return self.squares[self.focus_position-1].squareId
    else:
      raise IndexError("No focused square.")

  def keypress(self,size,key):
    if self.focus_position == 0:
      if key == 'enter':
        try:
          self.focus_position = 1
          return super(SearchBox,self).keypress(size,key)
        except IndexError:
          pass
      else:
        value = super(SearchBox,self).keypress(size,key)
        self.update()
        return value
    if key in keybindings['command-mode.up']:
      return super(SearchBox,self).keypress(size,'up')
    elif key in keybindings['command-mode.down']:
      return super(SearchBox,self).keypress(size,'down')
    elif key in keybindings['jump-to-command-bar']:
      self.view.focus_position = 'footer'
    elif key == 'enter':
      self.view.selection = self.focused_square
      self.view.mode = 'command'
      self.view.update()
    elif key in keybindings['insert-mode']:
      self.view.selection = self.focused_square
      self.view.mode = 'insert'
      self.view.update()
    elif key in keybindings['add-to-stack']:
      self.view.clipboard.squares.append(self.view.graph[self.focused_square])
      self.view.update()
    else:
      return super(SearchBox,self).keypress(size,key)

class CommandBar(urwid.Edit):
  def __init__(self,view):
    self.view = view
    self.edit = self
    super(CommandBar,self).__init__(":")

  def keypress(self,size,key):
    if key != 'enter':
      return super(CommandBar,self).keypress(size,key)
    success = False
    com = self.edit.edit_text
    if com == "savedot":
      success = True
      try:
        self.view.graph.saveDot()
      except OSError as e:
        self.view.statusMessage = str(e)
    else:
      if "w" in com:
        success = True
        try:
          self.view.recordChanges()
          self.view.graph.save()
          self.view.graph.edited = False
        except (FileNotFoundError,OSError) as e:
          self.edit.set_caption("Unable to save:"+str(e)+"\n:")
      if "q" in com:
        success = True
        if self.view.graph.edited and "!" not in com:
          self.edit.set_caption("Not quiting. Save your work first, or use 'q!'\n:")
        else:
          raise urwid.ExitMainLoop()
      try:
        newSelection = int(com)
        if newSelection >= 0 and newSelection < len(self.view.graph) and self.view.graph[newSelection].text is not None:
          self.view.selection = newSelection
          self.view.update()
          self.view.focus_item = self.view.currentSquareWidget
          self.view.mode = 'command'
          success = True
        else:
          self.edit.set_caption("Cannot jump to "+com+". Square does not exist.\n:")
      except ValueError:
        pass
    self.edit.edit_text = ""
    if success:
      self.view.focus_item = self.view.currentSquareWidget
    else:
      self.edit.set_caption(com + " is not a valid mge command.\n:")

keybindings = {
 # global/command-mode
 'back' : ['meta left','b'],
 'street-or-back-street-last-stack-item' : ['p'],
 'add-to-stack' : ['c'],
 'move-square-up' : ['ctrl up'],
 'move-square-down' : ['ctrl down'],
 'new-square' : ['n'],
 'new-square-with-blank-street-name' : ['N'],
 'new-square-setting-street-name' : ['ctrl n'],
 'new-square-streeted-to-previous-square' : ['meta enter'],
 'remove-street-or-incommingStreet' : ['d'],
 'delete-square' : ['delete'],
 'delete-tree' : ['ctrl delete'],
 'move-to-square-zero' : ['.'],
 'jump-to-command-bar' : [':'],
 'leave-and-go-to-mainer-part' : ['esc'],
 'move-up-one-mega-widget' : ['meta up'],
 'move-down-one-mega-widget' : ['meta down'],
 'command-mode' : ['esc'],
 'command-mode.up' : ['k'],
 'command-mode.down' : ['j'],
 'command-mode.left' : ['h'],
 'command-mode.right' : ['l'],
 'command-mode.undo' : ['u'],
 'command-mode.redo' : ['ctrl r'],
 'insert-mode' : ['i'],
 'search-mode' : ['/'],
 'show-map-of-neighborhood': ['m'],
 'show-map': ['M'],
 'clear-default-street-name': ['F'],
 'go-down-default-street': ['g'],
 'go-up-default-street': ['G'],
 # street navigator
 'set-default-street-name': ['f'],
 # stack area
 'remove-from-stack' : ['d'],
 'street-to-stack-item-no-pop' : ['ctrl right'],
 'street-to-stack-item' : ['right'],
 'incommingStreet-to-stack-item-no-pop' : ['ctrl left'],
 'incommingStreet-to-stack-item' : ['left'],
 }
pallet = [('incommingStreet_selected', 'white', 'dark blue')
         ,('street_selected', 'white', 'dark red')
         ,('selection','black','white')
         ,('clipboard','white','dark gray')]

if __name__ == "__main__":
  parser = optparse.OptionParser(usage = "mge FILE",description = "Edit simple text graph file(tg file) using a simple,fast TUI interface.")
  options,args = parser.parse_args(sys.argv[1:])

  if not len(args) == 1:
    sys.exit("mge expects to be passed a single file path for editing. Use --help for help.")

  graphView = GraphView(TextGraph(args[0]))
  urwid.MainLoop(graphView,pallet,handle_mouse=False).run()
