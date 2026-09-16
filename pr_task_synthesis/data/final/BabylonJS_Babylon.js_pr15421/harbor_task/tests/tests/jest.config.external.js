/**
 * Jest configuration for external WGSL shader verification tests.
 * This config is separate from the main Babylon.js test suite.
 */
module.exports = {
    testEnvironment: 'node',
    extensionsToTreatAsEsm: ['.ts'],
    moduleFileExtensions: ['ts', 'tsx', 'js', 'jsx'],
    transform: {
        '^.+\\.tsx?$': ['/workspace/node_modules/ts-jest', {
            isolatedModules: true,
            useESM: true,
        }],
    },
    // Look for tests in the same directory as this config file
    roots: ['<rootDir>'],
    testMatch: ['**/*.test.ts'],
};
