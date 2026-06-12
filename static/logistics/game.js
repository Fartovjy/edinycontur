/**
 * Logistics Flow (Логистический Переполох)
 * Django Production Integrated Client Engine
 */

window.onerror = function(message, source, lineno, colno, error) {
    alert("Ошибка скрипта: " + message + " (строка " + lineno + ")");
    console.error("Script error:", message, "at", source, "line", lineno, "col", colno, error);
    return false;
};

// --- Cities and Colors mapping ---
const CITY_COLORS = {
    'МСК': 'red',
    'СПБ': 'orange',
    'КЗН': 'yellow',
    'ЕКБ': 'green',
    'НСК': 'cyan',
    'КРД': 'blue',
    'ВЛД': 'purple'
};

const COLOR_HEX = {
    neutral: '#64748b',
    red: '#ef4444',
    orange: '#f97316',
    yellow: '#eab308',
    green: '#22c55e',
    cyan: '#06b6d4',
    blue: '#3b82f6',
    purple: '#a855f7'
};

// --- API Paths ---
const API_URLS = {
    getApi: '/games/api/',
    assign: '/games/assign/',
    depart: '/games/depart/'
};

// --- Game State Variables ---
let gameState = 'START_SCREEN'; // START_SCREEN, PLAYING, PAUSED, GAMEOVER
let score = 0;
let highScore = 0;
let level = 1;
let reputation = 100;
let lastTime = 0;

// Conveyor & Boxes
let boxes = [];
const maxDaysHorizon = 15; // 15 days left maps to 0% conveyor progress, 0 days left maps to 100% (right end)
const dayRealtimeSeconds = 5; // 1 day of days_left ticks down in 5 seconds of real-time
let baseBoxSpeed = 50; 
let currentBoxSpeed = 50;

// Interaction
let draggedBox = null;
let draggedBoxElement = null;
let dragStartX = 0;
let dragStartY = 0;
let dragOffset = { x: 0, y: 0 };
let activeTouchId = null;
let selectedBox = null;

// Sound settings
let isMuted = false;
let audioCtx = null;

// Breakdowns (simulated fleet disruptions)
let breakdownTimer = 18; 

// Trucks list (populated dynamically from Django API)
let trucks = [];
let isTrucksInitialized = false;

// Polling timer
let apiPollTimer = 0;
const API_POLL_INTERVAL = 20; // seconds

// --- Particle System ---
const particles = [];
let canvas = null;
let ctx = null;

class Particle {
    constructor(x, y, color, type = 'spark') {
        this.x = x;
        this.y = y;
        this.color = color;
        this.type = type;
        
        if (type === 'smoke') {
            this.size = Math.random() * 10 + 8;
            this.speedX = (Math.random() - 0.5) * 1.5;
            this.speedY = -Math.random() * 2 - 1;
            this.gravity = -0.02;
            this.alpha = 0.7;
            this.decay = Math.random() * 0.015 + 0.01;
        } else {
            this.size = Math.random() * 5 + 3;
            this.speedX = (Math.random() - 0.5) * 8;
            this.speedY = (Math.random() - 0.5) * 8 - 2;
            this.gravity = 0.15;
            this.alpha = 1;
            this.decay = Math.random() * 0.02 + 0.015;
        }
    }

    update() {
        this.x += this.speedX;
        this.y += this.speedY;
        this.speedY += this.gravity;
        this.alpha -= this.decay;
    }

