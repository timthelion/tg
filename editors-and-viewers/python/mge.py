#!/usr/bin/python3
#
# Authors: Timothy Hobbs
# Copyright years: 2016
#
# Description:
#
# mge is a simple TUI Vim style modal editor for textual graphs.
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
import json
import optparse
import copy
import subprocess
try:
  import urwid
except ImportError:
  sys.exit("The urwid TUI toolkit is required to run this program. On debian based systems you need to install python3-urwid. On other systems you'll have to search the web.")

def showErrorDialog(error):
  # http://stackoverflow.com/questions/12876335/urwid-how-to-see-errors
  import tkinter as tk
  root = tk.Tk()
  window = tk.Label(root, text=error)
  window.pack()
  root.mainloop()

class Node():
  def __init__(self,nodeId,text,links):
    self.nodeId = nodeId
    self.text = text
    self.links = links

  def __repr__(self):
    return str((self.nodeId,self.text,self.links))

  @property
  def title(self):
    try:
      return self.text.splitlines()[0]
    except IndexError:
      return "<blank-text>"

class TextGraph(list):
  def __init__(self,fileName):
    self.fileName = fileName
    self.edited = False
    self.deleted = []
    self.stagedNodes = []
    self.undone = []
    self.done = []
    self.header = ""
    try:
      with open(fileName) as fd:
        self.json = fd.read()
    except FileNotFoundError:
      self.append(Node(0,"",[]))
    for node in self:
      if node.text is None:
        self.deleted.append(node.nodeId)

  def allocNode(self):
    """
    Return the ID of a new or free node.
    """
    if self.deleted:
      return self.deleted.pop()
    else:
      nodeId = len(self)
      self.append(Node(nodeId,None,[]))
      return nodeId

  def stageNode(self,node):
    self.stagedNodes.append(copy.deepcopy(node))

  def applyChanges(self):
    didNow = []
    didSomething = False
    for node in self.stagedNodes:
      if node.text is None:
        self.deleted.append(node.nodeId)
      elif node.nodeId in self.deleted:
        self.deleted.remove(node.nodeId)
      prevState = self[node.nodeId]
      didNow.append((copy.deepcopy(prevState),copy.deepcopy(node)))
      if not (prevState.text == node.text and prevState.links == node.links):
        didSomething = True
        prevState.text = node.text
        prevState.links = copy.copy(node.links)
    if didSomething:
      self.undone = []
      self.stagedNodes = []
      self.done.append(didNow)
      self.edited = True

  def undo(self):
    try:
      transaction = self.done.pop()
    except IndexError:
      return
    self.edited = True
    for (prevState,postState) in transaction:
      currentState = self[prevState.nodeId]
      currentState.text = prevState.text
      currentState.links = copy.copy(prevState.links)
    self.undone.append(transaction)

  def redo(self):
    try:
      transaction = self.undone.pop()
    except IndexError:
      return
    self.edited = True
    for (prevState,postState) in transaction:
      currentState = self[postState.nodeId]
      currentState.text = postState.text
      currentState.links = copy.copy(postState.links)
    self.done.append(transaction)

  def trimBlankNodesFromEnd(self):
    try:
      node = self.pop()
    except IndexError:
      pass
    if not node.text is None:
      self.append(node)
    else:
      # I am not sure if the return makes for tail recursion, but I hope so.
      return self.trimBlankNodesFromEnd()

  def getBacklinks(self,nodeId):
    backlinks = []
    for node in self:
      if nodeId in node.links:
        backlinks.append(node.nodeId)
    return backlinks

  def getDeleteNodeChanges(self,nodeId):
    changes = []
    for backlink in self.getBacklinks(nodeId):
      if backlink != nodeId:
        backlinkingNode = copy.deepcopy(self[backlink])
        backlinkingNode.links = [value for value in backlinkingNode.links if value != nodeId]
        changes.append(backlinkingNode)
    changes.append(Node(nodeId,None,[]))
    return changes

  def stageNodeForDeletion(self,nodeId):
    for node in self.getDeleteNodeChanges(nodeId):
      self.stageNode(node)

  def deleteNode(self,nodeId):
    self.stageNodeForDeletion(nodeId)
    self.applyChanges()

  def getTree(self,nodeId):
    node = self[nodeId]
    tree = set([node.nodeId])
    for link in node.links:
      if not link in tree:
        tree.update(self.getTree(link))
    return tree

  def deleteTree(self,nodeId):
    nodesForDeletion = set(self.getTree(nodeId))
    for node in self:
      if not node.nodeId in nodesForDeletion:
        newLinks = []
        for link in node.links:
          if not link in nodesForDeletion:
            newLinks.append(link)
        if newLinks != node.links:
          self.stageNode(Node(node.nodeId,node.text,newLinks))
    for node in nodesForDeletion:
      self.stageNode(Node(node,None,[]))
    self.applyChanges()

  @property
  def json(self):
    self.trimBlankNodesFromEnd()
    serialized = self.header
    for node in self:
      serialized += json.dumps([node.text,node.links])
      serialized += "\n"
    return serialized

  @json.setter
  def json(self,text):
    self.header = ""
    readingHeader = True
    nodeId = 0
    for line in text.splitlines():
      if not line or line.startswith("#"):
        if readingHeader:
          self.header += line+"\n"
      else:
        readingHeader = False
        try:
          (text,links) = json.loads(line)
          self.append(Node(nodeId,text,links))
          nodeId += 1
        except ValueError as e:
          sys.exit("Cannot load file "+self.fileName+"\n"+str(e))

  @property
  def dot(self):
    dot = "digraph graphname{\n"
    labels = ""
    edges = ""
    for node in self:
      if node.text is not None:
        labels += str(node.nodeId)+"[label="+json.dumps(node.text)+"]\n"
        for link in node.links:
          edges += str(node.nodeId)+" -> "+str(link)+"\n"
    dot += labels
    dot += edges
    dot += "}"
    return dot

  def showDiagram(self):
    subprocess.Popen(["dot","-T","xlib","/dev/stdin"],stdin=subprocess.PIPE).communicate(input=self.dot.encode("ascii"))

  def save(self):
    with open(self.fileName,"w") as fd:
      fd.write(self.json)

