#pragma once
#define PANEL_COLUMNS 64u
#define PANEL_SCAN_ROWS 32u
#define PANEL_ROW_US 250u
#define PANEL_ON_US 10u
/* PB13 only controls the documented NMOS buffer-enable circuit. */
#define PANEL_SHIFT_EN 1
#define PANEL_RGB_MASK 0x003fu
#define PANEL_CLK (1u << 6)
#define PANEL_LAT (1u << 7)
#define PANEL_OE (1u << 8)
#define PANEL_ADDRESS_MASK 0x1c03u