    draw() {
        ctx.save();
        ctx.globalAlpha = Math.max(0, this.alpha);
        ctx.fillStyle = this.color;
        ctx.beginPath();
        ctx.arc(this.x, this.y, this.size, 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();
    }
}

// Helper to fetch CSRF token from cookies
function getCsrfToken() {
    return document.cookie.match(/csrftoken=([^;]+)/)?.[1] || '';
}

// --- Synthesizer Sound Engine (Web Audio API) ---
function initAudio() {
    try {
        if (!audioCtx) {
            const AudioCtxClass = window.AudioContext || window.webkitAudioContext;
            if (AudioCtxClass) {
                audioCtx = new AudioCtxClass();
            }
        }
    } catch (e) {
        console.warn('Web Audio API could not be initialized:', e);
    }
}

function playSound(type) {
    if (isMuted) return;
    initAudio();
    if (!audioCtx) return;
    try {
        if (audioCtx.state === 'suspended') {
            audioCtx.resume();
        }
    } catch (e) {
        console.warn('AudioContext resume failed:', e);
        return;
    }

    const t = audioCtx.currentTime;
    
    try {
        switch (type) {
            case 'spawn': {
                const osc = audioCtx.createOscillator();
                const gain = audioCtx.createGain();
                osc.connect(gain); gain.connect(audioCtx.destination);
                osc.type = 'sine';
                osc.frequency.setValueAtTime(400, t);
                osc.frequency.exponentialRampToValueAtTime(700, t + 0.07);
                gain.gain.setValueAtTime(0.06, t);
                gain.gain.exponentialRampToValueAtTime(0.005, t + 0.07);
                osc.start(t); osc.stop(t + 0.07);
                break;
            }
            case 'load': {
                const osc = audioCtx.createOscillator();
                const gain = audioCtx.createGain();
                osc.connect(gain); gain.connect(audioCtx.destination);
                osc.type = 'triangle';
                osc.frequency.setValueAtTime(587.33, t);
                osc.frequency.exponentialRampToValueAtTime(880, t + 0.12);
                gain.gain.setValueAtTime(0.08, t);
                gain.gain.exponentialRampToValueAtTime(0.005, t + 0.12);
                osc.start(t); osc.stop(t + 0.12);
                break;
            }
            case 'unload': {
                const osc = audioCtx.createOscillator();
                const gain = audioCtx.createGain();
                osc.connect(gain); gain.connect(audioCtx.destination);
                osc.type = 'triangle';
                osc.frequency.setValueAtTime(880, t);
                osc.frequency.exponentialRampToValueAtTime(587.33, t + 0.12);
                gain.gain.setValueAtTime(0.08, t);
                gain.gain.exponentialRampToValueAtTime(0.005, t + 0.12);
                osc.start(t); osc.stop(t + 0.12);
                break;
            }
            case 'depart': {
                const osc = audioCtx.createOscillator();
                const gain = audioCtx.createGain();
                osc.connect(gain); gain.connect(audioCtx.destination);
                osc.type = 'sawtooth';
                osc.frequency.setValueAtTime(150, t);
                osc.frequency.linearRampToValueAtTime(50, t + 0.7);
                gain.gain.setValueAtTime(0.12, t);
                gain.gain.linearRampToValueAtTime(0.01, t + 0.7);
                osc.start(t); osc.stop(t + 0.7);
                break;
            }
            case 'alarm': {
                const osc = audioCtx.createOscillator();
                const gain = audioCtx.createGain();
                osc.connect(gain); gain.connect(audioCtx.destination);
                osc.type = 'square';
                osc.frequency.setValueAtTime(660, t);
                osc.frequency.setValueAtTime(440, t + 0.15);
                gain.gain.setValueAtTime(0.1, t);
                gain.gain.linearRampToValueAtTime(0.005, t + 0.3);
                osc.start(t); osc.stop(t + 0.3);
                break;
            }
            case 'repaired': {
                const osc = audioCtx.createOscillator();
                const gain = audioCtx.createGain();
                osc.connect(gain); gain.connect(audioCtx.destination);
                osc.type = 'sine';
                osc.frequency.setValueAtTime(440, t);
                osc.frequency.setValueAtTime(880, t + 0.1);
                gain.gain.setValueAtTime(0.1, t);
                gain.gain.linearRampToValueAtTime(0.005, t + 0.2);
                osc.start(t); osc.stop(t + 0.2);
                break;
            }
            case 'error': {
                const osc = audioCtx.createOscillator();
                const gain = audioCtx.createGain();
                osc.connect(gain); gain.connect(audioCtx.destination);
                osc.type = 'square';
                osc.frequency.setValueAtTime(110, t);
                gain.gain.setValueAtTime(0.12, t);
                gain.gain.linearRampToValueAtTime(0.01, t + 0.25);
                osc.start(t); osc.stop(t + 0.25);
                break;
            }
            case 'recycler': {
                const osc = audioCtx.createOscillator();
                const gain = audioCtx.createGain();
                osc.connect(gain); gain.connect(audioCtx.destination);
                osc.type = 'sawtooth';
                osc.frequency.setValueAtTime(220, t);
                osc.frequency.exponentialRampToValueAtTime(70, t + 0.35);
                gain.gain.setValueAtTime(0.1, t);
                gain.gain.linearRampToValueAtTime(0.01, t + 0.35);
                osc.start(t); osc.stop(t + 0.35);
                break;
            }
            case 'perfect': {
                const freqs = [523.25, 659.25, 783.99, 1046.50];
                freqs.forEach((f, i) => {
                    const osc = audioCtx.createOscillator();
                    const gain = audioCtx.createGain();
                    osc.connect(gain); gain.connect(audioCtx.destination);
                    osc.type = 'sine';
                    osc.frequency.setValueAtTime(f, t + i * 0.07);
                    gain.gain.setValueAtTime(0.08, t + i * 0.07);
                    gain.gain.exponentialRampToValueAtTime(0.005, t + i * 0.07 + 0.25);
                    osc.start(t + i * 0.07); osc.stop(t + i * 0.07 + 0.25);
                });
                break;
            }
            case 'levelUp': {
                const osc = audioCtx.createOscillator();
                const gain = audioCtx.createGain();
                osc.connect(gain); gain.connect(audioCtx.destination);
                osc.type = 'sine';
                osc.frequency.setValueAtTime(330, t);
                osc.frequency.exponentialRampToValueAtTime(1320, t + 0.35);
                gain.gain.setValueAtTime(0.1, t);
                gain.gain.exponentialRampToValueAtTime(0.01, t + 0.35);
                osc.start(t); osc.stop(t + 0.35);
                break;
            }
            case 'gameOver': {
                const notes = [392.00, 349.23, 311.13, 261.63];
                notes.forEach((f, i) => {
                    const osc = audioCtx.createOscillator();
                    const gain = audioCtx.createGain();
                    osc.connect(gain); gain.connect(audioCtx.destination);
                    osc.type = 'triangle';
                    osc.frequency.setValueAtTime(f, t + i * 0.15);
                    gain.gain.setValueAtTime(0.12, t + i * 0.15);
                    gain.gain.linearRampToValueAtTime(0.005, t + i * 0.15 + 0.35);
                    osc.start(t + i * 0.15); osc.stop(t + i * 0.15 + 0.35);
                });
                break;
            }
        }
    } catch (e) {
        console.warn('Playing sound failed:', e);
    }
}

// --- DOM elements ---
const domStartScreen = document.getElementById('screen-start');
const domPauseScreen = document.getElementById('screen-pause');
const domGameOverScreen = document.getElementById('screen-gameover');
const domScoreVal = document.getElementById('score-val');
const domHighScoreVal = document.getElementById('highscore-val');
const domStartHighScoreVal = document.getElementById('start-highscore');
const domLevelVal = document.getElementById('level-val');
const domReputationPct = document.getElementById('reputation-pct');
const domReputationBarFill = document.getElementById('reputation-bar-fill');
const domConveyorBoxes = document.getElementById('conveyor-boxes');
const domTrucksBay = document.getElementById('trucks-bay');
const domDragOverlay = document.getElementById('drag-overlay');
const domParticlesCanvas = document.getElementById('particles-canvas');

// --- Initialization ---
function init() {
    setupCanvas();
    loadHighScore();
    setupEventListeners();
    
    // Initial fetch of DB state
    pollApi(true);
    
    requestAnimationFrame(updateLoop);
}

function setupCanvas() {
    canvas = domParticlesCanvas;
    ctx = canvas.getContext('2d');
    resizeCanvas();
    window.addEventListener('resize', resizeCanvas);
}

function resizeCanvas() {
    const rect = canvas.parentNode.getBoundingClientRect();
    canvas.width = rect.width;
    canvas.height = rect.height;
}

function loadHighScore() {
    try {
        const saved = localStorage.getItem('logisticsflow_highscore');
        if (saved) {
            highScore = parseInt(saved, 10);
            domHighScoreVal.textContent = highScore;
            domStartHighScoreVal.textContent = highScore;
        }
    } catch (e) {
        console.warn('localStorage is not accessible:', e);
    }
}

function saveHighScore() {
    if (score > highScore) {
        highScore = score;
        try {
            localStorage.setItem('logisticsflow_highscore', highScore);
        } catch (e) {
            console.warn('localStorage is not writeable:', e);
        }
        domHighScoreVal.textContent = highScore;
    }
}

// --- API Polling and State Sync ---
async function pollApi(isInitial = false) {
    try {
        const response = await fetch(API_URLS.getApi);
        if (!response.ok) throw new Error('API fetch failed');
        const data = await response.json();
        
        syncVehicles(data.vehicles, isInitial);
        syncRequests(data.requests);
    } catch (err) {
        console.error('Error polling API:', err);
    }
}

// Populate / update fleet cards dynamically
function syncVehicles(apiVehicles, isInitial) {
    if (isInitial || !isTrucksInitialized) {
        trucks = apiVehicles.map((v, index) => {
            // Map capacity in kg to 3, 6, 9 visual slots
            let capacity = 6;
            let type = 'Камаз';
            let scoreMult = 1.5;
            if (v.capacity_kg <= 3500) {
                capacity = 3;
                type = 'Газель';
                scoreMult = 1.0;
            } else if (v.capacity_kg > 12000) {
                capacity = 9;
                type = 'Фура';
                scoreMult = 2.2;
            }

            // Sync loaded requests
            let loadedUnits = 0;
            let loadedBoxes = [];
            if (v.assigned_requests) {
                v.assigned_requests.forEach(r => {
                    let size = 1;
                    if (r.weight_kg > 3000) size = 3;
                    else if (r.weight_kg > 1000) size = 2;
                    
                    loadedUnits += size;
                    loadedBoxes.push({
                        id: r.id,
                        number: r.number,
                        client: r.client,
                        size: size,
                        weight_kg: r.weight_kg,
                        deadline: r.days_left * dayRealtimeSeconds // convert remaining days to seconds
                    });
                });
            }

            let color = 'neutral';
            let isAssigned = false;
            let assignedCity = '';
            let assignedAbbr = '';
            if (loadedBoxes.length > 0) {
                assignedAbbr = loadedBoxes[0].number.split('-')[0]; // Extract city abbr from number, e.g. "ЕК"
                if (assignedAbbr === 'ЕК') assignedAbbr = 'ЕКБ'; // normalise ЕК -> ЕКБ
                color = CITY_COLORS[assignedAbbr] || 'neutral';
                isAssigned = true;
                assignedCity = CITIES_BY_ABBR[assignedAbbr] || 'Город';
            }

            return {
                id: v.id,
                index: index,
                plate: v.plate,
                name: v.name,
                driver: v.driver,
                type: type,
                capacity: capacity,
                scoreMult: scoreMult,
                
                color: color,
                isAssigned: isAssigned,
                assignedCity: assignedCity,
                assignedAbbr: assignedAbbr,
                
                loadedUnits: loadedUnits,
                loadedBoxes: loadedBoxes,
                timer: 0,
                isTimerActive: loadedBoxes.length > 0,
                isDeparting: false,
                isBroken: false
            };
        });
        
        renderTruckSlots();
        isTrucksInitialized = true;
    } else {
        // Incremental updates: update status parameters of loaded trucks if changed on server
        apiVehicles.forEach(apiV => {
            const localT = trucks.find(t => t.id === apiV.id);
            if (localT && !localT.isDeparting && !localT.isBroken) {
                // If cargo count changed in DB, rebuild cargo hold blocks
                const apiCount = apiV.assigned_requests ? apiV.assigned_requests.length : 0;
                if (apiCount !== localT.loadedBoxes.length) {
                    localT.loadedBoxes = [];
                    localT.loadedUnits = 0;
                    
                    if (apiV.assigned_requests) {
                        apiV.assigned_requests.forEach(r => {
                            let size = 1;
                            if (r.weight_kg > 3000) size = 3;
                            else if (r.weight_kg > 1000) size = 2;
                            
                            localT.loadedUnits += size;
                            localT.loadedBoxes.push({
                                id: r.id,
                                number: r.number,
                                size: size,
                                weight_kg: r.weight_kg,
                                deadline: r.days_left * dayRealtimeSeconds
                            });
                        });
                    }
                    
                    // Update routing colors based on first loaded
                    if (localT.loadedBoxes.length > 0) {
                        localT.assignedAbbr = localT.loadedBoxes[0].number.substring(0, 2);
                        // Normalise abbreviations
                        if (localT.assignedAbbr === 'ЕК') localT.assignedAbbr = 'ЕКБ';
                        if (localT.assignedAbbr === 'МС') localT.assignedAbbr = 'МСК';
                        if (localT.assignedAbbr === 'СП') localT.assignedAbbr = 'СПБ';
                        if (localT.assignedAbbr === 'КЗ') localT.assignedAbbr = 'КЗН';
                        if (localT.assignedAbbr === 'НС') localT.assignedAbbr = 'НСК';
                        if (localT.assignedAbbr === 'КР') localT.assignedAbbr = 'КРД';
                        if (localT.assignedAbbr === 'ВЛ') localT.assignedAbbr = 'ВЛД';

                        localT.color = CITY_COLORS[localT.assignedAbbr] || 'neutral';
                        localT.isAssigned = true;
                    } else {
                        localT.color = 'neutral';
                        localT.isAssigned = false;
                        localT.assignedAbbr = '';
                    }
                    
                    redrawTruckCargoHold(localT);
                }
            }
        });
    }
}

// Sync conveyor requests
function syncRequests(apiRequests) {
    // 1. Remove conveyor boxes no longer in API list (unless currently dragged)
    for (let i = boxes.length - 1; i >= 0; i--) {
        const localB = boxes[i];
        if (draggedBox && draggedBox.id === localB.id) continue;
        
        const inApi = apiRequests.some(r => r.id === localB.id);
        if (!inApi) {
            localB.dom.remove();
            boxes.splice(i, 1);
        }
    }
    
    // 2. Add new requests
    apiRequests.forEach(apiR => {
        const alreadyExists = boxes.some(b => b.id === apiR.id);
        if (!alreadyExists) {
            // Spawn box
            // City abbr from number: e.g. "ЕК-2026/80" -> "ЕК" -> map to full abbr "ЕКБ"
            let abbr = apiR.number.split('-')[0];
            if (abbr === 'ЕК') abbr = 'ЕКБ';
            
            // Weight to size mapping
            let size = 1;
            if (apiR.weight_kg > 3000) size = 3;
            else if (apiR.weight_kg > 1000) size = 2;
            
            // Convert days_left to realtime seconds
            let deadline = apiR.days_left * dayRealtimeSeconds;
            
            spawnRequestBox(apiR.id, abbr, size, deadline, apiR.weight_kg);
        }
    });
}

const CITIES_BY_ABBR = {
    'МСК': 'Москва',
    'СПБ': 'Санкт-Петербург',
    'КЗН': 'Казань',
    'ЕКБ': 'Екатеринбург',
    'НСК': 'Новосибирск',
    'КРД': 'Краснодар',
    'ВЛД': 'Владивосток'
};

// Render vehicles layout
function renderTruckSlots() {
    domTrucksBay.innerHTML = '';
    
    trucks.forEach((truck) => {
        const slotDiv = document.createElement('div');
        slotDiv.className = `truck-slot ${truck.color}`;
        slotDiv.id = `truck-${truck.index}`;
        slotDiv.dataset.index = truck.index;
        
        const timerBg = document.createElement('div');
        timerBg.className = 'truck-timer-bar-bg';
        const timerFill = document.createElement('div');
        timerFill.className = 'truck-timer-bar-fill';
        timerBg.appendChild(timerFill);
        if (truck.isTimerActive) timerBg.classList.add('active');
        
        const cargoHold = document.createElement('div');
        cargoHold.className = 'truck-cargo-hold';
        
        // Draw slot markers or current cargo hold blocks
        redrawTruckCargoHoldData(cargoHold, truck);
        
        const badge = document.createElement('div');
        badge.className = 'truck-badge';
        const typeLabel = `${truck.type} (${truck.capacity}т)`;
        const plateLabel = truck.plate ? `[${truck.plate}]` : '';
        const cityLabel = truck.isAssigned ? truck.assignedAbbr : 'СВОБОДЕН';
        
        badge.innerHTML = `
            <span class="truck-type-title" title="${truck.plate || ''}">${typeLabel} ${plateLabel}</span>
            <div class="truck-icon-container">
                <svg class="truck-icon" viewBox="0 0 24 24" style="color: ${COLOR_HEX[truck.color]}">
                    <path fill="currentColor" d="M20 8h-3V4H3c-1.1 0-2 .9-2 2v11h2c0 1.66 1.34 3 3 3s3-1.34 3-3h6c0 1.66 1.34 3 3 3s3-1.34 3-3h2v-5l-3-4zM6 18.5c-.83 0-1.5-.67-1.5-1.5s.67-1.5 1.5-1.5 1.5.67 1.5 1.5-.67 1.5-1.5 1.5zm12 0c-.83 0-1.5-.67-1.5-1.5s.67-1.5 1.5-1.5 1.5.67 1.5 1.5-.67 1.5-1.5 1.5zm1.5-6H17V9.5h2.5v3z"/>
                </svg>
                <span class="truck-city-tag">${cityLabel}</span>
            </div>
            <span class="truck-capacity-label font-outfit">${truck.loadedUnits} / ${truck.capacity}</span>
        `;
        
        if (truck.loadedUnits === truck.capacity) {
            badge.querySelector('.truck-capacity-label').classList.add('full');
        }
        
        const btnDepart = document.createElement('button');
        btnDepart.className = 'btn-depart';
        btnDepart.disabled = (truck.loadedUnits === 0);
        btnDepart.innerHTML = `
            <svg viewBox="0 0 24 24"><path fill="currentColor" d="M2,21L23,12L2,3V10L17,12L2,14V21Z"/></svg>
            <span>ОТПРАВИТЬ</span>
        `;
        
        btnDepart.addEventListener('click', (e) => {
            e.stopPropagation();
            if (truck.isDeparting || truck.isBroken) return;
            departTruck(truck.index);
        });

        slotDiv.appendChild(timerBg);
        slotDiv.appendChild(cargoHold);
        slotDiv.appendChild(badge);
        slotDiv.appendChild(btnDepart);
        
        domTrucksBay.appendChild(slotDiv);
        
        truck.dom = slotDiv;
        truck.domTimerBg = timerBg;
        truck.domTimerFill = timerFill;
        truck.domCargoHold = cargoHold;
        truck.domCapacityLabel = badge.querySelector('.truck-capacity-label');
        truck.domCityTag = badge.querySelector('.truck-city-tag');
        truck.domIcon = badge.querySelector('.truck-icon');
        truck.domDepartBtn = btnDepart;
        
        recalculateTruckTimer(truck);
    });
}

function redrawTruckCargoHold(truck) {
    if (!truck.domCargoHold) return;
    redrawTruckCargoHoldData(truck.domCargoHold, truck);
    truck.domCapacityLabel.textContent = `${truck.loadedUnits} / ${truck.capacity}`;
    if (truck.loadedUnits === truck.capacity) {
        truck.domCapacityLabel.classList.add('full');
    } else {
        truck.domCapacityLabel.classList.remove('full');
    }
    
    // Update city title
    if (truck.isAssigned) {
        truck.domCityTag.textContent = truck.assignedAbbr;
        truck.dom.className = `truck-slot ${truck.color}`;
        truck.domIcon.style.color = COLOR_HEX[truck.color];
        truck.domTimerBg.classList.add('active');
        truck.domDepartBtn.disabled = false;
    } else {
        truck.domCityTag.textContent = 'СВОБОДЕН';
        truck.dom.className = 'truck-slot neutral';
        truck.domIcon.style.color = COLOR_HEX.neutral;
        truck.domTimerBg.classList.remove('active');
        truck.domDepartBtn.disabled = true;
    }
    recalculateTruckTimer(truck);
}

function redrawTruckCargoHoldData(container, truck) {
    container.innerHTML = '';
    
    // Loaded blocks
    truck.loadedBoxes.forEach(box => {
        const block = document.createElement('div');
        block.className = `cargo-hold-block size-${box.size}`;
        block.dataset.boxId = box.id;
        block.dataset.truckIndex = truck.index;
        block.title = "Нажмите, чтобы выгрузить обратно";
        container.appendChild(block);
    });
    
    // Remaining placeholders
    const placeholders = truck.capacity - truck.loadedUnits;
    for (let i = 0; i < placeholders; i++) {
        const marker = document.createElement('div');
        marker.className = 'cargo-hold-slot-marker';
        container.appendChild(marker);
    }
}

// --- Spawn request box on conveyor ---
function spawnRequestBox(id, abbr, size, deadline, weight_kg) {
    const color = (deadline > 14 * dayRealtimeSeconds) ? 'green' : 
                  ((deadline > 7 * dayRealtimeSeconds) ? 'yellow' : 
                  ((deadline > 3 * dayRealtimeSeconds) ? 'orange' : 'red'));
                  
    const dom = document.createElement('div');
    dom.className = `cargo-box size-${size} color-${color}`;
    dom.id = id;
    
    dom.innerHTML = `
        <span class="box-destination">${abbr}</span>
        <span class="box-volume">${Math.round(weight_kg)}кг</span>
        <div class="box-deadline font-outfit">📅 ${Math.ceil(deadline / dayRealtimeSeconds)}д</div>
    `;
    
    // Set position relative to its days_left (conveyor timeline metaphor)
    const daysLeft = deadline / dayRealtimeSeconds;
    const progress = Math.min(1.0, Math.max(0.0, (maxDaysHorizon - daysLeft) / maxDaysHorizon));
    const width = size === 1 ? 48 : (size === 2 ? 80 : 112);
    
    // Compute conveyor active span
    const conveyorWidth = domConveyorBoxes.clientWidth || 700;
    const limitX = conveyorWidth - 60;
    const initialLeft = progress * limitX;
    
    dom.style.left = `${initialLeft}px`;
    domConveyorBoxes.appendChild(dom);
    
    const boxObj = {
        id: id,
        color: color,
        abbr: abbr,
        size: size,
        deadline: deadline,
        left: initialLeft,
        width: width,
        dom: dom,
        domDeadline: dom.querySelector('.box-deadline'),
        isOverdue: daysLeft <= 0,
        penaltyApplied: daysLeft <= 0
    };
    
    dom.addEventListener('mousedown', (e) => onDragStart(e, boxObj));
    dom.addEventListener('touchstart', (e) => onDragStart(e, boxObj), { passive: false });
    
    boxes.push(boxObj);
    playSound('spawn');
}

// --- Drag and drop ---
function onDragStart(e, boxObj) {
    if (gameState !== 'PLAYING') return;
    e.preventDefault();
    
    if (selectedBox) {
        selectedBox.dom.classList.remove('selected');
        selectedBox = null;
    }
    
    draggedBox = boxObj;
    draggedBoxElement = boxObj.dom;
    draggedBoxElement.classList.add('dragging');
    
    let pageX, pageY;
    if (e.type === 'touchstart') {
        activeTouchId = e.changedTouches[0].identifier;
        pageX = e.changedTouches[0].pageX;
        pageY = e.changedTouches[0].pageY;
    } else {
        pageX = e.pageX;
        pageY = e.pageY;
    }
    
    const rect = draggedBoxElement.getBoundingClientRect();
    dragOffset.x = pageX - (rect.left + window.scrollX);
    dragOffset.y = pageY - (rect.top + window.scrollY);
    
    // Glow matching target trucks
    trucks.forEach(t => {
        if (!t.isBroken && !t.isDeparting) {
            if (t.color === 'neutral' || t.assignedAbbr === draggedBox.abbr) {
                t.dom.classList.add('glow-target');
            }
        }
    });
    
    domDragOverlay.classList.remove('hide');
}

function onDragMove(e) {
    if (gameState !== 'PLAYING' || !draggedBox) return;
    
    let pageX, pageY;
    if (e.type === 'touchmove') {
        e.preventDefault();
        let touch = null;
        for (let i = 0; i < e.touches.length; i++) {
            if (e.touches[i].identifier === activeTouchId) {
                touch = e.touches[i];
                break;
            }
        }
        if (!touch) return;
        pageX = touch.pageX;
        pageY = touch.pageY;
    } else {
        pageX = e.pageX;
        pageY = e.pageY;
    }
    
    const fieldRect = domConveyorBoxes.getBoundingClientRect();
    const left = pageX - (fieldRect.left + window.scrollX) - dragOffset.x;
    const top = pageY - (fieldRect.top + window.scrollY) - dragOffset.y;
    
    draggedBoxElement.style.left = `${left}px`;
    draggedBoxElement.style.top = `${top}px`;
}

async function onDragEnd(e) {
    if (gameState !== 'PLAYING' || !draggedBox) return;
    
    let pageX, pageY;
    if (e.type === 'touchend') {
        let touch = null;
        for (let i = 0; i < e.changedTouches.length; i++) {
            if (e.changedTouches[i].identifier === activeTouchId) {
                touch = e.changedTouches[i];
                break;
            }
        }
        if (!touch) return;
        pageX = touch.pageX;
        pageY = touch.pageY;
    } else {
        pageX = e.pageX;
        pageY = e.pageY;
    }
    
    let loadedSuccess = false;
    const boxRect = draggedBoxElement.getBoundingClientRect();
    const boxCenterX = boxRect.left + boxRect.width / 2;
    const boxCenterY = boxRect.top + boxRect.height / 2;
    
    for (let i = 0; i < trucks.length; i++) {
        const truck = trucks[i];
        if (truck.isBroken || truck.isDeparting) continue;
        
        const truckRect = truck.dom.getBoundingClientRect();
        
        if (boxCenterX >= truckRect.left && boxCenterX <= truckRect.right &&
            boxCenterY >= truckRect.top && boxCenterY <= truckRect.bottom) {
            
            // Check assignment constraint
            if (truck.color === 'neutral' || truck.assignedAbbr === draggedBox.abbr) {
                if (truck.loadedUnits + draggedBox.size <= truck.capacity) {
                    
                    // CALL API ASSIGN!
                    const assignOk = await assignRequestToVehicle(draggedBox.id, truck.id);
                    if (assignOk) {
                        loadBoxIntoTruck(draggedBox, truck);
                        loadedSuccess = true;
                    }
                    break;
                } else {
                    playSound('error');
                    spawnParticles(boxCenterX, boxCenterY, '#ef4444', 6);
                }
            } else {
                playSound('error');
                spawnParticles(boxCenterX, boxCenterY, '#ef4444', 6);
            }
        }
    }
    
    draggedBoxElement.classList.remove('dragging');
    trucks.forEach(t => t.dom.classList.remove('glow-target'));
    domDragOverlay.classList.add('hide');
    
    if (!loadedSuccess) {
        draggedBoxElement.style.top = '';
        draggedBox.left = parseFloat(draggedBoxElement.style.left);
    }
    
    draggedBox = null;
    draggedBoxElement = null;
    activeTouchId = null;
}

// Window Click (Tap assignments & Unloading clicks)
async function onWindowClick(e) {
    if (gameState !== 'PLAYING') return;
    
    // 1. Tapped a loaded block inside truck cargo hold -> EJECT IT back to conveyor
    const holdBlock = e.target.closest('.cargo-hold-block');
    if (holdBlock) {
        const truckIdx = parseInt(holdBlock.dataset.truckIndex, 10);
        const boxId = parseInt(holdBlock.dataset.boxId, 10);
        const truck = trucks[truckIdx];
        
        if (truck && !truck.isBroken && !truck.isDeparting) {
            // CALL API UNASSIGN (vehicle_id = 0)
            const unassignOk = await assignRequestToVehicle(boxId, 0);
            if (unassignOk) {
                unloadBoxFromTruck(boxId, truck);
            }
        }
        return;
    }
    
    // 2. Click conveyor box to select
    const boxDom = e.target.closest('.cargo-box');
    if (boxDom && !boxDom.classList.contains('dragging')) {
        const boxObj = boxes.find(b => b.id === parseInt(boxDom.id, 10));
        if (boxObj) {
            if (selectedBox) {
                selectedBox.dom.classList.remove('selected');
            }
            selectedBox = boxObj;
            selectedBox.dom.classList.add('selected');
            playSound('spawn');
            return;
        }
    }
    
    // 3. Click truck slot to assign selected box
    const truckDom = e.target.closest('.truck-slot');
    if (truckDom && selectedBox) {
        const truckIdx = parseInt(truckDom.dataset.index, 10);
        const truck = trucks[truckIdx];
        
        if (!truck.isBroken && !truck.isDeparting) {
            if (truck.color === 'neutral' || truck.assignedAbbr === selectedBox.abbr) {
                if (truck.loadedUnits + selectedBox.size <= truck.capacity) {
                    const assignOk = await assignRequestToVehicle(selectedBox.id, truck.id);
                    if (assignOk) {
                        const rect = selectedBox.dom.getBoundingClientRect();
                        spawnParticles(rect.left + rect.width / 2, rect.top + rect.height / 2, COLOR_HEX[truck.color] || '#fff', 10);
                        loadBoxIntoTruck(selectedBox, truck);
                        selectedBox = null;
                        return;
                    }
                }
            }
            playSound('error');
            const rect = truckDom.getBoundingClientRect();
            spawnParticles(rect.left + rect.width / 2, rect.top + rect.height / 2, '#ef4444', 6);
        }
        
        selectedBox.dom.classList.remove('selected');
        selectedBox = null;
        return;
    }
    
    // Deselect click
    if (selectedBox && !e.target.closest('.hud-btn')) {
        selectedBox.dom.classList.remove('selected');
        selectedBox = null;
    }
}

// --- Fetch backend API calls ---
async function assignRequestToVehicle(requestId, vehicleId) {
    try {
        const response = await fetch(API_URLS.assign, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken()
            },
            body: JSON.stringify({
                request_id: requestId,
                vehicle_id: vehicleId
            })
        });
        
