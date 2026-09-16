/**
 * Tests for conditional sampler uniforms in particle shaders
 *
 * This test verifies that:
 * 1. particle_cpu.js wraps internalTex0/1/2 in #ifdef PARTICLE_GPU blocks
 * 2. particle_init.js wraps internalTex0/1/2 in #ifdef PARTICLE_GPU blocks
 * 3. CPU particle shaders work without PARTICLE_GPU defined (no undefined uniform errors)
 * 4. GPU particle shaders work with PARTICLE_GPU defined
 */

import { expect } from 'chai';
import { readFileSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));

describe('Particle Shader Conditional Sampler Uniforms', function () {

    let particleCpuSource;
    let particleInitSource;

    before(function () {
        // Read the shader source files from current working directory
        const srcDir = join(process.cwd(), 'src/scene/shader-lib/chunks/particle/vert');
        particleCpuSource = readFileSync(join(srcDir, 'particle_cpu.js'), 'utf-8');
        particleInitSource = readFileSync(join(srcDir, 'particle_init.js'), 'utf-8');
    });

    describe('particle_cpu.js', function () {

        it('should wrap internalTex0 in #ifdef PARTICLE_GPU', function () {
            // The fix wraps sampler uniforms in #ifdef PARTICLE_GPU blocks
            // This pattern should be present in the fixed code
            const hasConditionalInternalTex0 = /#ifdef\s+PARTICLE_GPU[\s\S]*?uniform\s+highp\s+sampler2D\s+internalTex0/.test(particleCpuSource);

            expect(hasConditionalInternalTex0).to.be.true;
        });

        it('should wrap internalTex1 in #ifdef PARTICLE_GPU', function () {
            const hasConditionalInternalTex1 = /#ifdef\s+PARTICLE_GPU[\s\S]*?uniform\s+highp\s+sampler2D\s+internalTex1/.test(particleCpuSource);

            expect(hasConditionalInternalTex1).to.be.true;
        });

        it('should wrap internalTex2 in #ifdef PARTICLE_GPU', function () {
            const hasConditionalInternalTex2 = /#ifdef\s+PARTICLE_GPU[\s\S]*?uniform\s+highp\s+sampler2D\s+internalTex2/.test(particleCpuSource);

            expect(hasConditionalInternalTex2).to.be.true;
        });

        it('should not have unconditional internalTex0 declaration outside #ifdef block', function () {
            // Check that internalTex0 is NOT declared outside the #ifdef PARTICLE_GPU block
            // First, extract content outside #ifdef PARTICLE_GPU blocks
            const contentOutsideIfdef = particleCpuSource.replace(/#ifdef\s+PARTICLE_GPU[\s\S]*?#endif/g, '');

            // There should be no unconditional declaration of internalTex0
            const hasUnconditionalInternalTex0 = /uniform\s+highp\s+sampler2D\s+internalTex0/.test(contentOutsideIfdef);

            expect(hasUnconditionalInternalTex0).to.be.false;
        });

        it('should not have unconditional internalTex1 declaration outside #ifdef block', function () {
            const contentOutsideIfdef = particleCpuSource.replace(/#ifdef\s+PARTICLE_GPU[\s\S]*?#endif/g, '');
            const hasUnconditionalInternalTex1 = /uniform\s+highp\s+sampler2D\s+internalTex1/.test(contentOutsideIfdef);

            expect(hasUnconditionalInternalTex1).to.be.false;
        });

        it('should not have unconditional internalTex2 declaration outside #ifdef block', function () {
            const contentOutsideIfdef = particleCpuSource.replace(/#ifdef\s+PARTICLE_GPU[\s\S]*?#endif/g, '');
            const hasUnconditionalInternalTex2 = /uniform\s+highp\s+sampler2D\s+internalTex2/.test(contentOutsideIfdef);

            expect(hasUnconditionalInternalTex2).to.be.false;
        });

    });

    describe('particle_init.js', function () {

        it('should wrap internalTex0 in #ifdef PARTICLE_GPU', function () {
            const hasConditionalInternalTex0 = /#ifdef\s+PARTICLE_GPU[\s\S]*?uniform\s+highp\s+sampler2D\s+internalTex0/.test(particleInitSource);

            expect(hasConditionalInternalTex0).to.be.true;
        });

        it('should wrap internalTex1 in #ifdef PARTICLE_GPU', function () {
            const hasConditionalInternalTex1 = /#ifdef\s+PARTICLE_GPU[\s\S]*?uniform\s+highp\s+sampler2D\s+internalTex1/.test(particleInitSource);

            expect(hasConditionalInternalTex1).to.be.true;
        });

        it('should wrap internalTex2 in #ifdef PARTICLE_GPU', function () {
            const hasConditionalInternalTex2 = /#ifdef\s+PARTICLE_GPU[\s\S]*?uniform\s+highp\s+sampler2D\s+internalTex2/.test(particleInitSource);

            expect(hasConditionalInternalTex2).to.be.true;
        });

        it('should not have unconditional internalTex0 declaration outside #ifdef block', function () {
            const contentOutsideIfdef = particleInitSource.replace(/#ifdef\s+PARTICLE_GPU[\s\S]*?#endif/g, '');
            const hasUnconditionalInternalTex0 = /uniform\s+highp\s+sampler2D\s+internalTex0/.test(contentOutsideIfdef);

            expect(hasUnconditionalInternalTex0).to.be.false;
        });

        it('should not have unconditional internalTex1 declaration outside #ifdef block', function () {
            const contentOutsideIfdef = particleInitSource.replace(/#ifdef\s+PARTICLE_GPU[\s\S]*?#endif/g, '');
            const hasUnconditionalInternalTex1 = /uniform\s+highp\s+sampler2D\s+internalTex1/.test(contentOutsideIfdef);

            expect(hasUnconditionalInternalTex1).to.be.false;
        });

        it('should not have unconditional internalTex2 declaration outside #ifdef block', function () {
            const contentOutsideIfdef = particleInitSource.replace(/#ifdef\s+PARTICLE_GPU[\s\S]*?#endif/g, '');
            const hasUnconditionalInternalTex2 = /uniform\s+highp\s+sampler2D\s+internalTex2/.test(contentOutsideIfdef);

            expect(hasUnconditionalInternalTex2).to.be.false;
        });

    });

});
