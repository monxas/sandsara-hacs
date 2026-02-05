// Sandsara Pattern Viewer - Frontend

const canvas = document.getElementById('pattern-canvas');
const ctx = canvas.getContext('2d');
const noPatternMsg = document.getElementById('no-pattern');
const patternInfo = document.getElementById('pattern-info');
const patternList = document.getElementById('pattern-list');

let currentPattern = null;
let animationId = null;

// API calls
async function fetchPatterns() {
    try {
        const response = await fetch('/api/patterns');
        const patterns = await response.json();
        renderPatternList(patterns);
    } catch (error) {
        patternList.innerHTML = '<p class="empty">Failed to load patterns</p>';
        console.error('Error fetching patterns:', error);
    }
}

async function loadPattern(name) {
    try {
        const response = await fetch(`/api/patterns/${encodeURIComponent(name)}`);
        if (!response.ok) throw new Error('Pattern not found');
        
        const pattern = await response.json();
        currentPattern = pattern;
        
        // Update UI
        document.querySelectorAll('.pattern-item').forEach(el => {
            el.classList.toggle('active', el.dataset.name === name);
        });
        
        noPatternMsg.classList.add('hidden');
        patternInfo.classList.remove('hidden');
        
        document.getElementById('info-name').textContent = pattern.name;
        document.getElementById('info-points').textContent = pattern.num_points.toLocaleString();
        document.getElementById('info-size').textContent = formatBytes(pattern.file_size);
        
        // Draw pattern
        const animate = document.getElementById('animate-toggle').checked;
        drawPattern(pattern.points, animate);
        
        document.getElementById('replay-btn').disabled = false;
    } catch (error) {
        console.error('Error loading pattern:', error);
        alert('Failed to load pattern');
    }
}

async function generatePattern(type) {
    try {
        const response = await fetch(`/api/patterns/generate/${type}`, { method: 'POST' });
        if (!response.ok) throw new Error('Generation failed');
        
        const result = await response.json();
        await fetchPatterns();
        await loadPattern(result.name);
    } catch (error) {
        console.error('Error generating pattern:', error);
        alert('Failed to generate pattern');
    }
}

// File upload
document.getElementById('file-input').addEventListener('change', async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    
    const status = document.getElementById('upload-status');
    status.textContent = 'Uploading...';
    status.className = 'status';
    
    const formData = new FormData();
    formData.append('file', file);
    
    try {
        const response = await fetch('/api/patterns/upload', {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Upload failed');
        }
        
        const result = await response.json();
        status.textContent = `✓ Uploaded: ${result.num_points} points`;
        status.className = 'status success';
        
        await fetchPatterns();
        await loadPattern(result.name);
    } catch (error) {
        status.textContent = `✗ ${error.message}`;
        status.className = 'status error';
    }
    
    e.target.value = '';
});

// Pattern list rendering
function renderPatternList(patterns) {
    if (patterns.length === 0) {
        patternList.innerHTML = '<p class="empty">No patterns found.<br>Generate or upload one!</p>';
        return;
    }
    
    patternList.innerHTML = patterns.map(p => `
        <div class="pattern-item" data-name="${escapeHtml(p.name)}" onclick="loadPattern('${escapeHtml(p.name)}')">
            <div class="name">${escapeHtml(p.name)}</div>
            <div class="meta">${p.num_points.toLocaleString()} pts • ${formatBytes(p.file_size)}</div>
        </div>
    `).join('');
}

// Drawing
function drawPattern(points, animate = false) {
    // Cancel any existing animation
    if (animationId) {
        cancelAnimationFrame(animationId);
        animationId = null;
    }
    
    // Clear canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    if (points.length === 0) return;
    
    const centerX = canvas.width / 2;
    const centerY = canvas.height / 2;
    const scale = (canvas.width / 2) * 0.9; // 90% of radius
    
    // Draw background circle (sand table edge)
    ctx.beginPath();
    ctx.arc(centerX, centerY, scale, 0, 2 * Math.PI);
    ctx.strokeStyle = 'rgba(194, 178, 128, 0.3)';
    ctx.lineWidth = 2;
    ctx.stroke();
    
    // Center dot
    ctx.beginPath();
    ctx.arc(centerX, centerY, 3, 0, 2 * Math.PI);
    ctx.fillStyle = 'rgba(194, 178, 128, 0.5)';
    ctx.fill();
    
    if (animate) {
        animateDrawing(points, centerX, centerY, scale);
    } else {
        drawFullPath(points, centerX, centerY, scale);
    }
}