        const result = await response.json();
        if (!response.ok || !result.ok) {
            alert("Ошибка назначения: " + (result.error || "Неизвестная ошибка"));
            playSound('error');
            return false;
        }
        return true;
    } catch (e) {
        console.error('Error assigning vehicle:', e);
        playSound('error');
        return false;
    }
}

async function departVehicleAPI(vehicleId) {
    try {
        const response = await fetch(API_URLS.depart, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken()
            },
            body: JSON.stringify({
                vehicle_id: vehicleId
            })
        });
        
        const result = await response.json();
        return response.ok && result.ok;
    } catch (e) {
        console.error('Error departing vehicle:', e);
        return false;
    }
}

// --- Load/Unload state handling ---
function loadBoxIntoTruck(boxObj, truck) {
    if (truck.color === 'neutral') {
        truck.color = CITY_COLORS[boxObj.abbr] || 'neutral';
        truck.isAssigned = true;
        truck.assignedCity = CITIES_BY_ABBR[boxObj.abbr] || 'Город';
        truck.assignedAbbr = boxObj.abbr;
    }
    
    truck.loadedUnits += boxObj.size;
    truck.loadedBoxes.push({
        id: boxObj.id,
        abbr: boxObj.abbr,
        size: boxObj.size,
        deadline: boxObj.deadline
    });
    
    redrawTruckCargoHold(truck);
    
    // Visual FX
    const truckRect = truck.dom.getBoundingClientRect();
    spawnParticles(truckRect.left + truckRect.width / 2, truckRect.top + 30, COLOR_HEX[truck.color] || '#fff', 12);
    playSound('load');
    
    truck.dom.classList.add('shake');
    setTimeout(() => truck.dom.classList.remove('shake'), 300);
    
    // Remove conveyor element
    boxObj.dom.remove();
    boxes = boxes.filter(b => b.id !== boxObj.id);
    
    if (truck.loadedUnits === truck.capacity) {
        departTruck(truck.index);
    }
}

