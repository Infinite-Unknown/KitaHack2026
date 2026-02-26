// --- Firebase Integration Example ---
import { initializeApp } from "https://www.gstatic.com/firebasejs/10.8.0/firebase-app.js";
import { getDatabase, ref, onValue } from "https://www.gstatic.com/firebasejs/10.8.0/firebase-database.js";

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

    if (isEmergency) {
        statusContainer.classList.remove('normal');
        statusContainer.classList.add('emergency');
        statusText.textContent = "EMERGENCY DETECTED";
        statusIcon.innerHTML = `<path d="${alertPath}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"></path>`;
        orb1.style.background = 'radial-gradient(circle, rgba(239, 68, 68, 0.3) 0%, transparent 70%)';
    } else {
        statusContainer.classList.remove('emergency');
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

// --- Firebase Listener ---
const statusRef = ref(db, 'status');
onValue(statusRef, (snapshot) => {
    const data = snapshot.val();
    console.log("Firebase Data Received:", data);
    if (data) updateStatus(data);
});
