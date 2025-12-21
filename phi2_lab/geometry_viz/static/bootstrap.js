import * as THREE from './vendor/three.module.js';
import { OrbitControls } from './vendor/OrbitControls.js';

// Bridge module imports into the existing global-style dashboard code.
window.THREE = THREE;
THREE.OrbitControls = OrbitControls;
