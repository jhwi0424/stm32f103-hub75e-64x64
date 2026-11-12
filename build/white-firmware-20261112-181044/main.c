#include "stm32f1xx_hal.h"
#include "panel_config.h"

void _init(void) {}
void _fini(void) {}

typedef struct {
    uint32_t magic, version, frames, row, on_us, row_us, core_hz;
    uint32_t enable, rgb_mask, fault, last_frame_cycles;
} PanelStatus;
volatile PanelStatus panel_status = {0x48554237u, 1, 0, 0, PANEL_ON_US,
    PANEL_ROW_US, 0, 1, PANEL_RGB_MASK, 0, 0};

static void blank(void) {
    /* Force inactive high, including when PA8 is owned by TIM1. */
    TIM1->CR1 = TIM_CR1_OPM;
    TIM1->CCMR1 = (4u << 4); /* forced inactive; CC1P inverts to high */
    GPIOA->BSRR = PANEL_OE;
}

void Error_Handler(void) {
    __HAL_RCC_GPIOA_CLK_ENABLE();
    __HAL_RCC_GPIOB_CLK_ENABLE();
    __HAL_RCC_TIM1_CLK_ENABLE();
    blank();
    GPIOB->BSRR = (1u << (13 + 16));
    panel_status.fault = 1;
    __disable_irq();
    for (;;) {}
}
void HardFault_Handler(void) { Error_Handler(); }
void MemManage_Handler(void) { Error_Handler(); }
void BusFault_Handler(void) { Error_Handler(); }
void UsageFault_Handler(void) { Error_Handler(); }
void SysTick_Handler(void) { HAL_IncTick(); }

static void clock_init(void) {
    RCC_OscInitTypeDef osc = {0};
    RCC_ClkInitTypeDef clk = {0};
    osc.OscillatorType = RCC_OSCILLATORTYPE_HSI;
    osc.HSIState = RCC_HSI_ON;
    osc.HSICalibrationValue = RCC_HSICALIBRATION_DEFAULT;
    osc.PLL.PLLState = RCC_PLL_ON;
    osc.PLL.PLLSource = RCC_PLLSOURCE_HSI_DIV2;
    osc.PLL.PLLMUL = RCC_PLL_MUL16;
    if (HAL_RCC_OscConfig(&osc) != HAL_OK) Error_Handler();
    clk.ClockType = RCC_CLOCKTYPE_SYSCLK | RCC_CLOCKTYPE_HCLK |
        RCC_CLOCKTYPE_PCLK1 | RCC_CLOCKTYPE_PCLK2;
    clk.SYSCLKSource = RCC_SYSCLKSOURCE_PLLCLK;
    clk.AHBCLKDivider = RCC_SYSCLK_DIV1;
    clk.APB1CLKDivider = RCC_HCLK_DIV2;
    clk.APB2CLKDivider = RCC_HCLK_DIV1;
    if (HAL_RCC_ClockConfig(&clk, FLASH_LATENCY_2) != HAL_OK) Error_Handler();
}

static void gpio_init(void) {
    __HAL_RCC_AFIO_CLK_ENABLE();
    __HAL_RCC_GPIOA_CLK_ENABLE();
    __HAL_RCC_GPIOB_CLK_ENABLE();
    __HAL_AFIO_REMAP_SWJ_NOJTAG(); /* retain PA13/PA14 SWD */
    GPIOA->BSRR = PANEL_OE | ((PANEL_RGB_MASK | PANEL_CLK | PANEL_LAT) << 16);
    GPIOB->BSRR = (PANEL_ADDRESS_MASK | (1u << 13)) << 16;
    GPIO_InitTypeDef gpio = {0};
    gpio.Pin = PANEL_RGB_MASK | PANEL_CLK | PANEL_LAT | PANEL_OE;
    gpio.Mode = GPIO_MODE_OUTPUT_PP;
    gpio.Speed = GPIO_SPEED_FREQ_MEDIUM;
    HAL_GPIO_Init(GPIOA, &gpio);
    gpio.Pin = PANEL_ADDRESS_MASK | (1u << 13);
    HAL_GPIO_Init(GPIOB, &gpio);
}

