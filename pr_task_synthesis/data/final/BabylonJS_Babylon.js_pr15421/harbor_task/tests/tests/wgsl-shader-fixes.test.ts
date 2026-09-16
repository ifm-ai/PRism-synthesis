/**
 * Tests for WGSL shader bug fixes in Babylon.js WebGPU renderer.
 *
 * This test file verifies that the shader source files contain the correct
 * variable references and syntax required for proper WGSL shader compilation.
 *
 * The bugs fixed include:
 * - bumpFragment.fx: Correct fragmentInputs.* UV references and vec4f construction
 * - depthPrePass.fx: Correct fragmentOutputs usage and return statement
 * - oitFragment.fx: Use 'var' instead of 'uvar'
 * - morphTargetsVertex.fx: Correct vec4f construction for tangent updates
 * - default.fragment.fx: Correct fragmentInputs.* and uniforms.* references
 */

import * as fs from 'fs';
import * as path from 'path';

// Base path to the shader files - uses environment variable or defaults to /workspace
const SHADERS_BASE = process.env.TEST_WORKSPACE_PATH || '/workspace/packages/dev/core/src/ShadersWGSL';

/**
 * Reads a shader file and returns its content
 */
function readShaderFile(relativePath: string): string {
    const fullPath = path.join(SHADERS_BASE, relativePath);
    return fs.readFileSync(fullPath, 'utf-8');
}