function drawFullPath(points, centerX, centerY, scale) {
    ctx.beginPath();
    
    for (let i = 0; i < points.length; i++) {
        const x = centerX + points[i].x * scale;
        const y = centerY - points[i].y * scale; // Flip Y for canvas
        
        if (i === 0) {
            ctx.moveTo(x, y);
        } else {
            ctx.lineTo(x, y);
        }
    }
    
    ctx.strokeStyle = '#c2b280';
    ctx.lineWidth = 1.5;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.stroke();
    
    // Draw ball at final position
    if (points.length > 0) {
        const last = points[points.length - 1];
        drawBall(centerX + last.x * scale, centerY - last.y * scale);
    }
}

function animateDrawing(points, centerX, centerY, scale) {
    let currentIndex = 0;
    const pointsPerFrame = Math.max(1, Math.floor(points.length / 300)); // Aim for ~300 frames
    
    ctx.strokeStyle = '#c2b280';
    ctx.lineWidth = 1.5;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    
    function draw() {
        const endIndex = Math.min(currentIndex + pointsPerFrame, points.length);
        
        if (currentIndex === 0 && endIndex > 0) {
            ctx.beginPath();
            const x = centerX + points[0].x * scale;
            const y = centerY - points[0].y * scale;
            ctx.moveTo(x, y);
        }
        
        ctx.beginPath();
        if (currentIndex > 0) {
            const prev = points[currentIndex - 1];
            ctx.moveTo(centerX + prev.x * scale, centerY - prev.y * scale);
        } else {
            ctx.moveTo(centerX + points[0].x * scale, centerY - points[0].y * scale);
        }
        
        for (let i = currentIndex; i < endIndex; i++) {
            const x = centerX + points[i].x * scale;
            const y = centerY - points[i].y * scale;
            ctx.lineTo(x, y);
        }
        ctx.stroke();
        
        // Draw ball at current position
        if (endIndex > 0) {
            // Clear previous ball area (approximate)
            if (currentIndex > 0) {
                const prev = points[currentIndex - 1];
                ctx.save();
                ctx.globalCompositeOperation = 'destination-out';
                ctx.beginPath();
                ctx.arc(centerX + prev.x * scale, centerY - prev.y * scale, 8, 0, 2 * Math.PI);
                ctx.fill();
                ctx.restore();
                
                // Redraw the line segment
                ctx.beginPath();
                if (currentIndex > 1) {
                    const prevPrev = points[currentIndex - 2];
                    ctx.moveTo(centerX + prevPrev.x * scale, centerY - prevPrev.y * scale);
                    ctx.lineTo(centerX + prev.x * scale, centerY - prev.y * scale);
                    ctx.stroke();
                }
            }
            
            const current = points[endIndex - 1];
            drawBall(centerX + current.x * scale, centerY - current.y * scale);
        }
        
        currentIndex = endIndex;
        
        if (currentIndex < points.length) {
            animationId = requestAnimationFrame(draw);
        } else {
            animationId = null;
        }
    }
    
    draw();
}

function drawBall(x, y) {
    // Outer glow
    const gradient = ctx.createRadialGradient(x, y, 0, x, y, 8);
    gradient.addColorStop(0, 'rgba(194, 178, 128, 0.8)');
    gradient.addColorStop(0.5, 'rgba(194, 178, 128, 0.3)');
    gradient.addColorStop(1, 'rgba(194, 178, 128, 0)');
    
    ctx.beginPath();
    ctx.arc(x, y, 8, 0, 2 * Math.PI);
    ctx.fillStyle = gradient;
    ctx.fill();
    
    // Ball
    ctx.beginPath();
    ctx.arc(x, y, 4, 0, 2 * Math.PI);
    ctx.fillStyle = '#e0d5b5';
    ctx.fill();
}

// Replay button
document.getElementById('replay-btn').addEventListener('click', () => {
    if (currentPattern) {
        drawPattern(currentPattern.points, true);
    }
});

// Animate toggle change
document.getElementById('animate-toggle').addEventListener('change', () => {
    if (currentPattern) {
        const animate = document.getElementById('animate-toggle').checked;
        drawPattern(currentPattern.points, animate);
    }
});

// Utilities
function formatBytes(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Initialize
fetchPatterns();
