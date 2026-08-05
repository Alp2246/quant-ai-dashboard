' Quant AI Dashboard — panel (port 8501), arka planda baslat, pencere yok.
'
' start_dashboard.bat'tan FARKI: o dosya eski instance'i OLDURUP yeniden
' baslatir (Tailscale Funnel'i da kurar). Bu dosya yalnizca arayuzu acar:
' calisiyorsa dokunmaz. Telefon erisimi / Funnel gerekiyorsa
' start_dashboard.bat kullanilmali.

Option Explicit
Dim sh, fso, dir, st, i

Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
dir = fso.GetParentFolderName(WScript.ScriptFullName)
sh.CurrentDirectory = dir

st = fso.BuildPath(dir, "venv\Scripts\streamlit.exe")

If Not PortListening(8501) Then
  If Not fso.FileExists(st) Then
    sh.Popup "venv bulunamadi: " & st & vbCrLf & _
             "Once setup.ps1 calistirin.", 8, "Quant AI Dashboard", 48
    WScript.Quit 1
  End If
  sh.Run """" & st & """ run app.py --server.port 8501 --server.headless true " & _
         "--server.runOnSave false --server.fileWatcherType none " & _
         "--browser.gatherUsageStats false", 0, False
  ' Streamlit ilk acilista yavas — 60 saniyeye kadar bekle
  For i = 1 To 120
    WScript.Sleep 500
    If PortListening(8501) Then Exit For
  Next
End If

sh.Run "http://localhost:8501", 1, False

Function PortListening(port)
  Dim oExec, out
  On Error Resume Next
  ' ReadAll ONCE gelmeli: "Status = 0 iken bekle" boru arabellegi dolunca
  ' kilitlenir (cocuk surec yazamaz, biz Status'u bekleriz).
  Set oExec = sh.Exec("cmd /c netstat -ano | findstr "":" & port & """ | findstr LISTENING")
  out = oExec.StdOut.ReadAll
  PortListening = (Len(Trim(out)) > 0)
  On Error GoTo 0
End Function