static void wait_cycles(uint32_t cycles) {
    uint32_t start = DWT->CYCCNT;
    while ((uint32_t)(DWT->CYCCNT - start) < cycles) {}
}
static void shift_latch(uint32_t rgb) {
    GPIOA->BSRR = rgb | ((PANEL_RGB_MASK & ~rgb) << 16);
    wait_cycles(32); /* >=0.5 us data setup at 64 MHz */
    for (unsigned x = 0; x < PANEL_COLUMNS; ++x) {
        GPIOA->BSRR = PANEL_CLK;
        wait_cycles(32);
        GPIOA->BSRR = PANEL_CLK << 16;
        wait_cycles(32);
    }
    GPIOA->BSRR = PANEL_LAT;
    wait_cycles(64);
    GPIOA->BSRR = PANEL_LAT << 16;
    wait_cycles(128);
}

static void pulse_init(void) {
    __HAL_RCC_TIM1_CLK_ENABLE();
    TIM1->CR1 = TIM_CR1_OPM;
    TIM1->PSC = 63; /* 64 MHz / 64 = 1 MHz */
    TIM1->ARR = PANEL_ON_US + 1;
    TIM1->CCR1 = 2;
    TIM1->CCER = TIM_CCER_CC1E | TIM_CCER_CC1P;
    TIM1->CR2 = TIM_CR2_OIS1;
    TIM1->BDTR = TIM_BDTR_MOE | TIM_BDTR_OSSI | TIM_BDTR_OSSR;
    blank();
    TIM1->EGR = TIM_EGR_UG;
    GPIO_InitTypeDef gpio = {0};
    gpio.Pin = PANEL_OE;
    gpio.Mode = GPIO_MODE_AF_PP;
    gpio.Speed = GPIO_SPEED_FREQ_MEDIUM;
    HAL_GPIO_Init(GPIOA, &gpio);
    /* Leave TIM1 running during a CPU debug halt so pulses finish. */
    DBGMCU->CR &= ~DBGMCU_CR_DBG_TIM1_STOP;
}

static void pulse(uint32_t us) {
    TIM1->ARR = us + 1;
    TIM1->CNT = 0;
    TIM1->EGR = TIM_EGR_UG;
    TIM1->SR = 0;
    TIM1->CCMR1 = 7u << 4; /* PWM2, inverted: high at CNT=0, low after 2 */
    TIM1->CR1 = TIM_CR1_OPM | TIM_CR1_CEN;
    while (TIM1->CR1 & TIM_CR1_CEN) {}
    blank();
}

int main(void) {
    HAL_Init();
    gpio_init();
    clock_init();
    panel_status.core_hz = SystemCoreClock;
    CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk;
    DWT->CYCCNT = 0;
    DWT->CTRL |= DWT_CTRL_CYCCNTENA_Msk;
    pulse_init();
#if PANEL_SHIFT_EN
    GPIOB->BSRR = 1u << 13;
#endif
    shift_latch(0); /* clear before first exposure */
    uint32_t frame_start = DWT->CYCCNT;
    for (;;) {
        for (uint32_t row = 0; row < PANEL_SCAN_ROWS; ++row) {
            uint32_t slot_start = DWT->CYCCNT;
            blank();
            uint32_t address = (row & 3u) | ((row & 28u) << 8);
            GPIOB->BSRR = address | ((PANEL_ADDRESS_MASK & ~address) << 16);
            panel_status.row = row;
            wait_cycles(128);
            shift_latch(panel_status.enable ? panel_status.rgb_mask & PANEL_RGB_MASK : 0);
            uint32_t on = panel_status.on_us;
            if (on > 100u) on = 100u; /* low-load bring-up ceiling */
            if (panel_status.enable && on) pulse(on);
            while ((uint32_t)(DWT->CYCCNT - slot_start) < PANEL_ROW_US * 64u) {}
        }
        ++panel_status.frames;
        uint32_t now = DWT->CYCCNT;
        panel_status.last_frame_cycles = now - frame_start;
        frame_start = now;
    }
}
