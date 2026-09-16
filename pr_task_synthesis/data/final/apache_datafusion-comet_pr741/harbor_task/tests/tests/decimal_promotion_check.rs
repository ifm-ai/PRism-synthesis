// Test to verify that low-precision Decimal128 operations do NOT trigger unnecessary Decimal256 promotion
// This test detects the optimization fix in planner.rs
//
// Buggy code: Always promotes Decimal128 + Decimal128 to Decimal256 internally (has Cast nodes)
// Fixed code: Only promotes when precision would overflow (no unnecessary Cast nodes)
//
// This test will:
// - FAIL on buggy code (finds unnecessary Cast to Decimal256)
// - PASS on fixed code (no unnecessary Decimal256 casts)

use arrow_schema::{DataType, DECIMAL128_MAX_PRECISION};
use datafusion::physical_plan::{ExecutionPlan, projection::ProjectionExec};
use datafusion::physical_expr::expressions::{BinaryExpr, CastExpr};
use datafusion_comet_proto::{
    spark_expression::{self, expr::ExprStruct},
    spark_operator::{self, operator::OpStruct, Operator},
};
use comet::execution::datafusion::planner::PhysicalPlanner;
use datafusion_comet_spark_expr::Cast;
use std::sync::Arc;

/// Recursively search for Cast expressions to Decimal256 in the physical plan
/// Returns the count of Decimal256 casts found
fn count_decimal256_casts(plan: &Arc<dyn ExecutionPlan>) -> usize {
    let mut count = 0;
    
    // Check if this is a ProjectionExec
    if let Some(projection) = plan.as_any().downcast_ref::<ProjectionExec>() {
        for expr in projection.expr() {
            count += count_decimal256_in_expr(&expr.0);
        }
    }

    // Check children recursively
    for child in plan.children() {
        count += count_decimal256_casts(&child);
    }

    count
}

/// Count Cast to Decimal256 in an expression tree
fn count_decimal256_in_expr(expr: &Arc<dyn datafusion_physical_expr::PhysicalExpr>) -> usize {
    let mut count = 0;

    // Check for our custom Cast expression (from spark-expr crate)
    if let Some(cast) = expr.as_any().downcast_ref::<Cast>() {
        if matches!(cast.data_type, DataType::Decimal256(_, _)) {
            count += 1;
        }
        // Recurse into the child expression
        count += count_decimal256_in_expr(&cast.child);
    }

    // Check for DataFusion's CastExpr
    if let Some(cast_expr) = expr.as_any().downcast_ref::<CastExpr>() {
        if matches!(cast_expr.cast_type(), DataType::Decimal256(_, _)) {
            count += 1;
        }
    }

    // Recurse into BinaryExpr children
    if let Some(binary) = expr.as_any().downcast_ref::<BinaryExpr>() {
        count += count_decimal256_in_expr(binary.left());
        count += count_decimal256_in_expr(binary.right());
    }

    count
}

/// Helper to create Decimal128 DataType for proto
fn decimal_type(p: i32, s: i32) -> spark_expression::DataType {
    spark_expression::DataType {
        type_id: spark_expression::data_type::DataTypeId::Decimal as i32,
        type_info: Some(Box::new(spark_expression::data_type::DataTypeInfo {
            datatype_struct: Some(spark_expression::data_type::data_type_info::DatatypeStruct::Decimal(
                spark_expression::data_type::DecimalInfo {
                    precision: p,
                    scale: s,
                },
            )),
        })),
    }
}

#[test]
fn test_low_precision_decimal_addition_no_unnecessary_decimal256_promotion() {
    use std::cmp::max;

    // Low precision decimals: precision=10, scale=2
    // With the fix: max(s1, s2) + max(p1 - s1, p2 - s2) = 2 + max(8, 8) = 10 < 38
    // So NO Decimal256 promotion should occur
    let p1: u8 = 10;
    let s1: i8 = 2;
    let p2: u8 = 10;
    let s2: i8 = 2;

    // Verify the boundary calculation matches the fix condition
    let boundary_value = max(s1, s2) as u8 + max(p1 - s1 as u8, p2 - s2 as u8);
    assert!(
        boundary_value < DECIMAL128_MAX_PRECISION,
        "Test setup error: boundary {} should be < {} for low precision test",
        boundary_value,
        DECIMAL128_MAX_PRECISION
    );

    // Create scan with two Decimal128 columns
    let op_scan = Operator {
        children: vec![],
        op_struct: Some(OpStruct::Scan(spark_operator::Scan {
            fields: vec![
                decimal_type(p1 as i32, s1 as i32),
                decimal_type(p2 as i32, s2 as i32),
            ],
        })),
    };

    // Create addition expression: col0 + col1
    let left = spark_expression::Expr {
        expr_struct: Some(ExprStruct::Bound(spark_expression::BoundReference {
            index: 0,
            datatype: Some(decimal_type(p1 as i32, s1 as i32)),
        })),
    };
    let right = spark_expression::Expr {
        expr_struct: Some(ExprStruct::Bound(spark_expression::BoundReference {
            index: 1,
            datatype: Some(decimal_type(p2 as i32, s2 as i32)),
        })),
    };

    let add_expr = spark_expression::Expr {
        expr_struct: Some(ExprStruct::Add(Box::new(spark_expression::Add {
            left: Some(Box::new(left)),
            right: Some(Box::new(right)),
            fail_on_error: false,
            return_type: Some(decimal_type(11, 2)),
        }))),
    };

    // Create projection with the addition
    let op = Operator {
        children: vec![op_scan],
        op_struct: Some(OpStruct::Projection(spark_operator::Projection {
            project_list: vec![add_expr],
        })),
    };

    let planner = PhysicalPlanner::default();
    let (_scans, plan) = planner.create_plan(&op, &mut vec![])
        .expect("Should create physical plan");

    // KEY TEST: Count Cast to Decimal256 in the plan
    // 
    // BUGGY CODE BEHAVIOR:
    // - The buggy planner.rs always creates Cast to Decimal256 for Plus/Minus/Multiply/Modulo
    // - We expect to find 2 casts: left cast to Decimal256 and right cast to Decimal256
    // - This test will find those Casts and FAIL
    //
    // FIXED CODE BEHAVIOR:
    // - The fixed planner.rs only creates Cast to Decimal256 when precision would overflow
    // - For low-precision (10,2) + (10,2), boundary=10 < 38, so no Cast is created
    // - This test will find 0 Decimal256 casts and PASS
    
    let cast_count = count_decimal256_casts(&plan);

    assert_eq!(
        cast_count, 0,
        "BUG DETECTED: Low-precision Decimal128({},{}) + Decimal128({},{}) created {} unnecessary Decimal256 cast(s). \
         Boundary value {} is less than DECIMAL128_MAX_PRECISION ({}), so the optimization should \
         keep operations in Decimal128 without promotion to Decimal256. \
         This indicates the buggy code path that always promotes to Decimal256.",
        p1, s1, p2, s2, cast_count, boundary_value, DECIMAL128_MAX_PRECISION
    );
}