function unloadBoxFromTruck(boxId, truck) {
    const boxIndex = truck.loadedBoxes.findIndex(b => b.id === boxId);
    if (boxIndex === -1) return;
    
    const boxObj = truck.loadedBoxes[boxIndex];
    truck.loadedBoxes.splice(boxIndex, 1);
    truck.loadedUnits -= boxObj.size;
    
    // Spawn back on conveyor at left
    spawnRequestBox(boxObj.id, boxObj.abbr, boxObj.size, boxObj.deadline, boxObj.size * 1000);
    
    if (truck.loadedUnits === 0) {
        truck.color = 'neutral';
        truck.isAssigned = false;
        truck.assignedCity = '';
        truck.assignedAbbr = '';
        truck.isTimerActive = false;
    }
    
    redrawTruckCargoHold(truck);
    
    const rect = truck.dom.getBoundingClientRect();
    spawnParticles(rect.left + rect.width / 2, rect.top + 30, COLOR_HEX[boxObj.color] || '#64748b', 10);
    playSound('unload');
}

function recalculateTruckTimer(truck) {
    if (truck.loadedBoxes.length > 0) {
        truck.timer = Math.min(...truck.loadedBoxes.map(b => b.deadline));
        truck.isTimerActive = true;
    } else {
        truck.timer = 0;
        truck.isTimerActive = false;
    }
}

