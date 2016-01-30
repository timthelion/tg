#!/usr/bin/python3

import sys
import json
import optparse
try:
  import urwid
except ImportError:
  sys.exit("The urwid TUI toolkit is required to run this program. On debian based systems you need to install python3-urwid. On other systems you'll have to search the web.")

class Node():
  def __init__(self,nodeId,text,links):
    self.nodeId = nodeId
    self.text = text
    self.links = links

class TextGraph(list):
  def __init__(self,fileName):
    self.fileName = fileName
    self.edited = False
    self.orphans = []
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
      if self.isOrphan(node):
        self.orphans.append(node.nodeId)

  def getBacklinks(self,nodeId):
    backlinks = []
    for node in self:
      if nodeId in node.links:
        backlinks.append(node)
    return backlinks

  def isOrphan(self,node):
    if not node.links and not self.getBacklinks(node.nodeId):
      return True
    else:
      return False

  def newNode(self):
    if self.orphans:
      index = self.orphans.pop()
    else:
      index = len(self)
    node = Node(index,"",[])
    self[index] = node
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

  @property
  def selection(self):
    return self._selection

  @selection.setter
  def selection(self,value):
    self.history.append(self.selection)
    self._selection = value

  def keypress(self,size,key):
    if key in keybindings["back"]:
      if self.history:
        self._selection = self.history.pop()
        self.update()
    elif key in keybindings['jump-to-command-bar'] and self.focus_item != self.currentNodeWidget:
      self.focus_item = self.commandBar
    elif key in keybindings['jump-to-node-edit-box']:
      self.focus_item = self.currentNodeWidget
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
    if key in [self.alignment,'enter']:
      if self.nodes:
        newText = self.view.currentNode.edit_text
        if self.view.graph[self.view.selection].text != newText:
          self.view.graph[self.view.selection].text = newText
          self.view.graph.edited = True
        self.view.selection = self.nodes[self.focus_position].nodeId
        self.view.update()
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
      self.view.graph[self.view.selection].text = self.view.currentNode.edit_text

      node = self.view.graph.newNode()
      node.links = [self.view.selection]
      self.view.selection = node.nodeId
      self.view.update()
      self.view.focus_item = self.view.currentNodeWidget
    if key in ['right']:
      self.view.focus_item = self.view.links
      self.view.links.focus_position = 0
    if key in keybindings['link-or-back-link-last-stack-item']:
      if self.view.clipboard.nodes:
        node = self.view.clipboard.nodes.pop()
        node.links.append(self.view.selection)
        self.view.graph.edited = True
        self.view.update()
        self.focus_position = self.nodes.index(node)
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
      self.view.graph[self.view.selection].text = self.view.currentNode.edit_text
      node = self.view.graph.newNode()
      self.view.graph[self.view.selection].links.append(node.nodeId)
      self.view.selection = node.nodeId
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
        if self.view.graph.isOrphan(node):
          node.text = ""
          self.view.graph.orphans.append(node.nodeId)
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
        self.view.graph[self.view.selection].text = self.view.currentNode.edit_text
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
 'jump-to-command-bar' : [':'],
 'jump-to-node-edit-box' : ['esc'],
 'move-up-one-mega-widget' : ['meta up'],
 'move-down-one-mega-widget' : ['meta down'],
 }
pallet = [('backlink_selected', 'white', 'dark blue')
         ,('link_selected', 'white', 'dark red')
         ,('selection','black','white')
         ,('clipboard','white','dark gray')]

urwid.MainLoop(graphView,pallet).run()
