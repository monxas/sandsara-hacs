# Sandsara Home Assistant Integration

A custom Home Assistant integration for controlling **Sandsara Mini Pro** kinetic sand tables via Bluetooth Low Energy (BLE).

## Features

- **Light Control**: On/off, brightness, RGB color
- **Media Player**: Play, pause, next track, sleep
- **Ball Speed Control**: Adjustable motor speed (1-100)
- **LED Animation Speed**: Adjustable LED rotation speed (1-100)
- **Auto-Discovery**: Automatically detects Sandsara devices via Bluetooth
- **ESP32 BLE Proxy Support**: Works with ESPHome Bluetooth proxies

## Requirements

- Home Assistant 2024.1.0 or newer
- Bluetooth adapter or ESP32 BLE proxy with available connection slot
- Sandsara Mini Pro (firmware v6.3.1 tested)

## Installation

### HACS (Recommended)

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)

1. **Install HACS** if you haven't already: [HACS Installation Guide](https://hacs.xyz/docs/setup/prerequisites)
2. **Add Custom Repository**:
   - Go to HACS → Integrations
   - Click the three dots menu (⋮) → Custom repositories
   - Add repository URL: `https://github.com/monxas/sandsara-hacs`
   - Category: Integration
   - Click ADD
3. **Install Integration**:
   - Search for "Sandsara" in HACS
   - Click DOWNLOAD
4. **Restart Home Assistant**
5. **Add Integration**:
   - Go to Settings → Devices & Services
   - Click "+ ADD INTEGRATION" 
   - Search for "Sandsara"
   - Follow the configuration wizard

### Manual Installation

1. Copy the `custom_components/sandsara` folder to your Home Assistant `config/custom_components/` directory
2. Restart Home Assistant
3. Go to Settings → Devices & Services → Add Integration → Sandsara

## Entities

Once configured, the integration creates the following entities:

| Entity | Type | Description |
|--------|------|-------------|
| `light.sandsara_led` | Light | LED on/off, brightness, color |
| `media_player.sandsara_playback` | Media Player | Play/pause/next/stop |
| `number.sandsara_ball_speed` | Number | Motor speed (1-100) |
| `number.sandsara_led_animation_speed` | Number | LED rotation speed (1-100) |

## Important Notes

### Persistent Connection Required

The Sandsara requires a **persistent BLE connection** to operate. This means:

- The device occupies one BLE connection slot permanently
- If using ESP32 proxies, ensure `max_connections` is set high enough (default is 3)
- The ball stops moving when the BLE connection drops

### ESP32 Proxy Configuration

If your Sandsara is only reachable via ESP32 BLE proxies, increase the connection limit in the proxy's ESPHome config:

```yaml
bluetooth_proxy:
  active: true
  cache_services: true
  max_connections: 5
```

### Color Format Quirk

The Mini Pro requires colors to be sent as gradients, even for solid colors. The integration handles this automatically.

## Protocol Documentation

See [docs/PROTOCOL_NOTES.md](docs/PROTOCOL_NOTES.md) for the complete reverse-engineered BLE protocol specification.

## Development Tools

The `tools/` directory contains Python scripts for direct device communication:

- `sandsara_controller.py` - CLI controller for testing
- `sandsara_test_server.py` - Persistent connection server for protocol exploration

## Troubleshooting

### "Out of connection slots" Error

Your BLE proxies are full. Either:
- Increase `max_connections` in your ESP32 proxy config
- Move the Sandsara closer to your HA server's built-in Bluetooth adapter
- Disconnect other BLE devices to free up slots

### Commands Not Working

1. Check Settings → System → Logs for "sandsara" entries
2. Verify the device is connected (entities should be "available")
3. Ensure the init handshake completed (look for "Sandsara initialized" in logs)

### Device Not Found

- Ensure Sandsara is powered on
- Check that at least one Bluetooth adapter/proxy can see it
- The device advertises with service UUID `fd31a2be-22e7-11eb-adc1-0242ac120002`

## License

MIT

## Credits

Protocol reverse-engineered from the official Sandsara Android app and HCI packet captures.
