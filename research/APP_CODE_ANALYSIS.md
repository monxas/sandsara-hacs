# Sandsara APK – App Code Analysis (BLE file transfer)

## Summary
The extracted APK at `/tmp/sandsara_apk` **does not contain any native Flutter AOT libraries** (e.g., `libapp.so`, `libflutter.so`) or Dart snapshots (`kernel_blob.bin`, `isolate_snapshot_data`, `vm_snapshot_data`). As a result, **the actual Dart file‑transfer implementation is not present** in this extraction. Only the Android shell (classes.dex) and assets are available. The classes.dex strings show usage of the **flutter_blue_plus** plugin and standard BLE/GATT error/MTU strings, but **no app‑specific file transfer protocol strings, UUIDs, or chunk size constants** were found in this extraction.

**Implication:** to get the exact file‑transfer logic, we need the split APK that contains `libapp.so` (typically `split_config.arm64_v8a.apk` or similar). Without it, the Dart AOT code is missing.

---

## Findings from `classes.dex`

### 1) BLE plugin used
Found in strings:
- `flutter_blue_plus/methods`
- `Error registering plugin flutter_blue_plus, com.lib.flutter_blue_plus.FlutterBluePlusPlugin`

This indicates the app’s BLE stack is driven by **flutter_blue_plus**, which wraps Android GATT. The actual file transfer protocol is likely implemented in Dart (missing here).

### 2) MTU/GATT related strings (generic)
From strings search:
- `requestMtu`
- `onMtuChanged`
- `onMtuChanged:`
- `data longer than mtu allows. dataLength:`
- `gatt.requestMtu() returned false`

GATT error/status strings (standard Android BLE):
- `ERROR_GATT_WRITE_REQUEST_BUSY`
- `ERROR_GATT_WRITE_NOT_ALLOWED`
- `GATT_*` (many standard GATT error/status codes)
- `INDICATE not supported by this BLE characteristic`
- `CCCD descriptor for characteristic not found:`

These are **generic plugin/framework strings**, not app‑specific transfer logic.

### 3) No UUIDs or file transfer markers
Search for known UUIDs returned **no matches** in this extraction:
- `fcbff68e`, `fcbffa44`, `27566b01`, `250e79ac`, `fd31abc4`

Search for file transfer keywords (`file`, `chunk`, `upload`, `transfer`, `flag`) produced **no app‑specific protocol strings** beyond generic Android/framework output.

### 4) No native `.so` libraries present
`/tmp/sandsara_apk` contains **no `lib/` directory** and no `.so` files. `unzip -l /tmp/sandsara_base.apk | grep lib/.*\.so` returns nothing.

---

## Flutter assets
`/tmp/sandsara_apk/assets/flutter_assets/` contains only standard manifests, fonts, and image assets. There are **no Dart snapshots** (`kernel_blob.bin`, `vm_snapshot_data`, `isolate_snapshot_data`) and **no AOT `libapp.so`**.

---

## What’s Missing / Next Step Required
To extract the **actual file transfer implementation**, we need the **split APK with native libs**:
- Look for files named like `split_config.arm64_v8a.apk`, `split_config.armeabi_v7a.apk`, or similar.
- These should contain `/lib/*/libapp.so` and `/lib/*/libflutter.so`.
- Once obtained, run `strings` on `libapp.so` to locate protocol/UUID/chunk‑size constants.

---

## Conclusion
With the current extraction, **the exact file transfer protocol is not recoverable**. We can only confirm BLE usage via **flutter_blue_plus** and generic MTU/GATT behavior. **No app‑specific transfer logic, chunk size, UUIDs, or retry logic is visible** without the native AOT library.

---

## Raw command outputs (high‑signal)
- `strings /tmp/sandsara_apk/classes.dex | grep -i "flutter_blue"`:
  - `flutter_blue_plus/methods`
  - `Error registering plugin flutter_blue_plus, com.lib.flutter_blue_plus.FlutterBluePlusPlugin`

- `strings /tmp/sandsara_apk/classes.dex | grep -iE "mtu|requestMtu|onMtuChanged"`:
  - `mtu:`
  - `requestMtu`
  - `onMtuChanged`
  - `data longer than mtu allows. dataLength:`
  - `gatt.requestMtu() returned false`

- `strings /tmp/sandsara_apk/classes.dex | grep -i "fcbff68e|fcbffa44|27566b01|250e79ac|fd31abc4"`:
  - **no matches**