class GraphView(urwid.Frame):
  def __init__(self,graph):
    self.mode = 'command-mode'
    self.graph = graph
    self._selection = 0
    self.history = []
    # clipboard
    self.clipboard = Clipboard(self)
    self.clipboardBoxAdapter = urwid.BoxAdapter(self.clipboard,3)
    # backlinks
    self.backlinks = BackLinksList(self)
    # current node
    self.currentNode = CurrentNode(self)
    self.currentNodeWidget = urwid.Filler(urwid.AttrMap(self.currentNode,None,"selection"))
    # links
    self.links = LinksList(self)
    # status bar
    self.statusMessage = ""
    self.statusBar = urwid.Text("")
    # command bar
    self.commandBar = CommandBar(self)
    # search box
    self.searchBox = SearchBox(self)
    # main frame
    self.pile = urwid.Pile([self.backlinks,self.currentNodeWidget,self.links])
    self.body = urwid.WidgetPlaceholder(self.pile)
    super(GraphView,self).__init__(self.body,header=self.clipboardBoxAdapter,footer=urwid.BoxAdapter(urwid.ListBox(urwid.SimpleFocusListWalker([self.statusBar,self.commandBar])),height=3))
    self.update()
    self.updateStatusBar()
    self.focus_item = self.currentNodeWidget

  def update(self):
    # clipboard
    self.clipboard.update()
    # backlinks
    backlinks = []
    for backlink in self.graph.getBacklinks(self.selection):
      backlinks.append(copy.deepcopy(self.graph[backlink]))
    self.backlinks.update(backlinks)
    # current node
    self.currentNode.edit_text = self.graph[self.selection].text
    # links
    nodes = []
    for nodeId in self.graph[self.selection].links:
      try:
        nodes.append(copy.deepcopy(self.graph[nodeId]))
      except IndexError as e:
        raise IndexError("nodeId:"+str(nodeId)+"\nselection:"+str(self.selection)+str(self.graph.json))
    self.links.update(nodes)

  def updateStatusBar(self):
    if self.graph.edited:
      edited = "Edited"
    else:
      edited = "Saved"
    if self.mode == 'search-mode':
      try:
        currentNodeId = self.searchBox.focused_node
      except IndexError:
        currentNodeId = 0
    elif self.focus_item == self.backlinks:
      try:
        currentNodeId = self.backlinks.nodes[self.backlinks.focus_position].nodeId
      except IndexError:
        currentNodeId = self.selection
    elif self.focus_item == self.links:
      try:
        currentNodeId = self.links.nodes[self.links.focus_position].nodeId
      except IndexError:
        currentNodeId = self.selection
    else:
      currentNodeId = self.selection
    self.statusBar.set_text("Node: "+str(currentNodeId) + " " + edited + " Undo: "+str(len(self.graph.done))+" Redo: "+str(len(self.graph.undone))+" " +self.mode+ " | "+self.statusMessage)

  def recordChanges(self):
    if self.graph[self.selection].text != self.currentNode.edit_text:
      currentNode = copy.deepcopy(self.graph[self.selection])
      currentNode.text = self.currentNode.edit_text
      self.graph.stageNode(currentNode)
      self.graph.applyChanges()

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

  def inEditArea(self):
    return self.focus_item == self.commandBar or self.focus_item == self.currentNodeWidget

  def keypress(self,size,key):
    if self.mode == 'search-mode':
      return self.keypressSearchmode(size, key)
    focusedBeforeProcessing = self.focus_item
    value = self.handleKeypress(size,key)
    if key in keybindings['command-mode.down'] and focusedBeforeProcessing == self.currentNodeWidget and self.focus_item == self.links:
      self.links.focus_position = 0
    self.updateStatusBar()
    return value

  def handleKeypress(self,size,key):
    if key in keybindings['leave-and-go-to-mainer-part']:
      self.focus_item = self.currentNodeWidget
    if key in ['left','right','up','down','home','end']:
      self.recordChanges()
      return super(GraphView,self).keypress(size,key)
    if key in keybindings['command-mode']:
      self.recordChanges()
      self.mode = 'command-mode'
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
    elif self.focus_item != self.commandBar and (self.mode == 'command-mode' or not self.inEditArea()):
      self.recordChanges()
      if key in keybindings["back"]:
        if self.history:
          self._selection = self.history.pop()
          self.update()
      elif key in keybindings['move-to-node-zero']:
        self.selection = 0
        self.update()
        self.focus_item = self.currentNodeWidget
      elif key in keybindings['search-mode']:
        self.mode = 'search-mode'
        self.searchBox.searchEdit.edit_text = ""
        self.searchBox.update()
        self.body.original_widget = self.searchBox
        self.updateStatusBar()
        return None
      elif key in keybindings['jump-to-command-bar']:
        self.focus_item = self.commandBar
      elif key in keybindings['insert-mode']:
        self.mode = 'insert-mode'
        if not self.inEditArea():
          return super(GraphView,self).keypress(size,key)
      elif key in keybindings['show-map']:
        return self.graph.showDiagram()
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
        self.mode = 'command-mode'
        self.body.original_widget = self.pile
        self.updateStatusBar()
        return None
    elif self.focus_position == 'body':
      value = self.body.keypress(size,key)
      self.updateStatusBar()
      return value
    else:
      super(GraphView,self).keypress(size,key)

