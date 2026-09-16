"""
Hidden tests for verifying the Nucleo-H745ZI board support package fix.

This test suite verifies:
1. The core bug fix: setbits = 0 initialization in stm32_adc.c
2. The new driver files exist and have proper structure
3. The pysim_cm7 configuration exists with proper settings

These tests are deterministic and do not require actual hardware.

Test behavior:
- When fix.patch is applied to /workspace: ALL tests should PASS
- When fix.patch is NOT applied to /workspace: tests should FAIL
"""

import os
import re
import pytest

# Base paths - tests run from /workspace and check /workspace for the fix
WORKSPACE = "/workspace"


class TestCoreBugFix:
    """Tests for the core bug fix: uninitialized variable in stm32_adc.c"""

    def test_setbits_initialization(self):
        """
        Verify that the setbits variable is properly initialized to 0
        in arch/arm/src/stm32h7/stm32_adc.c
        
        This is the core bug fix - without initialization, the variable
        contains garbage values causing undefined behavior during ADC clock setup.
        """
        adc_file = os.path.join(WORKSPACE, "arch/arm/src/stm32h7/stm32_adc.c")
        assert os.path.exists(adc_file), f"ADC file not found: {adc_file}"

        with open(adc_file, "r") as f:
            content = f.read()

        # Check for the proper initialization pattern: uint32_t setbits = 0;
        # This is the core fix - the variable must be initialized to 0
        pattern = r'uint32_t\s+setbits\s*=\s*0\s*;'
        match = re.search(pattern, content)
        assert match is not None, (
            "Core bug fix not found: 'uint32_t setbits = 0;' initialization "
            "is missing in stm32_adc.c. This causes undefined behavior."
        )


class TestNewDriverFiles:
    """Tests for the new driver files added by the fix"""

    def test_adc_driver_exists(self):
        """Verify the new ADC driver file exists"""
        adc_driver = os.path.join(
            WORKSPACE,
            "boards/arm/stm32h7/nucleo-h745zi/src/stm32_adc.c"
        )
        assert os.path.exists(adc_driver), f"ADC driver not found: {adc_driver}"

        # Verify it has proper structure (license header, includes, function)
        with open(adc_driver, "r") as f:
            content = f.read()

        assert "Licensed to the Apache Software Foundation" in content
        assert "stm32_adc_setup" in content

    def test_gpio_driver_exists(self):
        """Verify the new GPIO driver file exists"""
        gpio_driver = os.path.join(
            WORKSPACE,
            "boards/arm/stm32h7/nucleo-h745zi/src/stm32_gpio.c"
        )
        assert os.path.exists(gpio_driver), f"GPIO driver not found: {gpio_driver}"

        with open(gpio_driver, "r") as f:
            content = f.read()

        assert "Licensed to the Apache Software Foundation" in content
        assert "stm32_gpio_initialize" in content

    def test_pwm_driver_exists(self):
        """Verify the new PWM driver file exists"""
        pwm_driver = os.path.join(
            WORKSPACE,
            "boards/arm/stm32h7/nucleo-h745zi/src/stm32_pwm.c"
        )
        assert os.path.exists(pwm_driver), f"PWM driver not found: {pwm_driver}"

        with open(pwm_driver, "r") as f:
            content = f.read()

        assert "Licensed to the Apache Software Foundation" in content
        assert "stm32_pwm_setup" in content

    def test_qencoder_driver_exists(self):
        """Verify the new QEncoder driver file exists"""
        qencoder_driver = os.path.join(
            WORKSPACE,
            "boards/arm/stm32h7/nucleo-h745zi/src/stm32_qencoder.c"
        )
        assert os.path.exists(qencoder_driver), f"QEncoder driver not found: {qencoder_driver}"

        with open(qencoder_driver, "r") as f:
            content = f.read()

        assert "Licensed to the Apache Software Foundation" in content
        assert "stm32_qencoder_initialize" in content
        assert "nuttx/sensors/qencoder.h" in content

    def test_usb_driver_exists(self):
        """Verify the new USB driver file exists"""
        usb_driver = os.path.join(
            WORKSPACE,
            "boards/arm/stm32h7/nucleo-h745zi/src/stm32_usb.c"
        )
        assert os.path.exists(usb_driver), f"USB driver not found: {usb_driver}"

        with open(usb_driver, "r") as f:
            content = f.read()

        assert "Licensed to the Apache Software Foundation" in content
        assert "stm32_usbhost_initialize" in content


