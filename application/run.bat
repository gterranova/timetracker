set Path=%Path%;C:\Users\g.terranova\Downloads\android-sdk-windows\platform-tools\
adb push script.py /sdcard/sl4a/scripts/test/

adb push rpcclient.py /sdcard/sl4a/scripts/test
adb push html/template.html /sdcard/sl4a/scripts/test/html
adb push application.zip /sdcard/sl4a/scripts/test
rem adb push js/json2.js /sdcard/sl4a/scripts/test/js

rem adb shell am start -a com.googlecode.android_scripting.action.LAUNCH_BACKGROUND_SCRIPT -n com.googlecode.android_scripting/.activity.ScriptingLayerServiceLauncher -e com.googlecode.android_scripting.extra.SCRIPT_PATH /sdcard/sl4a/scripts/test/script.py
