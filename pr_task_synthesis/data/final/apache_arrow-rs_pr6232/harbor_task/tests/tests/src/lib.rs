//! Test harness for verifying the infinite loop fix in parquet column reader.
//!
//! This test verifies the fix in parquet/src/column/reader.rs that checks
//! if both records_read == 0 && levels_read == 0 after calling read_rep_levels,
//! and returns an error instead of looping infinitely.
//!
//! Run: cargo test

use bytes::Bytes;
use parquet::basic::Encoding;
use parquet::column::page::{Page, PageMetadata, PageReader};
use parquet::column::reader::{get_column_reader, get_typed_column_reader, ColumnReaderImpl};
use parquet::data_type::Int32Type;
use parquet::schema::types::{ColumnDescriptor, ColumnPath, Type as SchemaType};
use parquet::basic::{Repetition, Type as PhysicalType};
use parquet::errors::Result;
use std::sync::Arc;
use std::time::{Duration, Instant};

/// A page reader that returns a page with empty repetition level data
/// to trigger the infinite loop condition.
///
/// This simulates a corrupted Parquet file where a DataPage V2 has
/// rep_levels_byte_len = 0, which causes the repetition level decoder
/// to return (0, 0) from read_rep_levels, triggering the infinite loop
/// in the buggy code.
struct EmptyRepLevelPageReader {
    page_sent: bool,
}

impl EmptyRepLevelPageReader {
    fn new() -> Self {
        Self {
            page_sent: false,
        }
    }
}

impl Iterator for EmptyRepLevelPageReader {
    type Item = Result<Page>;

    fn next(&mut self) -> Option<Self::Item> {
        self.get_next_page().transpose()
    }
}

impl PageReader for EmptyRepLevelPageReader {
    fn get_next_page(&mut self) -> Result<Option<Page>> {
        if self.page_sent {
            return Ok(None);
        }
        self.page_sent = true;

        // Create a DataPage V2 with empty repetition level data (rep_levels_byte_len = 0)
        // This triggers the condition where read_rep_levels returns (0, 0)
        //
        // In the buggy code, this causes an infinite loop because:
        // 1. read_rep_levels returns (records_read=0, levels_read=0)
        // 2. The loop condition checks total_records_read < max_records (true)
        // 3. has_next() returns true because there's a page
        // 4. Loop continues with no progress
        //
        // The fix adds a check: if records_read == 0 && levels_read == 0, return error
        let buffer = vec![
            // Value data follows (plain encoded int32)
            0x00, 0x00, 0x00, 0x00,  // one int32 value = 0
        ];

        Ok(Some(Page::DataPageV2 {
            buf: Bytes::from(buffer),
            num_values: 1,
            encoding: Encoding::PLAIN,
            num_nulls: 0,
            num_rows: 1,
            def_levels_byte_len: 0,
            rep_levels_byte_len: 0,  // Empty repetition levels - this triggers the bug
            is_compressed: false,
            statistics: None,
        }))
    }

    fn peek_next_page(&mut self) -> Result<Option<PageMetadata>> {
        if self.page_sent {
            Ok(None)
        } else {
            Ok(Some(PageMetadata {
                num_rows: Some(1),
                num_levels: Some(1),
                is_dict: false,
            }))
        }
    }

    fn skip_next_page(&mut self) -> Result<()> {
        self.page_sent = true;
        Ok(())
    }
}

#[test]
fn test_zero_repetition_levels_returns_error() {
    println!("Running test: test_zero_repetition_levels_returns_error");

    // Create a column descriptor with max_rep_level > 0 (so repetition levels are expected)
    let primitive_type = SchemaType::primitive_type_builder("test_col", PhysicalType::INT32)
        .with_repetition(Repetition::REPEATED)  // REPEATED means max_rep_level > 0
        .build()
        .expect("Failed to build type");

    let desc = Arc::new(ColumnDescriptor::new(
        Arc::new(primitive_type),
        0,  // max_def_level
        1,  // max_rep_level - must be > 0 to trigger the bug
        ColumnPath::new(vec![]),
    ));

    // Use the page reader that returns pages with zero repetition levels
    let page_reader = Box::new(EmptyRepLevelPageReader::new());

    // Create the column reader
    let column_reader = get_column_reader(desc.clone(), page_reader);
    let mut typed_reader: ColumnReaderImpl<Int32Type> = get_typed_column_reader(column_reader);

    // Prepare output buffers
    let mut values = Vec::new();
    let mut def_levels = Vec::new();
    let mut rep_levels = Vec::new();

    // Try to read records - this should return an error, not loop infinitely
    // The fix checks if records_read == 0 && levels_read == 0 and returns an error
    let result = typed_reader.read_records(
        10,  // max_records
        Some(&mut def_levels),
        Some(&mut rep_levels),
        &mut values,
    );

    // With the fix, this should return an error about insufficient repetition levels
    // Without the fix, this would loop infinitely (timeout in test)
    assert!(result.is_err(), "Expected error when reading page with zero repetition levels, got Ok instead");

    let err = result.unwrap_err();
    let err_msg = format!("{}", err);

    // Verify the error message indicates the specific problem
    assert!(
        err_msg.contains("Insufficient repetition levels") || err_msg.contains("repetition levels"),
        "Error message should mention repetition levels, got: {}", err_msg
    );

    println!("  PASSED: Got expected error: {}", err_msg);
}

#[test]
fn test_zero_rep_levels_terminates_quickly() {
    println!("Running test: test_zero_rep_levels_terminates_quickly");

    let primitive_type = SchemaType::primitive_type_builder("test_col", PhysicalType::INT32)
        .with_repetition(Repetition::REPEATED)
        .build()
        .expect("Failed to build type");

    let desc = Arc::new(ColumnDescriptor::new(
        Arc::new(primitive_type),
        0,
        1,
        ColumnPath::new(vec![]),
    ));

    let page_reader = Box::new(EmptyRepLevelPageReader::new());
    let column_reader = get_column_reader(desc.clone(), page_reader);
    let mut typed_reader: ColumnReaderImpl<Int32Type> = get_typed_column_reader(column_reader);

    let mut values = Vec::new();
    let mut def_levels = Vec::new();
    let mut rep_levels = Vec::new();

    let start = Instant::now();

    let result = typed_reader.read_records(
        100,  // Try to read many records - would timeout without fix
        Some(&mut def_levels),
        Some(&mut rep_levels),
        &mut values,
    );

    let elapsed = start.elapsed();

    // The operation should complete quickly (within 1 second) because it should
    // return an error, not loop infinitely
    assert!(
        elapsed < Duration::from_secs(1),
        "Read operation took too long ({:?}), indicating possible infinite loop", elapsed
    );

    // Verify we got an error (not a successful read)
    assert!(
        result.is_err(),
        "Expected error for zero repetition levels, got Ok after {:?}", elapsed
    );

    println!("  PASSED: Operation terminated quickly ({:?}) with error", elapsed);
}
