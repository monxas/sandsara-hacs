# Sandsara Pattern Names (from App Screenshots)

Extracted from app screenshots on 2026-02-08. The app shows patterns in alphabetical order.
Only the first portion of the list was captured (app wasn't scrolled far enough).

## Discovered Names (alphabetical)

1. Alfenique
2. Ancient Geometry
3. Art of Tiles
4. Atwood Quote
5. Beyond Infinity
6. Birth of a Poem

## Notes

- Only 6 patterns were visible across all screenshots (the list starts at "A" and wasn't scrolled much)
- The Sandsara has tracks 0-99 (files `Sandsara-trackNumber-0000.bin` to `0099.bin`)
- The app sorts alphabetically, but **track index ≠ alphabetical position** — we need BLE sniffing or firmware analysis to map indices to names
- Screenshots 16-17 showed "My Patterns" tab (empty)
- Screenshots 22-26 showed Settings page
- Firmware version: 6.3.2, Version: 3-mini

## TODO

- Scroll through the entire pattern list to capture all ~100 names
- Use BLE packet capture to map track indices to actual pattern names
- Check if pattern names are embedded in the .bin files on the SD card
