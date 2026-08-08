/* Tea Smart — 3D hero.
 *
 * Deliberately desktop-only: the WebGL context, the three.js bundle and the
 * per-frame work are all wasted weight on a phone, where the CSS teacup in
 * .hero-fallback already carries the composition. Nothing here is required for
 * the page to work — if any step fails we simply leave the fallback in place.
 */

const canvas = document.querySelector("[data-hero-canvas]");
const fallback = document.querySelector("[data-hero-fallback]");

const shouldRender = () =>
  canvas &&
  window.matchMedia("(min-width: 1024px)").matches &&
  window.matchMedia("(pointer: fine)").matches &&
  !window.matchMedia("(prefers-reduced-motion: reduce)").matches;

const hasWebGL = () => {
  try {
    return Boolean(document.createElement("canvas").getContext("webgl2") ||
                   document.createElement("canvas").getContext("webgl"));
  } catch {
    return false;
  }
};

if (shouldRender() && hasWebGL()) {
  boot().catch((error) => {
    // The CSS teacup stays put; log so a failure is not silent in dev.
    console.warn("Tea Smart: 3D hero unavailable —", error);
  });
}

async function boot() {
  const THREE = await import("https://unpkg.com/three@0.169.0/build/three.module.js");

  const host = canvas.parentElement;
  const scene = new THREE.Scene();

  // Framed so the saucer rim and the handle both stay inside a square canvas.
  const camera = new THREE.PerspectiveCamera(30, 1, 0.1, 100);
  camera.position.set(0, 1.55, 5.4);
  camera.lookAt(0, -0.02, 0);

  const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.05;

  // Glazed ceramic needs something to reflect or it reads as flat plastic.
  // Optional extra — if the import fails we just keep the direct lights.
  try {
    const { RoomEnvironment } = await import(
      "https://unpkg.com/three@0.169.0/examples/jsm/environments/RoomEnvironment.js");
    const pmrem = new THREE.PMREMGenerator(renderer);
    scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
    pmrem.dispose();
  } catch {
    /* no environment map */
  }

  /* --- Materials --------------------------------------------------------- */
  const ceramic = new THREE.MeshPhysicalMaterial({
    color: 0xfdfbf3, roughness: 0.26, clearcoat: 1, clearcoatRoughness: 0.14,
    side: THREE.DoubleSide,
  });
  const brew = new THREE.MeshPhysicalMaterial({
    color: 0xb87a2c, roughness: 0.12, metalness: 0.05,
    clearcoat: 1, clearcoatRoughness: 0.05,
    emissive: 0x5a3410, emissiveIntensity: 0.35,
  });

  /* --- Cup (a lathed profile, so it has real wall thickness) -------------- */
  // A teacup flares fast just above the foot and then eases off — roughly
  // r = 0.60 + 0.35·√y. Straight-line points read as a funnel, so keep these.
  const profile = [
    // inner wall, from the centre of the base up to the rim
    [0.00, 0.085], [0.56, 0.09], [0.633, 0.15], [0.690, 0.25], [0.747, 0.40],
    [0.802, 0.58], [0.848, 0.76], [0.888, 0.94], [0.905, 1.02],
    // over the rim and back down the outside to the foot
    [0.95, 1.02], [0.932, 0.94], [0.893, 0.76], [0.847, 0.58], [0.792, 0.40],
    [0.735, 0.25], [0.678, 0.15], [0.60, 0.07], [0.55, 0.035], [0.52, 0.00], [0.00, 0.00],
  ].map(([x, y]) => new THREE.Vector2(x, y));

  const cup = new THREE.Mesh(new THREE.LatheGeometry(profile, 96), ceramic);

  const liquid = new THREE.Mesh(new THREE.CircleGeometry(0.878, 72), brew);
  liquid.rotation.x = -Math.PI / 2;
  liquid.position.y = 0.90;

  const handle = new THREE.Mesh(
    new THREE.TorusGeometry(0.28, 0.05, 20, 72, Math.PI * 1.25), ceramic);
  handle.position.set(0.86, 0.55, 0);
  handle.rotation.z = -Math.PI * 0.375;

  const saucerProfile = [
    [0.00, 0.00], [1.05, 0.015], [1.22, 0.10], [1.24, 0.125],
    [1.05, 0.055], [0.55, 0.04], [0.00, 0.035],
  ].map(([x, y]) => new THREE.Vector2(x, y));
  const saucer = new THREE.Mesh(new THREE.LatheGeometry(saucerProfile, 96), ceramic);
  saucer.position.y = -0.1;

  /* --- Steam: additive sprites drifting up from the surface --------------- */
  const puffTexture = makePuffTexture(THREE);
  const puffMaterial = new THREE.SpriteMaterial({
    map: puffTexture, transparent: true, depthWrite: false,
    blending: THREE.AdditiveBlending, opacity: 0,
  });

  const puffs = Array.from({ length: 22 }, () => {
    const sprite = new THREE.Sprite(puffMaterial.clone());
    sprite.userData = {
      phase: Math.random(),
      speed: 0.18 + Math.random() * 0.18,
      drift: (Math.random() - 0.5) * 0.4,
      radius: Math.random() * 0.38,
      angle: Math.random() * Math.PI * 2,
      scale: 0.09 + Math.random() * 0.13,
    };
    scene.add(sprite);
    return sprite;
  });

  /* --- Contact shadow (cheap: a faded disc, no shadow map) ---------------- */
  const shadow = new THREE.Mesh(
    new THREE.CircleGeometry(1.6, 64),
    new THREE.MeshBasicMaterial({
      map: makeShadowTexture(THREE), transparent: true, depthWrite: false, opacity: 0.3,
    })
  );
  shadow.rotation.x = -Math.PI / 2;
  shadow.position.y = -0.14;

  /* --- Lights ------------------------------------------------------------- */
  scene.add(new THREE.HemisphereLight(0xffffff, 0xd8d2c0, 0.6));

  const key = new THREE.DirectionalLight(0xfff6e6, 1.7);
  key.position.set(3, 5, 4);
  scene.add(key);

  const rim = new THREE.DirectionalLight(0x9fc47c, 1.1);
  rim.position.set(-4, 2.2, -3);
  scene.add(rim);

  // Warms the inside of the cup, as if the brew were catching the light.
  const fill = new THREE.PointLight(0xe0a55c, 4, 6, 2);
  fill.position.set(0, 1.4, 0.5);
  scene.add(fill);

  /* --- Assemble ----------------------------------------------------------- */
  const rig = new THREE.Group();
  rig.add(cup, liquid, handle, saucer, shadow);
  rig.position.y = -0.55;
  scene.add(rig);

  /* --- Sizing -------------------------------------------------------------- */
  const resize = () => {
    const { width, height } = host.getBoundingClientRect();
    if (!width || !height) return;
    renderer.setSize(width, height, false);
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
  };
  resize();
  new ResizeObserver(resize).observe(host);

  /* --- Interaction: a little parallax, nothing dizzying -------------------- */
  const pointer = { x: 0, y: 0 };
  const target = { x: 0, y: 0 };
  window.addEventListener("pointermove", (event) => {
    target.x = (event.clientX / window.innerWidth - 0.5) * 2;
    target.y = (event.clientY / window.innerHeight - 0.5) * 2;
  }, { passive: true });

  /* --- Loop (paused when scrolled away or the tab is hidden) --------------- */
  let visible = true;
  new IntersectionObserver(
    ([entry]) => { visible = entry.isIntersecting; },
    { threshold: 0.01 }
  ).observe(host);

  const clock = new THREE.Clock();
  let revealed = false;

  renderer.setAnimationLoop(() => {
    if (!visible || document.hidden) return;

    // getDelta() advances the clock, so read it first and take elapsed after.
    const delta = Math.min(clock.getDelta(), 0.05);
    const elapsed = clock.elapsedTime;

    pointer.x += (target.x - pointer.x) * 0.045;
    pointer.y += (target.y - pointer.y) * 0.045;

    rig.rotation.y = elapsed * 0.13 + pointer.x * 0.28;
    rig.rotation.x = pointer.y * 0.08;
    rig.position.y = -0.55 + Math.sin(elapsed * 0.7) * 0.025;

    puffs.forEach((sprite) => {
      const data = sprite.userData;
      data.phase += delta * data.speed;
      if (data.phase > 1) {
        data.phase -= 1;
        data.angle = Math.random() * Math.PI * 2;
        data.radius = Math.random() * 0.42;
      }

      const life = data.phase;
      const spread = 1 + life * 2.4;
      sprite.position.set(
        Math.cos(data.angle) * data.radius + data.drift * life,
        0.42 + life * 1.25,
        Math.sin(data.angle) * data.radius
      );
      sprite.scale.setScalar(data.scale * spread);
      sprite.material.opacity = Math.sin(life * Math.PI) * 0.16;
    });

    renderer.render(scene, camera);

    if (!revealed) {
      revealed = true;
      canvas.classList.add("is-ready");
      fallback?.classList.add("is-hidden");
    }
  });
}

/* A soft radial blob, drawn once into a 2D canvas — no texture download. */
function makePuffTexture(THREE) {
  const size = 128;
  const c = document.createElement("canvas");
  c.width = c.height = size;
  const ctx = c.getContext("2d");
  const gradient = ctx.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
  gradient.addColorStop(0, "rgba(255,255,255,0.55)");
  gradient.addColorStop(0.35, "rgba(255,255,255,0.18)");
  gradient.addColorStop(1, "rgba(255,255,255,0)");
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, size, size);
  return new THREE.CanvasTexture(c);
}

function makeShadowTexture(THREE) {
  const size = 256;
  const c = document.createElement("canvas");
  c.width = c.height = size;
  const ctx = c.getContext("2d");
  const gradient = ctx.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
  gradient.addColorStop(0, "rgba(20,32,26,0.55)");
  gradient.addColorStop(0.55, "rgba(20,32,26,0.22)");
  gradient.addColorStop(1, "rgba(20,32,26,0)");
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, size, size);
  return new THREE.CanvasTexture(c);
}
