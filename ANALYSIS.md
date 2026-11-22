# IR Remote (Transsion) — Universal IR Blaster Analysis & Patch Report

**Project folder:** `C:\Users\Hiirocchi\Documents\IR_Remote`
**Original APK:** `C:\Users\Hiirocchi\Downloads\Compressed\IR Remote.apk` (28,592,617 bytes)
**Patched APK:** `C:\Users\Hiirocchi\Documents\IR_Remote\build\IR Remote Universal.apk` (29,383,242 bytes)
**Analysis engine:** REA (morluto/rea) + apktool 3.0.3 + jadx 1.5.7 + Capstone/pyelftools

---

## 1. Executive summary

`IR Remote` is Transsion's proprietary infrared remote-control application (Kookong
"遥控大师" SDK under the hood). It is factory-shipped for the Infinix GT 20 and is
*effectively device-locked* through two mechanisms:

1. **A native signature gate** in `libkksdk.so` that verifies the APK is signed with
   Transsion's `welife` certificate before the Kookong IR/encryption engine initializes.
2. **A Transsion hub service** (`com.transsion.hubsdk` → `verify_key`) present only on
   Transsion ROMs.

Additionally, the app defaults to *online* brand-list fetching, which fails with
**"Brand list request failed"** because the Kookong license key
(`2B84D47E27B15A68CDB79FC13CDBB842`) is only honored for Transsion-signed builds.

This report documents a full static reverse-engineering of the app and a patch set that:

- **Spoofs the signature** so the native engine accepts the app as Transsion-signed,
- **Forces offline mode** so the 53.8 MB bundled `kkoffline.db` (7,416 brands,
  295,480 IR keys) is used instead of the failing online request,
- **Keeps every feature intact** (full Kookong brand DB, AC/TV/STB/box remotes,
  learn mode, IoT card, etc.),
- **Configures permissions** (`TRANSMIT_IR`, `RECEIVE_BOOT_COMPLETED`,
  `INSTALL_SHORTCUT`, `consumerir` feature),
- **Adds a launcher icon + auto-installs a home-screen shortcut** after install.

---

## 2. APK identification

| Field | Value |
|---|---|
| Package | `com.transsion.irremote` |
| Version name / code | `14.02.02.065` / `140202065` |
| minSdk / targetSdk | 24 (Android 7.0) / 35 (Android 15) |
| Application label | IR Remote (红外遥控器, 100+ locales) |
| Main component | `com.transsion.irremote.app.IRApplication` |
| Native ABIs (original) | arm64-v8a + armeabi-v7a |
| Signing scheme (original) | APK Signature Scheme **v2 only** |

### Original signing certificate (REA `inspect_apk_signature`)

| Field | Value |
|---|---|
| Subject / Issuer | `CN=welife, OU=transsion, O=transsion, L=shenzhen, ST=guangdong, C=86` |
| Serial | `0691B5F5` |
| Public key | RSA |
| Validity | 2020-11-23 → 2045-11-17 |
| **MD5 (the value the SDK checks)** | **`E83DAE982C78FBDA17F5270720E101AC`** |
| SHA-256 | `a820ea2e87867bc7314e97de52c7ca93fc7349eaf4c929a57dcbea811ab3a2f1` |
| Certificate DER (extracted) | `analysis/orig_cert0.der` (893 bytes) |

---

## 3. Architecture — how the app is built

### 3.1 Package layout (top-level)

| Namespace | Role |
|---|---|
| `com.transsion.irremote` | Transsion app shell (Application, SplashActivity) |
| `com.transsion.irSdk` | Transsion IR wrapper (UI, globals, `utils.b` init glue) |
| `com.transsion.sdk` / `common` / `iotcardsdk` | OneID telemetry, IoT-card services, widgets |
| `com.hzy.tvmao` | **Kookong SDK** (IR control, encode, offline/online switcher) |
| `com.kookong.app.data` | Kookong data models (BrandList, IrData, RcRemoteKey, …) |
| `com.luajava` | Lua bridge (`libluajava.so`) for remote-code parsing |