class TestPysimConfig:
    """Tests for the new pysim_cm7 configuration"""

    def test_pysim_cm7_defconfig_exists(self):
        """Verify the pysim_cm7 defconfig file exists"""
        defconfig = os.path.join(
            WORKSPACE,
            "boards/arm/stm32h7/nucleo-h745zi/configs/pysim_cm7/defconfig"
        )
        assert os.path.exists(defconfig), f"pysim_cm7 defconfig not found: {defconfig}"

    def test_pysim_cm7_has_adc_config(self):
        """Verify pysim_cm7 config enables ADC"""
        defconfig = os.path.join(
            WORKSPACE,
            "boards/arm/stm32h7/nucleo-h745zi/configs/pysim_cm7/defconfig"
        )
        with open(defconfig, "r") as f:
            content = f.read()

        assert "CONFIG_ADC=y" in content, "ADC not enabled in pysim_cm7 config"
        assert "CONFIG_STM32H7_ADC1=y" in content

    def test_pysim_cm7_has_gpio_config(self):
        """Verify pysim_cm7 config enables GPIO"""
        defconfig = os.path.join(
            WORKSPACE,
            "boards/arm/stm32h7/nucleo-h745zi/configs/pysim_cm7/defconfig"
        )
        with open(defconfig, "r") as f:
            content = f.read()

        assert "CONFIG_DEV_GPIO=y" in content, "GPIO not enabled in pysim_cm7 config"

    def test_pysim_cm7_has_pwm_config(self):
        """Verify pysim_cm7 config enables PWM"""
        defconfig = os.path.join(
            WORKSPACE,
            "boards/arm/stm32h7/nucleo-h745zi/configs/pysim_cm7/defconfig"
        )
        with open(defconfig, "r") as f:
            content = f.read()

        assert "CONFIG_PWM=y" in content, "PWM not enabled in pysim_cm7 config"

    def test_pysim_cm7_has_qencoder_config(self):
        """Verify pysim_cm7 config enables QEncoder"""
        defconfig = os.path.join(
            WORKSPACE,
            "boards/arm/stm32h7/nucleo-h745zi/configs/pysim_cm7/defconfig"
        )
        with open(defconfig, "r") as f:
            content = f.read()

        assert "CONFIG_SENSORS_QENCODER=y" in content, "QEncoder not enabled"

    def test_pysim_cm7_has_usb_config(self):
        """Verify pysim_cm7 config enables USB"""
        defconfig = os.path.join(
            WORKSPACE,
            "boards/arm/stm32h7/nucleo-h745zi/configs/pysim_cm7/defconfig"
        )
        with open(defconfig, "r") as f:
            content = f.read()

        assert "CONFIG_USBHOST=y" in content, "USBHOST not enabled in pysim_cm7 config"
        assert "CONFIG_STM32H7_OTGFS=y" in content


class TestBringupIntegration:
    """Tests for the integration in stm32_bringup.c"""

    def test_bringup_includes_adc_init(self):
        """Verify stm32_bringup.c includes ADC initialization"""
        bringup_file = os.path.join(
            WORKSPACE,
            "boards/arm/stm32h7/nucleo-h745zi/src/stm32_bringup.c"
        )
        with open(bringup_file, "r") as f:
            content = f.read()

        assert "stm32_adc_setup" in content, "ADC setup not called in bringup"

    def test_bringup_includes_gpio_init(self):
        """Verify stm32_bringup.c includes GPIO initialization"""
        bringup_file = os.path.join(
            WORKSPACE,
            "boards/arm/stm32h7/nucleo-h745zi/src/stm32_bringup.c"
        )
        with open(bringup_file, "r") as f:
            content = f.read()

        assert "stm32_gpio_initialize" in content, "GPIO init not called in bringup"

    def test_bringup_includes_pwm_init(self):
        """Verify stm32_bringup.c includes PWM initialization"""
        bringup_file = os.path.join(
            WORKSPACE,
            "boards/arm/stm32h7/nucleo-h745zi/src/stm32_bringup.c"
        )
        with open(bringup_file, "r") as f:
            content = f.read()

        assert "stm32_pwm_setup" in content, "PWM setup not called in bringup"

    def test_bringup_includes_qencoder_init(self):
        """Verify stm32_bringup.c includes QEncoder initialization"""
        bringup_file = os.path.join(
            WORKSPACE,
            "boards/arm/stm32h7/nucleo-h745zi/src/stm32_bringup.c"
        )
        with open(bringup_file, "r") as f:
            content = f.read()

        assert "stm32_qencoder_initialize" in content, "QEncoder init not called"

    def test_bringup_includes_usb_init(self):
        """Verify stm32_bringup.c includes USB initialization"""
        bringup_file = os.path.join(
            WORKSPACE,
            "boards/arm/stm32h7/nucleo-h745zi/src/stm32_bringup.c"
        )
        with open(bringup_file, "r") as f:
            content = f.read()

        assert "stm32_usbhost_initialize" in content, "USB init not called in bringup"


