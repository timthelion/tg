#!/usr/bin/python3

import sys
import json
import optparse
import copy
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

class RingBuffer():
  def __init__(self,maxlen):
    self.maxlen = maxlen
    self._list = [None]*maxlen
    self.index = 0

  def incIndex(self):
    self.index += 1
    if self.index >= self.maxlen:
      self.index = 0

  def decIndex(self):
    self.index -= 1
    if self.index < 0:
      self.index = self.maxlen - 1

  def append(self,item):
    self.incIndex()
    self._list[self.index] = item

  def pop(self):
    self.decIndex()
    item = self._list[self.index]
    return item

  def popForward(self):
    self.incIndex()
    return self._list[self.index]

class Node():
  def __init__(self,nodeId,text,links):
    self.nodeId = nodeId
    self.text = text
    self.links = links

class TextGraph(list):
  def __init__(self,fileName):
    self.fileName = fileName
    self._edited = False
    self.history = RingBuffer(20)
    self.deleted = []
    nodeId = 0
    try:
      with open(fileName) as fd:
        try:
          table = json.load(fd)
        except ValueError as e:
          print("Cannot load file "+fileName)
          sys.exit(str(e))
        for (text,links) in table:
          self.append(Node(nodeId,text,links))
          nodeId += 1
    except FileNotFoundError:
      self.append(Node(0,"",[]))
    for node in self:
      if node.text is None:
        self.deleted.append(node.nodeId)
    self.history.append(copy.deepcopy(self))

  @property
  def edited(self):
    return self._edited

  @edited.setter
  def edited(self,value):
    if value:
      self.history.append(copy.deepcopy(self))
    self._edited = value

  def undo(self):
    previousState = self.history.pop()
    if not previousState is None:
      self.resetState(previousState)

  def redo(self):
    precedingState = self.history.popForward()
    if not precedingState is None:
      self.resetState(precedingState)

  def resetState(self,state):
    self._edited = True
    self.clear()
    self.extend(state)
    self.deleted = state.deleted

  def getBacklinks(self,nodeId):
    backlinks = []
    for node in self:
      if nodeId in node.links:
        backlinks.append(node)
    return backlinks

  def getTree(self,nodeId):
    node = self[nodeId]
    tree = set([node.nodeId])
    for link in node.links:
      if not link in tree:
        tree.update(self.getTree(link))
    return tree

  def newNode(self):
    if self.deleted:
      node = Node(self.deleted.pop(),"",[])
      self[index] = node
    else:
      node = Node(len(self),"",[])
      self.append(node)
    return node

  def save(self):
    # We format the output to privide better diff support.
    serialized = "["
    for node in self:
      serialized += json.dumps([node.text,node.links])
      serialized += "\n,"
    serialized = serialized[:-2] + "]\n"
    with open(self.fileName,"w") as fd:
      fd.write(serialized)

