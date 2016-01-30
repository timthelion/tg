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
  def __init__(self,fileText):
    self.fileText = fileText
    self.edited = False
    nodeId = 0
    with open(fileText) as fd:
      try:
        table = json.load(fd)
      except ValueError as e:
        print("Cannot load file "+fileText)
        sys.exit(str(e))
      for (text,links) in table:
        self.append(Node(nodeId,text,links))
        nodeId += 1

  def getBacklinks(self,nodeId):
    backlinks = []
    for node in self:
      if nodeId in node.links:
        backlinks.append(node)
    return backlinks

  def save(self):
    # We format the output to privide better diff support.
    serialized = "["
    for node in self:
      serialized += json.dumps([node.text,node.links])
      serialized += "\n,"
    serialized = serialized[:-2] + "]\n"
    with open(self.fileText,"w") as fd:
      fd.write(serialized)

class GraphView():
  def __init__(self,graph):
    self.graph = graph
    self.selection = 0
    self.pallet = [('backlink_selected', 'white', 'dark blue')
                  ,('link_selected', 'white', 'dark red')
                  ,('selection','black','white')
                  ,('clipboard','white','dark gray')]
    # clipboard
    self.clipboard = Clipboard(self)
    # backlinks
    self.backlinks = BackLinksList(self)
    # current node
    self.currentNode = urwid.Edit(edit_text="",align="center",multiline=True)
    self.currentNodeWidget = urwid.AttrMap(self.currentNode,None,"selection")
    # links
    self.links = LinksList(self)
    # command bar
    self.commandBar = CommandBar(self)
    # main pile
    self.mainPile = urwid.Pile([self.clipboard,self.backlinks,urwid.Filler(self.currentNodeWidget),self.links,self.commandBar])
    self.update()

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

  def show(self):
    urwid.MainLoop(self.mainPile,self.pallet).run()

class NodeList(urwid.ListBox):
  def __init__(self,selectionCollor,alignment):
    self.selectionCollor = selectionCollor
    self.alignment = alignment
    self.nodes = []
    super(NodeList,self).__init__(urwid.SimpleFocusListWalker([]))

  def update(self,nodes=None):
    if nodes:
      self.nodes = nodes
    items = []
    for node in self.nodes:
      title = node.text.splitlines()[0]
      items.append(urwid.AttrMap(urwid.Padding(urwid.SelectableIcon(title,0),align=self.alignment,width="pack"),None,self.selectionCollor))
    self.body.clear()
    self.body.extend(items)

class Clipboard(NodeList):
  def __init__(self,view):
    self.view = view
    super(Clipboard,self).__init__("clipboard","right")

  def keypress(self,size,key):
    if key == 'd':
      fcp = self.focus_position
      del self.nodes[fcp]
      self.update()
      if fcp < len(self.nodes):
        self.focus_position = fcp
    if key == 'right' or key == 'ctrl right':
      node = self.nodes[self.focus_position]
      if not key == 'ctrl right':
        del self.nodes[self.focus_position]
      self.view.graph[self.view.selection].links.append(node.nodeId)
      self.view.graph.edited = True
      self.view.update()
    if key == 'left' or key == 'ctrl left':
      node = self.nodes[self.focus_position]
      if not key == 'ctrl left':
        del self.nodes[self.focus_position]
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
    if key == self.alignment:
      newText = self.view.currentNode.edit_text
      if self.view.graph[self.view.selection].text != newText:
        self.view.graph[self.view.selection].text = newText
        self.view.graph.edited = True
      self.view.selection = self.nodes[self.focus_position].nodeId
      self.view.update()
    if key == 'c':
      self.view.clipboard.nodes.append(self.nodes[self.focus_position])
      self.view.update()
    else:
      return super(NodeNavigator,self).keypress(size,key)

class BackLinksList(NodeNavigator):
  def __init__(self,view):
    self.view = view
    super(BackLinksList,self).__init__(view,'backlink_selected','left')

class LinksList(NodeNavigator):
  def __init__(self,view):
    self.view = view
    super(LinksList,self).__init__(view,'link_selected','right')

  def keypress(self,size,key):
    if key == 'ctrl up':
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
    elif key == 'ctrl down':
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
      self.view.graph.save()
      self.view.graph.edited = False
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
graphView.show()
