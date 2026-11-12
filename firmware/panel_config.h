#pragma once
#define PANEL_COLUMNS 64u
#define PANEL_SCAN_ROWS 32u
#define PANEL_ROW_US 300u
/* Uniform blue is latched once; scan only the row address afterwards. */
#define PANEL_SOLID_BLUE 1
#if PANEL_SOLID_BLUE
#define PANEL_ON_US 294u
#define PANEL_MAX_ON_US 294u
#define PANEL_BLUE_MASK ((1u << 2) | (1u << 5))
#else
/* Total exposure per row across all four color planes. */
#define PANEL_ON_US 70u
#define PANEL_MAX_ON_US 100u
#endif
/* PB13 only controls the documented NMOS buffer-enable circuit. */
#define PANEL_SHIFT_EN 1
#define PANEL_RGB_MASK 0x003fu
#define PANEL_CLK (1u << 6)
#define PANEL_LAT (1u << 7)
#define PANEL_OE (1u << 8)
#define PANEL_ADDRESS_MASK 0x1c03u
