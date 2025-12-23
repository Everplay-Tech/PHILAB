import * as THREE from './vendor/three.module.js';
import { OrbitControls } from './vendor/OrbitControls.js';

// Bridge module imports into the existing global-style dashboard code.
// Note: THREE is a frozen ES module, so we create a new object with OrbitControls attached.
window.THREE = Object.assign({}, THREE, { OrbitControls });
