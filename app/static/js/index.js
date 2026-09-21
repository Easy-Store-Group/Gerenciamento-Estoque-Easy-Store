(() => {
    const canvas = document.getElementById('bg-canvas');
    const glRenderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true });
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(35, window.innerWidth / window.innerHeight, 0.1, 1000);
    camera.position.z = 12;

    const group = new THREE.Group();
    scene.add(group);

    const geometry = new THREE.SphereGeometry(0.72, 18, 18);
    const material = new THREE.MeshPhysicalMaterial({
        color: 0x8bb9ff,
        emissive: 0x93c5fd,
        emissiveIntensity: 0.10,
        transparent: true,
        opacity: 0.12,
        roughness: 0.60,
        metalness: 0.06,
        clearcoat: 0.14,
        clearcoatRoughness: 0.7
    });

    const count = 7;
    const mesh = new THREE.InstancedMesh(geometry, material, count);
    const dummy = new THREE.Object3D();
    const particles = [];

    for (let i = 0; i < count; i += 1) {
        const x = (Math.random() - 0.5) * 10;
        const y = (Math.random() - 0.5) * 6;
        const z = (Math.random() - 0.5) * 7 - 1;
        const scale = 0.28 + Math.random() * 0.7;
        const phase = Math.random() * Math.PI * 2;
        const speed = 0.6 + Math.random() * 1.0;
        const amplitude = 0.10 + Math.random() * 0.24;

        dummy.position.set(x, y, z);
        dummy.rotation.set(Math.random() * Math.PI, Math.random() * Math.PI, 0);
        dummy.scale.setScalar(scale);
        dummy.updateMatrix();
        mesh.setMatrixAt(i, dummy.matrix);

        particles.push({ x, y, z, phase, speed, amplitude, scale });
    }

    group.add(mesh);

    const ambientLight = new THREE.AmbientLight(0xffffff, 0.7);
    scene.add(ambientLight);

    const pointLight = new THREE.PointLight(0xbedcff, 0.35, 50);
    pointLight.position.set(1, 2, 8);
    scene.add(pointLight);

    function resizeRenderer() {
        const width = window.innerWidth;
        const height = window.innerHeight;
        glRenderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
        glRenderer.setSize(width, height, false);
        camera.aspect = width / height;
        camera.updateProjectionMatrix();
    }

    window.addEventListener('resize', resizeRenderer);
    resizeRenderer();

    function animate(now) {
        const t = now * 0.001;
        for (let i = 0; i < count; i += 1) {
            const item = particles[i];
            dummy.position.set(
                item.x + Math.sin(t * item.speed + item.phase) * item.amplitude,
                item.y + Math.cos(t * item.speed * 1.2 + item.phase) * item.amplitude,
                item.z + Math.sin(t * item.speed * 0.8 + item.phase) * 0.22
            );
            dummy.rotation.y += 0.0012;
            dummy.rotation.x += 0.0008;
            dummy.scale.setScalar(item.scale * (1 + Math.sin(t * 1.6 + item.phase) * 0.05));
            dummy.updateMatrix();
            mesh.setMatrixAt(i, dummy.matrix);
        }

        mesh.instanceMatrix.needsUpdate = true;
        group.rotation.y = t * 0.04;
        glRenderer.render(scene, camera);
        requestAnimationFrame(animate);
    }

    requestAnimationFrame(animate);
})();