class GraphView(urwid.Pile):
  def __init__(self,graph):
    self.mode = 'command-mode'
    self.graph = graph
    self._selection = 0
    self.history = []
    # clipboard
    self.clipboard = Clipboard(self)
    # backlinks
    self.backlinks = BackLinksList(self)
    # current node
    self.currentNode = urwid.Edit(edit_text="",align="center",multiline=True)
    self.currentNodeWidget = urwid.Filler(urwid.AttrMap(self.currentNode,None,"selection"))
    # links
    self.links = LinksList(self)
    # command bar
    self.commandBar = CommandBar(self)
    # main pile
    super(GraphView,self).__init__([self.clipboard,self.backlinks,self.currentNodeWidget,self.links,self.commandBar])
    self.update()
    self.focus_item = self.currentNodeWidget

  def update(self):
    # clipboard
    self.clipboard.update()
    # backlinks
    self.backlinks.update(self.graph.getBacklinks(self.selection))
    # current node
    self.currentNode.edit_text = self.graph[self.selection].text
    # links
    nodes = []
    for nodeId in self.graph[self.selection].links:
      nodes.append(self.graph[nodeId])
    self.links.update(nodes)

  def recordChanges(self,markEdited=True):
    newText = self.currentNode.edit_text
    if self.graph[self.selection].text != newText:
      self.graph[self.selection].text = newText
      if markEdited:
        self.graph.edited = True

  @property
  def selection(self):
    return self._selection

  @selection.setter
  def selection(self,value):
    self.history.append(self.selection)
    self._selection = value

  def keypress(self,size,key):
    if key in keybindings['jump-to-node-edit-box']:
      self.focus_item = self.currentNodeWidget
    if key in keybindings['command-mode']:
      self.mode = 'command-mode'
    elif key in keybindings['move-down-one-mega-widget']:
      try:
        self.focus_position = self.focus_position + 1
      except IndexError:
        pass
    elif key in keybindings['move-up-one-mega-widget']:
      try:
        self.focus_position = self.focus_position - 1
      except IndexError:
        pass
    elif self.mode == 'command-mode' or (self.focus_item != self.currentNodeWidget  and self.focus_item != self.commandBar):
      if key in keybindings["back"]:
        if self.history:
          self._selection = self.history.pop()
          self.update()
      elif key in keybindings['move-to-node-zero']:
        self.recordChanges()
        self.selection = 0
        self.update()
        self.focus_item = self.currentNodeWidget
      #TODO elif key in keybindings['search-nodes']:
      elif key in keybindings['jump-to-command-bar']:
        self.focus_item = self.commandBar
      elif key in keybindings['insert-mode']:
        self.mode = 'insert-mode'
        if self.focus_item != self.commandBar and self.focus_item != self.currentNodeWidget:
          return super(GraphView,self).keypress(size,key)
      elif key in keybindings['command-mode.up']:
        return super(GraphView,self).keypress(size,'up')
      elif key in keybindings['command-mode.down']:
        return super(GraphView,self).keypress(size,'down')
      elif key in keybindings['command-mode.left']:
        return super(GraphView,self).keypress(size,'left')
      elif key in keybindings['command-mode.right']:
        return super(GraphView,self).keypress(size,'right')
      elif key in keybindings['command-mode.undo']:
        self.recordChanges()
        self.graph.undo()
        self.update()
      elif key in keybindings['command-mode.redo']:
        self.graph.redo()
        self.update()
      else:
        return super(GraphView,self).keypress(size,key)
    else:
      return super(GraphView,self).keypress(size,key)

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
    for node in self.nodes:
      try:
        title = node.text.splitlines()[0]
      except IndexError:
        title = "<blank-text>"
      items.append(urwid.AttrMap(urwid.Padding(urwid.SelectableIcon(title,0),align=self.alignment,width="pack"),None,self.selectionCollor))
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
        self.view.graph[self.view.selection].links.append(node.nodeId)
        self.view.graph.edited = True
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
        self.view.graph.edited = True
        self.view.update()
    else:
      return super(Clipboard,self).keypress(size,key)

class NodeNavigator(NodeList):
  def __init__(self,view,selectionCollor,alignment):
    self.alignment = alignment
    super(NodeNavigator,self).__init__(selectionCollor,alignment)

  def keypress(self,size,key):
    if key in [self.alignment,'enter'] or key in keybindings['insert-mode']:
      if self.nodes:
        self.view.recordChanges()
        self.view.selection = self.nodes[self.focus_position].nodeId
        self.view.update()
        self.view.focus_item = self.view.currentNodeWidget
    if key in keybindings["add-to-stack"]:
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

  def keypress(self,size,key):
    if key in keybindings['new-node']:

      node = self.view.graph.newNode()
      node.links = [self.view.selection]
      self.view.recordChanges(markEdited=False)
      self.view.selection = node.nodeId
      self.view.graph.edited = True
      self.view.update()
      self.view.focus_item = self.view.currentNodeWidget
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
        self.view.graph.edited = True
        self.view.update()
        self.focus_position = self.nodes.index(node)
    elif key in keybindings['remove-link-or-backlink']:
      try:
        fcp = self.focus_position
        node = self.nodes[fcp]
        node.links.remove(self.view.selection)
        self.view.graph.edited = True
        self.view.update()
      except IndexError:
        pass
    else:
      return super(BackLinksList,self).keypress(size,key)