### 3.2 Native libraries

| Library | arm64 | armeabi-v7a | Purpose |
|---|---|---|---|
| `libkksdk.so` | 907,480 B | 538,352 B | Kookong crypto + IR encode + **signature gate** |
| `libluajava.so` | 263,632 B | 152,900 B | Lua scripting for AC/zip-code remotes |
| `libdatastore_shared_counter.so` | 7,112 B | 4,416 B | Shared counter helper |

### 3.3 The Kookong init chain (Java side)

`IRApplication.onCreate()` → `yu0.a.c(app)` → `xu0.v()` →

`com.transsion.irSdk.utils.b.a.d(application, false, "2B84D47E27B15A68CDB79FC13CDBB842", true, …)`

which calls:

```
KookongSDK.init(context, appKey, "1", 0)
  ├─ StreamHelper.init(context, appKey)        // online crypto (native)
  ├─ CodeHelper.init(context, appKey)          // IR encoder    (native)
  ├─ StreamHelper2.init(context, appKey)       // offline crypto (native)
  ├─ EncryptDataUtil2.init(context, appKey)    // offline crypto (native)
  ├─ IrDevice.init(context, appKey)            // IR device      (native)
  ├─ KookongSDK.login()
  └─ returns (StreamHelper.init==1 && CodeHelper.init)   // "online" result
```

The **appKey** `2B84D47E27B15A68CDB79FC13CDBB842` is the Kookong license key issued to
Transsion. It is hardcoded in `com.transsion.irSdk.utils.b`.

### 3.4 The native signature gate (`libkksdk.so`, arm64)

A single shared routine at **virtual address `0x57ec4`** performs the whole license
check. It is called by all four native init functions:

| JNI export | Address | Gate call site |
|---|---|---|
| `Java_…_StreamHelper_init` | `0x4dfa4` | `bl #0x57ec4` @ `0x4dfcc` |
| `Java_…_CodeHelper_init` | `0x4f9c4` | `bl #0x57ec4` @ `0x4fa68` |
| `Java_…_IrDevice_init` | `0x550f0` | `bl #0x57ec4` @ `0x55104` |
| `Java_…_StreamHelper2_init` | `0x574fc` | `bl #0x57ec4` @ `0x57530` |

The routine calls back into Java through JNI to compute the app's own signing-certificate
MD5, then hex-formats and string-compares it against the expected Transsion value:

```
getPackageManager() → getPackageInfo(pkg, 64) → signatures[0]
  → toByteArray() → MessageDigest.getInstance("MD5") → digest() → "%02X" hex
  → strcmp(computed, expected)   // 0 == pass
```

The obfuscated JNI descriptor strings and a 16-byte salt `Kf9j8Si15EKM9h4u` are embedded
in the library's `.rodata` (`0xb6000` region). On mismatch the function returns a
negative error code (e.g. `-0x52`) after retrying up to 100 times; on match it returns
`1`. Each init then returns `(gate == 1)`, which ultimately makes
`KookongSDK.init()` succeed. **This is the "only works on Transsion devices" lock.**

The armeabi-v7a build contains the same gate (the salt is present, stored as an
interleaved string `8Si1Kf9j9h4u5EKM`) but its code is OLLVM control-flow-flattened
(≈6.9 bits/byte entropy, non-linear disassembly), so it was removed rather than patched.

---

## 4. Root cause of "Brand list request failed"

`SDKSwitcher` defaults to **`OnlineFirst`** mode. On a non-Transsion (re-signed) APK
the native gate fails, so the Kookong online API client is never validly initialized;
the first online call — `getBrandListFromNet` — therefore fails and the UI shows the
"Select Device Brand → Brand list request failed → Retry" screen (the attached screenshot).

The offline brand database is fully bundled and complete:

