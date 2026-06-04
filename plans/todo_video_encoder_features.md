# Video Encoder Features — TODO

## 1. Quick audio-copy toggle button

Add a button next to the encoder combobox that auto-switches the audio mode between **Encode** and **Copy** when the user switches the video mode between **Encode** and **Copy**.

- When user sets Video → **Copy**, the button should also set Audio Mode → **Copy** (in Advanced Encoding Settings)
- When user sets Video → **Encode**, the button should set Audio Mode → **Encode**
- Could be a small toggle/link button like `[🔗]` or a label "Sync Audio Copy"

## 2. Encoding presets combobox and dialog

Add an encoding presets system:

- A **presets combobox** + **manage/save button** placed after the encoder combobox (or near the top of encoding settings)
- Clicking the manage button opens a dialog where the user can tweak all encoding settings
- The user types a name and clicks "Add" / "Save" to create a new preset
- Presets are persisted in `settings.json` under a `video_presets` key
- Selecting a preset from the combobox applies all stored settings
- Selecting a built-in "Default" option resets to app defaults
