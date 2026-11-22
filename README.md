# IR for All

**Universal IR remote for any Android device with an IR blaster.**

A repackaged, unlocked build of Transsion's *IR Remote* (`com.transsion.irremote`, v14.02.02.065) — a factory system app on the Infinix GT 20 and other Transsion devices. This build removes the device lock and runs on **any** Android phone with a consumer IR emitter (Xiaomi, Samsung, Huawei, Redmi, Realme, TCL, LeEco, and others).

> ⚠️ **Disclaimer:** The original app is Transsion's proprietary software. This repository distributes only the patch tooling (MIT-licensed) and a repackaged APK for interoperability and personal use. All original code, trademarks, and the Kookong IR database remain the property of their respective owners. This project is not affiliated with, endorsed by, or sponsored by Transsion or Kookong.

---

## Install

Download `IR Remote Universal.apk` from the latest [release](../../releases) and install:

```
adb install -r "IR Remote Universal.apk"
```

The launcher icon appears immediately; a home-screen shortcut is broadcast on install and on every reboot.

**Requirements:** a device with a real IR emitter (`ConsumerIrManager.hasIrEmitter()`), Android 7.0+ (API 24), arm64-v8a.
```
# 1. decode
java -jar apktool.jar d IR-Remote.apk -o decoded

# 2. patch the native gate
python patches/patch_libkksdk.py decoded/lib/arm64-v8a/libkksdk.so

# 3. patch smali + manifest
python patches/patch_smali.py decoded

# 4. drop the obfuscated 32-bit ABI
rm -rf decoded/lib/armeabi-v7a

# 5. rebuild + sign
java -jar apktool.jar b decoded -o patched-unsigned.apk
zipalign -f -p 4 patched-unsigned.apk aligned.apk
apksigner sign --ks your.keystore --out "IR Remote Universal.apk" aligned.apk
```

## License

The patch tooling in this repository is MIT licensed (see [LICENSE](LICENSE)). The repackaged APK is a derivative of Transsion's proprietary software and is provided for personal/interoperability use only.