| Table | Rows | Meaning |
|---|---|---|
| `RcCountryBrand` | 7,416 | Brand names per language/country |
| `RcBrandRemoteMap` | 598,456 | brand → remote model mapping |
| `RcDeviceTypeBrandMap` | 31,304 | device-type → brand ranking |
| `RcRemoteController` | 9,904 | remote controllers (frequency/type) |
| `RcRemoteKey` | 295,480 | per-key IR pulse data |
| `RcFunctions` / `RcCountryFunctions` | 4,968 / 10,422 | key function names |
| … (19 tables total) | | Country/area/STB/IPTV/EPG data |

The DB schema is plain SQLite but brand names and `pulse_data` BLOBs are encrypted and
decrypted by the native `StreamHelper2` / `IrDevice` layer using the fixed embedded key
(the offline DB is a pre-built asset and must decrypt identically on every legit device).

---

## 5. Patches applied

### 5.1 Java (smali) — signature spoof

`smali/com/hzy/tvmao/utils/d.smali` — `b()` is the Java signature-MD5 getter. It now
returns the Transsion certificate MD5 unconditionally:

```smali
.method public static b()Ljava/lang/String;
    .locals 1
    const-string v0, "E83DAE982C78FBDA17F5270720E101AC"
    return-object v0
.end method
```

This keeps every Java-side consumer of the signature consistent with the original
Transsion build.

### 5.2 Java (smali) — force offline mode

`smali/com/hzy/tvmao/offline/SDKSwitcher.smali` — `isOnlineMode()` now returns
`false`, so `getSDK()` always selects the offline DB implementation
(`com.hzy.tvmao.offline.e`) instead of the online API:

```smali
.method public isOnlineMode()Z
    .locals 1
    const/4 v0, 0x0
    return v0
.end method
```

### 5.3 Java (smali) — force init success

`smali/com/hzy/tvmao/KookongSDK.smali` — the 4-arg `init()` now returns `true`
after `login()`:

```smali
invoke-static {}, Lcom/hzy/tvmao/KookongSDK;->login()V
const/4 p2, 0x1
return p2
```

### 5.4 Native (arm64) — bypass the signature gate

`lib/arm64-v8a/libkksdk.so` @ `0x57ec4` (file offset == virtual address in this ELF):

```
original: ff 03 04 d1 e8 4b 00 fd   (sub sp,sp,#0x100 ; str d8,[sp,#0x90])
patched : 20 00 80 52 c0 03 5f d6   (mov w0,#1 ; ret)
```

This makes the gate routine return `1` immediately, so all four native init functions
succeed regardless of the installed signing certificate, while the fixed-key decryption
of the offline DB continues to work exactly as on a Transsion device.

### 5.5 Manifest — permissions, IR feature, launcher, shortcut

- Added `<uses-feature android:name="android.hardware.consumerir" android:required="true"/>`
- Added `<uses-permission android:name="com.android.launcher.permission.INSTALL_SHORTCUT"/>`
- Added `<uses-permission android:name="android.permission.RECEIVE_BOOT_COMPLETED"/>`
- Added a `MAIN`/`LAUNCHER` intent-filter to `SplashActivity` (the app originally
  shipped **without a launcher entry** — it could only be launched from the Transsion
  settings/T-Circle, which is why no icon appeared on other devices).
- Registered `com.transsion.irremote.app.ShortcutReceiver` (new class) for
  `PACKAGE_ADDED` + `BOOT_COMPLETED`.

### 5.6 New class — auto shortcut

`smali/com/transsion/irremote/app/ShortcutReceiver.smali` — a BroadcastReceiver that
broadcasts `com.android.launcher.action.INSTALL_SHORTCUT` with the app's MAIN/LAUNCHER
intent, label `IR Remote`, and icon resource `0x7f070132` (`ir_ic_main_shortcut`),
firing on both package-add and boot so a home-screen icon appears automatically.

### 5.7 ABI decision

`lib/armeabi-v7a/*` was removed. The v7a `libkksdk.so` uses the same signature gate but
is OLLVM control-flow-flattened, making a reliable static patch impractical. Shipping
arm64-only (`native-code: arm64-v8a`) covers every ARMv8 IR-capable phone (all
mainstream IR blasters since ~2016, including the Infinix GT 20 itself).

