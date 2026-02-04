import * as THREE from 'three';
import { STLLoader } from 'three/addons/loaders/STLLoader.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

const MODEL_COLORS = [
    0x7ec8e3, // light blue
    0xb39ddb, // light purple
    0xfff176, // yellow
    0xffb74d, // orange
    0x81c784, // bright green
    0xe57373, // red
];

function randomColor() {
    return MODEL_COLORS[Math.floor(Math.random() * MODEL_COLORS.length)];
}

class STLViewer {
    constructor(canvas, stlUrl, color) {
        this.canvas = canvas;
        this.color = color;
        this.disposed = false;

        this.scene = new THREE.Scene();
        this.scene.background = new THREE.Color(0xf5f5f5);

        this.camera = new THREE.PerspectiveCamera(
            60, canvas.width / canvas.height, 0.1, 10000
        );
        this.renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
        this.renderer.setSize(canvas.width, canvas.height);
        this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

        this.controls = new OrbitControls(this.camera, canvas);
        this.controls.enableDamping = true;
        this.controls.autoRotate = true;
        this.controls.autoRotateSpeed = 2;

        // Lighting
        const ambient = new THREE.AmbientLight(0x404040, 2);
        this.scene.add(ambient);
        const dirLight = new THREE.DirectionalLight(0xffffff, 1.5);
        dirLight.position.set(1, 1, 1);
        this.scene.add(dirLight);
        const backLight = new THREE.DirectionalLight(0xffffff, 0.5);
        backLight.position.set(-1, -1, -1);
        this.scene.add(backLight);

        this.loadSTL(stlUrl);
        this.animate();
    }

    loadSTL(url) {
        const loader = new STLLoader();
        loader.load(url, (geometry) => {
            // Convert from Z-up (common in CAD tools like Tinkercad) to Y-up (Three.js)
            geometry.rotateX(-Math.PI / 2);

            geometry.computeBoundingBox();
            geometry.center();

            // Shift up so the bottom sits on the grid plane (y=0)
            const halfHeight = (geometry.boundingBox.max.y - geometry.boundingBox.min.y) / 2;
            geometry.translate(0, halfHeight, 0);

            const material = new THREE.MeshPhongMaterial({
                color: this.color || randomColor(),
                specular: 0x222222,
                shininess: 40,
            });
            const mesh = new THREE.Mesh(geometry, material);
            mesh.name = 'stl-mesh';
            this.scene.add(mesh);
            this.fitCamera(geometry);
        });
    }

    fitCamera(geometry) {
        const box = geometry.boundingBox;
        const size = new THREE.Vector3();
        box.getSize(size);
        const maxDim = Math.max(size.x, size.y, size.z);
        const fov = this.camera.fov * (Math.PI / 180);
        const dist = maxDim / (2 * Math.tan(fov / 2)) * 1.5;
        this.camera.position.set(dist, dist * 0.8, dist);
        this.controls.target.set(0, 0, 0);
        this.controls.update();
    }

    animate() {
        if (this.disposed) return;
        requestAnimationFrame(() => this.animate());
        this.controls.update();
        this.renderer.render(this.scene, this.camera);
    }

    dispose() {
        this.disposed = true;
        this.controls.dispose();
        this.renderer.dispose();
        this.scene.traverse((obj) => {
            if (obj.geometry) obj.geometry.dispose();
            if (obj.material) obj.material.dispose();
        });
    }
}

// Track active viewers for cleanup
const viewers = new Map();

function initViewers() {
    document.querySelectorAll('canvas[data-stl-url]').forEach((canvas) => {
        if (viewers.has(canvas)) return; // already initialized

        const observer = new IntersectionObserver((entries) => {
            entries.forEach((entry) => {
                if (entry.isIntersecting && !viewers.has(canvas)) {
                    const viewer = new STLViewer(canvas, canvas.dataset.stlUrl, canvas.dataset.stlColor);
                    viewers.set(canvas, viewer);
                    observer.disconnect();
                }
            });
        }, { threshold: 0.1 });

        observer.observe(canvas);
    });
}

// Initialize on page load
initViewers();

// Re-initialize after HTMX swaps
document.addEventListener('htmx:afterSwap', () => {
    // Clean up viewers for removed elements
    for (const [canvas, viewer] of viewers) {
        if (!document.contains(canvas)) {
            viewer.dispose();
            viewers.delete(canvas);
        }
    }
    initViewers();
});

// Expose for modal use
window.STLViewer = STLViewer;
window.initSTLViewers = initViewers;