describe('WGSL Shader Fixes', () => {
    describe('bumpFragment.fx', () => {
        let content: string;

        beforeAll(() => {
            content = readShaderFile('ShadersInclude/bumpFragment.fx');
        });

        it('should use fragmentInputs.vDetailUV instead of bare vDetailUV in TBNUV select', () => {
            // The bug was: select(-vDetailUV, vDetailUV, fragmentInputs.frontFacing)
            // The fix is: select(-fragmentInputs.vDetailUV, fragmentInputs.vDetailUV, fragmentInputs.frontFacing)
            const buggyPattern = /select\(\s*-vDetailUV\s*,\s*vDetailUV\s*,/;
            const fixedPattern = /select\(\s*-fragmentInputs\.vDetailUV\s*,\s*fragmentInputs\.vDetailUV\s*,/;

            expect(buggyPattern.test(content)).toBe(false);
            expect(fixedPattern.test(content)).toBe(true);
        });

        it('should use fragmentInputs.vDetailUV in textureSample for detail', () => {
            // The bug was: textureSample(..., vDetailUV + uvOffset)
            // The fix is: textureSample(..., fragmentInputs.vDetailUV + uvOffset)
            const buggyPattern = /textureSample\(detailSampler,\s*detailSamplerSampler,\s*vDetailUV\s*\+/;
            const fixedPattern = /textureSample\(detailSampler,\s*detailSamplerSampler,\s*fragmentInputs\.vDetailUV\s*\+/;

            expect(buggyPattern.test(content)).toBe(false);
            expect(fixedPattern.test(content)).toBe(true);
        });

        it('should use fragmentInputs.vBumpUV in textureSample for bump', () => {
            // The bug was: textureSample(..., vBumpUV + uvOffset)
            // The fix is: textureSample(..., fragmentInputs.vBumpUV + uvOffset)
            const buggyPattern = /textureSample\(bumpSampler,\s*bumpSamplerSampler,\s*vBumpUV\s*\+/;
            const fixedPattern = /textureSample\(bumpSampler,\s*bumpSamplerSampler,\s*fragmentInputs\.vBumpUV\s*\+/;

            expect(buggyPattern.test(content)).toBe(false);
            expect(fixedPattern.test(content)).toBe(true);
        });

        it('should use vec3f construction for detailNormal scaling (whiteout method)', () => {
            // The bug was: detailNormal.xy *= uniforms.vDetailInfos.z;
            // The fix is: detailNormal = vec3f(detailNormal.xy * uniforms.vDetailInfos.z, detailNormal.z);
            const buggyPattern = /detailNormal\.xy\s*\*=\s*uniforms\.vDetailInfos\.z/;
            const fixedPattern = /detailNormal\s*=\s*vec3f\s*\(\s*detailNormal\.xy\s*\*\s*uniforms\.vDetailInfos\.z\s*,\s*detailNormal\.z\s*\)/;

            expect(buggyPattern.test(content)).toBe(false);
            expect(fixedPattern.test(content)).toBe(true);
        });

        it('should use vec3f construction for detailNormal scaling (RNM method)', () => {
            // Same fix as above for the RNM branch
            const lines = content.split('\n');
            let inRnmBlock = false;
            let foundBuggyPattern = false;
            let foundFixedPattern = false;

            for (let i = 0; i < lines.length; i++) {
                const line = lines[i];
                if (line.includes('DETAIL_NORMALBLENDMETHOD == 1')) {
                    inRnmBlock = true;
                }
                if (inRnmBlock) {
                    if (/detailNormal\.xy\s*\*=\s*uniforms\.vDetailInfos\.z/.test(line)) {
                        foundBuggyPattern = true;
                    }
                    if (/detailNormal\s*=\s*vec3f\s*\(\s*detailNormal\.xy\s*\*\s*uniforms\.vDetailInfos\.z/.test(line)) {
                        foundFixedPattern = true;
                    }
                    if (line.includes('#endif') && i > 0 && lines[i-1].includes('blendedNormal')) {
                        break;
                    }
                }
            }

            expect(foundBuggyPattern).toBe(false);
            expect(foundFixedPattern).toBe(true);
        });

        it('should use vec3f construction for detailNormal in DETAIL-only branch', () => {
            // The bug was: detailNormal.xy *= vDetailInfos.z;
            // The fix is: detailNormal = vec3f(detailNormal.xy * uniforms.vDetailInfos.z, detailNormal.z);
            // This is in the #elif defined(DETAIL) branch at the end
            const buggyPattern = /detailNormal\.xy\s*\*=\s*vDetailInfos\.z/;
            // Use global flag to count all occurrences
            const fixedPattern = /detailNormal = vec3f\(detailNormal\.xy \* uniforms\.vDetailInfos\.z/g;

            // Count occurrences - we should have 3 fixed patterns (whiteout, RNM, DETAIL branches) and 0 buggy
            const buggyMatches = content.match(buggyPattern);
            const fixedMatches = content.match(fixedPattern);

            expect(buggyMatches).toBeNull();
            expect(fixedMatches).not.toBeNull();
            expect(fixedMatches!.length).toBeGreaterThanOrEqual(3);
        });
    });

    describe('depthPrePass.fx', () => {
        let content: string;

        beforeAll(() => {
            content = readShaderFile('ShadersInclude/depthPrePass.fx');
        });

        it('should use fragmentOutputs.color instead of gl_FragColor', () => {
            // The bug was: gl_FragColor = vec4f(0., 0., 0., 1.0);
            // The fix is: fragmentOutputs.color = vec4f(0., 0., 0., 1.0);
            const buggyPattern = /gl_FragColor\s*=/;
            const fixedPattern = /fragmentOutputs\.color\s*=\s*vec4f\s*\(\s*0\.\s*,\s*0\.\s*,\s*0\.\s*,\s*1\.0\s*\)/;

            expect(buggyPattern.test(content)).toBe(false);
            expect(fixedPattern.test(content)).toBe(true);
        });

        it('should return fragmentOutputs instead of bare return', () => {
            // The bug was: return;
            // The fix is: return fragmentOutputs;
            const buggyPattern = /#\s*ifdef\s+DEPTHPREPASS[\s\S]*?return\s*;/;
            const fixedPattern = /return\s+fragmentOutputs\s*;/;

            expect(buggyPattern.test(content)).toBe(false);
            expect(fixedPattern.test(content)).toBe(true);
        });
    });

    describe('oitFragment.fx', () => {
        let content: string;

        beforeAll(() => {
            content = readShaderFile('ShadersInclude/oitFragment.fx');
        });

        it('should use var instead of uvar for halfFloat declaration', () => {
            // The bug was: uvar halfFloat: i32 = packHalf2x16(vec2f(fragDepth));
            // The fix is: var halfFloat: i32 = packHalf2x16(vec2f(fragDepth));
            const buggyPattern = /uvar\s+halfFloat\s*:/;
            const fixedPattern = /var\s+halfFloat\s*:\s*i32\s*=\s*packHalf2x16\s*\(\s*vec2f\s*\(\s*fragDepth\s*\)\s*\)/;

            expect(buggyPattern.test(content)).toBe(false);
            expect(fixedPattern.test(content)).toBe(true);
        });
    });

    describe('morphTargetsVertex.fx', () => {
        let content: string;

        beforeAll(() => {
            content = readShaderFile('ShadersInclude/morphTargetsVertex.fx');
        });

        it('should use vec4f construction for tangentUpdated in texture mode', () => {
            // The bug was: tangentUpdated.xyz = tangentUpdated.xyz + (...)
            // The fix is: tangentUpdated = vec4f(tangentUpdated.xyz + (...), tangentUpdated.a);
            // This is in the MORPHTARGETS_TEXTURE block
            const textureBlockStart = content.indexOf('#ifdef MORPHTARGETS_TEXTURE');
            const textureBlockEnd = content.indexOf('#else', textureBlockStart);
            const textureBlock = content.substring(textureBlockStart, textureBlockEnd);

            const buggyPattern = /tangentUpdated\.xyz\s*=\s*tangentUpdated\.xyz\s*\+/;
            const fixedPattern = /tangentUpdated\s*=\s*vec4f\s*\(\s*tangentUpdated\.xyz\s*\+/;

            expect(buggyPattern.test(textureBlock)).toBe(false);
            expect(fixedPattern.test(textureBlock)).toBe(true);
        });

        it('should use vec4f construction for tangentUpdated in non-texture mode', () => {
            // Same fix for the non-texture block (after #else, before final #endif)
            // Structure: #ifdef MORPHTARGETS_TEXTURE ... #else (non-texture) ... #endif
            // The non-texture block contains MORPHTARGETS_TANGENT with the fixed pattern
            const lines = content.split('\n');
            let inNonTextureBlock = false;
            let foundBuggyPattern = false;
            let foundFixedPattern = false;
            let ifdefDepth = 0;

            for (let i = 0; i < lines.length; i++) {
                const line = lines[i];
                
                // Track nesting depth for #ifdef/#endif
                if (line.trim().startsWith('#ifdef') || line.trim().startsWith('#if ')) {
                    ifdefDepth++;
                }
                
                if (line.includes('#else') && ifdefDepth === 2) {
                    // This is the #else at depth 2 (inside #ifdef MORPHTARGETS)
                    inNonTextureBlock = true;
                    continue;
                }
                
                if (line.trim().startsWith('#endif')) {
                    ifdefDepth--;
                    // Exit when we close the outer MORPHTARGETS block
                    if (ifdefDepth < 2 && inNonTextureBlock) {
                        break;
                    }
                }
                
                if (inNonTextureBlock) {
                    if (/tangentUpdated\.xyz\s*=\s*tangentUpdated\.xyz\s*\+/.test(line)) {
                        foundBuggyPattern = true;
                    }
                    if (/tangentUpdated\s*=\s*vec4f\s*\(\s*tangentUpdated\.xyz\s*\+/.test(line)) {
                        foundFixedPattern = true;
                    }
                }
            }

            expect(foundBuggyPattern).toBe(false);
            expect(foundFixedPattern).toBe(true);
        });
    });

    describe('default.fragment.fx', () => {
        let content: string;

        beforeAll(() => {
            content = readShaderFile('default.fragment.fx');
        });

        it('should use fragmentInputs.vDecalUV instead of vDecalUV (first occurrence)', () => {
            // The bug was: textureSample(..., vDecalUV + uvOffset)
            // The fix is: textureSample(..., fragmentInputs.vDecalUV + uvOffset)
            // Check first occurrence (before DECAL_AFTER_DETAIL)
            const decalBeforeDetailIndex = content.indexOf('#if defined(DECAL) && !defined(DECAL_AFTER_DETAIL)');
            const decalAfterDetailIndex = content.indexOf('#if defined(DECAL) && defined(DECAL_AFTER_DETAIL)');

            const firstBlock = content.substring(decalBeforeDetailIndex, decalAfterDetailIndex);

            const buggyPattern = /textureSample\(decalSampler,\s*decalSamplerSampler,\s*vDecalUV\s*\+/;
            const fixedPattern = /textureSample\(decalSampler,\s*decalSamplerSampler,\s*fragmentInputs\.vDecalUV\s*\+/;

            expect(buggyPattern.test(firstBlock)).toBe(false);
            expect(fixedPattern.test(firstBlock)).toBe(true);
        });

        it('should use fragmentInputs.vDecalUV instead of vDecalUV (second occurrence)', () => {
            // Check second occurrence (after DECAL_AFTER_DETAIL)
            const decalAfterDetailIndex = content.indexOf('#if defined(DECAL) && defined(DECAL_AFTER_DETAIL)');
            const secondBlock = content.substring(decalAfterDetailIndex, decalAfterDetailIndex + 500);

            const buggyPattern = /textureSample\(decalSampler,\s*decalSamplerSampler,\s*vDecalUV\s*\+/;
            const fixedPattern = /textureSample\(decalSampler,\s*decalSamplerSampler,\s*fragmentInputs\.vDecalUV\s*\+/;

            expect(buggyPattern.test(secondBlock)).toBe(false);
            expect(fixedPattern.test(secondBlock)).toBe(true);
        });

        it('should use uniforms.vDetailInfos.y instead of bare vDetailInfos.y', () => {
            // The bug was: mix(0.5, detailColor.r, vDetailInfos.y)
            // The fix is: mix(0.5, detailColor.r, uniforms.vDetailInfos.y)
            const buggyPattern = /mix\s*\(\s*0\.5\s*,\s*detailColor\.r\s*,\s*vDetailInfos\.y\s*\)/;
            const fixedPattern = /mix\s*\(\s*0\.5\s*,\s*detailColor\.r\s*,\s*uniforms\.vDetailInfos\.y\s*\)/;

            expect(buggyPattern.test(content)).toBe(false);
            expect(fixedPattern.test(content)).toBe(true);
        });

        it('should use uniforms.refractionMatrix and scene.view for refraction calculation', () => {
            // The bug was: var vRefractionUVW: vec3f = vec3f(refractionMatrix * (view * vec4f(...)))
            // The fix is: var vRefractionUVW: vec3f = (uniforms.refractionMatrix * (scene.view * vec4f(...))).xyz;
            const buggyPattern = /var\s+vRefractionUVW\s*:\s*vec3f\s*=\s*vec3f\s*\(\s*refractionMatrix\s*\*\s*\(\s*view\s*\*/;
            const fixedPattern = /var\s+vRefractionUVW\s*:\s*vec3f\s*=\s*\(\s*uniforms\.refractionMatrix\s*\*\s*\(\s*scene\.view\s*\*/;

            expect(buggyPattern.test(content)).toBe(false);
            expect(fixedPattern.test(content)).toBe(true);
        });
    });
});
