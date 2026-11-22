# IR Remote — universal build (patch notes)

Patched from `com.transsion.irremote` v14.02.02.065 (Infinix GT 20 system app).

## Root cause of the Infinix GT 20 lock

1. **Native signature gate** — `libkksdk.so` verifies the APK is signed with
   Transsion's `welife` certificate (MD5 `E83DAE982C78FBDA17F5270720E101AC`).
   All four native init functions call one shared gate routine.
2. **Online-first brand list** — `SDKSwitcher` defaults to `OnlineFirst`, which
   hits Kookong's API with Transsion key `2B84D47E27B15A68CDB79FC13CDBB842`; a
   re-signed build gets rejected ("Brand list request failed").
3. **No launcher entry** — no `MAIN`/`LAUNCHER` activity.

## Changes

### Native (`libkksdk.so`, arm64-v8a)

| Address | Patch | Effect |
|---|---|---|
| `0x57ec4` | write Transsion MD5 to the out-param, return 1 | gate passes AND downstream `strcmp` sees a match |
| `0x57ad8` | force the "matched" branch | sets offline decrypt-key flag `[de000+0xfc]=1` |
| `0x57af4`/`0x57af8` | NOP the `free(*out)` | the out-param is now a static string |

With `[de000+0xfc]=1`, `StreamHelper2_dec` uses fixed key `0x133a133`, which
correctly decrypts the bundled `kkoffline.db`.

### Java (smali)

- `utils.d.b()` → hardcoded Transsion cert MD5.
- `offline.SDKSwitcher.isOnlineMode()` → `false` (offline DB).
- `KookongSDK.init()` → returns `true`.

### Manifest

- `uses-feature android.hardware.consumerir` (required).
- Permissions: `TRANSMIT_IR`, `RECEIVE_BOOT_COMPLETED`, `INSTALL_SHORTCUT`.
- `SplashActivity` gets `MAIN`/`LAUNCHER`.
- New `ShortcutReceiver` (auto home-screen shortcut on install + boot).

### ABI

- `armeabi-v7a` dropped (OLLVM control-flow-flattened gate). arm64 only.

## Install notes

- Signature differs from stock: uninstall/disable the original first (on the GT 20 it
  is a system app).
- Re-signed with a new key (v2/v3), zipaligned, libs uncompressed.

## Verification

On-device (RedMagic NX769J, Android 16, PH): brand list loads (TV = 1,983 brands),
first-launch DB copy completes, no crash. IR transmission not yet hardware-tested.