// --- Departures ---
async function departTruck(truckIndex) {
    const truck = trucks[truckIndex];
    if (truck.isDeparting) return;
    
    truck.isDeparting = true;
    truck.isTimerActive = false;
    if (truck.domTimerBg) truck.domTimerBg.classList.remove('active');
    if (truck.domDepartBtn) truck.domDepartBtn.disabled = true;
    
    // 1. Notify Backend!
    const departOk = await departVehicleAPI(truck.id);
    if (!departOk) {
        alert("Ошибка отправки машины на сервере.");
        truck.isDeparting = false;
        redrawTruckCargoHold(truck);
        return;
    }
    
    // 2. Score locally based on efficiency
    let deliveredUnits = 0;
    let lateUnits = 0;
    
    truck.loadedBoxes.forEach(box => {
        if (box.deadline <= 0) {
            lateUnits += box.size;
        } else {
            deliveredUnits += box.size;
        }
    });
    
    let gainScore = Math.floor(deliveredUnits * 10 * truck.scoreMult);
    const efficiency = truck.loadedUnits / truck.capacity;
    let isPerfect = false;
    let reputationChange = 0;
    
    if (efficiency === 1.0 && lateUnits === 0) {
        gainScore *= 2;
        reputationChange = 6;
        isPerfect = true;
    } else if (efficiency >= 0.75) {
        gainScore = Math.floor(gainScore * 1.4);
        reputationChange = 3;
    } else if (efficiency < 0.50) {
        gainScore = Math.floor(gainScore * 0.5);
        reputationChange = -4;
    }
    
    if (lateUnits > 0) {
        reputationChange -= (lateUnits * 6);
    }
    
    score += gainScore;
    domScoreVal.textContent = score;
    reputation = Math.min(100, Math.max(0, reputation + reputationChange));
    updateReputationBar();
    
    // Level Up triggers
    const newLevel = Math.floor(score / 1000) + 1;
    if (newLevel > level) {
        level = newLevel;
        domLevelVal.textContent = level;
        playSound('levelUp');
        updateLevelDifficulty();
    }
    
    // Animation drive away
    truck.dom.classList.add('departing');
    playSound('depart');
    
    const rect = truck.dom.getBoundingClientRect();
    if (isPerfect) {
        playSound('perfect');
        spawnParticles(rect.left + rect.width / 2, rect.top + rect.height / 2, '#eab308', 35);
    } else {
        spawnParticles(rect.left + rect.width / 2, rect.top + rect.height / 2, COLOR_HEX[truck.color] || '#fff', 15);
    }
    
    if (reputation <= 0) {
        setTimeout(triggerGameOver, 600);
        return;
    }
    
    // Spawn new empty truck slot in 1.5 seconds
    setTimeout(() => {
        resetTruckSlot(truck.index);
    }, 1500);
}

