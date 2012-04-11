#!/usr/bin/python
# -*- coding: utf-8 -*-

import os
import wx
from TextCtrlAutoComplete import TextCtrlAutoComplete
import datetime
import time

LOCAL = False

if LOCAL:
    import functions as client

else:
    from rpcclient import rpcClient
    client = rpcClient()
        
class main:
    def __init__(self):
        args = dict()
        self.dynamic_choices = client.getActivities().result
        args["choices"] = self.dynamic_choices        
        if len(args["choices"]) ==0:
            args["choices"].append("No activities")
            
        app = wx.PySimpleApp()
        self.frame = wx.Frame(None,-1,"Timetracker - [idle]",style=wx.TAB_TRAVERSAL|wx.DEFAULT_FRAME_STYLE)
#        _icon = wx.EmptyIcon()
#        _icon.CopyFromBitmap(wx.Bitmap("timetracker.ico", wx.BITMAP_TYPE_ICO))
#        self.frame.SetIcon(_icon)
        self.frame.SetIcon(wx.Icon("timetracker.ico", wx.BITMAP_TYPE_ICO))
        
        panel = wx.Panel(self.frame)
        sizer = wx.BoxSizer(wx.VERTICAL)

        font1 = wx.Font(14, wx.SWISS, wx.NORMAL, wx.BOLD, False, u'Tahoma')
        font2 = wx.Font(12, wx.SWISS, wx.NORMAL, wx.NORMAL, False, u'Tahoma')
        self._ctrl = TextCtrlAutoComplete(panel, **args)
        self._ctrl.SetEntryCallback(self.setDynamicChoices)
        self._ctrl.SetMatchFunction(self.match)
        self._ctrl.SetFont(font1)
        sizer.Add(self._ctrl, 0, wx.EXPAND|wx.ADJUST_MINSIZE, 0)

        il = wx.ImageList(16,16)

        self.fldridx = il.Add(wx.ArtProvider.GetBitmap(wx.ART_FOLDER, wx.ART_OTHER, (16,16)))
        self.fldropenidx = il.Add(wx.ArtProvider.GetBitmap(wx.ART_FILE_OPEN,   wx.ART_OTHER, (16,16)))
        self.fileidx = il.Add(wx.ArtProvider.GetBitmap(wx.ART_NORMAL_FILE, wx.ART_OTHER, (16,16)))

        treesizer = wx.BoxSizer(wx.HORIZONTAL)
        self.tree = wx.TreeCtrl(panel, size=(-1,100), style=wx.TR_DEFAULT_STYLE | wx.TR_EDIT_LABELS | wx.TR_HIDE_ROOT)
        self.tree.AssignImageList(il)
        treesizer.Add(self.tree, 1, wx.EXPAND|wx.ALL, 0)
        sizer.Add(treesizer, 1, wx.EXPAND|wx.ALL, 0)

        buttonsizer = wx.BoxSizer(wx.HORIZONTAL)
        self.but = wx.Button(panel,label="Start")
        self.but.SetFont(font2)
        self.but.Bind(wx.EVT_BUTTON, self.onBtStart)
        self.but2 = wx.Button(panel,label="Stop")
        self.but2.Bind(wx.EVT_BUTTON, self.onBtStop)
        self.but2.Disable()        
        self.but2.SetFont(font2)
        self.butShowLog = wx.Button(panel,label="Show log by activity...")
        self.butShowLog.Bind(wx.EVT_BUTTON, self.onBtShowLog)
        self.butShowLog.SetFont(font2)        
        
        buttonsizer.Add(self.but, 0, wx.EXPAND|wx.ADJUST_MINSIZE, 0)
        buttonsizer.Add(self.but2, 0, wx.EXPAND|wx.ADJUST_MINSIZE, 0)
        buttonsizer.Add(self.butShowLog, 0, wx.EXPAND|wx.ADJUST_MINSIZE, 0)        
        sizer.Add(buttonsizer, 0, wx.EXPAND|wx.ADJUST_MINSIZE, 0)
        
        panel.SetAutoLayout(True)
        panel.SetSizer(sizer)
        sizer.Fit(panel)
        sizer.SetSizeHints(panel)
        panel.Layout()

        self.populate_by_date = True
        self.populateTree(self.populate_by_date)

        app.SetTopWindow(self.frame)
        self.frame.Bind(wx.EVT_TIMER, self.OnTimer)

        status = client.getStatus().result
        if status['name'] != "none":
            self.but.Disable()
            self.but2.Enable()
            ctrl = self._ctrl
            ctrl.Disable()
            ctrl.SetValue(status['name'])
            self.start_time = datetime.datetime(*(time.strptime(status['start'], "%d/%m/%Y %H:%M")[0:5]))
            self.title_format = "Timetracker - %s [%%s]"  % status['name']
        else:        
            self.but.Enable()
            self.but2.Disable()
            ctrl = self._ctrl
            ctrl.Enable()
            self.start_time = datetime.datetime.now()
            self.title_format = "Timetracker - [idle] [%s]"
        
        self.OnTimer(None)
        self.timer = wx.Timer(self.frame, -1)
        # update clock digits every second (1000ms)
        self.timer.Start(1000)        
        
        self.frame.Show()
        self._ctrl.SetFocus()
        app.MainLoop()

    def OnTimer(self, event):
        #get current time from computer
        current = datetime.datetime.now()
        # time string can have characters 0..9, -, period, or space
        ts = current- self.start_time
        self.frame.SetTitle(self.title_format % str(ts).split(".")[0])

    def populateTree(self, by_date=False):
        self.tree.DeleteAllItems()
        self.root = self.tree.AddRoot("Activities")
        self.tree.SetItemImage(self.root, self.fldridx,wx.TreeItemIcon_Normal)
        self.tree.SetItemImage(self.root, self.fldropenidx,wx.TreeItemIcon_Expanded)

        if not by_date:
            logs = client.getLogs().result
        else:
            logs = client.getLogsByDate().result
        for (k, v) in logs.items():
            act = self.tree.AppendItem(self.root, k)
            self.tree.SetItemImage(act, self.fldridx,wx.TreeItemIcon_Normal)
            self.tree.SetItemImage(act, self.fldropenidx,wx.TreeItemIcon_Expanded)
            for (mykey, times) in v.items():
                for (descr, time) in times:
                    item = "%s: %s %s" % (mykey, descr, str(time).split('.')[0])
                    log = self.tree.AppendItem(act, item)
                    self.tree.SetItemImage(log, self.fileidx,wx.TreeItemIcon_Normal)
                
    def onBtStart(self, event):
        self.but.Disable()
        self.but2.Enable()
        ctrl = self._ctrl
        ctrl.Disable()
        text = ctrl.GetValue()