class NodeList(urwid.ListBox):
  def __init__(self,selectionCollor,alignment):
    self.selectionCollor = selectionCollor
    self.alignment = alignment
    self.nodes = []
    super(NodeList,self).__init__(urwid.SimpleFocusListWalker([]))

  def update(self,nodes=None):
    if nodes is not None:
      self.nodes = nodes
    items = []
    if not self.nodes:
      items.append(urwid.AttrMap(urwid.Padding(urwid.SelectableIcon(" ",0),align=self.alignment,width="pack"),None,self.selectionCollor))
    for node in self.nodes:
      items.append(urwid.AttrMap(urwid.Padding(urwid.SelectableIcon(node.title,0),align=self.alignment,width="pack"),None,self.selectionCollor))
    self.body.clear()
    self.body.extend(items)

class Clipboard(NodeList):
  def __init__(self,view):
    self.view = view
    super(Clipboard,self).__init__("clipboard","right")

  def keypress(self,size,key):
    if key in keybindings["remove-from-stack"]:
      fcp = self.focus_position
      del self.nodes[fcp]
      self.update()
      if fcp < len(self.nodes):
        self.focus_position = fcp
    if key in keybindings['link-to-stack-item'] or key in keybindings['link-to-stack-item-no-pop']:
      try:
        fcp = self.focus_position
      except IndexError:
        pass
      else:
        node = self.nodes[fcp]
        if not key in keybindings['link-to-stack-item-no-pop']:
          del self.nodes[fcp]
        currentNode = copy.deepcopy(self.view.graph[self.view.selection])
        currentNode.links.append(node.nodeId)
        self.graph.stageNode(currentNode)
        self.graph.applyChanges()
        self.view.update()
    if key in keybindings['backlink-to-stack-item'] or key in keybindings['backlink-to-stack-item-no-pop']:
      try:
        fcp = self.focus_position
      except IndexError:
        pass
      else:
        node = self.nodes[fcp]
        if not key in keybindings['backlink-to-stack-item-no-pop']:
          del self.nodes[fcp]
        node.links.append(self.view.selection)
        self.view.graph.stageNode(node)
        self.view.graph.applyChanges()
        self.view.update()
    else:
      return super(Clipboard,self).keypress(size,key)

