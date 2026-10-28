# Changelog

## [1.4.0](https://github.com/Megabytemb/ha-kano-wand/compare/v1.3.0...v1.4.0) (2026-10-28)


### Features

* add Flick event & triggers, boolean Battery binary sensor, Temperature sensor, and Magnetometer Calibration from official Kano app ([bd874c7](https://github.com/Megabytemb/ha-kano-wand/commit/bd874c7c13781df04b397bc65930a6b35aad7ac8))
* always render every wand attempt on Last Spell Drawing and add all 25 model & official app spell diagrams ([f015433](https://github.com/Megabytemb/ha-kano-wand/commit/f015433a399b8bdfac1139470eadbc35828f1167))


### Documentation

* add section explaining Recentre Orientation vs Magnetometer Calibration in README ([e2ef1b9](https://github.com/Megabytemb/ha-kano-wand/commit/e2ef1b966d466c021ec7bc17e516f63b7a4eaeef))

## [1.3.0](https://github.com/Megabytemb/ha-kano-wand/compare/v1.2.0...v1.3.0) (2026-10-25)


### Features

* add visual device automations (triggers, actions, conditions) and logbook activity ([1544058](https://github.com/Megabytemb/ha-kano-wand/commit/154405868168a8746ccf53f454edb9bb307cb84b))

## [1.2.0](https://github.com/Megabytemb/ha-kano-wand/compare/v1.1.2...v1.2.0) (2026-10-25)


### Features

* add Vibration Pattern select, haptic switches, confidence threshold, recentre/disconnect buttons, and diagnostics ([da5d4e0](https://github.com/Megabytemb/ha-kano-wand/commit/da5d4e0b354d9874112d0d8744615b99d6479df4))


### Bug Fixes

* bypass habluetooth static advertisement deduplication on wand wake-up ([b1cb609](https://github.com/Megabytemb/ha-kano-wand/commit/b1cb6096c12042c879e476ad37dc7bdeccc3da97))
* fix spell drawing ImageEntity init, add Auto Connect switch, and remove unimplemented 0% battery sensor ([1146f4f](https://github.com/Megabytemb/ha-kano-wand/commit/1146f4f76b3686d7c81f472b3a04a0059541a62c))

## [1.1.2](https://github.com/Megabytemb/ha-kano-wand/compare/v1.1.1...v1.1.2) (2026-10-25)


### Bug Fixes

* replace ai-edge-litert with pure-NumPy TFLite model execution for musllinux/HA OS compatibility ([30177c1](https://github.com/Megabytemb/ha-kano-wand/commit/30177c12e7006bf858c639d40eea8f96c9504ccf))

## [1.1.1](https://github.com/Megabytemb/ha-kano-wand/compare/v1.1.0...v1.1.1) (2026-10-25)


### Bug Fixes

* update service UUIDs and dependencies in manifest.json ([3d22007](https://github.com/Megabytemb/ha-kano-wand/commit/3d220077f6e4c671dce07f99ccb45312e13e8e04))

## [1.1.0](https://github.com/Megabytemb/ha-kano-wand/compare/v1.0.0...v1.1.0) (2026-10-25)


### Features

* initial release of Kano Wand Home Assistant integration ([ab10e24](https://github.com/Megabytemb/ha-kano-wand/commit/ab10e2445e587a15370fcfbe68814433d6aff093))