// --- Automatic Fleet Breakdowns ---
function triggerBreakdown() {
    const candidates = trucks.filter(t => !t.isBroken && !t.isDeparting);
    if (candidates.length === 0) return;
    
    const truck = candidates[Math.floor(Math.random() * candidates.length)];
    
    truck.isBroken = true;
    truck.isTimerActive = false;
    truck.domTimerBg.classList.remove('active');
    truck.domDepartBtn.disabled = true;
    
    // Cargo disruption: Dump all loaded cargo back to conveyor and unassign in DB!
    if (truck.loadedUnits > 0) {
        truck.loadedBoxes.forEach(async (box) => {
            // Eject in DB
            await assignRequestToVehicle(box.id, 0);
            
            // Re-spawn on conveyor locally
            spawnRequestBox(box.id, box.abbr, box.size, box.deadline, box.size * 1000);
        });
        
        truck.domCargoHold.innerHTML = '';
        truck.loadedUnits = 0;
        truck.loadedBoxes = [];
    }
    
    truck.color = 'neutral';
    truck.isAssigned = false;
    truck.assignedCity = '';
    truck.assignedAbbr = '';
    
    truck.dom.className = 'truck-slot neutral broken';
    truck.domCapacityLabel.textContent = `0 / ${truck.capacity}`;
    truck.domCapacityLabel.classList.remove('full');
    truck.domCityTag.textContent = 'РЕМОНТ';
    truck.domIcon.style.color = '#ef4444';
    
    const overlay = document.createElement('div');
    overlay.className = 'repair-overlay';
    overlay.innerHTML = `
        <div class="repair-title font-outfit">ПОЛОМКА</div>
        <div class="repair-progress-bg">
            <div class="repair-progress-fill" style="width: 0%;"></div>
        </div>
    `;
    truck.dom.appendChild(overlay);
    
    truck.domRepairOverlay = overlay;
    truck.domRepairProgress = overlay.querySelector('.repair-progress-fill');
    
    truck.repairDuration = Math.random() * 4 + 6; 
    truck.repairTimer = truck.repairDuration;
    
    const rect = truck.dom.getBoundingClientRect();
    spawnParticles(rect.left + rect.width / 2, rect.top + 30, '#ef4444', 20);
    playSound('alarm');
}

