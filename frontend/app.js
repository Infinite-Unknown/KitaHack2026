// --- Firebase Integration Example ---
import { initializeApp } from "https://www.gstatic.com/firebasejs/10.8.0/firebase-app.js";
import { getDatabase, ref, onValue, set } from "https://www.gstatic.com/firebasejs/10.8.0/firebase-database.js";

const firebaseConfig = {
    apiKey: "AIzaSyB36DBBAE72GaHqEfqlkDvckt4EKGt_Imc",
    authDomain: "gen-lang-client-0281295533.firebaseapp.com",
    databaseURL: "https://gen-lang-client-0281295533-default-rtdb.asia-southeast1.firebasedatabase.app",
    projectId: "gen-lang-client-0281295533",
    storageBucket: "gen-lang-client-0281295533.firebasestorage.app",
    messagingSenderId: "314995185032",
    appId: "1:314995185032:web:9e08397ddaf8b3a950563d",
    measurementId: "G-SJDWK5J29N"
};

const app = initializeApp(firebaseConfig);
const db = getDatabase(app);

// DOM Elements
const statusContainer = document.getElementById('statusContainer');
const statusText = document.getElementById('statusText');
const timestampText = document.getElementById('timestampText');
const statusIcon = document.getElementById('statusIcon');
const orb1 = document.querySelector('.orb-1');
const modeSelect = document.getElementById('modeSelect');

// SVG Paths
const normalPath = "M22 12h-4l-3 9L9 3l-3 9H2";
const alertPath = "M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z";

function updateStatus(data) {
    if (!data) return;

    // Handle string or object structure safely
    let statusStr = "Normal";
    let nodesData = {};

    if (typeof data === 'string') {
        statusStr = data;
    } else if (data.status) {
        statusStr = data.status;
        if (data.nodes) {
            nodesData = data.nodes;
        }
    }

    const isEmergency = statusStr.toLowerCase().includes("emergency");
    const isMotion = statusStr.toLowerCase().includes("motion");

    if (isEmergency) {
        statusContainer.classList.remove('normal', 'warning');
        statusContainer.classList.add('emergency');
        statusText.textContent = "EMERGENCY DETECTED";
        statusIcon.innerHTML = `<path d="${alertPath}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"></path>`;
        orb1.style.background = 'radial-gradient(circle, rgba(239, 68, 68, 0.3) 0%, transparent 70%)';
    } else if (isMotion) {
        statusContainer.classList.remove('normal', 'emergency');
        statusContainer.classList.add('warning');
        statusText.textContent = "MOTION DETECTED";
        // Can use the same alert icon or a different one for motion. Using alert for now.
        statusIcon.innerHTML = `<path d="${alertPath}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"></path>`;
        orb1.style.background = 'radial-gradient(circle, rgba(245, 158, 11, 0.3) 0%, transparent 70%)';
    } else {
        statusContainer.classList.remove('emergency', 'warning');
        statusContainer.classList.add('normal');
        statusText.textContent = "Normal Activity";
        statusIcon.innerHTML = `<path d="${normalPath}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"></path>`;
        orb1.style.background = 'radial-gradient(circle, rgba(74, 222, 128, 0.3) 0%, transparent 70%)';
    }

    const now = new Date();
    timestampText.textContent = `Last updated: ${now.toLocaleTimeString()}`;

    // Update Nodes Safely
    updateNodeUI("node-1", nodesData["ESP32_NODE_1"]);
    updateNodeUI("node-2", nodesData["ESP32_NODE_2"]);
    updateNodeUI("node-3", nodesData["ESP32_NODE_3"]);
    updateNodeUI("node-4", nodesData["ESP32_NODE_4"]);
}

function updateNodeUI(elementId, status) {
    const card = document.getElementById(elementId);
    if (!card) return;

    const dot = card.querySelector('.status-dot');
    const statusText = card.querySelector('.node-status-text');

    if (status === "online") {
        dot.classList.add('healthy');
        dot.classList.remove('offline');
        statusText.textContent = "Status: Online";
    } else {
        dot.classList.remove('healthy');
        dot.classList.add('offline');
        statusText.textContent = "Status: Offline";
    }
}

// Default state
updateStatus("Normal");

// --- Mocking Data for testing without Firebase ---
/*
setInterval(() => {
    const rand = Math.random();
    if(rand > 0.8) {
        updateStatus("Emergency");
        setTimeout(() => updateStatus("Normal"), 5000);
    }
}, 8000);
*/

const statusRef = ref(db, 'status');
onValue(statusRef, (snapshot) => {
    const data = snapshot.val();
    console.log("Firebase Status Received:", data);
    if (data) updateStatus(data);
});

// --- Mode Syncing ---
const modeRef = ref(db, 'mode');

// Listen for mode changes from backend
onValue(modeRef, (snapshot) => {
    const data = snapshot.val();
    if (data && data.mode) {
        console.log("Firebase Mode sync from backend:", data.mode);
        if (modeSelect.value !== data.mode) {
            modeSelect.value = data.mode;
        }
    }
});

// Send mode changes to backend when user changes the dropdown
modeSelect.addEventListener('change', (e) => {
    const newMode = e.target.value;
    console.log("User changing mode to:", newMode);
    set(modeRef, { mode: newMode })
        .then(() => console.log('Mode update sent to Firebase successfully'))
        .catch((error) => console.error('Error updating mode in Firebase:', error));
});

