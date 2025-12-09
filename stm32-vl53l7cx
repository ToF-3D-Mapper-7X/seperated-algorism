#include "stm32f1xx_hal.h"
#include <stdio.h>
#include <string.h>
#include "vl53l7cx_api.h"
#include "platform.h"


I2C_HandleTypeDef  hi2c1;
UART_HandleTypeDef huart3;

/* VL53 상태 플래그들 */
uint8_t  g_is_alive_status = 255;
uint8_t  g_alive_flag      = 0;
uint8_t  g_init_status     = 255;
uint8_t  g_ready           = 0;
uint8_t  g_status          = 255;
uint8_t  g_attempts        = 0;


volatile uint8_t g_rx_byte   = 0;
volatile uint8_t g_cmd_flag  = 0;
volatile uint8_t g_rx_state = 0;

int _write(int file, char *ptr, int len)
{
    (void)file;
    HAL_UART_Transmit(&huart3, (uint8_t*)ptr, (uint16_t)len, 100);
    return len;
}



static void SystemClock_Config(void);
static void MX_GPIO_Init(void);
static void MX_I2C1_Init(void);
static void MX_USART3_UART_Init(void);
static void SensorHardReset(VL53L7CX_Platform *pf);
static void print_8x8_csv(const VL53L7CX_ResultsData *r);



int main(void)
{
    HAL_Init();
    SystemClock_Config();
    MX_GPIO_Init();
    MX_I2C1_Init();
    MX_USART3_UART_Init();

    printf("\r\n=== VL53L7CX 8x8===\r\n");


    VL53L7CX_Platform platform = {
        .hi2c     = &hi2c1,
        .address  = VL53L7CX_I2C_ADDR,
        .lpn_port = GPIOA,
        .lpn_pin  = GPIO_PIN_10
    };

    VL53L7CX_Configuration dev;
    VL53L7CX_ResultsData   results;


    for (g_attempts = 0; g_attempts < 2; ++g_attempts)
    {
        SensorHardReset(&platform);

        memset(&dev, 0, sizeof(dev));
        memset(&results, 0, sizeof(results));
        dev.platform = platform;

        g_status = vl53l7cx_is_alive(&dev, &g_alive_flag);
        g_is_alive_status = g_status;
        printf("is_alive status=%u, alive=%u (try %u)\r\n",
               g_status, g_alive_flag, g_attempts + 1);

        if (g_status || !g_alive_flag)
        {
            /* 실패하면 다시 시도 */
            continue;
        }

        g_init_status = vl53l7cx_init(&dev);
        printf("init status=%u (try %u)\r\n",
               g_init_status, g_attempts + 1);

        if (g_init_status == 0) break;
    }

    if (g_init_status != 0)
    {
        printf("ERROR: VL53L7CX init failed. I2C 풀업/전원/배선 확인 필수.\r\n");
        while (1)
        {
            HAL_Delay(500);
        }
    }

    /* ====== 해상도/주파수 설정 후 측정 시작 ====== */
    g_status = vl53l7cx_set_resolution(&dev, VL53L7CX_RESOLUTION_8X8);
    printf("set_resolution status=%u\r\n", g_status);

    g_status = vl53l7cx_set_ranging_frequency_hz(&dev, 5);   // 내부는 계속 5Hz로 측정
    printf("set_freq status=%u\r\n", g_status);

    g_status = vl53l7cx_start_ranging(&dev);
    printf("start_ranging status=%u\r\n", g_status);

    if (g_status)
    {
        printf("ERROR: start_ranging 실패\r\n");
        while (1) HAL_Delay(1000);
    }

    printf("VL53L7CX start OK. Send 'MeS' from Raspberry Pi to get one frame.\r\n");


    while (1)
    {

        if (g_cmd_flag)
        {
            g_cmd_flag = 0;
            uint8_t  ready = 0;
            uint32_t tries = 0;
            do
            {
                g_status = vl53l7cx_check_data_ready(&dev, &ready);
                HAL_Delay(5);
                tries++;
            } while (!g_status && !ready && (tries < 40));

            if (!g_status && ready)
            {
                g_status = vl53l7cx_get_ranging_data(&dev, &results);
                if (!g_status)
                {
                    print_8x8_csv(&results);
                }
                else
                {
                    printf("ERR:get_ranging_data status=%u\r\n", g_status);
                }
            }
            else
            {
                printf("ERR:no_data status=%u, ready=%u, tries=%lu\r\n",
                       g_status, ready, (unsigned long)tries);
            }
        }


        HAL_Delay(5);
    }
}

/* === 센서 하드 리셋 & 부팅 대기 === */
static void SensorHardReset(VL53L7CX_Platform *pf)
{
    VL53L7CX_LPn_Low(pf);
    HAL_Delay(10);      /* Low 유지 */
    VL53L7CX_LPn_High(pf);
    HAL_Delay(50);      /* 부팅 여유 시간 */
}

/* === 8x8 전체를 CSV 한 줄로 전송 ===*/
static void print_8x8_csv(const VL53L7CX_ResultsData *r)
{
    for (int i = 0; i < 64; i++)
    {
        uint16_t d = r->distance_mm[i];
        if (i < 63)
            printf("%u,", d);
        else
            printf("%u\r\n", d);
    }
}


