# Changelog

All notable changes to the Sandsara Home Assistant integration will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2025-02-03

### Added
- Initial release of Sandsara Mini Pro Home Assistant integration
- Light entity with RGB color support, brightness control, and on/off functionality
- Media player entity with play/pause/next/stop commands and sleep mode
- Number entities for ball speed (1-100) and LED animation speed (1-100)
- Auto-discovery via Bluetooth service UUID
- Support for ESP32 BLE proxies
- Complete BLE protocol reverse engineering documentation
- Config flow for easy setup through Home Assistant UI
- Persistent BLE connection management
- Translation support (English)

### Features
- **Bluetooth Low Energy (BLE) Communication**: Direct control via Bluetooth or ESP32 proxies
- **Comprehensive Device Control**: All major device functions exposed as Home Assistant entities
- **Automatic Discovery**: Finds Sandsara devices automatically via BLE advertisement
- **ESP32 Proxy Support**: Works with ESPHome Bluetooth proxy for extended range
- **Protocol Documentation**: Complete reverse-engineered protocol for developers

### Technical Details
- Requires Home Assistant 2024.1.0 or newer
- Uses bleak and bleak-retry-connector for BLE communication
- Implements persistent connection for real-time device control
- Supports Sandsara Mini Pro firmware v6.3.1 (tested)

### Documentation
- Comprehensive README with installation instructions
- HACS compliance with proper repository structure
- Troubleshooting guide for common issues
- Protocol documentation for developers