/**
 * Tests for duplicate attribute handling in shader-utils.js
 *
 * This test verifies that when the same attribute appears multiple times
 * in a vertex shader, the collectAttributes method handles it gracefully
 * by emitting a warning instead of treating it as a new attribute.
 */

import { pathToFileURL } from 'url';
import { join } from 'path';
import { expect } from 'chai';

// Dynamically import ShaderUtils from current working directory
const shaderUtilsPath = pathToFileURL(join(process.cwd(), 'src/platform/graphics/shader-utils.js')).href;
const { ShaderUtils } = await import(shaderUtilsPath);

describe('ShaderUtils.collectAttributes - Duplicate Attribute Handling', function () {

    describe('duplicate attribute detection', function () {

        it('should handle a single attribute correctly', function () {
            const vsCode = `
                attribute vec4 vertex_position;
                void main() { }
            `;

            const attribs = ShaderUtils.collectAttributes(vsCode);

            expect(attribs).to.be.an('object');
            expect(attribs.vertex_position).to.exist;
            expect(Object.keys(attribs).length).to.equal(1);
        });

        it('should handle multiple unique attributes correctly', function () {
            const vsCode = `
                attribute vec4 vertex_position;
                attribute vec3 vertex_normal;
                attribute vec2 vertex_texCoord0;
                void main() { }
            `;

            const attribs = ShaderUtils.collectAttributes(vsCode);

            expect(attribs).to.be.an('object');
            expect(attribs.vertex_position).to.exist;
            expect(attribs.vertex_normal).to.exist;
            expect(attribs.vertex_texCoord0).to.exist;
            expect(Object.keys(attribs).length).to.equal(3);
        });

        it('should handle duplicate attributes without adding them twice', function () {
            // This is the key test for the fix - duplicate attributes should be handled
            const vsCode = `
                attribute vec4 vertex_position;
                attribute vec3 vertex_normal;
                attribute vec4 vertex_position;
                void main() { }
            `;

            const attribs = ShaderUtils.collectAttributes(vsCode);

            expect(attribs).to.be.an('object');
            expect(attribs.vertex_position).to.exist;
            expect(attribs.vertex_normal).to.exist;
            // Should only have 2 unique attributes, not 3
            expect(Object.keys(attribs).length).to.equal(2);
        });

        it('should handle multiple duplicate occurrences of the same attribute', function () {
            const vsCode = `
                attribute vec4 vertex_position;
                attribute vec4 vertex_position;
                attribute vec4 vertex_position;
                void main() { }
            `;

            const attribs = ShaderUtils.collectAttributes(vsCode);

            expect(attribs).to.be.an('object');
            expect(attribs.vertex_position).to.exist;
            // Should only have 1 unique attribute
            expect(Object.keys(attribs).length).to.equal(1);
        });

        it('should handle duplicate custom attributes (non-semantic)', function () {
            // Custom attributes that don't map to semantics should also be deduplicated
            const vsCode = `
                attribute vec4 custom_attr;
                attribute vec3 vertex_normal;
                attribute vec4 custom_attr;
                void main() { }
            `;

            const attribs = ShaderUtils.collectAttributes(vsCode);

            expect(attribs).to.be.an('object');
            expect(attribs.vertex_normal).to.exist;
            expect(attribs.custom_attr).to.exist;
            // Should have 2 unique attributes (vertex_normal and custom_attr)
            expect(Object.keys(attribs).length).to.equal(2);
        });

        it('should not change mapping for duplicate custom attributes', function () {
            // This is the key behavioral test - duplicate custom attributes should keep their original mapping
            // Buggy code would reassign "ATTR1" to custom_attr on second occurrence
            // Fixed code keeps "ATTR0" for custom_attr
            const vsCode = `
                attribute vec4 custom_attr;
                attribute vec4 custom_attr;
                void main() { }
            `;

            const attribs = ShaderUtils.collectAttributes(vsCode);

            expect(attribs).to.be.an('object');
            expect(attribs.custom_attr).to.equal('ATTR0');
            // Should only have 1 unique attribute
            expect(Object.keys(attribs).length).to.equal(1);
        });

        it('should handle the particle shader duplicate attribute pattern', function () {
            // This simulates the pattern in particle_cpu.js where particle_vertexData5
            // appears in both the USE_MESH and non-USE_MESH branches
            const vsCode = `
                attribute vec4 particle_vertexData;
                attribute vec4 particle_vertexData2;
                attribute vec4 particle_vertexData3;
                attribute float particle_vertexData4;
                #ifndef USE_MESH
                attribute vec2 particle_vertexData5;
                #else
                attribute vec4 particle_vertexData5;
                #endif
                void main() { }
            `;

            const attribs = ShaderUtils.collectAttributes(vsCode);

            expect(attribs).to.be.an('object');
            expect(attribs.particle_vertexData).to.exist;
            expect(attribs.particle_vertexData2).to.exist;
            expect(attribs.particle_vertexData3).to.exist;
            expect(attribs.particle_vertexData4).to.exist;
            expect(attribs.particle_vertexData5).to.exist;
            // Should have 5 unique attributes
            expect(Object.keys(attribs).length).to.equal(5);
        });

    });

});
