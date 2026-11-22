# Patches

Two scripts reproduce the universal build from a decoded APK.

## Steps

```
# decode
java -jar apktool.jar d IR-Remote.apk -o decoded

# native gate (libkksdk.so, arm64)
python patches/patch_libkksdk.py decoded/lib/arm64-v8a/libkksdk.so

# smali + manifest
python patches/patch_smali.py decoded

# drop the OLLVM-obfuscated 32-bit ABI
rm -rf decoded/lib/armeabi-v7a

# rebuild + sign
java -jar apktool.jar b decoded -o patched-unsigned.apk
zipalign -f -p 4 patched-unsigned.apk aligned.apk
apksigner sign --ks your.keystore --out "IR Remote Universal.apk" aligned.apk
```

## What each patch does

- **`patch_libkksdk.py`** — bypasses the native signature gate in
  `libkksdk.so`. See the script header for the exact addresses and rationale.
- **`patch_smali.py`** — spoofs the Java signature getter, forces offline mode,
  forces init success, adds a launcher entry + auto-shortcut receiver, and
  configures the manifest.

See [../PATCH_NOTES.md](../PATCH_NOTES.md) for the full change summary and
[../ANALYSIS.md](../ANALYSIS.md) for the reverse-engineering report.
