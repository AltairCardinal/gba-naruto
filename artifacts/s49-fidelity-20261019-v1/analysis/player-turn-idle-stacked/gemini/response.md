Based on a frame-by-frame analysis of [capture.mp4](file:///Users/altair/github/gba-naruto/artifacts/s49-fidelity-20261019-v1/analysis/player-turn-idle-stacked/gemini/capture.mp4) using `ffprobe` and `ffmpeg`, here is the complete breakdown of every visible difference, verified with exact frame citations (0-based frames 0–95 at 60 fps, timestamp $t = n/60\text{ s}$).

---

### Video & Stream Properties (`ffprobe`)
* **Dimensions**: $480 \times 648$ (Top half: original GBA $480 \times 320$ [upscaled $2\times$ from $240 \times 160$]; Middle: 8 px magenta separator at $y \in [320, 327]$; Bottom half: Butano remake $480 \times 320$).
* **Stream Details**: H.264 / AVC High Profile, `yuv420p`, 60.00 fps constant (`-fps_mode passthrough`), 96 frames, duration 1.60 s.
* **Top-Left Stamp**: Stamped frame index on a black badge ($x \in [0, 25], y \in [0, 12]$) on the top half.

---

### 1. Unit Positions on the Map Grid
* **Naruto (Selected Player Unit)**:
  * **Identical position**: Both original and remake position Naruto at grid coordinate **$\{11, 6\}$** with his tile selection bracket center at screen coordinate $(127.5, 79.5)$.
* **Konohamaru (Ally Unit)**:
  * **Original (Top)**: Positioned at grid coordinate **$\{8, 7\}$** (screen bounding box $x \in [16, 44], y \in [50, 101]$, base center at $x = 30.0, y = 101$). In the original battle entry, Konohamaru starts at $\{8, 7\}$ prior to executing his scripted opening move.
  * **Remake (Bottom)**: Positioned at grid coordinate **$\{10, 7\}$** (screen bounding box $x \in [83, 108], y \in [51, 100]$, base center at $x = 95.5, y = 100$). The remake savestate has Konohamaru already moved to $\{10, 7\}$ (1 tile left and 1 tile down from Naruto).
  * **Difference**: A horizontal shift of **2 map grid tiles** ($\Delta x = 65.5\text{ px}$). Where Konohamaru stands in the original, the remake displays background grass; where Konohamaru stands in the remake, the original displays background grass.

---

### 2. Sprite Appearance and Palette
* **Konohamaru's Sprite & Facing**:
  * **Original (Top)**:
    * **Facing**: Faces **South-East / Down-Right** (front 3/4 view facing toward Naruto).
    * **Appearance**: Spiky black hair, front of white helmet with gold emblem, visible facial features (eyes, eyebrows, mouth), blue scarf looped at the front neck, light yellow/tan shirt with the Konoha leaf emblem on his chest, grey shorts, and blue sandals.
    * **Palette**: Standard allied unit palette.
  * **Remake (Bottom)**:
    * **Facing**: Faces **North / Up** (back view facing away from the camera).
    * **Appearance**: Back of spiky hair, back of white helmet with a red cross/plus badge, long blue scarf hanging straight down his back, back of yellow shirt, and grey shorts.
* **Naruto's Outline & Palette**:
  * **Original (Top)**: Naruto's selection highlight outline undergoes **continuous dynamic palette cycling** at 60 fps across all 96 frames. The outline color breathes in a 32-frame sinusoidal wave from dark teal `RGB(0, 8, 8)` to bright cyan `RGB(0, 255, 255)` (e.g., at pixel $(121, 58)$ during Pose A: Frame 0 is `(0, 90, 90)`, Frame 10 peaks at `(0, 255, 255)`, and Frame 26 troughs at `(0, 8, 8)`).
  * **Remake (Bottom)**: Naruto's outline color is **completely static** at hardcoded constant cyan `RGB(0, 189, 189)` (`bn::color(0, 23, 23)`). It has no palette cycling or breathing glow.

---

### 3. Motion & Animation Over the 96 Frames (Phase & Cadence)

#### A. Konohamaru's Idle Animation
* **Original (Top)**: **Completely static** across all 96 frames (0 pixel changes from Frame 0 through 95). As an unselected ally unit, he does not play an idle loop.
* **Remake (Bottom)**: **Actively animates** an idle loop cycling through 3 poses every 8 frames ($32\text{ frames} = 0.533\text{ s}$ per full cycle):
  * **Pose 0 (Neutral)**: Frames **0–6**, **15–22**, **31–38**, **47–54**, **63–70**, **79–86**, **95**.
  * **Pose 1 (Shift/Bob 1)**: Frames **7–14**, **39–46**, **71–78** (pose transitions occur at Frames **7**, **39**, **71**).
  * **Pose 2 (Shift/Bob 2)**: Frames **23–30**, **55–62**, **87–94** (pose transitions occur at Frames **23**, **55**, **87**).

#### B. Naruto's Idle Animation Phase
Both games use the same 32-frame, 4-step idle cycle (Pose A $\rightarrow$ Pose B $\rightarrow$ Pose A $\rightarrow$ Pose C), but they differ by an exact **6-frame phase offset**:
* **Original (Top)**:
  * Frame 0: Last frame of Pose A.
  * Frames **1–8**: Pose B (switches at **Frame 1**).
  * Frames **9–16**: Pose A.
  * Frames **17–24**: Pose C (switches at **Frame 17**).
  * Frames **25–32**: Pose A.
  * Frames **33–40**: Pose B (switches at **Frame 33**).
  * Frames **41–48**: Pose A.
  * Frames **49–56**: Pose C (switches at **Frame 49**).
  * Frames **57–64**: Pose A.
  * Frames **65–72**: Pose B (switches at **Frame 65**).
  * Frames **73–80**: Pose A.
  * Frames **81–88**: Pose C (switches at **Frame 81**).
  * Frames **89–95**: Pose A.
* **Remake (Bottom)**:
  * Frames **0–6**: Pose A (7 frames).
  * Frames **7–14**: Pose B (switches at **Frame 7**, exactly 6 frames later than original).
  * Frames **15–22**: Pose A.
  * Frames **23–30**: Pose C (switches at **Frame 23**, exactly 6 frames later than original).
  * Frames **31–38**: Pose A.
  * Frames **39–46**: Pose B (switches at **Frame 39**).
  * Frames **47–54**: Pose A.
  * Frames **55–62**: Pose C (switches at **Frame 55**).
  * Frames **63–70**: Pose A.
  * Frames **71–78**: Pose B (switches at **Frame 71**).
  * Frames **79–86**: Pose A.
  * Frames **87–94**: Pose C (switches at **Frame 87**).
  * Frame **95**: Pose A (1 frame).

#### C. 4-Direction Facing Indicator (Above Naruto's Head)
* **Appearance**: Compass marker with a red West/Left arrow (`RGB(255, 0, 0)`) and blue North/East/South arrows.
* **Lateral Pulsing Phase**:
  * **Original (Top)**: Red arrow tip pulses outward to $x = 113$ at **Frame 1**, retracts to $x = 111$ at **Frame 6**, and returns to base $x = 110$ at **Frame 10**. (Subsequent cycles shift outward at Frames **17**, **33**, **49**, **65**, **81**).
  * **Remake (Bottom)**: Red arrow tip pulses outward to $x = 113$ at **Frame 2**, retracts to $x = 111$ at **Frame 7**, and returns to base $x = 110$ at **Frame 11**. (Subsequent cycles shift outward at Frames **18**, **34**, **50**, **66**, **82**).
  * **Difference**: Remake is delayed by **1 frame** relative to original.

#### D. Selection Bracket Pulsing (Breathing)
* **Original (Top)**: Neutral at $(111, 72)$ (Frames **0–2**), expands outward to $(110, 71)$ (Frames **3–7**), reaches maximum expansion at $(109, 70)$ (Frames **8–11**), contracts back to $(110, 71)$ (Frames **12–15**), and returns to neutral at Frame **16** (16-frame period).
* **Remake (Bottom)**: Starts 1 px tighter at $(112, 73)$ (Frames **0–10**), expands to $(111, 72)$ (Frames **11–18**), expands to $(110, 71)$ (Frames **19–23**), and peaks at $(109, 70)$ (Frames **24–27**). The remake has a different breathing cadence and phase.

---

### 4. Bottom Status Bar Text and Numbers
* **Zero Difference**: Across all 96 frames, the bottom status bar region ($y \in [104, 159]$ in native $240 \times 160$ coordinates, or $y \in [208, 319]$ top / $y \in [536, 647]$ bottom in the capture) is **100% bit-for-bit identical** (0 differing pixels across all 96 frames):
  * Name: `漩涡鸣人` (purple font, identical glyph rasterization).
  * State text: `本体` (black) and `结束` (red).
  * Labels: `体力` and `查克拉` (black).
  * Numeric stats: HP `138` and Chakra `5`.
  * Visual gauges: Orange HP bar and cyan Chakra bar with identical borders.

---

### 5. Movement-Range Overlay
* **Plain Statement**: **Cannot be confirmed / Not shown in this capture**. Neither the original GBA game nor the Butano remake displays movement-range overlay tiles (blue movable grid / red attack grid) in any of these 96 frames. Both sides are in the idle entry state (`unit_selection`) before the player presses `A` to open the movement range.

---

### 6. Categories of Difference That Cannot Be Confirmed From This Capture
1. **Movement-range overlay & pathfinding**: Not triggered during idle entry.
2. **Action / Command menus**: Menus (移动, 忍术, 忍具, 待机) are not opened.
3. **Enemy units (Wild Bees)**: All five scenario 49 enemy bees are positioned elsewhere on the map outside this $240 \times 160$ camera window.
4. **Other player units (Sasuke, Sakura)**: Located off-screen at this camera viewport.
5. **Combat / damage / level-up presentations**: No combat interactions occur.
6. **Audio / SFX**: `capture.mp4` contains only a video stream (`ffprobe` shows 0 audio streams); audio dispatch and SFX playback cannot be evaluated.
