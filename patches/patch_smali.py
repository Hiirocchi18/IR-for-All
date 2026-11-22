#!/usr/bin/env python3
"""Apply the Java (smali) and manifest patches to an apktool-decoded tree.

Run AFTER apktool decode:

    java -jar apktool.jar d IR-Remote.apk -o decoded
    python patch_smali.py decoded

Patches applied:
  1. com/hzy/tvmao/utils/d.smali           -> b() returns the Transsion cert MD5
  2. com/hzy/tvmao/offline/SDKSwitcher.smali -> isOnlineMode() returns false
  3. com/hzy/tvmao/KookongSDK.smali        -> init() returns true
  4. AndroidManifest.xml                    -> launcher, permissions, feature,
                                              ShortcutReceiver registration
  5. New class: com/transsion/irremote/app/ShortcutReceiver.smali
"""
import os
import re
import sys

TRANSION_MD5 = "E83DAE982C78FBDA17F5270720E101AC"


def read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def write(path, s):
    with open(path, "w", encoding="utf-8") as f:
        f.write(s)


def replace_method(s, sig, body):
    pat = re.compile(re.escape(sig) + r".*?\.end method", re.S)
    new, n = pat.subn(body + "\n.end method", s, count=1)
    if n != 1:
        raise SystemExit("FAILED to match method: " + sig)
    return new


def patch_decoded(root):
    smali = os.path.join(root, "smali")

    d = os.path.join(smali, "com", "hzy", "tvmao", "utils", "d.smali")
    s = read(d)
    s = replace_method(
        s,
        ".method public static b()Ljava/lang/String;",
        '.method public static b()Ljava/lang/String;\n    .locals 1\n\n    const-string v0, "%s"\n\n    return-object v0' % TRANSION_MD5,
    )
    write(d, s)
    print("patched d.smali b()")

    sw = os.path.join(smali, "com", "hzy", "tvmao", "offline", "SDKSwitcher.smali")
    s = read(sw)
    s = replace_method(
        s,
        ".method public isOnlineMode()Z",
        '.method public isOnlineMode()Z\n    .locals 1\n\n    const/4 v0, 0x0\n\n    return v0',
    )
    write(sw, s)
    print("patched SDKSwitcher.isOnlineMode()")

    k = os.path.join(smali, "com", "hzy", "tvmao", "KookongSDK.smali")
    s = read(k)
    old = "invoke-static {}, Lcom/hzy/tvmao/KookongSDK;->login()V\n\n    return p2"
    new = "invoke-static {}, Lcom/hzy/tvmao/KookongSDK;->login()V\n\n    const/4 p2, 0x1\n\n    return p2"
    if old not in s:
        raise SystemExit("FAILED to match KookongSDK.init() tail")
    s = s.replace(old, new, 1)
    write(k, s)
    print("patched KookongSDK.init()")

    mf = os.path.join(root, "AndroidManifest.xml")
    m = read(mf)

    anchor = '<uses-permission android:name="android.permission.WAKE_LOCK"/>'
    if anchor in m:
        m = m.replace(
            anchor,
            anchor
            + '\n    <uses-feature android:name="android.hardware.consumerir" android:required="true"/>'
            + '\n    <uses-permission android:name="com.android.launcher.permission.INSTALL_SHORTCUT"/>'
            + '\n    <uses-permission android:name="android.permission.RECEIVE_BOOT_COMPLETED"/>',
            1,
        )

    splash = '<activity android:exported="true" android:label="@string/ir_remote" android:name="com.transsion.irremote.ui.SplashActivity"'
    if splash in m:
        m = m.replace(
            splash + ' android:theme="@style/Theme.CustomSplashScreen"/>',
            splash
            + ' android:theme="@style/Theme.CustomSplashScreen">\n            <intent-filter>\n                <action android:name="android.intent.action.MAIN"/>\n                <category android:name="android.intent.category.LAUNCHER"/>\n            </intent-filter>\n        </activity>',
            1,
        )

    receiver = (
        '        <receiver android:name="com.transsion.irremote.app.ShortcutReceiver" '
        'android:enabled="true" android:exported="false">\n'
        '            <intent-filter>\n'
        '                <action android:name="android.intent.action.PACKAGE_ADDED"/>\n'
        '                <action android:name="android.intent.action.BOOT_COMPLETED"/>\n'
        '                <data android:scheme="package"/>\n'
        '            </intent-filter>\n'
        '        </receiver>\n'
    )
    if "</application>" in m:
        m = m.replace("</application>", receiver + "    </application>", 1)

    write(mf, m)
    print("patched AndroidManifest.xml")

    recv_path = os.path.join(smali, "com", "transsion", "irremote", "app", "ShortcutReceiver.smali")
    os.makedirs(os.path.dirname(recv_path), exist_ok=True)
    write(recv_path, SHORTCUT_RECEIVER)
    print("wrote ShortcutReceiver.smali")