static void SystemClock_Config(void)
{
    RCC_OscInitTypeDef RCC_OscInitStruct = {0};
    RCC_ClkInitTypeDef RCC_ClkInitStruct = {0};


    RCC_OscInitStruct.OscillatorType      = RCC_OSCILLATORTYPE_HSI;
    RCC_OscInitStruct.HSIState            = RCC_HSI_ON;
    RCC_OscInitStruct.HSICalibrationValue = RCC_HSICALIBRATION_DEFAULT;
    RCC_OscInitStruct.PLL.PLLState        = RCC_PLL_NONE;
    if (HAL_RCC_OscConfig(&RCC_OscInitStruct) != HAL_OK)
    {
        while (1);
    }

    RCC_ClkInitStruct.ClockType      = RCC_CLOCKTYPE_HCLK |
                                       RCC_CLOCKTYPE_SYSCLK |
                                       RCC_CLOCKTYPE_PCLK1 |
                                       RCC_CLOCKTYPE_PCLK2;
    RCC_ClkInitStruct.SYSCLKSource   = RCC_SYSCLKSOURCE_HSI;
    RCC_ClkInitStruct.AHBCLKDivider  = RCC_SYSCLK_DIV1;
    RCC_ClkInitStruct.APB1CLKDivider = RCC_HCLK_DIV1;
    RCC_ClkInitStruct.APB2CLKDivider = RCC_HCLK_DIV1;

    if (HAL_RCC_ClockConfig(&RCC_ClkInitStruct, FLASH_LATENCY_0) != HAL_OK)
    {
        while (1);
    }
}

static void MX_GPIO_Init(void)
{
    __HAL_RCC_GPIOA_CLK_ENABLE();
    __HAL_RCC_GPIOB_CLK_ENABLE();
    __HAL_RCC_AFIO_CLK_ENABLE();


    __HAL_AFIO_REMAP_I2C1_ENABLE();

    GPIO_InitTypeDef GPIO_InitStruct = {0};


    GPIO_InitStruct.Pin   = GPIO_PIN_10;
    GPIO_InitStruct.Mode  = GPIO_MODE_OUTPUT_PP;
    GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;
    HAL_GPIO_Init(GPIOA, &GPIO_InitStruct);

    HAL_GPIO_WritePin(GPIOA, GPIO_PIN_10, GPIO_PIN_SET); /* 기본 ON */
}

static void MX_I2C1_Init(void)
{
    __HAL_RCC_I2C1_CLK_ENABLE();

    GPIO_InitTypeDef GPIO_InitStruct = {0};

    GPIO_InitStruct.Pin   = GPIO_PIN_8 | GPIO_PIN_9;
    GPIO_InitStruct.Mode  = GPIO_MODE_AF_OD;
    GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_HIGH;
    HAL_GPIO_Init(GPIOB, &GPIO_InitStruct);

    hi2c1.Instance             = I2C1;
    hi2c1.Init.ClockSpeed      = 100000;
    hi2c1.Init.DutyCycle       = I2C_DUTYCYCLE_2;
    hi2c1.Init.OwnAddress1     = 0;
    hi2c1.Init.AddressingMode  = I2C_ADDRESSINGMODE_7BIT;
    hi2c1.Init.DualAddressMode = I2C_DUALADDRESS_DISABLE;
    hi2c1.Init.OwnAddress2     = 0;
    hi2c1.Init.GeneralCallMode = I2C_GENERALCALL_DISABLE;
    hi2c1.Init.NoStretchMode   = I2C_NOSTRETCH_DISABLE;

    if (HAL_I2C_Init(&hi2c1) != HAL_OK)
    {
        while (1);
    }
}


static void MX_USART3_UART_Init(void)
{
    __HAL_RCC_USART3_CLK_ENABLE();
    __HAL_RCC_GPIOB_CLK_ENABLE();

    GPIO_InitTypeDef GPIO_InitStruct = {0};


    GPIO_InitStruct.Pin   = GPIO_PIN_10;
    GPIO_InitStruct.Mode  = GPIO_MODE_AF_PP;
    GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_HIGH;
    HAL_GPIO_Init(GPIOB, &GPIO_InitStruct);


    GPIO_InitStruct.Pin  = GPIO_PIN_11;
    GPIO_InitStruct.Mode = GPIO_MODE_INPUT;
    GPIO_InitStruct.Pull = GPIO_NOPULL;
    HAL_GPIO_Init(GPIOB, &GPIO_InitStruct);

    huart3.Instance        = USART3;
    huart3.Init.BaudRate   = 115200;
    huart3.Init.WordLength = UART_WORDLENGTH_8B;
    huart3.Init.StopBits   = UART_STOPBITS_1;
    huart3.Init.Parity     = UART_PARITY_NONE;
    huart3.Init.Mode       = UART_MODE_TX_RX;
    huart3.Init.HwFlowCtl  = UART_HWCONTROL_NONE;
    huart3.Init.OverSampling = UART_OVERSAMPLING_16;

    if (HAL_UART_Init(&huart3) != HAL_OK)
    {
        while (1);
    }

    /* ★ USART3 RX 인터럽트 설정 */
    HAL_NVIC_SetPriority(USART3_IRQn, 0, 0);
    HAL_NVIC_EnableIRQ(USART3_IRQn);


    HAL_UART_Receive_IT(&huart3, (uint8_t *)&g_rx_byte, 1);
}


void HAL_UART_RxCpltCallback(UART_HandleTypeDef *huart)
{
    if (huart->Instance == USART3)
    {
        switch (g_rx_state)
        {
            case 0:
                if (g_rx_byte == 'M')
                    g_rx_state = 1;
                else
                    g_rx_state = 0;
                break;

            case 1:
                if (g_rx_byte == 'e')
                    g_rx_state = 2;
                else
                    g_rx_state = 0;
                break;

            case 2:
                if (g_rx_byte == 'S')
                {
                    g_cmd_flag = 1;
                }
                g_rx_state = 0;
                break;
        }


        HAL_UART_Receive_IT(&huart3, (uint8_t *)&g_rx_byte, 1);
    }
}

