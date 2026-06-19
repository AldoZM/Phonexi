' Phonexi detached launcher.
' Runs main.py with pythonw.exe (no console window) fully detached from any
' terminal. Closing the terminal you launched it from does NOT kill it.
' Double-click this file, or run:  wscript start_phonexi.vbs [args]
'   args are passed through to main.py, e.g.:  wscript start_phonexi.vbs -P
Option Explicit

Dim sh, fso, dir, args, i, extra
Set sh  = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

dir = fso.GetParentFolderName(WScript.ScriptFullName)
sh.CurrentDirectory = dir

' Forward any CLI args (-P, -w) to main.py
extra = ""
For i = 0 To WScript.Arguments.Count - 1
    extra = extra & " " & WScript.Arguments(i)
Next

' Window style 0 = hidden, bWaitOnReturn = False -> launcher exits, child lives on
sh.Run "pythonw.exe " & Chr(34) & dir & "\main.py" & Chr(34) & extra, 0, False
