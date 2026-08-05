import * as THREE from "three";

/* Concept A — "Convergence"
 * A turbulent cloud of paper fragments assembles, via scroll progress t,
 * into a 3D ARR waterfall. Values transcribed from
 * docs/site/artifacts/specs/arr-waterfall.json (Q1 10.0, +3.0, +2.5, -0.5, Q4 15.0).
 */

const PALETTE = {
  navy: 0x15296b,
  blue: 0x2563eb,
  ink: 0x000000,
  grey700: 0x374151,
  grey500: 0x6b7280,
  grey300: 0xd1d5db,
  fill: 0xf3f4f6,
  tint: 0xeff3fb,
  risk: 0xb91c1c,
  paper: 0xffffff,
};

const UNIT = 0.29; // world units per $1M
const BARS = [
  { from: 0, to: 10.0, kind: "total", text: "$10M" },
  { from: 10.0, to: 13.0, kind: "driver", text: "+$3M" },
  { from: 13.0, to: 15.5, kind: "driver", text: "+$2.5M" },
  { from: 15.5, to: 15.0, kind: "risk", text: "-$0.5M" },
  { from: 0, to: 15.0, kind: "total", text: "$15M" },
];

const BAR_W = 0.9;
const BAR_D = 0.5;
const BAR_PITCH = 1.35;
const SLICE_H = 0.048;
const BAR_T0 = 0.22;
const BAR_T_STEP = 0.095;
const BAR_T_DUR = 0.26;

const CAM_BASE = new THREE.Vector3(5.6, 3.6, 8.2);
const CAM_TARGET = new THREE.Vector3(0, 2.05, 0);

const FLOOR_Y = -0.05;
const FLOOR_X = 3.9;
const FLOOR_Z = 2.6;
const FLOOR_STEP = 0.4333;

// 3x5 micro-font: the drifting dots settle into the bars' value labels
const GLYPHS = {
  0: ["111", "101", "101", "101", "111"],
  1: ["010", "110", "010", "010", "111"],
  2: ["111", "001", "111", "100", "111"],
  3: ["111", "001", "111", "001", "111"],
  5: ["111", "100", "111", "001", "111"],
  ".": ["000", "000", "000", "000", "010"],
  "+": ["000", "010", "111", "010", "000"],
  "-": ["000", "000", "111", "000", "000"],
  $: ["010", "111", "110", "011", "111"],
  M: ["101", "111", "111", "101", "101"],
};

