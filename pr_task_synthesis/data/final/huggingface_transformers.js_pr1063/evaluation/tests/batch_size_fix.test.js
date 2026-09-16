/**
 * Test for the batch_size calculation fix in PreTrainedModel.addPastKeyValues
 *
 * The fix changes line 1760 in src/models.js from:
 *   const batch_size = (decoderFeeds[this.main_input_name] ?? decoderFeeds.attention_mask).dims?.[0] ?? 1;
 * to:
 *   const batch_size = (decoderFeeds[this.main_input_name] ?? decoderFeeds.attention_mask)?.dims?.[0] ?? 1;
 *
 * This handles cases where the decoder input object exists but is missing the `dims` property.
 * Without the fix, accessing .dims on an object without that property returns undefined,
 * and then undefined?.[0] throws a TypeError.
 * With the fix, optional chaining on the whole expression safely returns undefined,
 * and the ?? 1 fallback provides the default batch size.
 *
 * Test behavior:
 * - Without the fix: calling addPastKeyValues with decoder input lacking dims throws TypeError
 * - With the fix: calling addPastKeyValues with decoder input lacking dims uses batch_size=1
 */

import { PreTrainedModel } from '../../src/transformers.js';

describe('batch_size calculation fix', () => {
    describe('addPastKeyValues with missing dims property', () => {
        it('should handle decoder input without dims property (key test case)', () => {
            // Create a mock model instance with minimal but complete setup
            // The config needs normalized_config with all properties that getKeyValueShapes uses
            const mockModel = {
                main_input_name: 'input_ids',
                config: {
                    // Add normalized_config with properties needed by getKeyValueShapes
                    normalized_config: {
                        is_encoder_decoder: false,
                        model_type: 'gpt2',  // Use a simple decoder-only type
                        num_heads: 2,
                        num_layers: 2,
                        hidden_size: 64,
                        num_attention_heads: 2,
                        dim_kv: 32
                    }
                },
                sessions: {}
            };

            // Bind the actual addPastKeyValues method from PreTrainedModel prototype
            const addPastKeyValues = PreTrainedModel.prototype.addPastKeyValues.bind(mockModel);

            // Decoder feeds where input_ids exists but has no dims property
            // This simulates the case described in the issue
            const decoderFeeds = {
                input_ids: {
                    // Note: no 'dims' property here - this triggers the bug
                    data: [1, 2, 3, 4]
                }
            };

            // With the fix, this should NOT throw
            // It should use batch_size = 1 as the fallback
            // Without the fix, this throws: Cannot read properties of undefined (reading '0')
            expect(() => {
                addPastKeyValues(decoderFeeds, null);
            }).not.toThrow();

            // Verify that past key/values were added with batch_size=1
            // The keys are named 'past_key_values.{layer}.key' and 'past_key_values.{layer}.value'
            expect(decoderFeeds['past_key_values.0.key']).toBeDefined();
            expect(decoderFeeds['past_key_values.0.value']).toBeDefined();
            
            // Verify batch_size=1 was used (first dimension of the shape)
            expect(decoderFeeds['past_key_values.0.key'].dims[0]).toBe(1);
            expect(decoderFeeds['past_key_values.0.value'].dims[0]).toBe(1);
        });

        it('should use dims[0] when decoder input has dims property', () => {
            const mockModel = {
                main_input_name: 'input_ids',
                config: {
                    normalized_config: {
                        is_encoder_decoder: false,
                        model_type: 'gpt2',
                        num_heads: 2,
                        num_layers: 2,
                        hidden_size: 64,
                        num_attention_heads: 2,
                        dim_kv: 32
                    }
                },
                sessions: {}
            };

            const addPastKeyValues = PreTrainedModel.prototype.addPastKeyValues.bind(mockModel);

            const decoderFeeds = {
                input_ids: {
                    dims: [3, 10] // batch_size=3, seq_len=10
                }
            };

            expect(() => {
                addPastKeyValues(decoderFeeds, null);
            }).not.toThrow();

            // Verify batch_size=3 was used (first dimension of the shape)
            expect(decoderFeeds['past_key_values.0.key'].dims[0]).toBe(3);
        });

        it('should fall back to attention_mask.dims when input_ids is missing', () => {
            const mockModel = {
                main_input_name: 'input_ids',
                config: {
                    normalized_config: {
                        is_encoder_decoder: false,
                        model_type: 'gpt2',
                        num_heads: 2,
                        num_layers: 2,
                        hidden_size: 64,
                        num_attention_heads: 2,
                        dim_kv: 32
                    }
                },
                sessions: {}
            };

            const addPastKeyValues = PreTrainedModel.prototype.addPastKeyValues.bind(mockModel);

            const decoderFeeds = {
                // No input_ids
                attention_mask: {
                    dims: [5, 20] // batch_size=5
                }
            };

            expect(() => {
                addPastKeyValues(decoderFeeds, null);
            }).not.toThrow();

            // Should use attention_mask.dims[0] = 5
            expect(decoderFeeds['past_key_values.0.key'].dims[0]).toBe(5);
        });

        it('should default to batch_size=1 when decoderFeeds is empty', () => {
            const mockModel = {
                main_input_name: 'input_ids',
                config: {
                    normalized_config: {
                        is_encoder_decoder: false,
                        model_type: 'gpt2',
                        num_heads: 1,
                        num_layers: 1,
                        hidden_size: 32,
                        num_attention_heads: 1,
                        dim_kv: 32
                    }
                },
                sessions: {}
            };

            const addPastKeyValues = PreTrainedModel.prototype.addPastKeyValues.bind(mockModel);
            const decoderFeeds = {};

            // With the fix, this should NOT throw and should default to batch_size=1
            expect(() => {
                addPastKeyValues(decoderFeeds, null);
            }).not.toThrow();

            expect(decoderFeeds['past_key_values.0.key'].dims[0]).toBe(1);
        });

        it('should handle input_ids without dims when attention_mask also lacks dims', () => {
            // This test specifically targets the fix:
            // When input_ids exists but has no dims, and attention_mask also has no dims,
            // the buggy code throws because (input_ids).dims is undefined
            // The fixed code uses optional chaining to safely get undefined and fall back to 1
            const mockModel = {
                main_input_name: 'input_ids',
                config: {
                    normalized_config: {
                        is_encoder_decoder: false,
                        model_type: 'gpt2',
                        num_heads: 1,
                        num_layers: 1,
                        hidden_size: 32,
                        num_attention_heads: 1,
                        dim_kv: 32
                    }
                },
                sessions: {}
            };

            const addPastKeyValues = PreTrainedModel.prototype.addPastKeyValues.bind(mockModel);
            const decoderFeeds = {
                input_ids: { data: [1, 2, 3] },  // No dims
                attention_mask: { data: [0, 0, 0, 1] }  // No dims
            };

            // With the fix, this should NOT throw and should default to batch_size=1
            // Without the fix, this throws: Cannot read properties of undefined (reading '0')
            expect(() => {
                addPastKeyValues(decoderFeeds, null);
            }).not.toThrow();

            expect(decoderFeeds['past_key_values.0.key'].dims[0]).toBe(1);
        });
    });
});