class TestMakefileUpdates:
    """Tests for the Makefile updates to include new drivers"""

    def test_makefile_includes_adc(self):
        """Verify Makefile includes ADC driver compilation"""
        makefile = os.path.join(
            WORKSPACE,
            "boards/arm/stm32h7/nucleo-h745zi/src/Makefile"
        )
        with open(makefile, "r") as f:
            content = f.read()

        assert "stm32_adc.c" in content
        assert "CONFIG_ADC" in content

    def test_makefile_includes_gpio(self):
        """Verify Makefile includes GPIO driver compilation"""
        makefile = os.path.join(
            WORKSPACE,
            "boards/arm/stm32h7/nucleo-h745zi/src/Makefile"
        )
        with open(makefile, "r") as f:
            content = f.read()

        assert "stm32_gpio.c" in content
        assert "CONFIG_DEV_GPIO" in content

    def test_makefile_includes_pwm(self):
        """Verify Makefile includes PWM driver compilation"""
        makefile = os.path.join(
            WORKSPACE,
            "boards/arm/stm32h7/nucleo-h745zi/src/Makefile"
        )
        with open(makefile, "r") as f:
            content = f.read()

        assert "stm32_pwm.c" in content
        assert "CONFIG_PWM" in content

    def test_makefile_includes_qencoder(self):
        """Verify Makefile includes QEncoder driver compilation"""
        makefile = os.path.join(
            WORKSPACE,
            "boards/arm/stm32h7/nucleo-h745zi/src/Makefile"
        )
        with open(makefile, "r") as f:
            content = f.read()

        assert "stm32_qencoder.c" in content
        assert "CONFIG_SENSORS_QENCODER" in content

    def test_makefile_includes_usb(self):
        """Verify Makefile includes USB driver compilation"""
        makefile = os.path.join(
            WORKSPACE,
            "boards/arm/stm32h7/nucleo-h745zi/src/Makefile"
        )
        with open(makefile, "r") as f:
            content = f.read()

        assert "stm32_usb.c" in content
        assert "CONFIG_STM32H7_OTGFS" in content


class TestBoardHeaderUpdates:
    """Tests for the board.h header file updates"""

    def test_board_h_has_adc_definitions(self):
        """Verify board.h has ADC pin definitions"""
        board_h = os.path.join(
            WORKSPACE,
            "boards/arm/stm32h7/nucleo-h745zi/include/board.h"
        )
        with open(board_h, "r") as f:
            content = f.read()

        assert "GPIO_ADC" in content, "ADC definitions missing from board.h"

    def test_board_h_has_tim_definitions(self):
        """Verify board.h has TIM definitions for PWM/QEncoder"""
        board_h = os.path.join(
            WORKSPACE,
            "boards/arm/stm32h7/nucleo-h745zi/include/board.h"
        )
        with open(board_h, "r") as f:
            content = f.read()

        assert "GPIO_TIM" in content, "TIM definitions missing from board.h"

    def test_board_h_has_otg_definitions(self):
        """Verify board.h has OTGFS definitions"""
        board_h = os.path.join(
            WORKSPACE,
            "boards/arm/stm32h7/nucleo-h745zi/include/board.h"
        )
        with open(board_h, "r") as f:
            content = f.read()

        assert "GPIO_OTGFS" in content, "OTGFS definitions missing from board.h"
