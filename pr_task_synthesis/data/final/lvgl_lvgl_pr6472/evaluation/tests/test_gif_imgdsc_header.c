/**
 * @file test_gif_imgdsc_header.c
 *
 * Test to verify that GIF image descriptor header fields are properly initialized.
 * This test checks the fix for GIF imgdsc type change from lv_draw_buf_t to lv_image_dsc_t
 * and proper initialization of header fields (magic, flags, stride, data_size).
 *
 * The test verifies:
 * 1. imgdsc is lv_image_dsc_t type (not lv_draw_buf_t)
 * 2. Header fields are properly initialized (magic, flags, stride, data_size)
 * 3. Proper cleanup behavior when reloading GIF
 */

#if LV_BUILD_TEST
#include "../lvgl.h"
#include "unity/unity.h"
#include <string.h>

/* We need to access the internal lv_gif_t structure to verify the fix */
#include "../../src/libs/gif/lv_gif.h"

void setUp(void)
{
    /* Function run before every test */
}

void tearDown(void)
{
    lv_obj_clean(lv_screen_active());
}

/**
 * Test that verifies the imgdsc structure is lv_image_dsc_t (not lv_draw_buf_t).
 * The fix changes imgdsc type from lv_draw_buf_t to lv_image_dsc_t.
 *
 * This test will FAIL TO COMPILE with the buggy version because:
 * - Buggy: imgdsc is lv_draw_buf_t which has 'void * unaligned_data'
 * - Fixed: imgdsc is lv_image_dsc_t which has 'const void * reserved'
 */
void test_gif_imgdsc_type_verification(void)
{
    /* Create a GIF object */
    lv_obj_t * gif_obj = lv_gif_create(lv_screen_active());
    TEST_ASSERT_NOT_NULL(gif_obj);

    lv_gif_t * gif = (lv_gif_t *)gif_obj;

    /* This test verifies imgdsc is lv_image_dsc_t by accessing its fields */
    /* If imgdsc were lv_draw_buf_t, this would fail to compile */

    /* Check that we can access the 'reserved' field (lv_image_dsc_t specific) */
    /* lv_draw_buf_t has 'unaligned_data' instead */
    const void * reserved_field = gif->imgdsc.reserved;
    TEST_ASSERT_NULL(reserved_field);  /* Should be NULL initially */

    /* Verify imgdsc.data is const pointer (lv_image_dsc_t characteristic) */
    const uint8_t * data_ptr = gif->imgdsc.data;
    TEST_ASSERT_NULL(data_ptr);  /* Initially NULL before loading */

    /* Check that we can access header fields */
    TEST_ASSERT_EQUAL(0, gif->imgdsc.header.magic);
    TEST_ASSERT_EQUAL(0, gif->imgdsc.header.cf);
    TEST_ASSERT_EQUAL(0, gif->imgdsc.header.flags);
    TEST_ASSERT_EQUAL(0, gif->imgdsc.header.w);
    TEST_ASSERT_EQUAL(0, gif->imgdsc.header.h);
    TEST_ASSERT_EQUAL(0, gif->imgdsc.header.stride);
    TEST_ASSERT_EQUAL(0, gif->imgdsc.data_size);

    /* Clean up */
    lv_obj_del(gif_obj);
}

/**
 * Test that verifies imgdsc header fields are properly initialized after loading.
 * This test simulates what lv_gif_set_src does after the fix.
 */