function mulberry32(seed) {
  let a = seed >>> 0;
  return function () {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const clamp01 = (x) => (x < 0 ? 0 : x > 1 ? 1 : x);
const smooth = (x) => {
  const c = clamp01(x);
  return c * c * (3 - 2 * c);
};

const X_AXIS = new THREE.Vector3(1, 0, 0);
const Y_AXIS = new THREE.Vector3(0, 1, 0);
const IDENTITY_Q = new THREE.Quaternion();

function buildPlan() {
  const rand = mulberry32(1337);
  const shards = [];
  const scraps = [];
  const dots = [];

  const C_NAVY = new THREE.Color(PALETTE.navy);
  const C_RISK = new THREE.Color(PALETTE.risk);
  const C_INK = new THREE.Color(PALETTE.ink);
  const C_BLUE = new THREE.Color(PALETTE.blue);
  const C_GREY700 = new THREE.Color(PALETTE.grey700);
  const C_GREY500 = new THREE.Color(PALETTE.grey500);
  const C_GREY300 = new THREE.Color(PALETTE.grey300);
  const C_FILL = new THREE.Color(PALETTE.fill);
  const C_TINT = new THREE.Color(PALETTE.tint);

  const chaos = (targetScale) => {
    const axis = new THREE.Vector3(
      rand() * 2 - 1,
      rand() * 2 - 1,
      rand() * 2 - 1,
    );
    if (axis.lengthSq() < 1e-6) axis.set(0, 1, 0);
    axis.normalize();
    return {
      cPos: new THREE.Vector3(
        (rand() * 2 - 1) * 7.4,
        0.25 + rand() * 6.3,
        (rand() * 2 - 1) * 4.8,
      ),
      cQuat: new THREE.Quaternion().setFromEuler(
        new THREE.Euler(
          rand() * Math.PI * 2,
          rand() * Math.PI * 2,
          rand() * Math.PI * 2,
        ),
      ),
      cScale: targetScale.clone().multiplyScalar(0.55 + rand() * 0.9),
      spinAxis: axis,
      spinRate: (rand() - 0.5) * 1.1,
      dAmp: 0.2 + rand() * 0.24,
      dFreq: [0.12 + rand() * 0.22, 0.12 + rand() * 0.22, 0.12 + rand() * 0.22],
      dPhase: [
        rand() * Math.PI * 2,
        rand() * Math.PI * 2,
        rand() * Math.PI * 2,
      ],
    };
  };

  const barX = (i) => (i - 2) * BAR_PITCH;

  // Bars: horizontal slices, two shards deep, bottom-to-top stagger
  BARS.forEach((bar, bi) => {
    const base = Math.min(bar.from, bar.to) * UNIT;
    const h = Math.abs(bar.to - bar.from) * UNIT;
    const layers = Math.max(2, Math.round(h / SLICE_H));
    const sliceH = h / layers;
    const c1 = bar.kind === "risk" ? C_RISK : C_NAVY;
    const w0Bar = BAR_T0 + bi * BAR_T_STEP;
    for (let j = 0; j < layers; j++) {
      for (let k = 0; k < 2; k++) {
        const tScale = new THREE.Vector3(
          BAR_W,
          sliceH * 0.88,
          (BAR_D / 2) * 0.92,
        );
        const w0 = w0Bar + (j / layers) * BAR_T_DUR * 0.55 + rand() * 0.015;
        shards.push({
          ...chaos(tScale),
          tPos: new THREE.Vector3(
            barX(bi),
            base + (j + 0.5) * sliceH,
            (k === 0 ? -1 : 1) * (BAR_D / 4),
          ),
          tQuat: IDENTITY_Q.clone(),
          tScale,
          c0: C_FILL,
          c1,
          w0,
          w1: w0 + BAR_T_DUR * 0.45,
        });
      }
    }
  });

  // Baseline axis
  {
    const tScale = new THREE.Vector3(7.5, 0.03, 0.06);
    shards.push({
      ...chaos(tScale),
      tPos: new THREE.Vector3(0, -0.015, 0),
      tQuat: IDENTITY_Q.clone(),
      tScale,
      c0: C_GREY300,
      c1: C_GREY700,
      w0: 0.14,
      w1: 0.32,
    });
  }

  // Dashed connectors at each cumulative level
  for (let i = 0; i < BARS.length - 1; i++) {
    const y = BARS[i].to * UNIT;
    const left = barX(i) + BAR_W / 2;
    const w0 = BAR_T0 + (i + 1) * BAR_T_STEP - 0.03;
    for (let d = 0; d < 3; d++) {
      const tScale = new THREE.Vector3(0.1, 0.02, 0.03);
      shards.push({
        ...chaos(tScale),
        tPos: new THREE.Vector3(left + 0.05 + d * 0.175, y, 0),
        tQuat: IDENTITY_Q.clone(),
        tScale,
        c0: C_FILL,
        c1: C_GREY300,
        w0,
        w1: w0 + 0.12,
      });
    }
  }

  // Floor: 8px-style grid, each line built from paper-scrap segments
  const qFlat = new THREE.Quaternion().setFromAxisAngle(X_AXIS, -Math.PI / 2);
  const qFlatZ = new THREE.Quaternion()
    .setFromAxisAngle(Y_AXIS, Math.PI / 2)
    .multiply(qFlat);
  const nzLines = Math.round((FLOOR_Z * 2) / FLOOR_STEP) + 1;
  const nxLines = Math.round((FLOOR_X * 2) / FLOOR_STEP) + 1;
  for (let zi = 0; zi < nzLines; zi++) {
    const z = -FLOOR_Z + zi * FLOOR_STEP;
    for (let seg = 0; seg < 4; seg++) {
      const len = (FLOOR_X * 2) / 4 - 0.06;
      const tScale = new THREE.Vector3(len, 0.014, 1);
      const w0 = 0.02 + rand() * 0.06;
      scraps.push({
        ...chaos(tScale),
        tPos: new THREE.Vector3(
          -FLOOR_X + (seg + 0.5) * ((FLOOR_X * 2) / 4),
          FLOOR_Y,
          z,
        ),
        tQuat: qFlat.clone(),
        tScale,
        c0: rand() < 0.5 ? C_TINT : C_FILL,
        c1: C_GREY300,
        w0,
        w1: w0 + 0.3,
      });
    }
  }
  for (let xi = 0; xi < nxLines; xi++) {
    const x = -FLOOR_X + xi * FLOOR_STEP;
    for (let seg = 0; seg < 3; seg++) {
      const len = (FLOOR_Z * 2) / 3 - 0.06;
      const tScale = new THREE.Vector3(len, 0.014, 1);
      const w0 = 0.02 + rand() * 0.06;
      scraps.push({
        ...chaos(tScale),
        tPos: new THREE.Vector3(
          x,
          FLOOR_Y,
          -FLOOR_Z + (seg + 0.5) * ((FLOOR_Z * 2) / 3),
        ),
        tQuat: qFlatZ.clone(),
        tScale,
        c0: rand() < 0.5 ? C_TINT : C_FILL,
        c1: C_GREY300,
        w0,
        w1: w0 + 0.3,
      });
    }
  }

  // Grid-intersection accent dots
  for (let xi = 0; xi < nxLines; xi += 4) {
    for (let zi = 0; zi < nzLines; zi += 4) {
      const tScale = new THREE.Vector3(0.03, 0.03, 0.03);
      const w0 = 0.05 + rand() * 0.08;
      dots.push({
        ...chaos(tScale),
        tPos: new THREE.Vector3(
          -FLOOR_X + xi * FLOOR_STEP,
          FLOOR_Y + 0.005,
          -FLOOR_Z + zi * FLOOR_STEP,
        ),
        tQuat: IDENTITY_Q.clone(),
        tScale,
        c0: C_GREY300,
        c1: (xi + zi) % 3 === 0 ? C_GREY500 : C_BLUE,
        w0,
        w1: w0 + 0.25,
      });
    }
  }

  // Value labels: dot-matrix digits hovering above each bar top
  BARS.forEach((bar, bi) => {
    const bx = barX(bi);
    const topY = Math.max(bar.from, bar.to) * UNIT;
    const chars = bar.text.split("");
    let pitch = 0.038;
    const fit = Math.min(1, 1.05 / ((chars.length * 4 - 1) * pitch));
    pitch *= fit;
    const width = (chars.length * 4 - 1) * pitch;
    const yaw = Math.atan2(CAM_BASE.x - bx, CAM_BASE.z);
    const cosY = Math.cos(yaw);
    const sinY = Math.sin(yaw);
    const barEnd = BAR_T0 + bi * BAR_T_STEP + BAR_T_DUR;
    chars.forEach((ch, ci) => {
      const rows = GLYPHS[ch];
      if (!rows) return;
      for (let r = 0; r < 5; r++) {
        for (let c = 0; c < 3; c++) {
          if (rows[r][c] !== "1") continue;
          const lx = (ci * 4 + c) * pitch - width / 2;
          const ly = (2 - r) * pitch;
          const px = 0.027 * fit;
          const tScale = new THREE.Vector3(px, px, px);
          const w0 = barEnd - 0.08 + ci * 0.014 + rand() * 0.02;
          dots.push({
            ...chaos(tScale),
            tPos: new THREE.Vector3(
              bx + lx * cosY,
              topY + 0.2 + ly,
              -lx * sinY,
            ),
            tQuat: IDENTITY_Q.clone(),
            tScale,
            c0: C_GREY500,
            c1: C_INK,
            w0,
            w1: w0 + 0.14,
          });
        }
      }
    });
  });

  return { shards, scraps, dots };
}

export function initHero(
  canvas,
  { reducedMotion = false, staticMode = false } = {},
) {
  const renderer = new THREE.WebGLRenderer({
    canvas,
    antialias: true,
    powerPreference: "high-performance",
  });
  renderer.setClearColor(PALETTE.paper, 1);

  const scene = new THREE.Scene();
  scene.background = new THREE.Color(PALETTE.paper);
  scene.fog = new THREE.Fog(PALETTE.paper, 13, 24);

  const camera = new THREE.PerspectiveCamera(37, 1, 0.1, 60);
  camera.position.copy(CAM_BASE);
  camera.lookAt(CAM_TARGET);

  scene.add(new THREE.HemisphereLight(PALETTE.paper, PALETTE.tint, 1.0));
  const dir = new THREE.DirectionalLight(PALETTE.paper, 2.1);
  dir.position.set(5, 9, 6);
  scene.add(dir);

  const plan = buildPlan();
  const meshes = [];
  const makePool = (geometry, items, materialOpts) => {
    const material = new THREE.MeshLambertMaterial({
      color: 0xffffff,
      ...materialOpts,
    });
    const mesh = new THREE.InstancedMesh(geometry, material, items.length);
    mesh.frustumCulled = false;
    mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
    for (let i = 0; i < items.length; i++) mesh.setColorAt(i, items[i].c0);
    mesh.instanceColor.setUsage(THREE.DynamicDrawUsage);
    scene.add(mesh);
    meshes.push(mesh);
    return mesh;
  };

  const pools = [
    {
      mesh: makePool(new THREE.BoxGeometry(1, 1, 1), plan.shards),
      items: plan.shards,
    },
    {
      mesh: makePool(new THREE.PlaneGeometry(1, 1), plan.scraps, {
        side: THREE.DoubleSide,
      }),
      items: plan.scraps,
    },
    {
      mesh: makePool(new THREE.SphereGeometry(0.5, 8, 6), plan.dots),
      items: plan.dots,
    },
  ];

  const state = { t: reducedMotion ? 1 : 0, time: 0 };
  let lastMatrixT = -1;
  let lastMatrixTime = -1;
  let lastColorT = -1;

  const _p = new THREE.Vector3();
  const _s = new THREE.Vector3();
  const _q = new THREE.Quaternion();
  const _qs = new THREE.Quaternion();
  const _m = new THREE.Matrix4();
  const _c = new THREE.Color();

  function renderFrame() {
    const t = state.t;
    const time = state.time;

    // Matrices depend on (t, time) while drifting; at t=1 the frame is pinned
    if (t !== lastMatrixT || (t < 1 && time !== lastMatrixTime)) {
      for (const { mesh, items } of pools) {
        for (let i = 0; i < items.length; i++) {
          const f = items[i];
          const e = smooth((t - f.w0) / (f.w1 - f.w0));
          _p.set(
            f.cPos.x + Math.sin(time * f.dFreq[0] + f.dPhase[0]) * f.dAmp,
            f.cPos.y + Math.sin(time * f.dFreq[1] + f.dPhase[1]) * f.dAmp * 0.7,
            f.cPos.z + Math.cos(time * f.dFreq[2] + f.dPhase[2]) * f.dAmp,
          );
          _p.lerp(f.tPos, e);
          _qs.setFromAxisAngle(f.spinAxis, time * f.spinRate).multiply(f.cQuat);
          _q.slerpQuaternions(_qs, f.tQuat, e);
          _s.copy(f.cScale).lerp(f.tScale, e);
          _m.compose(_p, _q, _s);
          mesh.setMatrixAt(i, _m);
        }
        mesh.instanceMatrix.needsUpdate = true;
      }
      lastMatrixT = t;
      lastMatrixTime = time;
    }

    // Colors depend on t only — skip uploads while t is unchanged
    if (t !== lastColorT) {
      for (const { mesh, items } of pools) {
        for (let i = 0; i < items.length; i++) {
          const f = items[i];
          _c.copy(f.c0).lerp(f.c1, smooth((t - f.w0) / (f.w1 - f.w0)));
          mesh.setColorAt(i, _c);
        }
        mesh.instanceColor.needsUpdate = true;
      }
      lastColorT = t;
    }

    const sway = 1 - t;
    camera.position.set(
      CAM_BASE.x + Math.sin(time * 0.21) * 0.16 * sway,
      CAM_BASE.y + Math.sin(time * 0.27 + 1.3) * 0.1 * sway,
      CAM_BASE.z + Math.cos(time * 0.17) * 0.12 * sway,
    );
    camera.lookAt(CAM_TARGET);
    renderer.render(scene, camera);
  }

  const animated = !reducedMotion && !staticMode;
  let rafId = 0;
  let lastNow = -1;
  let disposed = false;

  function tick(now) {
    if (disposed) return;
    rafId = requestAnimationFrame(tick);
    if (state.t === 1 && lastMatrixT === 1 && lastColorT === 1) {
      lastNow = now;
      return; // fully assembled frame is static — skip redundant GPU work
    }
    if (lastNow < 0) lastNow = now;
    const dt = Math.min((now - lastNow) / 1000, 0.05);
    lastNow = now;
    if (!document.hidden) state.time += dt; // idle drift advances only via rAF while visible
    renderFrame();
  }

  function onResize() {
    const w = canvas.clientWidth || window.innerWidth;
    const h = canvas.clientHeight || window.innerHeight;
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.setSize(Math.max(1, w), Math.max(1, h), false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    renderFrame();
  }

  window.addEventListener("resize", onResize);
  onResize();
  if (animated) rafId = requestAnimationFrame(tick);

  return {
    setProgress(t) {
      if (disposed || reducedMotion) return; // reducedMotion stays locked at t=1
      state.t = clamp01(Number(t) || 0);
      if (!animated) renderFrame();
    },
    dispose() {
      if (disposed) return;
      disposed = true;
      cancelAnimationFrame(rafId);
      window.removeEventListener("resize", onResize);
      for (const mesh of meshes) {
        scene.remove(mesh);
        mesh.dispose();
        mesh.geometry.dispose();
        mesh.material.dispose();
      }
      renderer.dispose();
    },
  };
}
