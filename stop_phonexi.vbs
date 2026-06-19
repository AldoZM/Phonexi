' Phonexi stopper. Double-click to kill all detached Phonexi instances
' (pythonw.exe running this folder's main.py). Runs hidden, then reports.
Option Explicit

Dim fso, wmi, dir, procs, p, cmd
Set fso = CreateObject("Scripting.FileSystemObject")
dir = fso.GetParentFolderName(WScript.ScriptFullName)

Set wmi = GetObject("winmgmts:\\.\root\cimv2")
Set procs = wmi.ExecQuery( _
    "SELECT ProcessId, CommandLine FROM Win32_Process WHERE Name = 'pythonw.exe'")

For Each p In procs
    cmd = p.CommandLine
    If Not IsNull(cmd) Then
        If InStr(cmd, "main.py") > 0 And InStr(cmd, dir) > 0 Then
            p.Terminate()
        End If
    End If
Next