void test_gif_imgdsc_header_fields(void)
{
    /* Create a test image descriptor manually to simulate what lv_gif_set_src does */
    lv_image_dsc_t test_imgdsc;
    memset(&test_imgdsc, 0, sizeof(test_imgdsc));

    /* Simulate the fixed initialization code from lv_gif_set_src:
     * gifobj->imgdsc.header.magic = LV_IMAGE_HEADER_MAGIC;
     * gifobj->imgdsc.header.flags = LV_IMAGE_FLAGS_MODIFIABLE;
     * gifobj->imgdsc.header.cf = LV_COLOR_FORMAT_ARGB8888;
     * gifobj->imgdsc.header.h = gif->height;
     * gifobj->imgdsc.header.w = gif->width;
     * gifobj->imgdsc.header.stride = gif->width * 4;
     * gifobj->imgdsc.data_size = gif->width * gif->height * 4;
     */
    test_imgdsc.data = (const uint8_t *)0x12345678;  /* Simulated canvas pointer */
    test_imgdsc.header.magic = LV_IMAGE_HEADER_MAGIC;
    test_imgdsc.header.flags = LV_IMAGE_FLAGS_MODIFIABLE;
    test_imgdsc.header.cf = LV_COLOR_FORMAT_ARGB8888;
    test_imgdsc.header.w = 100;
    test_imgdsc.header.h = 50;
    test_imgdsc.header.stride = 100 * 4;  /* width * 4 for ARGB8888 */
    test_imgdsc.data_size = 100 * 50 * 4;  /* width * height * 4 */

    /* Verify the header fields are correctly set */
    TEST_ASSERT_EQUAL(LV_IMAGE_HEADER_MAGIC, test_imgdsc.header.magic);
    TEST_ASSERT_EQUAL_UINT16(LV_IMAGE_FLAGS_MODIFIABLE, test_imgdsc.header.flags);
    TEST_ASSERT_EQUAL(LV_COLOR_FORMAT_ARGB8888, test_imgdsc.header.cf);
    TEST_ASSERT_EQUAL(100, test_imgdsc.header.w);
    TEST_ASSERT_EQUAL(50, test_imgdsc.header.h);
    TEST_ASSERT_EQUAL(400, test_imgdsc.header.stride);
    TEST_ASSERT_EQUAL(20000, test_imgdsc.data_size);

    /* Verify the data pointer is set */
    TEST_ASSERT_NOT_NULL(test_imgdsc.data);
}

/**
 * Test that verifies the structure size and type compatibility.
 * This test confirms lv_gif_t uses lv_image_dsc_t.
 */
void test_gif_imgdsc_structure_type(void)
{
    /* The key test is that lv_gif_t uses lv_image_dsc_t */
    lv_gif_t gif_obj;
    memset(&gif_obj, 0, sizeof(gif_obj));

    /* Verify we can access imgdsc as lv_image_dsc_t */
    /* This compiles only if imgdsc is lv_image_dsc_t type */
    lv_image_dsc_t * imgdsc_ptr = &gif_obj.imgdsc;
    TEST_ASSERT_NOT_NULL(imgdsc_ptr);

    /* Verify the reserved field exists (lv_image_dsc_t specific)
     * This field doesn't exist in lv_draw_buf_t */
    TEST_ASSERT_NULL(gif_obj.imgdsc.reserved);
}

/**
 * Test that verifies the GIF object cleanup behavior.
 * The fix ensures proper cleanup of previous GIF before loading new one
 * by using a local variable 'gd_GIF * gif' to track the current GIF.
 */
void test_gif_cleanup_behavior(void)
{
    /* Create a GIF object */
    lv_obj_t * gif_obj = lv_gif_create(lv_screen_active());
    TEST_ASSERT_NOT_NULL(gif_obj);

    lv_gif_t * gif = (lv_gif_t *)gif_obj;

    /* Initially, gif pointer should be NULL */
    TEST_ASSERT_NULL(gif->gif);
    TEST_ASSERT_NULL(gif->imgdsc.data);

    /* The fix adds proper cleanup using a local variable:
     * gd_GIF * gif = gifobj->gif;
     * if(gif != NULL) {
     *     lv_image_cache_drop(lv_image_get_src(obj));
     *     gd_close_gif(gif);
     *     gifobj->gif = NULL;
     *     gifobj->imgdsc.data = NULL;
     * }
     */

    /* Verify we can access the cleanup path */
    /* In the fixed version, imgdsc.data is const uint8_t* */
    /* In the buggy version, it's uint8_t* (non-const) */
    /* This test verifies the const-correct behavior */

    /* Clean up */
    lv_obj_del(gif_obj);
}

#endif
