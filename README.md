# IR for All

**Universal IR remote for any Android device with an IR blaster.**

A repackaged, unlocked build of Transsion's *IR Remote* (`com.transsion.irremote`, v14.02.02.065) — a factory system app on the Infinix GT 20 and other Transsion devices. This build removes the device lock and runs on **any** Android phone with a consumer IR emitter (Xiaomi, Samsung, Huawei, Redmi, Realme, TCL, LeEco, and others).

> ⚠️ **Disclaimer:** The original app is Transsion's proprietary software. This repository distributes only the patch tooling (MIT-licensed) and a repackaged APK for interoperability and personal use. All original code, trademarks, and the Kookong IR database remain the property of their respective owners. This project is not affiliated with, endorsed by, or sponsored by Transsion or Kookong.

---

## Why the stock app only worked on the Infinix GT 20

1. **Native signature gate** — `libkksdk.so` (the Kookong IR engine) computes the MD5 of the APK's signing certificate and refuses to initialize unless it matches Transsion's `welife` certificate (`E83DAE982C78FBDA17F5270720E101AC`). Any re-signed build fails.
2. **Online-first brand list** — the app defaults to fetching the brand database from Kookong's servers with a Transsion-issued license key (`2B84D47E27B15A68CDB79FC13CDBB842`). On non-Transsion builds the request is rejected, producing **"Brand list request failed"**.
3. **No launcher entry** — the app has no `MAIN`/`LAUNCHER` activity, so only Transsion's system UI could start it; no icon appeared on other devices.

## What this build changes

| Patch | Layer | Effect |
|---|---|---|
| Signature spoof | native (`libkksdk.so`) | gate returns "Transsion-signed" and sets the offline decrypt-key flag |
| Signature spoof | Java (`utils.d`) | `b()` returns the Transsion cert MD5 |
| Force offline | Java (`SDKSwitcher`) | `isOnlineMode()` → `false`, uses the bundled 53.8 MB `kkoffline.db` (7,416 brands / 295,480 IR keys) |
| Force init success | Java (`KookongSDK`) | `init()` → `true` |
| Universal IR | *(already generic)* | stock `ConsumerIrManager.transmit()`, gated only by `hasIrEmitter()` |
| Permissions | manifest | `TRANSMIT_IR`, `RECEIVE_BOOT_COMPLETED`, `INSTALL_SHORTCUT`, `consumerir` feature |
| Launcher entry | manifest | `SplashActivity` gets `MAIN`/`LAUNCHER` |
| Auto shortcut | new `ShortcutReceiver` | home-screen shortcut on install + boot |
| arm64 only | build | dropped `armeabi-v7a` (OLLVM-obfuscated gate) |

## Install

Download `IR Remote Universal.apk` from the latest [release](../../releases) and install:

```
adb install -r "IR Remote Universal.apk"
```

The launcher icon appears immediately; a home-screen shortcut is broadcast on install and on every reboot.

**Requirements:** a device with a real IR emitter (`ConsumerIrManager.hasIrEmitter()`), Android 7.0+ (API 24), arm64-v8a.

## Verified

Tested on-device (RedMagic NX769J, Android 16, PH SIM) over wireless adb:

- ✅ No crash selecting a device type (native gate crash fixed)
- ✅ Brand list loads: TV + PH = **1,983 brands** (adapter shows 2,010 items)
- ✅ First-launch 53.8 MB offline DB copy completes within the coroutine timeout
- ✅ Offline decryption key `0x133a133` confirmed against the bundled DB

Not yet tested: physical IR transmission (no IR receiver attached). The path is stock `ConsumerIrManager.transmit()` and should work on any IR phone.

## How the lock works (technical)

All four native init functions (`StreamHelper.init`, `CodeHelper.init`, `StreamHelper2.init`, `IrDevice.init`) call one shared gate routine at arm64 `0x57ec4`. It calls back into Java to compute the signing cert's MD5 and string-compares it against Transsion's value. On mismatch it fails; the offline decrypt path then selects key `0` instead of `0x133a133`, so even the bundled DB can't be read.

The patch makes the gate **write the Transsion MD5 to its out-param** (so downstream `strcmp` sees a match), forces the "matched" branch (which sets the decrypt-key flag `[de000+0xfc]=1`), and NOPs the `free()` of that now-static string. Full details in [ANALYSIS.md](ANALYSIS.md).

## Reproducing the build

Requirements: apktool 3.x, a JDK, Android SDK build-tools (zipalign + apksigner), Python 3.

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
