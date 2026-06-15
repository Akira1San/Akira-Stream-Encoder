# Trim Panel — Side by Side Layout

Rearrange the Trim/Cut tab so the cuts list and parts-to-export list are side by side instead of stacked vertically.

## Current Layout

```
Trim/Cut Video (QGroupBox, QVBoxLayout)
  Cuts: 0
  [  cuts_list (maxHeight 100)  ]
  [Add Cut] [Delete] [Del Seg] [Clear All]
  ─────────────────────────────────────────
  Parts to Export: 0
  [  segments_list (maxHeight 150)  ]
  [Select All] [Deselect All]
  [Export Cut Parts]
```

## Target Layout

```
Trim/Cut Video (QGroupBox, QVBoxLayout)
  ┌─── Cuts: 0 ────────┐─── Parts to Export: 0 ──┐
  │                     │                          │
  │  [  cuts_list  ]    │  [  segments_list  ]     │
  │                     │                          │
  │ [Add Cut] [Delete]  │  [Select All]            │
  │ [Delete Segment]    │  [Deselect All]          │
  │ [Clear All]         │                          │
  └─────────────────────┴──────────────────────────┘
  [Export Cut Parts]
```

## File: `PySide6/trim_panel.py`

### Changes in `setup_ui()`

1. Remove the separator `QFrame` (no longer needed)
2. Remove fixed `setMaximumHeight()` on both lists (let them fill available space)
3. Wrap the two columns in a `QHBoxLayout` (50/50 split, no splitter)
4. Each column is a `QVBoxLayout` inside the horizontal layout

### Structure after change

```python
def setup_ui(self):
    layout = QVBoxLayout(self)

    # Horizontal layout for the two columns
    columns = QHBoxLayout()

    # === Left Column: Cuts ===
    left_column = QVBoxLayout()
    cuts_header = QHBoxLayout()
    self.cuts_count_label = QLabel("Cuts: 0")
    cuts_header.addWidget(self.cuts_count_label)
    cuts_header.addStretch()
    left_column.addLayout(cuts_header)

    self.cuts_list = QListWidget()  # no max height
    # same selection mode, tooltip
    left_column.addWidget(self.cuts_list)

    # Cut buttons
    cut_btn_layout = QHBoxLayout()
    self.set_cut_btn = QPushButton("Add Cut Point")
    # ... same buttons ...
    left_column.addLayout(cut_btn_layout)

    columns.addLayout(left_column)

    # === Right Column: Parts to Export ===
    right_column = QVBoxLayout()
    segments_header = QHBoxLayout()
    self.segments_count_label = QLabel("Parts to Export: 0")
    segments_header.addWidget(self.segments_count_label)
    segments_header.addStretch()
    right_column.addLayout(segments_header)

    self.segments_list = QListWidget()  # no max height
    # same tooltip
    right_column.addWidget(self.segments_list)

    # Segment buttons
    segment_btn_layout = QHBoxLayout()
    self.select_all_btn = QPushButton("Select All")
    # ... same buttons ...
    right_column.addLayout(segment_btn_layout)

    columns.addLayout(right_column)

    layout.addLayout(columns)

    # Export Button (spans full width at bottom)
    self.execute_btn = QPushButton("Export Cut Parts")
    layout.addWidget(self.execute_btn)

    layout.addStretch()
```

### Behaviors unchanged

- All signals, slots, and button handlers stay the same
- List heights expand to fill available space (no max height constraints)
- The group box is inside a QTabWidget, which already provides vertical space