class CurrentNode(urwid.Edit):
  def __init__(self,view):
    self.view = view
    super(CurrentNode,self).__init__(edit_text="",align="center",multiline=True)
    self.cursorCords = (0,0)

  def render(self,size,focus=None):
    self.move_cursor_to_coords(size,self.cursorCords[0],self.cursorCords[1])
    return super(CurrentNode,self).render(size,True)

  def keypress(self,size,key):
    if self.view.mode =='command-mode':
      if key in keybindings['add-to-stack']:
        self.view.clipboard.nodes.append(self.view.graph[self.view.selection])
        self.view.update()
      elif not self.valid_char(key):
        value = super(CurrentNode,self).keypress(size,key)
        self.cursorCords = self.get_cursor_coords(size)
        return value
      else:
        return key
    else:
      value = super(CurrentNode,self).keypress(size,key)
      self.cursorCords = self.get_cursor_coords(size)
      return value


class NodeNavigator(NodeList):
  def __init__(self,view,selectionCollor,alignment):
    self.alignment = alignment
    super(NodeNavigator,self).__init__(selectionCollor,alignment)

  def keypress(self,size,key):
    if key in keybindings['new-node']:
      self.newNode()
    if key in [self.alignment,'enter'] or key in keybindings['insert-mode']:
      if self.nodes:
        self.view.recordChanges()
        self.view.selection = self.nodes[self.focus_position].nodeId
        self.view.update()
        if not key == self.alignment:
          self.view.focus_item = self.view.currentNodeWidget
      else:
        self.newNode()
    if key in keybindings["delete-node"]:
      if self.nodes:
        nodeId = self.nodes[self.focus_position].nodeId
        if nodeId != 0:
          self.view.graph.deleteNode(nodeId)
          self.view.update()
        else:
          self.view.statusMessage = "Cannot delete node 0."
    if key in keybindings["delete-tree"]:
      if self.nodes:
        nodeId = self.nodes[self.focus_position].nodeId
        if nodeId != 0:
          self.view.graph.deleteTree(nodeId)
          self.view.update()
        else:
          self.view.statusMessage = "Cannot delete node 0."
    if key in keybindings["add-to-stack"]:
      if self.nodes:
        self.view.clipboard.nodes.append(self.nodes[self.focus_position])
        fcp = self.focus_position
        self.view.update()
        self.focus_position = fcp
    else:
      return super(NodeNavigator,self).keypress(size,key)