function updateRepair(truck, dt) {
    truck.repairTimer -= dt;
    
    const progress = ((truck.repairDuration - truck.repairTimer) / truck.repairDuration) * 100;
    if (truck.domRepairProgress) {
        truck.domRepairProgress.style.width = `${progress}%`;
    }
    
    const rect = truck.dom.getBoundingClientRect();
    if (Math.random() < 0.15) {
        spawnParticles(
            rect.left + rect.width / 2 + (Math.random() - 0.5) * 10,
            rect.top + 20,
            'rgba(100, 100, 100, 0.4)',
            1,
            'smoke'
        );
    }
    
    if (truck.repairTimer <= 0) {
        truck.isBroken = false;
        
        if (truck.domRepairOverlay) {
            truck.domRepairOverlay.remove();
        }
        
        truck.dom.classList.remove('broken');
        truck.domCityTag.textContent = 'СВОБОДЕН';
        truck.domIcon.style.color = COLOR_HEX.neutral;
        
        truck.domCargoHold.innerHTML = '';
        for (let i = 0; i < truck.capacity; i++) {
            const slotMarker = document.createElement('div');
            slotMarker.className = 'cargo-hold-slot-marker';
            truck.domCargoHold.appendChild(slotMarker);
        }
        
        playSound('repaired');
        const rRect = truck.dom.getBoundingClientRect();
        spawnParticles(rRect.left + rRect.width / 2, rRect.top + 30, '#10b981', 12);
    }
}

// --- Main Engine Loop ---
function updateLoop(timestamp) {
    if (!lastTime) lastTime = timestamp;
    const dt = (timestamp - lastTime) / 1000;
    lastTime = timestamp;
    
    if (gameState === 'PLAYING') {
        updateGame(dt);
    }
    
    renderParticles();
    
    requestAnimationFrame(updateLoop);
}

