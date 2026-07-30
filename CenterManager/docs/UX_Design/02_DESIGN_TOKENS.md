# CENTER DESIGN SYSTEM

# 02. DESIGN TOKENS

Version: 1.0

Status: Approved

---

# Purpose

Design Tokens define the smallest visual building blocks used throughout CenterManager.

All UI must reference these tokens.

Never hard-code values.

---

# Spacing System

The entire application uses an 8-point spacing grid.

## Tokens

Space-0   = 0
Space-1   = 4
Space-2   = 8
Space-3   = 12
Space-4   = 16
Space-5   = 24
Space-6   = 32
Space-7   = 40
Space-8   = 48
Space-9   = 64

---

# Usage

Inside Button

8

Inside Card

16

Between Controls

12

Between Sections

24

Between Major Blocks

32

Page Margin

24

Dashboard Margin

24

Dialog Margin

24

Never invent new spacing.

Examples

❌ 13

❌ 19

❌ 27

✅ 8

✅ 16

✅ 24

✅ 32

---

# Radius

Small

4

Medium

8

Large

12

Dialog

16

Round

999

---

# Border Width

Thin

1

Focus

2

Divider

1

Never use random border widths.

---

# Shadow

Level 0

None

Level 1

Card

Level 2

Floating Panel

Level 3

Dialog

Maximum allowed shadow

Level 3

---

# Scrollbar

Width

8

Radius

4

Track

Transparent

Thumb

Neutral Gray

Hover

Primary Gray

Always visible on hover.

---

# Icon Size

Small

16

Normal

20

Large

24

Hero

32

Never scale icons manually.

---

# Avatar

Small

24

Medium

32

Large

48

Profile

64

---

# Button Height

Toolbar Button

32

Default Button

36

Primary Button

40

Large Button

48

---

# Input Height

Compact

32

Default

36

Large

40

---

# Toolbar Height

Small Toolbar

40

Standard Toolbar

48

Page Header

64

---

# Sidebar

Collapsed

72

Expanded

240

Workspace Header

64

---

# Card

Internal Padding

16

Gap Between Cards

16

Card Radius

8

Maximum Width

None

Cards grow naturally.

---

# Table

Row Height

40

Header Height

44

Selection Column

40

Checkbox

Centered

Padding

16

---

# Dialog

Small

480

Medium

720

Large

960

Maximum

1200

---

# Chart

Minimum Height

240

Preferred Height

320

Maximum Height

480

---

# Timeline

Gap

16

Time Label Width

120

Event Padding

12

---

# Empty State

Illustration

96

Title Margin

16

Description Margin

8

Primary Button Margin

24

---

# Animation

Hover

120 ms

Normal

180 ms

Dialog

250 ms

Never exceed

300 ms

---

# Responsive Breakpoints

Compact

<1280

Standard

1280~1600

Wide

1600+

Ultra Wide

1920+

---

# Token Rules

Developers must never write

padding:17

margin:23

radius:11

Instead

use the nearest Design Token.

Consistency is more important than perfection.