class BackLinksList(NodeNavigator):
  def __init__(self,view):
    self.view = view
    super(BackLinksList,self).__init__(view,'backlink_selected','left')

  def newNode(self):
    self.view.recordChanges()
    nodeId = self.view.graph.allocNode()
    node = Node(nodeId,"",[self.view.selection])
    self.view.selection = node.nodeId
    self.view.graph.stageNode(node)
    self.view.graph.applyChanges()
    self.view.update()
    self.view.focus_item = self.view.currentNodeWidget
    self.view.mode = 'insert-mode'

  def keypress(self,size,key):
    if key in ['right']:
      self.view.focus_item = self.view.links
      try:
        self.view.links.focus_position = 0
      except IndexError:
        pass
    if key in keybindings['link-or-back-link-last-stack-item']:
      if self.view.clipboard.nodes:
        node = self.view.clipboard.nodes.pop()
        node.links.append(self.view.selection)
        self.view.graph.stageNode(node)
        self.view.graph.applyChanges()
        self.view.update()
        self.focus_position = len(self.nodes) - 1
    elif key in keybindings['remove-link-or-backlink']:
      try:
        fcp = self.focus_position
        node = self.nodes[fcp]
        node.links.remove(self.view.selection)
        self.view.graph.stageNode(node)
        self.view.graph.applyChanges()
        self.view.update()
      except IndexError:
        pass
    else:
      return super(BackLinksList,self).keypress(size,key)

class LinksList(NodeNavigator):
  def __init__(self,view):
    self.view = view
    super(LinksList,self).__init__(view,'link_selected','right')

  def newNode(self):
    self.view.recordChanges()
    newNodeId = self.view.graph.allocNode()
    newNode = Node(newNodeId,"",[])
    selectedNode = copy.deepcopy(self.view.graph[self.view.selection])
    selectedNode.links.append(newNodeId)
    self.view.selection = newNodeId
    self.view.graph.stageNode(newNode)
    self.view.graph.stageNode(selectedNode)
    self.view.graph.applyChanges()
    self.view.update()
    self.view.focus_item = self.view.currentNodeWidget

  def keypress(self,size,key):
    if key in keybindings['move-node-up']:
      sel = copy.deepcopy(self.view.graph[self.view.selection])
      fcp = self.focus_position
      if fcp >= 0:
        link = sel.links[fcp]
        prevLink = sel.links[fcp - 1]
        sel.links[fcp] = prevLink
        sel.links[fcp - 1] = link
        self.view.graph.stageNode(sel)
        self.view.graph.applyChanges()
        self.view.update()
        self.focus_position = fcp - 1
    elif key in keybindings['move-node-down']:
      sel = copy.deepcopy(self.view.graph[self.view.selection])
      fcp = self.focus_position
      if fcp < len(sel.links):
        link = sel.links[fcp]
        nextLink = sel.links[fcp + 1]
        sel.links[fcp] = nextLink
        sel.links[fcp + 1] = link
        self.view.graph.stageNode(sel)
        self.view.graph.applyChanges()
        self.view.update()
        self.focus_position = fcp + 1
    elif key in ['left']:
      self.view.focus_item = self.view.backlinks
    elif key in keybindings['link-or-back-link-last-stack-item']:
      if self.view.clipboard.nodes:
        if self.nodes:
          fcp = self.focus_position
        else:
          fcp = -1
        node = self.view.clipboard.nodes.pop()
        sel = copy.deepcopy(self.view.graph[self.view.selection])
        sel.links.insert(fcp + 1,node.nodeId)
        self.view.graph.stageNode(sel)
        self.view.graph.applyChanges()
        self.view.update()
        self.focus_position = fcp + 1
    elif key in keybindings['remove-link-or-backlink']:
      try:
        fcp = self.focus_position
        node = self.nodes[fcp]
        selectedNode = copy.deepcopy(self.view.graph[self.view.selection])
        selectedNode.links.remove(node.nodeId)
        self.view.graph.stageNode(selectedNode)
        self.view.graph.applyChanges()
        self.view.update()
      except IndexError:
        pass
    else:
      return super(LinksList,self).keypress(size,key)