#        self.frame.SetTitle("Timetracker - %s" % text)
        self.start_time = datetime.datetime.now()
        self.title_format = "Timetracker - %s [%%s]"  % text       
        client.startActivity(name=text)
        if text not in self.dynamic_choices:
            self.dynamic_choices.append(text)

    def onBtStop(self, event):
        dlg = wx.TextEntryDialog(self.frame, "Please enter a description",'A question', '') 
        if dlg.ShowModal() == wx.ID_OK: 
            descr = dlg.GetValue()
        else:
            return
        self.but.Enable()
        self.but2.Disable()
        ctrl = self._ctrl
        ctrl.Enable()
        self.start_time = datetime.datetime.now()
        self.title_format = "Timetracker - [idle] [%s]"
#        self.frame.SetTitle("Timetracker - [idle]")
        client.stopActivity(descr=descr)
        self.populateTree(self.populate_by_date)

    def onBtShowLog(self, event):
        self.populate_by_date = not self.populate_by_date
        if not self.populate_by_date:
            self.butShowLog.SetLabel("Show log by date...")
        else:
            self.butShowLog.SetLabel("Show log by activity...")
        self.populateTree(self.populate_by_date)
        
    def match(self, text, choice):
        t = text.lower()
        c = choice.lower()
        return c.startswith(t)

    def setDynamicChoices(self):
        ctrl = self._ctrl
        text = ctrl.GetValue().lower()
        current_choices = ctrl.GetChoices()
        choices = [choice for choice in self.dynamic_choices if self.match(text, choice)]
        if choices != current_choices:
            ctrl.SetChoices(choices)


if __name__ == "__main__":
    main()

