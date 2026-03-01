let cpuChart, memoryChart;
// RPi vcgencmd detection: set 3s after full page load via GET /api/rpi/vcgencmd_available
let vcgencmdAvailable = false;
let temperatureChart = null;
let temperatureIntervalId = null;

function initCharts() {
    const cpuCtx = document.getElementById('cpuChart').getContext('2d');
    cpuChart = new Chart(cpuCtx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'CPU Usage',
                data: [],
                borderColor: 'rgb(75, 192, 192)',
                tension: 0.1
            }]
        },
        options: {
            responsive: true,
            scales: {
                y: {
                    beginAtZero: true,
                    max: 100
                }
            }
        }
    });

    const memoryCtx = document.getElementById('memoryChart').getContext('2d');
    memoryChart = new Chart(memoryCtx, {
        type: 'doughnut',
        data: {
            labels: ['Used', 'Available'],
            datasets: [{
                data: [0, 100],
                backgroundColor: ['rgb(255, 99, 132)', 'rgb(54, 162, 235)']
            }]
        },
        options: {
            responsive: true
        }
    });
}

function initTemperatureChart() {
    const ctx = document.getElementById('temperatureChart').getContext('2d');
    temperatureChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Temperature (°C)',
                data: [],
                borderColor: 'rgb(255, 99, 132)',
                tension: 0.1
            }]
        },
        options: {
            responsive: true,
            scales: {
                y: {
                    beginAtZero: true,
                    suggestedMax: 90
                }
            }
        }
    });
}

function updateCharts(cpuUsage, memoryUsed, memoryAvailable) {
    const timestamp = new Date().toLocaleTimeString();

    // Update CPU chart
    cpuChart.data.labels.push(timestamp);
    cpuChart.data.datasets[0].data.push(cpuUsage);
    if (cpuChart.data.labels.length > 10) {
        cpuChart.data.labels.shift();
        cpuChart.data.datasets[0].data.shift();
    }
    cpuChart.update();

    memoryChart.data.datasets[0].data = [memoryUsed, memoryAvailable];
    // Fix memory data normalization
    //const totalMemory = memoryUsed + memoryAvailable;
    //memoryChart.data.datasets[0].data = [
    //    (memoryUsed / totalMemory) * 100,
    //    (memoryAvailable / totalMemory) * 100
    //];
    memoryChart.update();
}


function formatBytes(bytes) {
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    if (bytes === 0) return '0 Byte';
    const i = parseInt(Math.floor(Math.log(bytes) / Math.log(1024))) - 1;
    if (i < 0) i = 0;
    return Math.round(bytes / Math.pow(1024, i), 2) + ' ' + sizes[i];
}

function formatUptime(seconds) {
    const days = Math.floor(seconds / (3600*24));
    const hours = Math.floor(seconds % (3600*24) / 3600);
    const minutes = Math.floor(seconds % 3600 / 60);
    return `${days} days, ${hours} hours, ${minutes} minutes`;
}

function updateDiskInfo(diskData) {
    const diskInfoElement = document.getElementById('diskInfo');
    diskInfoElement.innerHTML = diskData.map(disk => `
        <h3>${disk.mountpoint}</h3>
        <p>Device: ${disk.device}</p>
        <p>Filesystem Type: ${disk.fstype}</p>
        <p>Total: ${formatBytes(disk.usage.total)}</p>
        <p>Used: ${formatBytes(disk.usage.used)} (${disk.usage.percent.toFixed(1)}%)</p>
        <progress value="${disk.usage.percent}" max="100"></progress>
    `).join('');
}

async function fetchData() {
    try {
        const [statusResponse, diskResponse] = await Promise.all([
            fetch('api/system_status'),
            fetch('api/disk')
        ]);
        const statusData = await statusResponse.json();
        const diskData = await diskResponse.json();

        updateCharts(
            statusData.cpu.usage,
            statusData.memory.used,
            statusData.memory.available
        );
        updateDiskInfo(diskData);

        document.getElementById('uptime').textContent = formatUptime(statusData.uptime.system);
    } catch (error) {
        console.error('Error fetching data:', error);
    }
}

async function fetchTemperature() {
    if (!temperatureChart) return;
    try {
        const response = await fetch('api/rpi/temperature');
        const data = await response.json();
        const timestamp = new Date().toLocaleTimeString();
        temperatureChart.data.labels.push(timestamp);
        temperatureChart.data.datasets[0].data.push(data.temperature);
        if (temperatureChart.data.labels.length > 10) {
            temperatureChart.data.labels.shift();
            temperatureChart.data.datasets[0].data.shift();
        }
        temperatureChart.update();
    } catch (error) {
        console.error('Error fetching temperature:', error);
    }
}

function startTemperatureChart() {
    const card = document.getElementById('temperatureCard');
    if (card) card.style.display = 'block';
    if (!temperatureChart) initTemperatureChart();
    if (!temperatureIntervalId) {
        temperatureIntervalId = setInterval(fetchTemperature, 10000);
        fetchTemperature();
    }
}

async function fetchVcgencmdAvailable() {
    try {
        const response = await fetch('api/rpi/vcgencmd_available');
        const data = await response.json();
        vcgencmdAvailable = data.vcgencmd_available === true;
        if (vcgencmdAvailable) startTemperatureChart();
    } catch (error) {
        vcgencmdAvailable = false;
        console.error('Error fetching vcgencmd_available:', error);
    }
}

initCharts();
window.addEventListener('load', () => {
    setTimeout(fetchVcgencmdAvailable, 3000);
});
setInterval(fetchData, 5000);
fetchData();
