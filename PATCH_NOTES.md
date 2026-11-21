# IR Remote – universal build

Patched from `com.transsion.irremote` v14.02.02.065 (Infinix GT 20 system app).

## Why it was GT 20-only
- No `MAIN/LAUNCHER` activity (`meta-data icon=invisible`): only Transsion system UI could start it.
- Direct hidden-API call (`android.os.SystemProperties`, `vz1.<clinit>`) – fine for a system app, crashes-prone for a user-installed one.
- Vendor-only permissions/services; Transsion `hubsdk` classes (already has AOSP fallbacks via `vi3`/THubCore).
- The IR check itself (`consumer_ir` + `hasIrEmitter()`) was already generic.

## Changes
- Manifest: `SplashActivity` is now the launcher entry (icon appears right after install) + static long-press shortcut (`res/xml/shortcuts.xml`).
- Manifest: `uses-feature android.hardware.consumerir` (required), `INSTALL_SHORTCUT` permission; removed Transsion-only permissions (`MULCOOPERATE_PROXIMITY`, `dataservice.READ/WRITE`) and GSF `READ_GSERVICES`.
- `SplashActivity.F()`: on first launch asks the launcher to pin a home-screen shortcut using the app's own `kh3.b()` (API 26+); legacy `INSTALL_SHORTCUT` broadcast on API 24-25. Runs once.
- `vz1.<clinit>`: hidden-API call wrapped in try/catch (default `true`).
- Resources: restored enum symbols in `attrs.xml` so aapt2 could relink (values unchanged).
- Re-signed with a new key (v2/v3), zipalign 16 KB, libs uncompressed.

## Install notes
- Signature differs from the original: uninstall/disable the stock copy first (on the GT 20 it is a system app).
- Android cannot add a home shortcut silently; the launcher shows a one-time confirmation.
- Not tested on hardware.