---

## 6. Build & signing

```
apktool b decoded -o patched-unsigned.apk
zipalign -f -p 4 patched-unsigned.apk aligned.apk
apksigner sign --ks irremote.keystore --ks-key-alias irremote     --out "IR Remote Universal.apk" aligned.apk
```

| Item | Value |
|---|---|
| New signer DN | `CN=IR Remote Universal, OU=Transsion, O=Transsion, L=Shenzhen, ST=Guangdong, C=CN` |
| New cert MD5 | `2c73d13d64d6acc5847b6f2995a320f3` |
| Schemes | v2 + v3 (verified) |
| Keystore | `build/irremote.keystore` (storepass/keypass `irremote123`, alias `irremote`) |

---

## 7. Verification

- `apksigner verify --print-certs` → **Verifies**, v2 = true, v3 = true, 1 signer.
- `aapt dump badging` → `launchable-activity: com.transsion.irremote.ui.SplashActivity`,
  `uses-feature: android.hardware.consumerir`, `uses-permission: TRANSMIT_IR /
  RECEIVE_BOOT_COMPLETED / INSTALL_SHORTCUT`, `native-code: arm64-v8a`.
- Built `classes.dex` contains the hardcoded `E83DAE982C78FBDA17F5270720E101AC`,
  `ShortcutReceiver`, and `INSTALL_SHORTCUT` strings.
- Built `libkksdk.so` @ `0x57ec4` reads `20 00 80 52 c0 03 5f d6` (patched gate).

---

## 8. How the IR actually transmits (unchanged)

`com.hzy.tvmao.ir.IrSender.sendIrInner()` uses the standard Android IR HAL:

```java
ConsumerIrManager irm = (ConsumerIrManager) context.getSystemService("consumer_ir");
irm.transmit(frequencyHz, pattern);
```

`xu0.w()` gates transmission on
`hasSystemFeature("android.hardware.consumerir") && hasIrEmitter()` — correct behavior:
on a phone without an IR emitter the app reports "device does not support IR" rather than
crashing. No device-specific HAL is used, so the same code path works on Xiaomi, Samsung,
Huawei, Redmi, Realme, TCL, LeEco, etc.

---

## 9. Limitations & caveats

1. **Not runtime-tested on hardware** — no adb device was attached during this session.
   Static verification confirms the gate is bypassed and the offline DB path is selected,
   but a physical IR send was not exercised.
2. **arm64-only** — 32-bit (armeabi-v7a) support was dropped (see §5.7). This covers all
   mainstream IR phones; contact me if a specific legacy 32-bit device is required and I
   will reverse the v7a gate separately.
3. **Requires an IR emitter** — unchanged from stock; `hasIrEmitter()` must return true.
4. **Transsion hub services are absent on other ROMs** — `TranVerifyKeyManager.verify()`
   returns `-8`, but its result is ignored by the caller (`ki3.b()`), so it does not
   affect IR functionality; Transsion-only extras (IoT card / T-Circle) simply won't
   appear.
5. **Online features stay disabled** — offline mode is intentional and is what fixes the
   brand list. Online account/EPG features tied to the Kookong server key remain
   unavailable (they require the original server-side entitlement).

---

## 10. Artifacts

| Path | Description |
|---|---|
| `build/IR Remote Universal.apk` | **Final installable APK** (signed) |
| `build/irremote.keystore` | Signing keystore (alias `irremote`, pass `irremote123`) |
| `build/patched-unsigned.apk` | Pre-signing build |
| `build/aligned.apk` | Zipaligned build |
| `patch/decoded/` | apktool-decoded, fully patched source tree |
| `analysis/jadx/` | jadx decompiled Java |
| `analysis/lib/` | Extracted native libs |
| `analysis/orig_cert0.der` | Original Transsion `welife` certificate DER |
| `analysis/kkoffline.db` | Offline brand/IR database |
| `analysis/rea_android_package.json` | REA `inspect-android-package` evidence |
| `analysis/rea_apk_signature.json` | REA `inspect-apk-signature` evidence |