class SearchBox(urwid.ListBox):
  def __init__(self,view):
    self.view = view
    self.nodes = self.view.graph
    super(SearchBox,self).__init__(urwid.SimpleFocusListWalker([]))
    self.searchEdit = urwid.Edit()
    self.body.append(self.searchEdit)
    self.update()

  def update(self):
    self.nodes = []
    items = []
    for node in self.view.graph:
      if node.text is not None:
        if self.searchEdit.edit_text in node.text:
          self.nodes.append(node)
          items.append(urwid.Padding(urwid.SelectableIcon(node.title,0),align='left',width="pack"))
    del self.body[1:]
    self.body.extend(items)
    self.focus_position = 0

  @property
  def focused_node(self):
    if self.focus_position > 0:
      return self.nodes[self.focus_position-1].nodeId
    else:
      raise IndexError("No focused node.")

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
      self.view.selection = self.focused_node
      self.view.mode = 'command-mode'
      self.view.body.original_widget = self.view.pile
      self.view.update()
    elif key in keybindings['insert-mode']:
      self.view.selection = self.focused_node
      self.view.mode = 'insert-mode'
      self.view.body.original_widget = self.view.pile
      self.view.update()
    elif key in keybindings['add-to-stack']:
      self.view.clipboard.nodes.append(self.view.graph[self.focused_node])
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
    if "w" in com:
      success = True
      try:
        self.view.recordChanges()
        self.view.graph.save()
        self.view.graph.edited = False
      except FileNotFoundError as e:
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
        self.view.focus_item = self.view.currentNodeWidget
        self.view.mode = 'command-mode'
        success = True
      else:
        self.edit.set_caption("Cannot jump to "+com+". Node does not exist.\n:")
    except ValueError:
      pass
    self.edit.edit_text = ""
    if success:
      self.view.focus_item = self.view.currentNodeWidget
    else:
      self.edit.set_caption(com + " is not a valid mge command.\n:")

keybindings = {
 'back' : ['meta left','b'],
 'remove-from-stack' : ['d','delete'],
 'link-to-stack-item-no-pop' : ['ctrl right'],
 'link-to-stack-item' : ['right'],
 'backlink-to-stack-item-no-pop' : ['ctrl left'],
 'backlink-to-stack-item' : ['left'],
 'link-or-back-link-last-stack-item' : ['p'],
 'add-to-stack' : ['c'],
 'move-node-up' : ['ctrl up'],
 'move-node-down' : ['ctrl down'],
 'new-node' : ['n'],
 'remove-link-or-backlink' : ['d'],
 'delete-node' : ['delete'],
 'delete-tree' : ['ctrl delete'],
 'move-to-node-zero' : ['.'],
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
 'show-map': ['m'],
 }
pallet = [('backlink_selected', 'white', 'dark blue')
         ,('link_selected', 'white', 'dark red')
         ,('selection','black','white')
         ,('clipboard','white','dark gray')]

if __name__ == "__main__":
  parser = optparse.OptionParser(usage = "tg FILE",description = "Edit simple text graph file(tg file) using a simple,fast TUI interface.")
  options,args = parser.parse_args(sys.argv[1:])

  if not len(args) == 1:
    sys.exit("mge expects to be passed a single file path for editing. Use --help for help.")

  graphView = GraphView(TextGraph(args[0]))
  urwid.MainLoop(graphView,pallet).run()