class LinksList(NodeNavigator):
  def __init__(self,view):
    self.view = view
    super(LinksList,self).__init__(view,'link_selected','right')

  def keypress(self,size,key):
    if key in keybindings['move-node-up']:
      sel = self.view.graph[self.view.selection]
      fcp = self.focus_position
      if fcp >= 0:
        link = sel.links[fcp]
        prevLink = sel.links[fcp - 1]
        sel.links[fcp] = prevLink
        sel.links[fcp - 1] = link
        self.view.graph.edited = True
        self.view.update()
        self.focus_position = fcp - 1
    elif key in keybindings['move-node-down']:
      sel = self.view.graph[self.view.selection]
      fcp = self.focus_position
      if fcp < len(sel.links):
        link = sel.links[fcp]
        nextLink = sel.links[fcp + 1]
        sel.links[fcp] = nextLink
        sel.links[fcp + 1] = link
        self.view.graph.edited = True
        self.view.update()
        self.focus_position = fcp + 1
    elif key in keybindings['new-node']:
      self.view.recordChanges(markEdited=False)
      node = self.view.graph.newNode()
      self.view.graph[self.view.selection].links.append(node.nodeId)
      self.view.selection = node.nodeId
      self.view.graph.edited = True
      self.view.update()
      self.view.focus_item = self.view.currentNodeWidget
    elif key in ['left']:
      self.view.focus_item = self.view.backlinks
    elif key in keybindings['link-or-back-link-last-stack-item']:
      if self.view.clipboard.nodes:
        try:
          fcp = self.focus_position
        except IndexError:
          fcp = -1
        node = self.view.clipboard.nodes.pop()
        self.view.graph[self.view.selection].links.insert(fcp + 1,node.nodeId)
        self.view.graph.edited = True
        self.view.update()
        self.focus_position = fcp + 1
    elif key in keybindings['remove-link-or-backlink']:
      try:
        fcp = self.focus_position
        node = self.nodes[fcp]
        selectedNode = self.view.graph[self.view.selection]
        selectedNode.links.remove(node.nodeId)
        self.view.graph.edited = True
        self.view.update()
      except IndexError:
        pass
    else:
      return super(LinksList,self).keypress(size,key)

class CommandBar(urwid.Filler):
  def __init__(self,view):
    self.view = view
    self.edit = urwid.Edit(":")
    super(CommandBar,self).__init__(self.edit)

  def keypress(self,size,key):
    if key != 'enter':
      return super(CommandBar,self).keypress(size,key)
    com = self.edit.edit_text
    if "w" in com:
      try:
        self.view.recordChanges()
        self.view.graph.save()
        self.view.graph.edited = False
      except FileNotFoundError as e:
        self.edit.set_caption("Unable to save:"+str(e)+"\n:")
    if "q" in com:
      if self.view.graph.edited and "!" not in com:
        self.edit.set_caption("Not quiting. Save your work first, or use 'q!'\n:")
      else:
        raise urwid.ExitMainLoop()
    self.edit.edit_text = ""

parser = optparse.OptionParser(usage = "stgre FILE",description = "Edit simple text graph file(stgr file) using a simple,fast TUI interface.")
options,args = parser.parse_args(sys.argv[1:])

if not len(args) == 1:
  sys.exit("tg expects to be passed a single file path for editing. Use --help for help.")

graphView = GraphView(TextGraph(args[0]))
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
 'remove-link-or-backlink' : ['d','delete'],
 'move-to-node-zero' : ['.'],
 'jump-to-command-bar' : [':'],
 'jump-to-node-edit-box' : ['esc'],
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
 }
pallet = [('backlink_selected', 'white', 'dark blue')
         ,('link_selected', 'white', 'dark red')
         ,('selection','black','white')
         ,('clipboard','white','dark gray')]

urwid.MainLoop(graphView,pallet).run()
