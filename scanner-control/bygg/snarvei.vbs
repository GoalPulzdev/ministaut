' Lager snarvei paa skrivebordet til MinistautControl.exe i mappen over.
Set fso = CreateObject("Scripting.FileSystemObject")
Set sh = CreateObject("WScript.Shell")
dir = fso.GetParentFolderName(fso.GetParentFolderName(WScript.ScriptFullName))
exe = dir & "\MinistautControl.exe"
If Not fso.FileExists(exe) Then
  WScript.Echo "Fant ikke MinistautControl.exe. Kjor 05_BYGG_WINDOWS_APP.bat forst."
  WScript.Quit 2
End If
Set s = sh.CreateShortcut(sh.SpecialFolders("Desktop") & "\Ministaut Scanner Control.lnk")
s.TargetPath = exe : s.WorkingDirectory = dir : s.IconLocation = exe & ",0"
s.Description = "Ministaut Scanner Control" : s.Save
WScript.Echo "Snarvei laget pa skrivebordet: Ministaut Scanner Control"