function updateGame(dt) {
    // 1. Conveyor Boxes deadlines & physical movement
    const conveyorWidth = domConveyorBoxes.clientWidth || 700;
    const limitX = conveyorWidth - 60;
    
    for (let i = boxes.length - 1; i >= 0; i--) {
        const boxObj = boxes[i];
        
        if (draggedBox && draggedBox.id === boxObj.id) continue;
        
        // Deadline ticks
        boxObj.deadline -= dt;
        
        // Position recalculation based on days left (conveyor timeline progress)
        const daysLeft = boxObj.deadline / dayRealtimeSeconds;
        
        // Progress increases as daysLeft gets smaller
        const progress = Math.min(1.0, Math.max(0.0, (maxDaysHorizon - daysLeft) / maxDaysHorizon));
        
        // Move towards the target position
        const targetLeft = progress * limitX;
        
        // Smooth slide movement towards target left
        boxObj.left += (targetLeft - boxObj.left) * 0.1;
        boxObj.dom.style.left = `${boxObj.left}px`;
        
        // Deadline display
        if (boxObj.domDeadline) {
            boxObj.domDeadline.textContent = `📅 ${Math.ceil(daysLeft)}д`;
            if (daysLeft <= 3) {
                boxObj.domDeadline.classList.add('urgent');
            }
        }
        
        // Overdue status check
        if (daysLeft <= 0) {
            boxObj.isOverdue = true;
            
            // Apply reputation and score penalty once
            if (!boxObj.penaltyApplied) {
                reputation = Math.max(0, reputation - 10);
                score = Math.max(0, score - 50); // -50 points penalty for overdue!
                domScoreVal.textContent = score;
                updateReputationBar();
                
                playSound('error');
                
                const rect = boxObj.dom.getBoundingClientRect();
                const parentRect = domConveyorBoxes.getBoundingClientRect();
                spawnParticles(
                    rect.left - parentRect.left + rect.width / 2,
                    rect.top - parentRect.top + rect.height / 2,
                    '#ef4444',
                    10
                );
                
                boxObj.penaltyApplied = true;
                
                if (reputation <= 0) {
                    triggerGameOver();
                    break;
                }
            }
            
            // Keep overdue box at the far right end of the conveyor
            boxObj.left = limitX;
            boxObj.dom.style.left = `${boxObj.left}px`;
        }
    }
    
    if (gameState !== 'PLAYING') return;
    
    // 2. Update Truck loading timers & inside cargo deadlines
    trucks.forEach(truck => {
        if (truck.isBroken) {
            updateRepair(truck, dt);
        } else if (truck.isTimerActive && !truck.isDeparting) {
            // Ticking deadlines inside loaded box elements
            truck.loadedBoxes.forEach(box => {
                box.deadline -= dt;
            });
            
            // Visual feedback inside loaded blocks in cargo hold (flash red if box deadline <= 3 days = 15s)
            truck.loadedBoxes.forEach(box => {
                const block = truck.domCargoHold.querySelector(`[data-box-id="${box.id}"]`);
                if (block) {
                    if (box.deadline <= 3 * dayRealtimeSeconds) {
                        block.classList.add('overdue');
                    } else {
                        block.classList.remove('overdue');
                    }
                }
            });
            
            // Truck timer is the minimum remaining deadline
            recalculateTruckTimer(truck);
            
            // Update visual progress timer bar
            const pct = Math.max(0, (truck.timer / (maxDaysHorizon * dayRealtimeSeconds)) * 100);
            truck.domTimerFill.style.width = `${pct}%`;
            
            if (truck.timer <= 3 * dayRealtimeSeconds) {
                truck.domTimerFill.style.backgroundColor = '#ef4444';
            } else if (truck.timer <= 7 * dayRealtimeSeconds) {
                truck.domTimerFill.style.backgroundColor = '#f59e0b';
            } else {
                truck.domTimerFill.style.backgroundColor = '#10b981';
            }
            
            // Auto depart if time expires
            if (truck.timer <= 0) {
                departTruck(truck.index);
            }
        }
    });
    
    // 3. API Polling Timer
    apiPollTimer += dt;
    if (apiPollTimer >= API_POLL_INTERVAL) {
        pollApi();
        apiPollTimer = 0;
    }
    
    // 4. Breakdown Spawner Timer
    breakdownTimer -= dt;
    if (breakdownTimer <= 0) {
        triggerBreakdown();
        breakdownTimer = Math.max(8, 20 - level * 1.5) + Math.random() * 8;
    }
}

function renderParticles() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    for (let i = particles.length - 1; i >= 0; i--) {
        const p = particles[i];
        p.update();
        p.draw();
        
        if (p.alpha <= 0) {
            particles.splice(i, 1);
        }
    }
}

function setupEventListeners() {
    const btnSound = document.getElementById('btn-sound');
    btnSound.addEventListener('click', () => {
        isMuted = !isMuted;
        btnSound.querySelector('.icon-sound-on').classList.toggle('hide', isMuted);
        btnSound.querySelector('.icon-sound-off').classList.toggle('hide', !isMuted);
        initAudio();
    });
    
    document.getElementById('btn-pause').addEventListener('click', pauseGame);
    document.getElementById('btn-start').addEventListener('click', startGame);
    document.getElementById('btn-resume').addEventListener('click', resumeGame);
    
    document.getElementById('btn-restart-pause').addEventListener('click', () => {
        hideOverlay(domPauseScreen);
        startGame();
    });
    
    document.getElementById('btn-restart').addEventListener('click', () => {
        hideOverlay(domGameOverScreen);
        startGame();
    });
    
    window.addEventListener('mousemove', onDragMove);
    window.addEventListener('touchmove', onDragMove, { passive: false });
    
    window.addEventListener('mouseup', onDragEnd);
    window.addEventListener('touchend', onDragEnd);
    
    window.addEventListener('click', onWindowClick);
}

function showOverlay(element) {
    element.classList.remove('hide');
    element.classList.add('active');
}

function hideOverlay(element) {
    element.classList.remove('active');
    element.classList.add('hide');
}

function pauseGame() {
    if (gameState !== 'PLAYING') return;
    gameState = 'PAUSED';
    showOverlay(domPauseScreen);
}

function resumeGame() {
    if (gameState !== 'PAUSED') return;
    hideOverlay(domPauseScreen);
    lastTime = performance.now();
    gameState = 'PLAYING';
}

function triggerGameOver() {
    gameState = 'GAME_OVER';
    saveHighScore();
    
    document.getElementById('final-score').textContent = score;
    document.getElementById('final-level').textContent = level;
    
    playSound('gameOver');
    showOverlay(domGameOverScreen);
}

function resetTruckSlot(truckIndex) {
    const truck = trucks[truckIndex];
    if (!truck) return;
    
    truck.color = 'neutral';
    truck.isAssigned = false;
    truck.assignedCity = '';
    truck.assignedAbbr = '';
    truck.loadedUnits = 0;
    truck.loadedBoxes = [];
    truck.isDeparting = false;
    truck.isTimerActive = false;
    truck.timer = 0;
    
    if (truck.dom) {
        truck.dom.className = 'truck-slot neutral';
        truck.dom.classList.remove('departing');
        if (truck.domTimerBg) truck.domTimerBg.classList.remove('active');
        if (truck.domDepartBtn) truck.domDepartBtn.disabled = true;
    }
    
    redrawTruckCargoHold(truck);
}

function startGame() {
    hideOverlay(domStartScreen);
    hideOverlay(domPauseScreen);
    hideOverlay(domGameOverScreen);
    
    score = 0;
    reputation = 100;
    level = 1;
    domScoreVal.textContent = score;
    domLevelVal.textContent = level;
    updateReputationBar();
    
    // Clear all boxes from conveyor belt
    boxes.forEach(b => {
        if (b.dom) b.dom.remove();
    });
    boxes = [];
    
    // Clear the conveyor HTML container just in case
    domConveyorBoxes.innerHTML = '';
    
    // Reset all trucks
    trucks.forEach(t => {
        resetTruckSlot(t.index);
    });
    
    // Re-trigger API polling immediately to get fresh data
    pollApi(true);
    
    gameState = 'PLAYING';
    lastTime = performance.now();
    playSound('repaired'); // Nice positive start sound
}

function updateReputationBar() {
    domReputationPct.textContent = `${reputation}%`;
    domReputationBarFill.style.width = `${reputation}%`;
    
    domReputationBarFill.classList.remove('warning', 'danger');
    if (reputation <= 30) {
        domReputationBarFill.classList.add('danger');
    } else if (reputation <= 60) {
        domReputationBarFill.classList.add('warning');
    }
}

function updateLevelDifficulty() {
    currentBoxSpeed = baseBoxSpeed + (level - 1) * 12;
    currentBoxSpeed = Math.min(currentBoxSpeed, 160);
}

// Run initialization directly
init();
