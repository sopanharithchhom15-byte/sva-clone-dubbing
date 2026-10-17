Set oWS = WScript.CreateObject("WScript.Shell")
sDesktop = oWS.SpecialFolders("Desktop")
sCurrentDir = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)

sShortcutPath = sDesktop & "\SVA Clone Dubbing.lnk"
Set oLink = oWS.CreateShortcut(sShortcutPath)
oLink.TargetPath = "wscript.exe"
oLink.Arguments = """" & sCurrentDir & "\START_PC_APP_SILENT.vbs"""
oLink.WorkingDirectory = sCurrentDir
oLink.IconLocation = sCurrentDir & "\app_icon.ico,0"
oLink.Description = "SVA Clone Dubbing - AI Studio"
oLink.Save

WScript.Echo "Shortcut Created: " & sShortcutPath
