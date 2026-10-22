# Dialogue Render Analysis

This report correlates dialogue-frame `IO`, `WRAM`, and `VRAM` snapshots.

## Frame `2160`

- `DISPCNT`: `0x1940`
- `BG0CNT`: `0x0087`
- `BG3CNT`: `0x0300`
- Best `WRAM 0xA8C0-0xAA7F` match in `VRAM`: `0x1B0A` with `364/448` identical bytes

## Frame `2340`

- `DISPCNT`: `0x1940`
- `BG0CNT`: `0x0087`
- `BG3CNT`: `0x0300`
- Best `WRAM 0xA8C0-0xAA7F` match in `VRAM`: `0x1B0A` with `370/448` identical bytes

## Frame `2520`

- `DISPCNT`: `0x1940`
- `BG0CNT`: `0x0087`
- `BG3CNT`: `0x0300`
- Best `WRAM 0xA8C0-0xAA7F` match in `VRAM`: `0x1B12` with `339/448` identical bytes

## Frame `2700`

- `DISPCNT`: `0x1940`
- `BG0CNT`: `0x0087`
- `BG3CNT`: `0x0300`
- Best `WRAM 0xA8C0-0xAA7F` match in `VRAM`: `0x1B0E` with `373/448` identical bytes

## VRAM Diff Hotspots

### `2160 -> 2340`

- `0x1C00`: `6` changed bytes
- `0x2000`: `150` changed bytes
- `0x2200`: `188` changed bytes
- `0x2400`: `88` changed bytes
- `0x2600`: `0` changed bytes

### `2340 -> 2520`

- `0x1C00`: `28` changed bytes
- `0x2000`: `0` changed bytes
- `0x2200`: `0` changed bytes
- `0x2400`: `120` changed bytes
- `0x2600`: `170` changed bytes

### `2520 -> 2700`

- `0x1C00`: `32` changed bytes
- `0x2000`: `134` changed bytes
- `0x2200`: `188` changed bytes
- `0x2400`: `0` changed bytes
- `0x2600`: `0` changed bytes

## Interpretation

- The dialogue scene is `Mode 0` with `BG0` and `BG3` enabled.
- `BG3CNT = 0x0300` means `BG3` uses `char base 0x0000` and `screen base 0x1800`.
- The `WRAM 0xA8C0-0xAA7F` buffer best matches `VRAM` around `0x1B0A`, inside the `BG3` screen block region.
- Page flips also heavily mutate `VRAM 0x2000+`, which is outside the `BG3` screen block and is therefore more likely glyph/tile graphics upload.

Working model:

1. Dialogue renderer builds `BG3` tilemap entries in `WRAM 0xA900+`.
2. That tilemap is copied into `VRAM 0x1800+`.
3. Character glyph tiles are uploaded or refreshed in `VRAM 0x2000+`.

