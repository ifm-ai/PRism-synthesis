#!/usr/bin/env bash
# NOTE: do NOT use set -e — the script must capture RC=$? explicitly without premature exit.
set -uo pipefail

# openenv: resolve_paths
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
TEST_PATCH_PATH="$SCRIPT_DIR/test.patch"
TESTS_DIR="$SCRIPT_DIR/tests"
WORKSPACE_DIR="/workspace"

# openenv: activate_runtime
# No activation command needed - .NET SDK is system-level install
# activation_command from environment_request.json is empty

# openenv: install_test_only_extras
# No extra packages needed - test uses inline compilation without external dependencies

# openenv: prepare_hidden_assets
# Create a temporary directory for the test project
TEMP_TEST_DIR=$(mktemp -d)

# Copy source files from workspace
# NumberListAlignment.cs only exists in fixed code - this is the key test
NUMBER_LIST_ALIGNMENT_SRC="$WORKSPACE_DIR/FracturedJson/NumberListAlignment.cs"

# Copy other required source files from FracturedJson
cp "$WORKSPACE_DIR/FracturedJson/EolStyle.cs" "$TEMP_TEST_DIR/"
cp "$WORKSPACE_DIR/FracturedJson/CommentPolicy.cs" "$TEMP_TEST_DIR/"
cp "$WORKSPACE_DIR/FracturedJson/FracturedJsonOptions.cs" "$TEMP_TEST_DIR/"
cp "$WORKSPACE_DIR/FracturedJson/JsonItemType.cs" "$TEMP_TEST_DIR/"
cp "$WORKSPACE_DIR/FracturedJson/JsonItem.cs" "$TEMP_TEST_DIR/"
cp "$WORKSPACE_DIR/FracturedJson/FracturedJsonException.cs" "$TEMP_TEST_DIR/"
cp "$WORKSPACE_DIR/FracturedJson/Formatter.cs" "$TEMP_TEST_DIR/"

# Copy subdirectory files
mkdir -p "$TEMP_TEST_DIR/Tokenizing"
cp "$WORKSPACE_DIR/FracturedJson/Tokenizing/InputPosition.cs" "$TEMP_TEST_DIR/Tokenizing/"
cp "$WORKSPACE_DIR/FracturedJson/Tokenizing/JsonToken.cs" "$TEMP_TEST_DIR/Tokenizing/"
cp "$WORKSPACE_DIR/FracturedJson/Tokenizing/TokenScanner.cs" "$TEMP_TEST_DIR/Tokenizing/"
cp "$WORKSPACE_DIR/FracturedJson/Tokenizing/ScannerState.cs" "$TEMP_TEST_DIR/Tokenizing/"
cp "$WORKSPACE_DIR/FracturedJson/Tokenizing/TokenType.cs" "$TEMP_TEST_DIR/Tokenizing/"

mkdir -p "$TEMP_TEST_DIR/Formatting"
cp "$WORKSPACE_DIR/FracturedJson/Formatting/LineWriterBuffer.cs" "$TEMP_TEST_DIR/Formatting/"
cp "$WORKSPACE_DIR/FracturedJson/Formatting/IBuffer.cs" "$TEMP_TEST_DIR/Formatting/"
cp "$WORKSPACE_DIR/FracturedJson/Formatting/TableTemplate.cs" "$TEMP_TEST_DIR/Formatting/"
cp "$WORKSPACE_DIR/FracturedJson/Formatting/PaddedFormattingTokens.cs" "$TEMP_TEST_DIR/Formatting/"
cp "$WORKSPACE_DIR/FracturedJson/Formatting/NullBuffer.cs" "$TEMP_TEST_DIR/Formatting/"
cp "$WORKSPACE_DIR/FracturedJson/Formatting/BracketPaddingType.cs" "$TEMP_TEST_DIR/Formatting/"
cp "$WORKSPACE_DIR/FracturedJson/Formatting/StringBuilderBuffer.cs" "$TEMP_TEST_DIR/Formatting/"

mkdir -p "$TEMP_TEST_DIR/Parsing"
cp "$WORKSPACE_DIR/FracturedJson/Parsing/DomConverter.cs" "$TEMP_TEST_DIR/Parsing/"
cp "$WORKSPACE_DIR/FracturedJson/Parsing/Parser.cs" "$TEMP_TEST_DIR/Parsing/"

# Copy the test runner from tests directory
cp "$TESTS_DIR/TestRunner.cs" "$TEMP_TEST_DIR/"

# Create a file list for compilation
COMPILE_FILES="TestRunner.cs EolStyle.cs CommentPolicy.cs FracturedJsonOptions.cs JsonItemType.cs JsonItem.cs FracturedJsonException.cs Formatter.cs"
COMPILE_FILES="$COMPILE_FILES Tokenizing/InputPosition.cs Tokenizing/JsonToken.cs Tokenizing/TokenScanner.cs Tokenizing/ScannerState.cs Tokenizing/TokenType.cs"
COMPILE_FILES="$COMPILE_FILES Formatting/LineWriterBuffer.cs Formatting/IBuffer.cs Formatting/TableTemplate.cs Formatting/PaddedFormattingTokens.cs Formatting/NullBuffer.cs Formatting/BracketPaddingType.cs Formatting/StringBuilderBuffer.cs"
COMPILE_FILES="$COMPILE_FILES Parsing/DomConverter.cs Parsing/Parser.cs"

if [ -f "$NUMBER_LIST_ALIGNMENT_SRC" ]; then
    cp "$NUMBER_LIST_ALIGNMENT_SRC" "$TEMP_TEST_DIR/"
    COMPILE_FILES="$COMPILE_FILES NumberListAlignment.cs"
fi

# Create project file with all compile items
cat > "$TEMP_TEST_DIR/InlineTest.csproj" << 'EOF'
<Project Sdk="Microsoft.NET.Sdk">
    <PropertyGroup>
        <TargetFramework>net8.0</TargetFramework>
        <OutputType>Exe</OutputType>
        <ImplicitUsings>disable</ImplicitUsings>
        <Nullable>enable</Nullable>
        <RootNamespace>FracturedJson</RootNamespace>
        <EnableDefaultCompileItems>false</EnableDefaultCompileItems>
    </PropertyGroup>
    <ItemGroup>
EOF

for file in $COMPILE_FILES; do
    echo "        <Compile Include=\"$file\" />" >> "$TEMP_TEST_DIR/InlineTest.csproj"
done

cat >> "$TEMP_TEST_DIR/InlineTest.csproj" << 'EOF'
    </ItemGroup>
</Project>
EOF

# openenv: run_verification
cd "$TEMP_TEST_DIR"

echo ">>>>> Start Test Output"

# Run the test using dotnet test with /t:Build target
# This makes dotnet test actually build the project (not just look for tests)
# If NumberListAlignment enum exists (fixed code), build succeeds (exit 0)
# If NumberListAlignment enum doesn't exist (buggy code), build fails (exit non-zero)
export DOTNET_CLI_TELEMETRY_OPTOUT=1

# Use dotnet test as the test runner invocation
# /t:Build forces the build target to run, which compiles the code
dotnet test "InlineTest.csproj" /t:Build --verbosity normal 2>&1

RC=$?

if [ $RC -eq 0 ]; then
    echo "Build successful - NumberListAlignment enum exists (FIXED CODE)"
else
    echo "Build failed - NumberListAlignment enum missing (BUGGY CODE)"
fi

echo ">>>>> End Test Output"

# Clean up temp directory
rm -rf "$TEMP_TEST_DIR"

# openenv: emit_result
echo "OPENENV_EXIT_CODE=$RC"
exit $RC
