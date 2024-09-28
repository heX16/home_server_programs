let cpuChart, memoryChart;

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
    const i = parseInt(Math.floor(Math.log(bytes) / Math.log(1024)));
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

initCharts();
setInterval(fetchData, 5000);
fetchData();
