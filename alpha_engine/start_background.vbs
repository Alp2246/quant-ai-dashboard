' Alpha Engine - gizli arka plan baslatici (pencere acilmaz)
' Cift tikla -> sessizce calisir, Telegram'a push gelir
' Durdurmak icin Task Manager > python.exe (alpha_engine cwd'li olan)

Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
proj = fso.GetParentFolderName(WScript.ScriptFullName)
venv = fso.BuildPath(fso.GetParentFolderName(proj), "venv\Scripts\pythonw.exe")
If Not fso.FileExists(venv) Then
    venv = fso.BuildPath(fso.GetParentFolderName(proj), "venv\Scripts\python.exe")
End If
cmd = """" & venv & """ """ & fso.BuildPath(proj, "main.py") & """"
sh.CurrentDirectory = proj
sh.Run cmd, 0, False  ' 0 = pencere gizli, False = bekleme