SHORTCUT_RECEIVER = '''.class public Lcom/transsion/irremote/app/ShortcutReceiver;
.super Landroid/content/BroadcastReceiver;
.source "ShortcutReceiver.java"


# direct methods
.method public constructor <init>()V
    .locals 0

    invoke-direct {p0}, Landroid/content/BroadcastReceiver;-><init>()V

    return-void
.end method

.method private a(Landroid/content/Context;)V
    .locals 6

    new-instance v0, Landroid/content/Intent;

    const-class v1, Lcom/transsion/irremote/ui/SplashActivity;

    invoke-direct {v0, p1, v1}, Landroid/content/Intent;-><init>(Landroid/content/Context;Ljava/lang/Class;)V

    const-string v1, "android.intent.action.MAIN"

    invoke-virtual {v0, v1}, Landroid/content/Intent;->setAction(Ljava/lang/String;)Landroid/content/Intent;

    const-string v1, "android.intent.category.LAUNCHER"

    invoke-virtual {v0, v1}, Landroid/content/Intent;->addCategory(Ljava/lang/String;)Landroid/content/Intent;

    new-instance v1, Landroid/content/Intent;

    invoke-direct {v1}, Landroid/content/Intent;-><init>()V

    const-string v2, "android.intent.extra.shortcut.INTENT"

    invoke-virtual {v1, v2, v0}, Landroid/content/Intent;->putExtra(Ljava/lang/String;Landroid/os/Parcelable;)Landroid/content/Intent;

    const-string v2, "android.intent.extra.shortcut.NAME"

    const-string v3, "IR Remote"

    invoke-virtual {v1, v2, v3}, Landroid/content/Intent;->putExtra(Ljava/lang/String;Ljava/lang/String;)Landroid/content/Intent;

    const-string v2, "android.intent.extra.shortcut.ICON_RESOURCE"

    const v3, 0x7f070132

    invoke-static {p1, v3}, Landroid/content/Intent$ShortcutIconResource;->fromContext(Landroid/content/Context;I)Landroid/content/Intent$ShortcutIconResource;

    move-result-object v3

    invoke-virtual {v1, v2, v3}, Landroid/content/Intent;->putExtra(Ljava/lang/String;Landroid/os/Parcelable;)Landroid/content/Intent;

    const-string v2, "com.android.launcher.action.INSTALL_SHORTCUT"

    invoke-virtual {v1, v2}, Landroid/content/Intent;->setAction(Ljava/lang/String;)Landroid/content/Intent;

    invoke-virtual {p1, v1}, Landroid/content/Context;->sendBroadcast(Landroid/content/Intent;)V

    return-void
.end method


# virtual methods
.method public onReceive(Landroid/content/Context;Landroid/content/Intent;)V
    .locals 3

    invoke-virtual {p2}, Landroid/content/Intent;->getAction()Ljava/lang/String;

    move-result-object v0

    const-string v1, "android.intent.action.BOOT_COMPLETED"

    invoke-virtual {v1, v0}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z

    move-result v1

    if-eqz v1, :cond_1

    :cond_0
    invoke-direct {p0, p1}, Lcom/transsion/irremote/app/ShortcutReceiver;->a(Landroid/content/Context;)V

    return-void

    :cond_1
    const-string v1, "android.intent.action.PACKAGE_ADDED"

    invoke-virtual {v1, v0}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z

    move-result v0

    if-nez v0, :cond_0

    return-void
.end method
'''


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: python patch_smali.py <decoded-dir>")
        sys.exit(1)
    patch_decoded(sys.argv[1])