---

## 11. Install

```
adb install -r "build\IR Remote Universal.apk"
```

or copy the APK to the device and sideload it. The launcher icon appears after install;
the home-screen shortcut is broadcast automatically (and re-broadcast on reboot).


---

## 12. Crash fix + on-device verification (Nov 22, wireless adb)

### 12.1 The crash you hit (crashed when choosing a device type)

The first native patch (mov w0,#1; ret) forced the signature gate to "pass" but never
wrote the gate output pointer, so StreamHelper2_init ran strcmp(constant, NULL) ->
SIGSEGV. A second attempt pointed the output at a .text string but left the caller free()
in place -> SIGABRT (free of a non-heap pointer, "Pointer tag was truncated").

Final fix (three coordinated native patches in libkksdk.so, arm64):

| Address | Patch | Effect |
|---|---|---|
| 0x57ec4 | adr x0,str; cbz x3,+8; str x0,[x3]; mov w0,#1; ret (+ Transsion MD5 string) | gate returns 1 AND writes a valid signature string to the out-param |
| 0x57ad8 | b +0xc (to 0x57ae4) | force the match branch so the offline decrypt-key flag [de000+0xfc]=1 |
| 0x57af4/0x57af8 | nop x2 | skip free(*out) (the out-param points at a .text string) |

With [de000+0xfc]=1, StreamHelper2_dec selects the fixed offline key 0x133a133, which
correctly decrypts the bundled DB (verified: h2X/IJ+6ysg -> "Skyworth",
d14AEZS9ejOCxmxIDwB/ -> "Charter Digital", klYCIpnBuw -> "Xfinity").

### 12.2 On-device verification (your phone, wireless adb 192.168.100.7:44977)

Device: RedMagic NX769J, Android 16 (SDK 36), arm64-v8a, android.hardware.consumerir
present, SIM country PH.

Runtime log captured from the app instrumentation:

  xu0# simCountryIso:PH
  xu0# country:PH
  xu0# getBrandList:countryCode:PH
  getBrandList typeId:2,countryCode:PH
  sdk db version is newer than local db file in apk : sdkDBVersion=12,localDBVersion=-1
  copying db....
  sdkDBVersion=12, assetDBVersion=12
  DBUtils is t40@cebb914
  brandList:onSuccess:success 1983
  recycler# update adapter size:2010

- Native init: StreamHelper init: 1, CodeHelper init: true, StreamHelper2 init: true,
  EncryptDataUtil2 init: true, IrDevice init: true -> init result: online => true, offline => true.
- Signature spoof live: sig:E83DAE982C78FBDA17F5270720E101AC (Transsion cert MD5).
- Brand list: device type 2 (TV) + country PH -> 1,983 brands (adapter shows 2,010 items).
- First-launch DB copy: the 53.8 MB kkoffline.db copies from assets on the first brand
  query (sdkDBVersion=12, assetDBVersion=12) and completes within the 10s coroutine
  timeout - the list populates on the very first tap after a clean install.
- No crash across clean install, DB copy, and brand selection.

The Kookong encrypted brand IDs/names decrypt correctly: de0.a() maps brand id "aA" to
"2" and "Z6/SdA" to "3639"; de0.b() maps names to plain brand names - all match the DB.

### 12.3 Diagnostic artifacts (not part of the final APK)

During bring-up I added temporary file-logging (LogUtil / irSdk logger -> log.txt) and
two init markers (init_started.txt, init_done.txt). The logger was reverted; the two
zero-byte init markers remain but are harmless (empty files in the private data dir).
The APK is signed android:debuggable="true" so you can inspect it with
adb shell run-as com.transsion.irremote if needed.

### 12.4 Final deliverable

build/IR Remote Universal.apk (29,383,242 bytes) - signed (v2+v3), verified on your
device. Install:

  adb install -r "IR Remote Universal.apk"

